"""Run an LLM agent on a BEHAVIOR-1K task.

Usage:
  # With OpenAI GPT-4o (default)
  python -m omnigibson.examples.llm_agent.run_llm_agent --model gpt-4o

  # With Google Gemini (auto-detected, uses Vertex AI)
  python -m omnigibson.examples.llm_agent.run_llm_agent --model gemini-2.0-flash

  # With Anthropic Claude
  python -m omnigibson.examples.llm_agent.run_llm_agent --model claude-sonnet-4-20250514

  # With local Qwen via vLLM (auto-detects api_base)
  python -m omnigibson.examples.llm_agent.run_llm_agent --model qwen2.5-14b-instruct

  # With mock LLM (for testing without API)
  python -m omnigibson.examples.llm_agent.run_llm_agent --llm mock

  # Custom scene/task
  python -m omnigibson.examples.llm_agent.run_llm_agent --model gpt-4o \
    --scene house_single_floor --task sorting_vegetables

  # Specify experiment output directory
  python -m omnigibson.examples.llm_agent.run_llm_agent --model gpt-4o \
    --exp-dir ./experiments/my_run
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

import omnigibson.macros as macros
from omnigibson.macros import gm
# Enable GPU dynamics for particle/fluid systems (e.g., melted_butter in spread tasks).
# Must be set before og.Environment is created.
gm.USE_GPU_DYNAMICS = True
gm.GPU_PAIRS_CAPACITY = 128 * 1024
gm.GPU_AGGR_PAIRS_CAPACITY = (2**13) * 1024
gm.GPU_MAX_PARTICLE_CONTACTS = 512 * 1024
gm.GPU_MAX_RIGID_CONTACT_COUNT = 524288
gm.GPU_MAX_RIGID_PATCH_COUNT = 81920

import omnigibson as og

# Path to the curated task list with recommended scene/robot-pose configs
AVAILABLE_TASKS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "joylo", "sampled_task", "available_tasks.yaml"
)


class _TeeStream:
    """Write to both the original stream and a log file in real-time."""

    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data):
        self._original.write(data)
        self._original.flush()
        try:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            # Strip ANSI escape codes for the log file
            import re
            clean = re.sub(r"\x1b\[[0-9;]*m", "", data)
            self._log_file.write(clean)
            self._log_file.flush()
        except Exception:
            pass

    def flush(self):
        self._original.flush()
        try:
            self._log_file.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original, name)

LLM_CONFIGS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "llm_agent", "configs"
)

EXPERIMENTS_BASE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "experiments"
)

# Local models served via vLLM: model name -> (api_base, api_key)
LOCAL_MODEL_DEFAULTS = {
    "qwen2.5-14b-instruct": ("http://localhost:8000/v1", "dummy"),
    "qwen2.5-14b-instruct-gptq": ("http://localhost:8000/v1", "dummy"),
    "qwen2.5-7b-instruct": ("http://localhost:8000/v1", "dummy"),
    "qwen2.5-coder-7b": ("http://localhost:8000/v1", "dummy"),
}


def _apply_custom_object_states(env, task_name):
    """
    Apply custom object states (Broken, High) to scene objects after environment loading.

    Since Broken and High are new states not part of original object metadata/abilities,
    we inject them programmatically here based on the task configuration.
    """
    from omnigibson.object_states.broken import Broken
    from omnigibson.object_states.high import High
    from omnigibson.object_states.nailed import Nailed
    from omnigibson.object_states.pierced import Pierced
    from omnigibson.object_states.placed_against import PlacedAgainst
    from omnigibson.object_states.torn import Torn

    # Task-specific rules: map task_name -> list of (scene_object_name, state_class, value)
    # Use exact scene object names (from inst_to_name mapping) to avoid substring mismatch
    TASK_STATE_RULES = {
        "heat_frozen_pancake_and_set_table": [
            ("burner_mjvqii_0", Broken, True),      # Stove/burner is broken
            ("shelf_pfusrd_0", High, True),          # Shelf is high (syrup unreachable from floor)
        ],
    }

    # States that need to be injected by category (for new custom object states)
    CATEGORY_STATE_RULES = {
        "hammer_nail": {
            "clout_nail": [Nailed, Pierced],         # Nail can be nailed and pierced
            "cardboard": [PlacedAgainst],             # Cardboard can be placed against wall
        },
        "tear_paper_along_a_ruler": {
            "paper_sheet": [Torn],                    # Paper can be torn
        },
    }

    cat_rules = CATEGORY_STATE_RULES.get(task_name, {})
    if cat_rules:
        print(f"\n[Custom States] Injecting category-based states for task '{task_name}':")
        for obj in env.scene.objects:
            obj_cat = getattr(obj, "category", "")
            if obj_cat in cat_rules:
                for state_cls in cat_rules[obj_cat]:
                    if state_cls not in obj.states:
                        state_instance = state_cls(obj)
                        state_instance.initialize()
                        obj.states[state_cls] = state_instance
                        print(f"  {obj.name} ({obj_cat}): injected {state_cls.__name__}")

    rules = TASK_STATE_RULES.get(task_name, [])
    if not rules:
        return

    print(f"\n[Custom States] Applying {len(rules)} custom object state(s) for task '{task_name}':")
    for obj in env.scene.objects:
        for target_name, state_cls, value in rules:
            if obj.name == target_name:
                # Add the state to the object if not already present
                if state_cls not in obj.states:
                    state_instance = state_cls(obj)
                    state_instance.initialize()
                    obj.states[state_cls] = state_instance
                obj.states[state_cls].set_value(value)
                state_name = state_cls.__name__
                print(f"  {obj.name}: {state_name} = {value}")


def main():
    parser = argparse.ArgumentParser(description="Run LLM agent on BEHAVIOR-1K task")
    parser.add_argument(
        "--llm",
        type=str,
        default="api",
        help="LLM config name (api, local_qwen, mock) or path to YAML",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name override (e.g., gpt-4o, gemini/gemini-2.0-flash, claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="API base URL override (for local vLLM servers)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key override",
    )
    parser.add_argument("--task", type=str, default="picking_up_trash", help="BEHAVIOR task name")
    parser.add_argument("--task-id", type=int, default=0, help="Task definition ID")
    parser.add_argument("--instance-id", type=int, default=0, help="Task instance ID")
    parser.add_argument(
        "--scene", type=str, default=None,
        help="Scene model name. If omitted, auto-selected from available_tasks.yaml.",
    )
    parser.add_argument("--robot", type=str, default="Tiago", help="Robot type")
    parser.add_argument("--max-steps", type=int, default=60, help="Max LLM planning steps")
    parser.add_argument(
        "--allow-abstain",
        action="store_true",
        default=False,
        help="Allow LLM to abstain from infeasible tasks.",
    )
    parser.add_argument(
        "--allow-ask",
        action="store_true",
        default=False,
        help="Allow LLM to ask clarifying questions (interactive prompt).",
    )
    parser.add_argument(
        "--symbolic",
        action="store_true",
        default=False,
        help="Use SymbolicSemanticActionPrimitives (14 actions, teleport-based) "
             "instead of StarterSemanticActionPrimitives (9 actions, physics-based).",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        default=False,
        help="Record simulation video to experiment_dir/video.mp4. "
             "Partial video is saved even if interrupted.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress detailed logs on terminal; only show step summaries. "
             "Full logs are always saved to experiment dir.",
    )
    parser.add_argument(
        "--exp-dir",
        type=str,
        default=None,
        help="Experiment output directory. Auto-generated if not specified.",
    )
    parser.add_argument(
        "--goal-override",
        type=str,
        default=None,
        help="Override the BDDL goal text with a custom instruction. "
             "The BDDL task still loads the scene/objects, but the LLM "
             "sees this text as the goal instead. Useful for abstain/ask "
             "experiments (e.g., 'Bring me the laptop from the bedroom').",
    )
    parser.add_argument(
        "--youtube-url",
        type=str,
        default=None,
        help="YouTube video URL to include with the first Gemini prompt. "
             "Only works with Gemini backend (--model gemini-*).",
    )
    parser.add_argument(
        "--video-file",
        type=str,
        default=None,
        help="Local video file path to include with the first Gemini prompt. "
             "Supports mp4, avi, mov, mkv, webm. Max ~20MB recommended.",
    )
    args = parser.parse_args()

    # Load LLM config
    if os.path.isfile(args.llm):
        llm_config_path = args.llm
    else:
        llm_config_path = os.path.join(LLM_CONFIGS_DIR, f"llm_{args.llm}.yaml")

    if not os.path.exists(llm_config_path):
        available = [f.replace("llm_", "").replace(".yaml", "")
                     for f in os.listdir(LLM_CONFIGS_DIR) if f.startswith("llm_")]
        raise FileNotFoundError(
            f"LLM config '{args.llm}' not found. Available: {available}"
        )

    with open(llm_config_path, "r") as f:
        llm_config = yaml.safe_load(f)

    # CLI overrides
    if args.model:
        # --model mock: auto-load task-specific mock config if available
        if args.model.lower() == "mock":
            mock_task_path = os.path.join(LLM_CONFIGS_DIR, f"llm_mock_{args.task}.yaml")
            mock_default_path = os.path.join(LLM_CONFIGS_DIR, "llm_mock_draw_a_line_on_paper.yaml")
            if os.path.exists(mock_task_path):
                with open(mock_task_path, "r") as f:
                    llm_config = yaml.safe_load(f)
            elif os.path.exists(mock_default_path):
                with open(mock_default_path, "r") as f:
                    llm_config = yaml.safe_load(f)
        else:
            llm_config.setdefault("generation_params", {})["model"] = args.model

            # Auto-detect model backend
            model_lower = args.model.lower()
            if model_lower.startswith("gemini"):
                # Strip "gemini/" prefix if present (e.g. "gemini/gemini-2.0-flash")
                clean_name = args.model.split("/", 1)[1] if "/" in args.model else args.model
                llm_config["generation_params"]["model"] = clean_name
                llm_config["type"] = "gemini"
            elif model_lower.startswith("gpt") or model_lower.startswith("o3") or model_lower.startswith("o4"):
                llm_config["type"] = "openai"
            else:
                # Auto-detect local models and set api_base/api_key
                for local_name, (default_base, default_key) in LOCAL_MODEL_DEFAULTS.items():
                    if local_name in model_lower:
                        if not args.api_base:
                            llm_config["generation_params"]["api_base"] = default_base
                        if not args.api_key:
                            llm_config["generation_params"]["api_key"] = default_key
                        llm_config["type"] = "local"
                        break

    if args.api_base:
        llm_config.setdefault("generation_params", {})["api_base"] = args.api_base
    if args.api_key:
        llm_config.setdefault("generation_params", {})["api_key"] = args.api_key
    if args.youtube_url:
        llm_config["youtube_url"] = args.youtube_url
    if args.video_file:
        llm_config["video_file"] = os.path.abspath(args.video_file)

    # Auto-select scene from available_tasks.yaml when --scene is not specified
    if args.scene is None:
        resolved_scene = None
        if os.path.exists(AVAILABLE_TASKS_PATH):
            with open(AVAILABLE_TASKS_PATH, "r") as f:
                available_tasks = yaml.safe_load(f) or {}
            task_entry = available_tasks.get(args.task)
            if task_entry:
                instance = task_entry.get(args.instance_id, task_entry.get(0))
                if instance and "scene_model" in instance:
                    resolved_scene = instance["scene_model"]
                    print(f"[Auto] Scene '{resolved_scene}' selected from available_tasks.yaml for task '{args.task}'")
        if resolved_scene is None:
            resolved_scene = "house_double_floor_lower"
            print(f"[Auto] Task '{args.task}' not found in available_tasks.yaml, using default scene '{resolved_scene}'")
        args.scene = resolved_scene

    # Build experiment directory
    model_name = llm_config.get("generation_params", {}).get("model", "unknown")
    model_short = model_name.replace("/", "_").replace(".", "_")
    if args.exp_dir:
        experiment_dir = args.exp_dir
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_dir = os.path.join(
            EXPERIMENTS_BASE_DIR,
            f"{timestamp}_{model_short}_{args.task}_{args.scene}",
        )

    # Set up real-time console logging to experiment dir
    os.makedirs(experiment_dir, exist_ok=True)
    _console_log = open(os.path.join(experiment_dir, "console.log"), "w", buffering=1)
    sys.stdout = _TeeStream(sys.stdout, _console_log)
    sys.stderr = _TeeStream(sys.stderr, _console_log)

    # Build OmniGibson environment config — pick the right primitives config for the robot
    ROBOT_CONFIG_MAP = {
        "Tiago": "tiago_primitives.yaml",
        "R1": "r1_primitives.yaml",
        "R1Pro": "r1pro_primitives.yaml",
        "Fetch": "fetch_primitives.yaml",
        "Stretch": "stretch_primitives.yaml",
    }
    config_filename = ROBOT_CONFIG_MAP.get(args.robot)
    if config_filename:
        env_config_path = os.path.join(og.example_config_path, config_filename)
    else:
        # Fallback: use tiago config and override robot type
        env_config_path = os.path.join(og.example_config_path, "tiago_primitives.yaml")

    with open(env_config_path, "r") as f:
        env_config = yaml.safe_load(f)

    # Override scene and task
    env_config["scene"]["scene_model"] = args.scene
    env_config["scene"]["load_task_relevant_only"] = True
    env_config["scene"]["not_load_object_categories"] = ["ceilings"]
    env_config["scene"]["include_robots"] = True
    env_config["task"] = {
        "type": "BehaviorTask",
        "activity_name": args.task,
        "activity_definition_id": args.task_id,
        "activity_instance_id": args.instance_id,
        "predefined_problem": None,
        "online_object_sampling": False,
        "use_presampled_robot_pose": True,
    }

    if not config_filename and args.robot != "Tiago":
        # When using a robot without a dedicated config, only keep
        # generic settings and let the robot class provide its own
        # defaults for reset_joint_pos and controller_config.
        robot_cfg = env_config["robots"][0]
        robot_cfg["type"] = args.robot
        robot_cfg.pop("reset_joint_pos", None)
        robot_cfg.pop("controller_config", None)
        robot_cfg["default_reset_mode"] = "untuck"

    if args.allow_abstain:
        # =====================================================================
        # EIB pipeline — used only when --allow-abstain is set
        # Vision-based (camera image + JSON), with exploration/abstain support
        # =====================================================================
        from omnigibson.envs.eib_omnigibson_kitchen_env import OmniGibsonKitchenEnv
        from omnigibson.llm_agent.eib_ih_planner import IHPlanner
        from omnigibson.envs.common.eib_remote_model import RemoteVLM

        EIB_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "eib", "data")
        eib_env_config_path = os.path.join(EIB_DATA_DIR, "env", "env.yaml")
        eib_prompt_config_path = os.path.join(EIB_DATA_DIR, "prompts", "ih_prompt.yaml")
        eib_bddl_dir = os.path.join(EIB_DATA_DIR, "task", "IH", "bddl")

        print(f"\nLoading EIB environment: scene={args.scene}, task={args.task}")
        print(f"Experiment dir: {experiment_dir}")

        eib_env = OmniGibsonKitchenEnv(
            config_path=eib_env_config_path,
            task_name=args.task,
            scene_name=args.scene,
            bddl_dir=eib_bddl_dir,
        )
        _apply_custom_object_states(eib_env.env, args.task)
        planner = IHPlanner(prompt_config_path=eib_prompt_config_path)

        _orig_stdout = sys.stdout._original if hasattr(sys.stdout, "_original") else sys.stdout
        _orig_stderr = sys.stderr._original if hasattr(sys.stderr, "_original") else sys.stderr
        start_time = time.time()

        skill_set = eib_env.language_skill_set
        receptacle_names = eib_env.get_receptacle_names()

        result = {"success": False, "steps": 0, "action_history": [], "final_reward": 0.0}

        for step_idx in range(args.max_steps):
            img_path = eib_env.save_image(experiment_dir, step_id=step_idx)
            plan = planner.plan(
                instruction=args.goal_override or args.task.replace("_", " "),
                image_path=img_path,
                skill_set=skill_set,
                receptacle_names=receptacle_names,
            )
            action = plan.get("action")
            target = plan.get("target")
            target2 = plan.get("target2")
            reasoning = plan.get("reasoning", "")

            if not action:
                _orig_stdout.write(f"  [Step {step_idx}] No action parsed from LLM response\n")
                _orig_stdout.flush()
                planner.update("unknown", None, success=False, feedback="Missing action in LLM response.")
                result["action_history"].append("unknown -> FAILED: no action parsed")
                continue

            action_desc = action
            if target:
                action_desc += f"[{target}]"
            if target2:
                action_desc += f"[{target2}]"

            exec_result = eib_env.execute_action(action, target, target2)
            success = exec_result["success"]
            mark = "OK" if success else "FAIL"
            _orig_stdout.write(f"  [Step {step_idx}] {action_desc} -> {mark}\n")
            _orig_stdout.flush()

            result["action_history"].append(
                f"{action_desc} -> {'SUCCESS' if success else 'FAILED'}: {exec_result['feedback']}"
            )
            planner.update(action, target, success=success, feedback=exec_result["feedback"])

            if exec_result.get("terminal"):
                terminal = exec_result["terminal"]
                if terminal == "terminate":
                    result["success"] = eib_env.is_goal_satisfied()
                    result["final_reward"] = 1.0 if result["success"] else 0.0
                elif terminal == "abstain":
                    result["abstained"] = True
                    result["abstain_reason"] = reasoning
                break

        result["steps"] = step_idx + 1
        elapsed = time.time() - start_time

        sys.stdout = _TeeStream(_orig_stdout, _console_log)
        sys.stderr = _TeeStream(_orig_stderr, _console_log)

        print(f"\n{'='*60}")
        if result.get("abstained"):
            status = f"ABSTAINED ({result.get('abstain_reason', '')[:100]})"
        elif result["success"]:
            status = "SUCCESS"
        else:
            status = "FAILURE"
        print(f"RESULT: {status}")
        print(f"Steps: {result['steps']}")
        print(f"Reward: {result['final_reward']:.3f}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Actions:")
        for i, action_entry in enumerate(result["action_history"]):
            print(f"  {i+1}. {action_entry}")
        print(f"Experiment: {experiment_dir}")
        print(f"{'='*60}")

        result_path = os.path.join(experiment_dir, "result.json")
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2)

        try:
            eib_env.close()
        except Exception as e:
            print(f"[Warning] eib_env.close() failed (non-critical cleanup): {e}")

        sys.stdout = sys.stdout._original if hasattr(sys.stdout, "_original") else sys.stdout
        sys.stderr = sys.stderr._original if hasattr(sys.stderr, "_original") else sys.stderr
        _console_log.close()

    else:
        # =====================================================================
        # OG planner pipeline — default (no --allow-abstain)
        # Text-based "Objects in the scene", ReAct Thought/Action format
        # =====================================================================
        primitive_mode = "symbolic (teleport)" if args.symbolic else "starter (physics)"
        print(f"\nLoading environment: scene={args.scene}, task={args.task}")
        print(f"LLM: {model_name}")
        print(f"Primitives: {primitive_mode}")
        print(f"Experiment dir: {experiment_dir}")

        # Create environment.
        # Fallback: if task has no presampled scene instance (task_dir=None → TypeError with "NoneType"),
        # switch to online object sampling (BDDL-driven placement) and disable presampled robot pose.
        try:
            env = og.Environment(configs=env_config)
        except (TypeError, AssertionError, KeyError) as e:
            err_msg = str(e)
            if "NoneType" in err_msg or "presampled" in err_msg.lower() or "joint_pos" in err_msg:
                print(f"[WARN] No presampled task instance for this scene/task (error: {err_msg}). "
                      f"Falling back to online_object_sampling=True.")
                # Stop the simulator so a fresh Environment can be created
                og.clear()
                env_config["task"]["online_object_sampling"] = True
                env_config["task"]["use_presampled_robot_pose"] = False
                env = og.Environment(configs=env_config)
            else:
                raise
        og.sim.enable_viewer_camera_teleoperation()

        # --- Apply custom object states (Broken, High) if needed ---
        _apply_custom_object_states(env, args.task)

        from omnigibson.llm_agent.planner import OmniGibsonLLMPlanner

        verbose = not args.quiet
        if args.quiet:
            llm_config["verbose"] = False

        planner = OmniGibsonLLMPlanner(
            env=env,
            llm_config=llm_config,
            max_steps=args.max_steps,
            verbose=verbose,
            experiment_dir=experiment_dir,
            allow_abstain=False,
            allow_ask=args.allow_ask,
            symbolic=args.symbolic,
            record_video=args.record,
            goal_text_override=args.goal_override,
        )

        _orig_stdout = sys.stdout._original if hasattr(sys.stdout, "_original") else sys.stdout
        _orig_stderr = sys.stderr._original if hasattr(sys.stderr, "_original") else sys.stderr
        if args.quiet:
            class _QuietStream:
                def __init__(self, log_file):
                    self._log_file = log_file
                    self._original = _orig_stdout
                def write(self, data):
                    try:
                        if isinstance(data, bytes):
                            data = data.decode("utf-8", errors="replace")
                        import re
                        clean = re.sub(r"\x1b\[[0-9;]*m", "", data)
                        self._log_file.write(clean)
                        self._log_file.flush()
                    except Exception:
                        pass
                def flush(self):
                    try:
                        self._log_file.flush()
                    except Exception:
                        pass
                def __getattr__(self, name):
                    return getattr(self._original, name)

            sys.stdout = _QuietStream(_console_log)
            sys.stderr = _QuietStream(_console_log)

        start_time = time.time()

        def _on_step(step_num, action_name, action_arg, status):
            mark = "OK" if status == "SUCCESS" else "FAIL" if status == "FAILED" else status
            _orig_stdout.write(f"  [Step {step_num}] {action_name}[{action_arg}] -> {mark}\n")
            _orig_stdout.flush()

        if args.quiet:
            planner._on_step_callback = _on_step

        result = planner.run()
        elapsed = time.time() - start_time

        sys.stdout = _TeeStream(_orig_stdout, _console_log)
        sys.stderr = _TeeStream(_orig_stderr, _console_log)

        print(f"\n{'='*60}")
        if result.get("abstained"):
            status = f"ABSTAINED ({result.get('abstain_reason', '')})"
        elif result["success"]:
            status = "SUCCESS"
        else:
            status = "FAILURE"
        print(f"RESULT: {status}")
        print(f"Steps: {result['steps']}")
        print(f"Reward: {result['final_reward']:.3f}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Actions:")
        for i, action in enumerate(result["action_history"]):
            print(f"  {i+1}. {action}")
        if result.get("video_path"):
            print(f"Video: {result['video_path']} ({result.get('video_frames', 0)} frames)")
        print(f"Experiment: {experiment_dir}")
        print(f"{'='*60}")

        try:
            og.clear()
        except (KeyError, Exception) as e:
            print(f"[Warning] og.clear() failed (non-critical cleanup): {e}")

        sys.stdout = sys.stdout._original if hasattr(sys.stdout, "_original") else sys.stdout
        sys.stderr = sys.stderr._original if hasattr(sys.stderr, "_original") else sys.stderr
        _console_log.close()


if __name__ == "__main__":
    main()
