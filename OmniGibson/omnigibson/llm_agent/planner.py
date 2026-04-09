"""ReAct planner that connects LLMs to OmniGibson via BDDL and action primitives."""

import atexit
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import yaml

import omnigibson as og
from omnigibson.action_primitives.action_primitive_set_base import (
    ActionPrimitiveError,
    ActionPrimitiveErrorGroup,
)
# OG planner imports
from omnigibson.action_primitives.starter_semantic_action_primitives import (
    StarterSemanticActionPrimitives,
    StarterSemanticActionPrimitiveSet,
)
from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
    SymbolicSemanticActionPrimitives,
)
from omnigibson.llm_agent.llm import create_llm
from omnigibson.llm_agent.prompt_utils import (
    ACTION_PRIMITIVES,
    build_step_prompt,
    build_system_prompt,
    format_goal_text,
    format_progress_text,
    format_state_text,
    parse_llm_response,
    resolve_object_name,
    set_primitive_mode,
)

# EIB pipeline imports (used when --allow-abstain)
from omnigibson.action_primitives.eib_semantic_action_primitives import (
    EIBSemanticActionPrimitives,
    EIBSemanticActionPrimitiveSet,
)
from omnigibson.envs.common.eib_camera import CameraMixin
from omnigibson.envs.common.eib_remote_model import RemoteVLM

logger = logging.getLogger(__name__)


class _CameraHelper(CameraMixin):
    """Lightweight wrapper that provides CameraMixin functionality for the planner.

    CameraMixin expects self.robot, self.scene, and self.primitives.
    This class bridges those from the OG environment and the action controller.
    """

    def __init__(self, env, controller):
        self.robot = env.robots[0]
        self.scene = env.scene
        self.primitives = controller
        self.__init_camera__()


class _VideoRecorder:
    """Incrementally writes simulation frames to an MP4 video file.

    Frames are written as they arrive so a partial video is always available,
    even if the process is interrupted.
    """

    def __init__(self, output_path: str, fps: int = 10, capture_every: int = 10):
        """
        Args:
            output_path: Path to the output .mp4 file.
            fps: Frames per second of the output video.
            capture_every: Capture a frame every N env.step() calls.
                At ~120 Hz physics, capture_every=10 gives ~12 raw fps.
        """
        import cv2

        self._cv2 = cv2
        self.output_path = output_path
        self.fps = fps
        self.capture_every = capture_every
        self._writer = None
        self._step_count = 0
        self.frame_count = 0
        self._closed = False

    def step(self):
        """Call after each env.step(). Captures a frame every N steps."""
        self._step_count += 1
        if self._step_count % self.capture_every != 0:
            return
        self._write_frame()

    def _write_frame(self):
        try:
            obs, _ = og.sim.viewer_camera.get_obs()
            rgb = obs["rgb"]
            # Convert torch tensor -> numpy
            if hasattr(rgb, "cpu"):
                rgb = rgb.cpu()
            if hasattr(rgb, "numpy"):
                rgb = rgb.numpy()
            rgb = np.asarray(rgb, dtype=np.uint8)
            # Drop alpha channel (H, W, 4) -> (H, W, 3)
            if rgb.ndim == 3 and rgb.shape[-1] == 4:
                rgb = rgb[:, :, :3]

            if self._writer is None:
                h, w = rgb.shape[:2]
                fourcc = self._cv2.VideoWriter_fourcc(*"mp4v")
                self._writer = self._cv2.VideoWriter(
                    self.output_path, fourcc, self.fps, (w, h),
                )
            bgr = self._cv2.cvtColor(rgb, self._cv2.COLOR_RGB2BGR)
            self._writer.write(bgr)
            self.frame_count += 1
        except Exception:
            pass  # Never crash the main loop for recording failures

    def close(self):
        """Flush and release the video writer."""
        if self._closed:
            return
        self._closed = True
        if self._writer is not None:
            self._writer.release()
            self._writer = None


