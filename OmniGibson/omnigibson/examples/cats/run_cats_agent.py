"""Run a CATS (Context-Adaptive Tool Selection) evaluation.

Usage:
  # With Gemini
  python -m omnigibson.examples.cats.run_cats_agent \
    --model gemini-2.0-flash --task retrieve_egg_from_gap

  # With mock LLM (testing without API)
  python -m omnigibson.examples.cats.run_cats_agent \
    --model mock --task retrieve_egg_from_gap

  # Custom experiment directory
  python -m omnigibson.examples.cats.run_cats_agent \
    --model gemini-2.0-flash --task retrieve_egg_from_gap \
    --exp-dir ./experiments/cats_test
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[4] / ".env", override=True)

import omnigibson.macros as macros
from omnigibson.macros import gm

gm.USE_GPU_DYNAMICS = True
gm.GPU_PAIRS_CAPACITY = 128 * 1024
gm.GPU_AGGR_PAIRS_CAPACITY = (2**13) * 1024
gm.GPU_MAX_PARTICLE_CONTACTS = 512 * 1024
gm.GPU_MAX_RIGID_CONTACT_COUNT = 524288
gm.GPU_MAX_RIGID_PATCH_COUNT = 81920

import omnigibson as og

# Paths
AVAILABLE_TASKS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "joylo", "sampled_task", "available_tasks.yaml"
)
LLM_CONFIGS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "llm_agent", "configs"
)
EXPERIMENTS_BASE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "experiments", "cats"
)


class _TeeStream:
    """Write to both the original stream and a log file."""

    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data):
        self._original.write(data)
        self._original.flush()
        try:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
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


def main():
    parser = argparse.ArgumentParser(description="CATS Evaluation Agent")
    parser.add_argument("--task", type=str, required=True, help="CATS task name")
    parser.add_argument("--model", type=str, default=None, help="Model name (or 'mock')")
    parser.add_argument("--llm", type=str, default="api", help="LLM config name or YAML path")
    parser.add_argument("--scene", type=str, default=None, help="Scene model override")
    parser.add_argument("--robot", type=str, default="Tiago", help="Robot type")
    parser.add_argument("--max-exploration-steps", type=int, default=10)
    parser.add_argument("--exp-dir", type=str, default=None)
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--instance-id", type=int, default=0)
    parser.add_argument("--demo-urls", type=str, nargs="+", default=None,
                        help="YouTube URLs for demo videos (overrides task config demo_image_paths)")
    args = parser.parse_args()

    # ---- Load CATS task config ----
    from omnigibson.llm_agent.cats_tasks import CATS_TASK_REGISTRY
    if args.task not in CATS_TASK_REGISTRY:
        raise ValueError(
            f"Unknown CATS task: '{args.task}'. "
            f"Available: {list(CATS_TASK_REGISTRY.keys())}"
        )
    task_config = CATS_TASK_REGISTRY[args.task]

    # ---- Override demo paths with YouTube URLs if provided ----
    if args.demo_urls:
        task_config["demo_image_paths"] = args.demo_urls

    # ---- Load LLM config ----
    if args.model and args.model.lower() == "mock":
        # Try task-specific mock, then generic
        mock_path = os.path.join(LLM_CONFIGS_DIR, f"llm_mock_cats_{args.task}.yaml")
        if not os.path.exists(mock_path):
            mock_path = os.path.join(LLM_CONFIGS_DIR, "llm_mock.yaml")
        with open(mock_path, "r") as f:
            llm_config = yaml.safe_load(f)
        llm_config["type"] = "mock"
    else:
        if os.path.isfile(args.llm):
            llm_config_path = args.llm
        else:
            llm_config_path = os.path.join(LLM_CONFIGS_DIR, f"llm_{args.llm}.yaml")
        with open(llm_config_path, "r") as f:
            llm_config = yaml.safe_load(f)

        if args.model:
            llm_config.setdefault("generation_params", {})["model"] = args.model
            model_lower = args.model.lower()
            if model_lower.startswith("gemini"):
                clean_name = args.model.split("/", 1)[1] if "/" in args.model else args.model
                llm_config["generation_params"]["model"] = clean_name
                llm_config["type"] = "gemini"
            elif model_lower.startswith("gpt") or model_lower.startswith("o3") or model_lower.startswith("o4"):
                llm_config["type"] = "openai"

    # ---- Auto-select scene ----
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
                    print(f"[Auto] Scene: {resolved_scene}")
        if resolved_scene is None:
            resolved_scene = "house_single_floor"
            print(f"[Auto] Using default scene: {resolved_scene}")
        args.scene = resolved_scene

    # ---- Build experiment directory ----
    model_name = llm_config.get("generation_params", {}).get("model", "mock")
    model_short = model_name.replace("/", "_").replace(".", "_")
    if args.exp_dir:
        experiment_dir = args.exp_dir
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_dir = os.path.join(
            EXPERIMENTS_BASE_DIR,
            f"{timestamp}_{model_short}_cats_{args.task}",
        )

    os.makedirs(experiment_dir, exist_ok=True)
    _console_log = open(os.path.join(experiment_dir, "console.log"), "w", buffering=1)
    sys.stdout = _TeeStream(sys.stdout, _console_log)
    sys.stderr = _TeeStream(sys.stderr, _console_log)

    # ---- Build OmniGibson environment ----
    ROBOT_CONFIG_MAP = {
        "Tiago": "tiago_primitives.yaml",
        "R1": "r1_primitives.yaml",
        "R1Pro": "r1pro_primitives.yaml",
        "Fetch": "fetch_primitives.yaml",
        "Stretch": "stretch_primitives.yaml",
    }
    config_filename = ROBOT_CONFIG_MAP.get(args.robot, "tiago_primitives.yaml")
    env_config_path = os.path.join(og.example_config_path, config_filename)

    with open(env_config_path, "r") as f:
        env_config = yaml.safe_load(f)

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

    print(f"\n{'='*60}")
    print(f"CATS Evaluation: {args.task}")
    print(f"Model: {model_name}")
    print(f"Scene: {args.scene} | Robot: {args.robot}")
    print(f"Experiment dir: {experiment_dir}")
    print(f"{'='*60}\n")

    env = og.Environment(configs=env_config)
    og.sim.enable_viewer_camera_teleoperation()

    # ---- Create and run CATS planner ----
    from omnigibson.llm_agent.planner_ca import CATSPlanner

    planner = CATSPlanner(
        env=env,
        llm_config=llm_config,
        task_config=task_config,
        max_exploration_steps=args.max_exploration_steps,
        experiment_dir=experiment_dir,
        verbose=True,
    )

    result = planner.run()

    # ---- Print summary ----
    print(f"\n{'='*60}")
    print("CATS EVALUATION RESULT")
    print(f"{'='*60}")
    print(f"Task: {args.task}")
    ts = result.get("tool_selection", {})
    print(f"Tool selected: {ts.get('selected_tool', 'N/A')}")
    print(f"Correct tool:  {ts.get('correct_tool', 'N/A')}")
    print(f"Tool correct:  {ts.get('tool_selection_correct', 'N/A')}")
    print(f"Committed:     {result.get('committed_tool', 'N/A')}")
    print(f"Total steps:   {result['total_steps']}")
    print(f"Total time:    {result['total_time_seconds']:.1f}s")
    print(f"Stage 3:       {result['stage3'].get('status', 'N/A')}")
    print(f"{'='*60}")

    og.shutdown()


if __name__ == "__main__":
    main()