class OmniGibsonLLMPlanner:
    """High-level LLM planner for OmniGibson BEHAVIOR tasks.

    Flow per step:
        1. Query BDDL for goal conditions (natural language) and progress
        2. Build text representation of current state
        3. Call LLM with ReAct prompt
        4. Parse LLM response into (action_name, object_name)
        5. Execute the action primitive (generator-based)
        6. Repeat until task is done or max steps reached
    """

    def __init__(
        self,
        env,
        llm_config: dict,
        max_steps: int = 50,
        verbose: bool = True,
        enable_head_tracking: bool = True,
        experiment_dir: Optional[str] = None,
        allow_abstain: bool = False,
        allow_ask: bool = False,
        ask_handler=None,
        symbolic: bool = False,
        record_video: bool = False,
        goal_text_override: Optional[str] = None,
    ):
        """
        Args:
            env: OmniGibson Environment instance (with BehaviorTask loaded).
            llm_config: Config dict for the LLM backend.
            max_steps: Maximum number of LLM planning steps.
            verbose: Whether to print planning info.
            enable_head_tracking: Enable robot head tracking of target objects.
            experiment_dir: Directory to save detailed step-by-step logs.
                            If None, no logs are saved.
            allow_abstain: If True, LLM can choose ABSTAIN[reason] to declare
                           the task infeasible with available primitives.
            allow_ask: If True, LLM can choose ASK[question] to request
                       clarification before acting.
            ask_handler: Callable(question: str) -> str that provides answers
                         to ASK questions. If None, defaults to interactive
                         input() prompt.
            goal_text_override: If provided, use this text as the task goal
                                instead of the BDDL-derived goal conditions.
                                Useful for abstain/ask experiments where the
                                instruction may reference objects not in the scene.
            symbolic: If True, use SymbolicSemanticActionPrimitives (14 actions,
                      teleport-based) instead of StarterSemanticActionPrimitives
                      (9 actions, physics-based).
            record_video: If True, record simulation video to experiment_dir/video.mp4.
        """
        self.env = env
        self.robot = env.robots[0]
        self.task = env.task
        self.max_steps = max_steps
        self.verbose = verbose
        self.llm_config = llm_config
        self.allow_abstain = allow_abstain
        self.allow_ask = allow_ask
        self.ask_handler = ask_handler
        self.symbolic = symbolic
        self.goal_text_override = goal_text_override

        # Switch global ACTION_PRIMITIVES to match the selected mode
        set_primitive_mode(symbolic=symbolic)

        # LLM backend
        self.llm = create_llm(llm_config)
        self.system_prompt = build_system_prompt(
            allow_abstain=allow_abstain, allow_ask=allow_ask, symbolic=symbolic,
            robot_type=type(self.robot).__name__,
            task_name=self.task.activity_name,
        )

        # Action primitives controller
        if symbolic:
            self.controller = SymbolicSemanticActionPrimitives(env, self.robot)
        else:
            self.controller = StarterSemanticActionPrimitives(
                env, self.robot, enable_head_tracking=enable_head_tracking
            )

        # State tracking
        self.action_history: List[str] = []
        self.step_count = 0
        self._on_step_callback = None  # optional callback(step, action, arg, status)

        # Discovery mode: when abstain or ask is enabled, objects are hidden
        # until the robot navigates close enough to discover them.
        self.discovery_mode = allow_abstain or allow_ask
        self.discovered_objects: set = set()
        self._newly_discovered: set = set()
        self._discovery_threshold = 2.0  # meters — proximity to discover objects
        self._initial_discovery_threshold = 5.0  # meters — larger radius on first step
        self._steps_since_last_discovery = 0

        # Experiment logging
        self.experiment_dir = experiment_dir
        self.step_logs: List[dict] = []
        self._log_file = None
        self._setup_file_logging()

        # Per-action image capture via CameraMixin helper
        self._camera_helper = None
        if experiment_dir:
            self._images_dir = os.path.join(experiment_dir, "images")
            os.makedirs(self._images_dir, exist_ok=True)
            # Create a lightweight wrapper so CameraMixin methods can be called
            self._camera_helper = _CameraHelper(self.env, self.controller)

        # Video recording
        self._video_recorder = None
        if record_video and experiment_dir:
            try:
                video_path = os.path.join(experiment_dir, "video.mp4")
                self._video_recorder = _VideoRecorder(video_path)
                atexit.register(self._video_recorder.close)
                logger.info(f"Video recording enabled: {video_path}")
            except ImportError:
                logger.warning("cv2 not installed, video recording disabled")

    def _setup_file_logging(self):
        """Set up real-time file logging to experiment_dir/run.log."""
        if not self.experiment_dir:
            return
        os.makedirs(self.experiment_dir, exist_ok=True)
        log_path = os.path.join(self.experiment_dir, "run.log")
        self._log_file = open(log_path, "w", buffering=1)  # line-buffered

        # Also set up diag log for action primitives (indented_print output)
        diag_path = os.path.join(self.experiment_dir, "diag.log")
        self._diag_log_file = open(diag_path, "w", buffering=1)
        try:
            from omnigibson.action_primitives.starter_semantic_action_primitives import indented_print
            indented_print._diag_log_file = self._diag_log_file
        except ImportError:
            pass

    def _log(self, msg: str):
        """Print to stdout and write to log file in real-time."""
        if self.verbose:
            print(msg)
        if self._log_file:
            self._log_file.write(msg + "\n")
            self._log_file.flush()

    def _save_step_incremental(self, step_log: dict):
        """Append a step log and flush to disk immediately."""
        self.step_logs.append(step_log)
        if self.experiment_dir:
            # Overwrite steps.json with all steps so far
            with open(os.path.join(self.experiment_dir, "steps.json"), "w") as f:
                json.dump(self.step_logs, f, indent=2, ensure_ascii=False)

            # Write individual step text file
            step_num = step_log["step"]
            steps_dir = os.path.join(self.experiment_dir, "steps")
            os.makedirs(steps_dir, exist_ok=True)
            step_file = os.path.join(steps_dir, f"step_{step_num:03d}.txt")
            with open(step_file, "w") as f:
                f.write(f"{'='*60}\n")
                f.write(f"STEP {step_num} (t={step_log['timestamp']:.1f}s)\n")
                f.write(f"{'='*60}\n\n")

                f.write(f"--- GOAL PROGRESS ---\n")
                progress = step_log["goal_progress"]
                for c in progress.get("satisfied", []):
                    f.write(f"  [DONE] {c}\n")
                for c in progress.get("unsatisfied", []):
                    f.write(f"  [TODO] {c}\n")

                if step_log.get("positions"):
                    f.write(f"\n--- POSITIONS ---\n")
                    f.write(self._format_positions_text(step_log["positions"]))
                    f.write("\n")

                if step_log.get("error_feedback_input"):
                    f.write(f"\n--- ERROR FEEDBACK FROM PREVIOUS STEP ---\n")
                    f.write(f"{step_log['error_feedback_input']}\n")

                f.write(f"\n--- PROMPT (system) ---\n")
                f.write(step_log["prompt"]["system"])
                f.write(f"\n\n--- PROMPT (user) ---\n")
                f.write(step_log["prompt"]["user"])
                f.write(f"\n\n--- LLM RAW RESPONSE ---\n")
                f.write(step_log["llm_raw_response"])

                parsed = step_log["parsed"]
                f.write(f"\n\n--- PARSED ---\n")
                f.write(f"Thought: {parsed['thought']}\n")
                f.write(f"Action:  {parsed['action_name']}[{parsed['action_arg']}]\n")
                if parsed["parse_error"]:
                    f.write(f"Parse Error: {parsed['parse_error']}\n")

                exe = step_log["execution"]
                f.write(f"\n--- EXECUTION ---\n")
                f.write(f"Status: {exe['status']}\n")
                if exe.get("error"):
                    f.write(f"Error: {exe['error']}\n")

                f.write(f"\nDuration: {step_log['duration_seconds']:.2f}s\n")

    def run(self) -> dict:
        """Run the ReAct planning loop until task completion or max steps.

        Returns:
            dict with keys: success, steps, action_history, final_reward
        """
        logger.info("Starting LLM planner...")

        # Get natural language goal from BDDL (or use override)
        if self.goal_text_override:
            goal_text = self.goal_text_override
        else:
            # Build goal text from ground conditions (same format as progress)
            # so that object names match exactly between Goal and Progress sections
            ground_conds = self.task.ground_goal_state_options[0]
            goal_lines = []
            for cond in ground_conds:
                terms = getattr(cond, "terms", None)
                if terms and len(terms) >= 2:
                    try:
                        goal_lines.append(self._body_to_text(list(terms)))
                    except Exception:
                        pass
                if not goal_lines or goal_lines[-1] == str(len(goal_lines) - 1):
                    body = getattr(cond, "body", None)
                    if body is not None:
                        try:
                            goal_lines.append(self._body_to_text(body))
                        except Exception:
                            pass
            if goal_lines:
                goal_text = format_goal_text(goal_lines)
            else:
                # Fallback to BDDL natural language
                goal_conditions_text = self.task.activity_natural_language_goal_conditions
                goal_text = format_goal_text(goal_conditions_text)

        self._log(f"\n{'='*60}")
        self._log(f"TASK: {self.task.activity_name}")
        self._log(f"GOAL:\n{goal_text}")
        self._log(f"{'='*60}\n")

        self.llm.reset()
        self.action_history = []
        self.step_logs = []
        self.discovered_objects = set()
        self._newly_discovered = set()
        self._steps_since_last_discovery = 0
        error_feedback = None
        run_start_time = time.time()

        # Let objects settle onto surfaces before the first action.
        # Initial template positions place object centers above surfaces;
        # og.sim.step() runs n_physics_timesteps_per_render per call (typically 10-20),
        # which is much more effective than step_physics() (single tiny dt step).
        self._log("Settling objects (10 sim steps)...")
        for _ in range(10):
            og.sim.step()

        try:
          return self._run_loop(goal_text, run_start_time)
        except KeyboardInterrupt:
            self._log("\nInterrupted by user.")
            result = self._make_result(success=False)
            self._save_experiment(result, goal_text, run_start_time)
            return result
        finally:
            if self._video_recorder:
                self._video_recorder.close()

    def _run_loop(self, goal_text: str, run_start_time: float) -> dict:
        """Inner planning loop, separated so run() can wrap with try/finally."""
        error_feedback = None
        prev_image_path = None  # after-image from the previous step

        for step in range(self.max_steps):
            self.step_count = step + 1
            step_start_time = time.time()

            # 1. Evaluate current goal progress
            goal_status = self._get_goal_progress()

            # Check if task is already done
            if goal_status.get("all_satisfied", False):
                self._log(f"\n[Step {self.step_count}] Task completed!")
                result = self._make_result(success=True)
                self._save_experiment(result, goal_text, run_start_time)
                return result

            # 2. Update discovered objects (discovery mode) and get state text
            self._update_discovered_objects()
            state_text = self._get_state_text()

            # When goal is overridden, BDDL progress is irrelevant and confusing
            if self.goal_text_override:
                progress_text = None
            else:
                progress_text = format_progress_text(goal_status)

            # 3. Build prompt and call LLM
            steps_remaining = self.max_steps - self.step_count
            exploration_status = None
            if self.discovery_mode:
                exploration_status = {
                    "total_discovered": len(self.discovered_objects),
                    "steps_since_last_discovery": self._steps_since_last_discovery,
                }

            step_prompt = build_step_prompt(
                goal_text=goal_text,
                state_text=state_text,
                progress_text=progress_text,
                action_history=self.action_history,
                error_feedback=error_feedback,
                steps_remaining=steps_remaining,
                exploration_status=exploration_status,
                allow_abstain=self.allow_abstain,
            )

            # Get positions for debugging
            positions = self._get_positions()
            self._log(f"\n[Step {self.step_count}] Calling LLM...")
            self._log(f"  Positions:")
            self._log(self._format_positions_text(positions))

            full_prompt = [
                ("system", self.system_prompt),
                ("user", step_prompt, prev_image_path),
            ]
            try:
                llm_response = self.llm.generate(full_prompt)
            except Exception as e:
                error_str = str(e)
                if "content_filter" in error_str or "ContentPolicyViolation" in error_str:
                    self._log(f"  LLM content filter triggered. Clearing action history and retrying...")
                    # Trim action history to reduce prompt size and avoid re-triggering
                    self.action_history = self.action_history[-3:]
                    error_feedback = "Previous action history was cleared due to a prompt issue. Continue from the current state."
                    continue
                raise

            # 4. Parse LLM response
            thought, action_name, action_arg, parse_error = parse_llm_response(llm_response)

            self._log(f"  Thought: {thought}")
            self._log(f"  Action: {action_name}[{action_arg}]")

            # Build step log
            step_log = {
                "step": self.step_count,
                "timestamp": time.time() - run_start_time,
                "prompt": {
                    "system": self.system_prompt,
                    "user": step_prompt,
                },
                "llm_raw_response": llm_response,
                "parsed": {
                    "thought": thought,
                    "action_name": action_name,
                    "action_arg": action_arg,
                    "parse_error": parse_error,
                },
                "goal_progress": goal_status,
                "positions": positions,
                "state_text": state_text,
                "error_feedback_input": error_feedback,
                "discovered_objects": sorted(self.discovered_objects) if self.discovery_mode else None,
                "newly_discovered": sorted(self._newly_discovered) if self.discovery_mode else None,
            }

            if parse_error and action_name is None:
                self._log(f"  Parse Error: {parse_error}")
                error_feedback = parse_error
                self.action_history.append(f"PARSE_ERROR: {parse_error}")
                step_log["execution"] = {"status": "PARSE_ERROR", "error": parse_error}
                step_log["duration_seconds"] = time.time() - step_start_time
                self._save_step_incremental(step_log)
                continue

            # Clear previous error on successful parse
            error_feedback = None

            # 5. Handle DONE action
            if action_name == "DONE":
                self._log(f"  LLM declared DONE.")
                if self.goal_text_override:
                    # With goal override, BDDL conditions are irrelevant;
                    # trust the LLM's judgment that the task is complete.
                    step_log["execution"] = {"status": "DONE_SUCCESS"}
                    step_log["duration_seconds"] = time.time() - step_start_time
                    self._save_step_incremental(step_log)
                    result = self._make_result(success=True)
                    self._save_experiment(result, goal_text, run_start_time)
                    return result
                goal_status = self._get_goal_progress()
                success = goal_status.get("all_satisfied", False)
                if not success:
                    error_feedback = "You declared DONE but not all goal conditions are satisfied. Continue working."
                    self.action_history.append("DONE (premature - goals not met)")
                    step_log["execution"] = {"status": "PREMATURE_DONE"}
                    step_log["duration_seconds"] = time.time() - step_start_time
                    self._save_step_incremental(step_log)
                    continue
                step_log["execution"] = {"status": "DONE_SUCCESS"}
                step_log["duration_seconds"] = time.time() - step_start_time
                self._save_step_incremental(step_log)
                result = self._make_result(success=True)
                self._save_experiment(result, goal_text, run_start_time)
                return result

            # 5b. Handle ABSTAIN action
            if action_name == "ABSTAIN":
                reason = action_arg or "no reason given"
                if not self.allow_abstain:
                    error_feedback = "ABSTAIN is not available. You must attempt the task."
                    self.action_history.append(f"ABSTAIN (not allowed): {reason}")
                    step_log["execution"] = {"status": "ABSTAIN_REJECTED"}
                    step_log["duration_seconds"] = time.time() - step_start_time
                    self._save_step_incremental(step_log)
                    continue
                self._log(f"  LLM abstained: {reason}")
                self.action_history.append(f"ABSTAIN: {reason}")
                step_log["execution"] = {"status": "ABSTAIN", "reason": reason}
                step_log["duration_seconds"] = time.time() - step_start_time
                self._save_step_incremental(step_log)
                result = self._make_result(success=False, abstained=True, abstain_reason=reason)
                self._save_experiment(result, goal_text, run_start_time)
                return result

            # 5c. Handle ASK action
            if action_name == "ASK":
                question = action_arg or "Can you clarify the task?"
                if not self.allow_ask:
                    error_feedback = "ASK is not available. You must proceed with the information given."
                    self.action_history.append(f"ASK (not allowed): {question}")
                    step_log["execution"] = {"status": "ASK_REJECTED"}
                    step_log["duration_seconds"] = time.time() - step_start_time
                    self._save_step_incremental(step_log)
                    continue
                self._log(f"  LLM asks: {question}")
                # Get answer from handler or interactive prompt
                if self.ask_handler is not None:
                    answer = self.ask_handler(question)
                else:
                    answer = input(f"  Agent asks: {question}\n  Your answer: ")
                self._log(f"  Answer: {answer}")
                self.action_history.append(f"ASK: {question} -> ANSWER: {answer}")
                error_feedback = f"Answer to your question: {answer}"
                step_log["execution"] = {
                    "status": "ASK",
                    "question": question,
                    "answer": answer,
                }
                step_log["duration_seconds"] = time.time() - step_start_time
                self._save_step_incremental(step_log)
                continue

            # 5.5 Capture image BEFORE action
            if self._camera_helper:
                try:
                    from PIL import Image as _PILImage
                    rgb = self._camera_helper.get_rgb()
                    path = os.path.join(self._images_dir, f"step_{self.step_count:04d}_1.png")
                    _PILImage.fromarray(rgb).save(path)
                    self._log(f"  Image saved (before): {path}")
                except Exception as img_err:
                    self._log(f"  [WARN] Before-image capture failed: {img_err}")

            # 6. Execute the action primitive
            error_feedback = self._execute_action(action_name, action_arg)

            # 6.1 Capture image AFTER action
            if self._camera_helper:
                try:
                    from PIL import Image as _PILImage
                    # PLACE_ON_TOP on non-surface targets: save both side + top views
                    _is_place_non_surface = (
                        action_name == 'PLACE_ON_TOP'
                        and action_arg
                        and 'countertop' not in action_arg
                    )
                    if _is_place_non_surface:
                        # Side view
                        rgb_side = self._camera_helper.get_rgb()
                        path_side = os.path.join(self._images_dir, f"step_{self.step_count:04d}_2_side.png")
                        _PILImage.fromarray(rgb_side).save(path_side)
                        self._log(f"  Image saved (after, side): {path_side}")
                        # Top view
                        self._camera_helper._force_overhead = True
                        rgb_top = self._camera_helper.get_rgb()
                        self._camera_helper._force_overhead = False
                        path_top = os.path.join(self._images_dir, f"step_{self.step_count:04d}_2_top.png")
                        _PILImage.fromarray(rgb_top).save(path_top)
                        self._log(f"  Image saved (after, top): {path_top}")
                        prev_image_path = path_side
                    else:
                        rgb = self._camera_helper.get_rgb()
                        path = os.path.join(self._images_dir, f"step_{self.step_count:04d}_2.png")
                        _PILImage.fromarray(rgb).save(path)
                        self._log(f"  Image saved (after): {path}")
                        prev_image_path = path
                except Exception as img_err:
                    self._log(f"  [WARN] After-image capture failed: {img_err}")

            if error_feedback:
                self.action_history.append(f"{action_name}[{action_arg}] -> FAILED: {error_feedback}")
                step_log["execution"] = {"status": "FAILED", "error": error_feedback}
            elif getattr(self, '_last_success_feedback', None):
                feedback = self._last_success_feedback
                self.action_history.append(f"{action_name}[{action_arg}] -> SUCCESS: {feedback}")
                step_log["execution"] = {"status": "SUCCESS", "feedback": feedback}
            else:
                self.action_history.append(f"{action_name}[{action_arg}] -> SUCCESS")
                step_log["execution"] = {"status": "SUCCESS"}

            step_log["duration_seconds"] = time.time() - step_start_time
            self._save_step_incremental(step_log)

            # Notify callback (used by --quiet mode for terminal summaries)
            if self._on_step_callback:
                self._on_step_callback(
                    self.step_count, action_name, action_arg,
                    step_log["execution"]["status"],
                )

        # Max steps reached
        self._log(f"\nMax steps ({self.max_steps}) reached.")
        result = self._make_result(success=False)
        self._save_experiment(result, goal_text, run_start_time)
        return result

    def _execute_action(self, action_name: str, action_arg: Optional[str]) -> Optional[str]:
        """Execute an action primitive.

        Returns:
            Error message string if failed, None if successful.
        """
        primitive = ACTION_PRIMITIVES[action_name]

        def _resolve_one(name: str):
            resolved = resolve_object_name(name.strip(), self.task.object_scope)
            if resolved is None:
                resolved = self._resolve_scene_object(name.strip())
            if resolved is None:
                return None, f"Object '{name.strip()}' not found. Available objects: {list(self.task.object_scope.keys())}"
            if resolved in self.task.object_scope:
                entity = self.task.object_scope[resolved]
                obj = getattr(entity, "wrapped_obj", entity)
                # Future substance: wrapped_obj is None but system exists in scene registry
                if obj is None and getattr(entity, "is_system", False):
                    from omnigibson.utils.bddl_utils import OBJECT_TAXONOMY
                    try:
                        substances = OBJECT_TAXONOMY.get_subtree_substances(entity.synset)
                        if substances:
                            obj = self.env.scene.get_system(substances[0])
                            # Update entity so (real ...) goal condition becomes True
                            entity.set_entity(obj)
                    except Exception:
                        obj = None
            else:
                obj = self._get_scene_object_by_name(resolved)
            if obj is None:
                return None, f"Could not retrieve object instance for '{resolved}'."
            return obj, None

        # Resolve object argument(s)
        action_objs = []
        if action_arg is not None:
            # Support multi-arg primitives: SPREAD[fluid_container, target_obj]
            parts = [p.strip() for p in action_arg.split(",")]
            for part in parts:
                obj, err = _resolve_one(part)
                if err:
                    return err
                action_objs.append(obj)

        try:
            self._log(f"  Executing {action_name}...")

            ctrl_gen = self.controller.apply_ref(primitive, *action_objs)

            for action in ctrl_gen:
                self.env.step(action)
                if self._video_recorder:
                    self._video_recorder.step()

            # Check for custom success feedback from the primitive (e.g. _draw)
            custom = getattr(self.controller, '_custom_success_feedback', None)
            if custom:
                self.controller._custom_success_feedback = None
                self._log(f"  {action_name}: {custom}")
                self._last_success_feedback = custom
            else:
                self._log(f"  {action_name} completed successfully.")
                self._last_success_feedback = None
            return None

        except (ActionPrimitiveError, ActionPrimitiveErrorGroup) as e:
            # Extract only the first attempt's core error for concise LLM feedback
            # (skip verbose multi-attempt dumps and metadata dicts)
            if isinstance(e, ActionPrimitiveErrorGroup) and e.exceptions:
                first = str(e.exceptions[0])
            else:
                first = str(e)
            # Strip ". Additional info: {...}" suffix — not useful for LLM
            error_msg = first.split(". Additional info:")[0]
            self._log(f"  {action_name} FAILED: {error_msg}")
            return error_msg
        except Exception as e:
            # [NaN-fix] PIERCE is purely symbolic — if the piercing tool's Pierced
            # state was successfully set before the generator error, treat it as success.
            if action_name == "PIERCE" and len(action_objs) >= 2:
                from omnigibson import object_states as os_module
                piercing_tool = action_objs[1]
                if os_module.Pierced in piercing_tool.states and piercing_tool.states[os_module.Pierced].get_value():
                    custom = getattr(self.controller, '_custom_success_feedback', None)
                    if custom:
                        self.controller._custom_success_feedback = None
                        self._log(f"  {action_name}: {custom}")
                        self._last_success_feedback = custom
                    else:
                        self._log(f"  {action_name} completed successfully.")
                        self._last_success_feedback = None
                    return None  # treat as success

            import traceback
            tb_str = traceback.format_exc()
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)[:200]}"
            self._log(f"  {action_name} FAILED: {error_msg}")
            self._log(f"  Traceback:\n{tb_str}")
            return error_msg

    def _body_to_text(self, body) -> str:
        """Convert a BDDL condition body (nested list) into readable text.

        Handles ground (quantifier-free) conditions like:
          ["ontop", "easter_egg.n.01_1", "lawn.n.01_1"]
          ["not", ["inside", "easter_egg.n.01_1", "wicker_basket.n.01_1"]]
          ["real", "cooked__popcorn.n.01_1"]
        """
        # Task-specific predicate text overrides
        _covered_text = "covered with"
        _torn_text = "torn"
        if hasattr(self, 'task') and getattr(self.task, 'activity_name', '') == 'draw_a_line_on_paper':
            _covered_text = "has a straight line drawn with"
        elif hasattr(self, 'task') and getattr(self.task, 'activity_name', '') == 'sweep_dustpan':
            _covered_text = "has breadcrumbs swept into it from"
        elif hasattr(self, 'task') and getattr(self.task, 'activity_name', '') == 'tear_paper_along_a_ruler':
            _torn_text = "torn along a straight line"
        PRED_NAMES = {"ontop": "on top of", "nextto": "next to", "inside": "inside",
                      "under": "under", "contains": "contains", "covered": _covered_text,
                      "saturated": "saturated with", "filled": "filled with",
                      "cooked": "cooked", "heated": "heated", "frozen": "frozen",
                      "open": "open", "toggled_on": "toggled on", "real": "exists",
                      "broken": "broken", "folded": "folded", "unfolded": "unfolded",
                      "assembled": "assembled", "draped": "draped over",
                      "overlaid": "overlaid on", "attached": "attached to",
                      "nailed": "nailed into the wall", "pierced": "pierced through a holder",
                      "placed_against": "placed against", "torn": _torn_text}

        def _obj_name(term):
            """Keep full synset name so it matches scene object names exactly.

            'sheet.n.02_1' → 'sheet.n.02_1' (unchanged)
            '?easter_egg.n.01' → 'easter_egg.n.01'
            """
            if not isinstance(term, str):
                name = getattr(term, "name", None)
                if name:
                    term = name
                else:
                    term = str(term)
            return term.lstrip("?")

        def _coerce(x):
            """Recursively convert tuples to lists for consistent handling."""
            if isinstance(x, tuple):
                return [_coerce(i) for i in x]
            return x

        def _fmt(term):
            # Handle both list and tuple (BDDL may return either)
            if isinstance(term, (tuple, list)):
                term = [_coerce(t) for t in term]
            if not isinstance(term, list):
                return _obj_name(str(term))
            if len(term) == 0:
                return ""
            head = term[0]
            # If head is not a string, try to format recursively
            if not isinstance(head, str):
                return " AND ".join(_fmt(t) for t in term)
            if head == "not":
                return f"NOT({_fmt(term[1])})"
            if head == "and":
                return " AND ".join(_fmt(t) for t in term[1:])
            if head == "or":
                return " OR ".join(_fmt(t) for t in term[1:])
            if head == "forall":
                return f"for every {_obj_name(term[1][0])}: {_fmt(term[2])}"
            if head == "exists":
                return f"for some {_obj_name(term[1][0])}: {_fmt(term[2])}"
            if head == "imply":
                return f"if {_fmt(term[1])} then {_fmt(term[2])}"
            pred = PRED_NAMES.get(head, head)
            # Predicates that use "{obj} {pred}" instead of "{obj} is {pred}"
            VERB_PREDS = {"contains", "exists"}
            # Task-specific covered text uses "has..." so it shouldn't have "is" prefix
            if "has " in _covered_text:
                VERB_PREDS.add(_covered_text)
            if len(term) == 2:
                if pred in VERB_PREDS:
                    return f"{_obj_name(term[1])} {pred}"
                return f"{_obj_name(term[1])} is {pred}"
            if len(term) == 3:
                if pred in VERB_PREDS:
                    return f"{_obj_name(term[1])} {pred} {_obj_name(term[2])}"
                return f"{_obj_name(term[1])} is {pred} {_obj_name(term[2])}"
            args = ", ".join(_obj_name(a) for a in term[1:])
            return f"{pred}({args})"

        return _fmt(_coerce(body))

    def _get_goal_progress(self) -> dict:
        """Evaluate goal conditions and return progress info."""
        try:
            from bddl.activity import evaluate_goal_conditions

            ground_conditions = self.task.ground_goal_state_options[0]
            success, results = evaluate_goal_conditions(ground_conditions)

            satisfied_idxs = results.get("satisfied", [])
            unsatisfied_idxs = results.get("unsatisfied", [])

            def _idx_to_text(idx):
                if idx < len(ground_conditions):
                    cond = ground_conditions[idx]
                    # Strategy 1: use terms (flat string list from HEAD)
                    terms = getattr(cond, "terms", None)
                    if terms and len(terms) >= 2:
                        try:
                            return self._body_to_text(list(terms))
                        except Exception:
                            pass
                    # Strategy 2: use body directly
                    body = getattr(cond, "body", None)
                    if body is not None:
                        try:
                            return self._body_to_text(body)
                        except Exception:
                            pass
                    # Strategy 3: reconstruct from children
                    children = getattr(cond, "children", [])
                    if children:
                        child = children[0]
                        state_name = getattr(child, "STATE_NAME", None)
                        input1 = getattr(child, "input1", None)
                        input2 = getattr(child, "input2", None)
                        if state_name and input1:
                            try:
                                parts = [state_name, str(input1)] + ([str(input2)] if input2 else [])
                                return self._body_to_text(parts)
                            except Exception:
                                pass
                return str(idx)

            satisfied_texts = [_idx_to_text(i) for i in satisfied_idxs]
            unsatisfied_texts = [_idx_to_text(i) for i in unsatisfied_idxs]

            return {
                "all_satisfied": success,
                "satisfied": satisfied_texts,
                "unsatisfied": unsatisfied_texts,
            }
        except Exception as e:
            logger.warning(f"Could not evaluate goal conditions: {e}")
            return {"all_satisfied": False, "satisfied": [], "unsatisfied": ["(evaluation error)"]}

    def _get_positions(self) -> dict:
        """Get positions of the robot and all task objects for debugging.

        Returns:
            dict with "robot" and "objects" keys containing position/orientation info.
        """
        import torch as th

        positions = {"robot": {}, "objects": {}}

        # Robot position and orientation
        try:
            pos, ori = self.robot.get_position_orientation()
            positions["robot"] = {
                "position": [round(float(x), 3) for x in pos],
                "orientation": [round(float(x), 3) for x in ori],
            }
        except Exception as e:
            positions["robot"] = {"error": str(e)}

        # Object positions
        for obj_name, entity in self.task.object_scope.items():
            if entity is None:
                continue
            try:
                obj = entity if not hasattr(entity, "wrapped_obj") else entity.wrapped_obj
                if obj is None or not hasattr(obj, "get_position_orientation"):
                    continue
                pos = obj.get_position_orientation()[0]
                positions["objects"][obj_name] = {
                    "position": [round(float(x), 3) for x in pos],
                }
            except Exception as e:
                positions["objects"][obj_name] = {"error": str(e)}

        # Compute distances from robot to each object
        robot_pos = positions["robot"].get("position")
        if robot_pos is not None:
            import math
            for obj_name, info in positions["objects"].items():
                obj_pos = info.get("position")
                if obj_pos is not None:
                    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(robot_pos, obj_pos)))
                    info["distance_to_robot"] = round(dist, 3)

        return positions

    def _format_positions_text(self, positions: dict) -> str:
        """Format positions dict into readable text for log files."""
        lines = []
        r = positions.get("robot", {})
        if "position" in r:
            lines.append(f"  Robot: pos={r['position']}, ori={r['orientation']}")
        elif "error" in r:
            lines.append(f"  Robot: ERROR - {r['error']}")

        for obj_name, info in positions.get("objects", {}).items():
            if "position" in info:
                dist_str = f", dist={info['distance_to_robot']}m" if "distance_to_robot" in info else ""
                lines.append(f"  {obj_name}: pos={info['position']}{dist_str}")
            elif "error" in info:
                lines.append(f"  {obj_name}: ERROR - {info['error']}")
        return "\n".join(lines)

    def _update_discovered_objects(self):
        """Check proximity to task objects and mark nearby ones as discovered.

        In discovery mode, an object is 'discovered' when the robot is within
        self._discovery_threshold meters of it. On the first step (no objects
        discovered yet), a larger radius is used so the robot has initial objects
        to navigate toward.
        """
        if not self.discovery_mode:
            return

        import math

        self._newly_discovered = set()

        # Use a larger radius on the first step to give the robot initial targets
        threshold = (self._initial_discovery_threshold
                     if not self.discovered_objects
                     else self._discovery_threshold)

        try:
            robot_pos = self.robot.get_position_orientation()[0]
            robot_pos = [float(x) for x in robot_pos]
        except Exception:
            return

        for obj_name, entity in self.task.object_scope.items():
            if obj_name in self.discovered_objects:
                continue
            if entity is None:
                continue
            try:
                obj = entity if not hasattr(entity, "wrapped_obj") else entity.wrapped_obj
                if obj is None or not hasattr(obj, "get_position_orientation"):
                    continue
                obj_pos = obj.get_position_orientation()[0]
                obj_pos = [float(x) for x in obj_pos]
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(robot_pos, obj_pos)))
                if dist <= threshold:
                    self._newly_discovered.add(obj_name)
                    self.discovered_objects.add(obj_name)
            except Exception:
                pass

        if self._newly_discovered:
            self._steps_since_last_discovery = 0
            self._log(f"  Discovered objects: {sorted(self._newly_discovered)}")
        else:
            self._steps_since_last_discovery += 1

    def _get_robot_holding(self) -> Optional[str]:
        """Get the name of the task-relevant object the robot is holding, if any.

        Filters out non-task objects (e.g., furniture accidentally grasped)
        to avoid confusing the LLM.

        Returns:
            Object name string if holding a task-relevant object, else None.
        """
        # Build a set of task-relevant object names for fast lookup
        task_obj_names = set()
        for entity in self.task.object_scope.values():
            if entity is None:
                continue
            try:
                obj = entity if not hasattr(entity, "wrapped_obj") else entity.wrapped_obj
                if obj is not None:
                    task_obj_names.add(getattr(obj, "name", None))
            except Exception:
                pass
        task_obj_names.discard(None)

        # Try the symbolic controller's _grasped_obj first (used in symbolic/teleport mode)
        try:
            if hasattr(self.controller, '_grasped_obj') and self.controller._grasped_obj is not None:
                obj = self.controller._grasped_obj
                if obj.name in task_obj_names:
                    return obj.name
        except Exception:
            pass

        # Try the action primitive controller (starter mode)
        try:
            if hasattr(self.controller, '_get_obj_in_hand') and callable(self.controller._get_obj_in_hand):
                obj = self.controller._get_obj_in_hand()
                if obj is not None and obj.name in task_obj_names:
                    return obj.name
        except Exception:
            pass

        # Fall back to raw robot grasp state
        try:
            for arm in self.robot.arm_names:
                obj = self.robot._ag_obj_in_hand.get(arm)
                if obj is not None and obj.name in task_obj_names:
                    return obj.name
        except Exception:
            pass

        return None

    def _get_state_text(self) -> str:
        """Build a text description of the current environment state."""
        robot_holding = self._get_robot_holding()

        # In discovery mode, the held object is always discovered
        if self.discovery_mode and robot_holding:
            for obj_name, entity in self.task.object_scope.items():
                if entity is None:
                    continue
                try:
                    obj = entity if not hasattr(entity, "wrapped_obj") else entity.wrapped_obj
                    if obj is not None and getattr(obj, "name", None) == robot_holding:
                        self.discovered_objects.add(obj_name)
                        break
                except Exception:
                    pass

        # Build object scope info
        object_states_info = {}
        from omnigibson import object_states as os_module

        # Resolve all task scope objects once
        scope_objects = {}  # obj_name -> actual obj
        for obj_name, entity in self.task.object_scope.items():
            if entity is None:
                continue
            try:
                obj = entity if not hasattr(entity, "wrapped_obj") else entity.wrapped_obj
                if obj is not None and hasattr(obj, "states"):
                    scope_objects[obj_name] = obj
            except Exception:
                pass

        for obj_name, obj in scope_objects.items():
            try:
                states = []
                # Boolean state checks (excluding Broken — hidden constraint)
                state_checks = {
                    "cooked": os_module.Cooked,
                    "toggled_on": os_module.ToggledOn,
                    "frozen": os_module.Frozen,
                    "heated": os_module.Heated,
                    "on_fire": os_module.OnFire,
                }
                for state_name, state_cls in state_checks.items():
                    if state_cls in obj.states:
                        try:
                            if obj.states[state_cls].get_value():
                                states.append(state_name)
                        except Exception:
                            pass
                # Open/Closed for openable objects
                if os_module.Open in obj.states:
                    try:
                        if obj.states[os_module.Open].get_value():
                            states.append("open")
                        else:
                            states.append("closed")
                    except Exception:
                        pass
                if states:
                    object_states_info[obj_name] = ", ".join(states)
            except Exception:
                pass

        # Build spatial relationships (OnTop, Inside, PlacedAgainst, NextTo)
        spatial_relations = {}  # obj_name -> list of relation strings
        for obj_name, obj in scope_objects.items():
            rels = []
            for other_name, other_obj in scope_objects.items():
                if obj_name == other_name:
                    continue
                try:
                    if os_module.OnTop in obj.states:
                        # Skip spurious "on top of" for non-surface objects (e.g. carton used as flat panel)
                        other_cat = getattr(other_obj, "category", "")
                        non_surface_cats = {"carton", "cardboard", "plywood", "rubber_mat", "sponge", "chopping_board"}
                        if other_cat not in non_surface_cats:
                            if obj.states[os_module.OnTop].get_value(other_obj):
                                rels.append(f"on top of {other_name}")
                except Exception:
                    pass
                try:
                    if os_module.Inside in obj.states:
                        # Skip spurious "inside" for non-container objects (e.g. carton used as flat panel)
                        other_cat = getattr(other_obj, "category", "")
                        non_container_cats = {"carton", "cardboard", "plywood", "rubber_mat", "sponge", "chopping_board"}
                        if other_cat not in non_container_cats:
                            if obj.states[os_module.Inside].get_value(other_obj):
                                rels.append(f"inside {other_name}")
                except Exception:
                    pass
                try:
                    if os_module.PlacedAgainst in obj.states:
                        if obj.states[os_module.PlacedAgainst].get_value(other_obj):
                            rels.append(f"placed against {other_name}")
                except Exception:
                    pass
                try:
                    if os_module.NextTo in obj.states:
                        if obj.states[os_module.NextTo].get_value(other_obj):
                            rels.append(f"next to {other_name}")
                except Exception:
                    pass
            if rels:
                spatial_relations[obj_name] = rels

        # In discovery mode, filter states and relations to discovered objects only
        if self.discovery_mode:
            object_states_info = {k: v for k, v in object_states_info.items()
                                  if k in self.discovered_objects}
            filtered_relations = {}
            for obj_name, rels in spatial_relations.items():
                if obj_name not in self.discovered_objects:
                    continue
                # Only keep relations referencing other discovered objects
                filtered_rels = [
                    rel for rel in rels
                    if any(other in rel for other in self.discovered_objects if other != obj_name)
                ]
                if filtered_rels:
                    filtered_relations[obj_name] = filtered_rels
            spatial_relations = filtered_relations

        # Check if robot is currently elevated (climbing)
        climb_info = None
        if self.symbolic and hasattr(self.controller, '_climb_obj') and self.controller._climb_obj is not None:
            climb_info = self.controller._climb_obj.name

        state_text = format_state_text(
            scene_objects=self.task.object_scope,
            robot_holding=robot_holding,
            object_states_info=object_states_info,
            spatial_relations=spatial_relations,
            discovery_mode=self.discovery_mode,
            discovered_objects=self.discovered_objects if self.discovery_mode else None,
            newly_discovered=self._newly_discovered if self.discovery_mode else None,
        )

        if climb_info:
            state_text = f"Robot is standing on: {climb_info} (elevated, cannot navigate)\n" + state_text

        return state_text

    def _resolve_scene_object(self, name: str) -> Optional[str]:
        """Try to resolve an object name from the full scene (not just task scope)."""
        try:
            scene = self.env.scene
            for obj in scene.objects:
                if name.lower() in obj.name.lower():
                    return obj.name
        except Exception:
            pass
        return None

    def _get_scene_object_by_name(self, name: str):
        """Get an object from the scene by name."""
        try:
            scene = self.env.scene
            for obj in scene.objects:
                if obj.name == name:
                    return obj
        except Exception:
            pass
        return None

    def _save_experiment(self, result: dict, goal_text: str, run_start_time: float):
        """Save final experiment summary to experiment_dir.

        Note: step logs and individual step files are already saved incrementally
        by _save_step_incremental() during the run.
        """
        if not self.experiment_dir:
            return

        os.makedirs(self.experiment_dir, exist_ok=True)

        # 1. Save config
        config_data = {
            "llm_config": self.llm_config,
            "task": self.task.activity_name,
            "scene": self.env.scene.scene_model if hasattr(self.env.scene, "scene_model") else "unknown",
            "max_steps": self.max_steps,
            "primitive_mode": "symbolic" if self.symbolic else "starter",
            "goal_text": goal_text,
            "system_prompt": self.system_prompt,
        }
        with open(os.path.join(self.experiment_dir, "config.json"), "w") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        # 2. Final flush of step logs
        with open(os.path.join(self.experiment_dir, "steps.json"), "w") as f:
            json.dump(self.step_logs, f, indent=2, ensure_ascii=False)

        # 3. Save summary result
        result["total_time_seconds"] = time.time() - run_start_time
        if self._video_recorder and self._video_recorder.frame_count > 0:
            result["video_frames"] = self._video_recorder.frame_count
            result["video_path"] = self._video_recorder.output_path
        with open(os.path.join(self.experiment_dir, "result.json"), "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # 4. Close log files
        if self._log_file:
            self._log_file.close()
            self._log_file = None
        if hasattr(self, '_diag_log_file') and self._diag_log_file:
            try:
                from omnigibson.action_primitives.starter_semantic_action_primitives import indented_print
                indented_print._diag_log_file = None
            except ImportError:
                pass
            self._diag_log_file.close()
            self._diag_log_file = None

        self._log(f"\nExperiment saved to: {self.experiment_dir}")

    def _build_full_action_history(self) -> List[str]:
        """Reconstruct the complete action history from step_logs.

        self.action_history may be truncated by content-filter retries
        (see the ``self.action_history = self.action_history[-3:]`` path).
        step_logs is never truncated, so we rebuild from there.
        """
        history: List[str] = []
        for step in self.step_logs:
            parsed = step.get("parsed", {})
            execution = step.get("execution", {})
            action_name = parsed.get("action_name")
            action_arg = parsed.get("action_arg")
            status = execution.get("status", "UNKNOWN")
            error = execution.get("error")

            if status == "PREMATURE_DONE":
                history.append("DONE (premature - goals not met)")
            elif action_name is None:
                # parse error or missing action
                parse_err = parsed.get("parse_error")
                if parse_err:
                    history.append(f"PARSE_ERROR: {parse_err}")
                else:
                    history.append(f"UNKNOWN_ACTION -> {status}")
            elif status == "SUCCESS":
                feedback = execution.get("feedback")
                if feedback:
                    history.append(f"{action_name}[{action_arg}] -> SUCCESS: {feedback}")
                else:
                    history.append(f"{action_name}[{action_arg}] -> SUCCESS")
            elif status == "FAILED":
                history.append(f"{action_name}[{action_arg}] -> FAILED: {error or 'unknown'}")
            elif status == "ABSTAIN":
                reason = execution.get("abstain_reason", "")
                history.append(f"ABSTAIN: {reason}")
            else:
                history.append(f"{action_name}[{action_arg}] -> {status}")
        return history

    def _make_result(
        self, success: bool, abstained: bool = False, abstain_reason: Optional[str] = None,
    ) -> dict:
        """Build the result dict."""
        reward = 0.0
        try:
            from bddl.activity import get_reward
            reward = get_reward(self.task.ground_goal_state_options)
        except Exception:
            pass

        # Use full history from step_logs (immune to content-filter truncation)
        full_history = self._build_full_action_history()

        result = {
            "success": success,
            "steps": self.step_count,
            "action_history": full_history,
            "final_reward": reward,
        }
        if self.allow_abstain:
            result["abstained"] = abstained
            if abstain_reason:
                result["abstain_reason"] = abstain_reason
        if self.allow_ask:
            asked = any(a.startswith("ASK:") for a in full_history)
            result["asked"] = asked
        return result


def load_config(config_path: str) -> dict:
    """Load a YAML config file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
