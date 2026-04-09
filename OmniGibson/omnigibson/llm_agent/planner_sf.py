"""SF (Scenario Flexibility) Planner for OmniGibson.

Pipeline that evaluates LLM agent's Scenario Flexibility:
  Phase 0: Observation        — non-destructive observation (no time cost)
  SF Prediction 1             — initial scenario prediction (verbal, structured)
  Phase 2: Investigation      — irreversible interaction (time cost, no reset)
  SF Prediction 2             — extended prediction + 3 execution plans (SF core)
  Phase 4: Mechanical Exec    — system executes each plan via save/restore (no LLM)
  Phase 5: Verification       — system checks predictions against sim (agent unaware)

Built on top of CATSPlanner patterns (camera, observation, base actions).
Key differences from CA:
  - No external demos — agent gathers info via observation + investigation
  - TimeSystem drives non-stationary environment (temperature decay, events)
  - Phase 2 is irreversible — no sim.save/restore for agent
  - Phase 4 is mechanical — system parses 3 plans and executes each with save/restore
  - Phase 5 verification of agent predictions
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import torch

import omnigibson as og
from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
    SymbolicSemanticActionPrimitives,
    SymbolicSemanticActionPrimitiveSet,
)
from omnigibson.action_primitives.action_primitive_set_base import (
    ActionPrimitiveError,
    ActionPrimitiveErrorGroup,
)
from omnigibson.envs.common.eib_camera import CameraMixin
from omnigibson.llm_agent.llm import create_llm
from omnigibson.llm_agent.time_system import TimeSystem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Camera helper (reused from planner_ca.py)
# ---------------------------------------------------------------------------
class _CameraHelper(CameraMixin):
    def __init__(self, env, controller):
        self.robot = env.robots[0]
        self.scene = env.scene
        self.primitives = controller
        self.__init_camera__()


# ---------------------------------------------------------------------------
# Action → OmniGibson Primitive mapping
# ---------------------------------------------------------------------------
_ACTION_PRIMITIVE_MAP = {
    "NAVIGATE_TO": SymbolicSemanticActionPrimitiveSet.NAVIGATE_TO,
    "GRASP": SymbolicSemanticActionPrimitiveSet.GRASP,
    "RELEASE": SymbolicSemanticActionPrimitiveSet.RELEASE,
    "PLACE_ON_TOP": SymbolicSemanticActionPrimitiveSet.PLACE_ON_TOP,
    "PLACE_INSIDE": SymbolicSemanticActionPrimitiveSet.PLACE_INSIDE,
    "OPEN": SymbolicSemanticActionPrimitiveSet.OPEN,
    "CLOSE": SymbolicSemanticActionPrimitiveSet.CLOSE,
}


class SFPlanner:
    """Five-phase SF planner for Scenario Flexibility evaluation."""

    def __init__(
        self,
        env,
        llm_config: dict,
        task_config: dict,
        max_exploration_steps: int = 10,
        experiment_dir: Optional[str] = None,
        verbose: bool = True,
    ):
        self.env = env
        self.robot = env.robots[0]
        self.task = env.task
        self.task_config = task_config
        self.max_exploration_steps = max_exploration_steps
        self.experiment_dir = experiment_dir
        self.verbose = verbose

        # LLM
        self.llm = create_llm(llm_config)

        # Controller (symbolic — teleport-based)
        self.controller = SymbolicSemanticActionPrimitives(env, self.robot)

        # Camera
        self._camera_helper = None
        self._images_dir = None
        if experiment_dir:
            self._images_dir = os.path.join(experiment_dir, "images")
            os.makedirs(self._images_dir, exist_ok=True)
            self._camera_helper = _CameraHelper(self.env, self.controller)

        # Time system
        self.time_system = TimeSystem(task_config["time_system"])

        # Logging
        self.step_logs: List[dict] = []
        self.step_count = 0
        self._log_file = None
        self._setup_file_logging()

    # ==================================================================
    # Logging
    # ==================================================================
    def _setup_file_logging(self):
        if self.experiment_dir:
            os.makedirs(self.experiment_dir, exist_ok=True)
            self._log_file = open(os.path.join(self.experiment_dir, "run.log"), "w")

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
        if self._log_file:
            self._log_file.write(msg + "\n")
            self._log_file.flush()

    def _save_step(self, step_log: dict):
        self.step_logs.append(step_log)
        if self.experiment_dir:
            path = os.path.join(self.experiment_dir, "steps.json")
            with open(path, "w") as f:
                json.dump(self.step_logs, f, indent=2, default=str)

    def _save_experiment(self, result: dict):
        if self.experiment_dir:
            path = os.path.join(self.experiment_dir, "result.json")
            with open(path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            self._log(f"\nExperiment saved to {self.experiment_dir}")
        if self._log_file:
            self._log_file.close()

    # ==================================================================
    # Scene object helpers (from planner_ca.py)
    # ==================================================================
    def _get_scene_object(self, name: str):
        for obj in self.env.scene.objects:
            if obj.name == name:
                return obj
        name_lower = name.lower().replace(" ", "_")
        for obj in self.env.scene.objects:
            obj_base = re.sub(r"_\d+$", "", obj.name).lower()
            if name_lower == obj_base or name_lower in obj_base or obj_base in name_lower:
                self._log(f"    [resolve] Fuzzy matched '{name}' → {obj.name}")
                return obj
        return None

    def _resolve_obj(self, name: str):
        if hasattr(self.task, "object_scope"):
            for scope_name, entity in self.task.object_scope.items():
                if name in scope_name or scope_name in name:
                    obj = getattr(entity, "wrapped_obj", entity)
                    if obj is not None:
                        return obj
        return self._get_scene_object(name)

    # ==================================================================
    # Camera helpers (from planner_ca.py)
    # ==================================================================
    def _teleport_to_face(self, target_obj, tracking_obj=None):
        target_pos = target_obj.get_position_orientation()[0]
        robot_pos = self.robot.get_position_orientation()[0]
        delta = target_pos[:2] - robot_pos[:2]
        dist = torch.norm(delta)
        direction = delta / dist if dist > 1e-3 else torch.tensor([1.0, 0.0])
        new_pos = target_pos.clone()
        new_pos[0] -= direction[0] * 1.0
        new_pos[1] -= direction[1] * 1.0
        new_pos[2] = robot_pos[2]
        yaw = torch.atan2(direction[1], direction[0])
        new_ori = torch.tensor([0.0, 0.0, torch.sin(yaw / 2), torch.cos(yaw / 2)])
        self.robot.set_position_orientation(position=new_pos, orientation=new_ori)
        self.robot.keep_still()
        self.controller._anchored_pos = new_pos.clone()
        self.controller._anchored_ori = new_ori.clone()
        self.controller._tracking_object = tracking_obj or target_obj
        og.sim.step()

    def _capture_image(self, label: str) -> Optional[str]:
        if not self._camera_helper or not self._images_dir:
            return None
        try:
            from PIL import Image as _PILImage
            import numpy as np
            rgb = self._camera_helper.get_rgb()
            path = os.path.join(self._images_dir, f"{label}.png")
            _PILImage.fromarray(rgb).save(path)
            return path
        except Exception as e:
            self._log(f"  [WARN] Image capture failed: {e}")
            return None

    # ==================================================================
    # LLM helpers
    # ==================================================================
    def _call_llm(self, system_prompt: str, user_prompt: str,
                  image_path: Optional[str] = None) -> str:
        messages = [("system", system_prompt)]
        if image_path and os.path.exists(image_path):
            messages.append(("user", user_prompt, image_path))
        else:
            messages.append(("user", user_prompt))
        return self.llm.generate(messages)

    def _parse_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse Think/Action response. Returns (thought, action_name, action_arg)."""
        thought = None
        action_name = None
        action_arg = None

        think_match = re.search(r"Thin(?:k|king):\s*(.+?)(?=\nAction:|\Z)", response, re.DOTALL)
        if think_match:
            thought = think_match.group(1).strip()

        action_match = re.search(r"Action:\s*(\w+)\[([^\]]*)\]", response)
        if action_match:
            action_name = action_match.group(1)
            action_arg = action_match.group(2).strip() or None
        else:
            action_match2 = re.search(r"Action:\s*(\w+)\[\]", response)
            if action_match2:
                action_name = action_match2.group(1)

        return thought, action_name, action_arg

    # ==================================================================
    # Phase 0 — Exploration (no time cost)
    # ==================================================================
    def _execute_exploration(
        self, action_name: str, action_arg: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """Execute exploration primitive. Returns (feedback, image_path|None)."""
        # Block any actions that would modify environment
        if action_name in ("GRASP", "RELEASE", "PLACE_ON_TOP", "PLACE_INSIDE", "WAIT", "NEW_ACTION"):
            return f"{action_name} is not available during exploration. Use NAVIGATE_TO, TOUCH, or LOOK_CLOSER.", None

        # Resolve feedback
        feedbacks = self.task_config.get("exploration_feedbacks", {})
        if action_arg:
            normalized_arg = ", ".join(p.strip() for p in action_arg.split(","))
        else:
            normalized_arg = ""
        key = f"{action_name}[{normalized_arg}]"

        if key not in feedbacks:
            raw_key = f"{action_name}[{action_arg or ''}]"
            if raw_key in feedbacks:
                key = raw_key
            else:
                available = [k for k in feedbacks if k.startswith(action_name)]
                return f"'{action_arg}' not available. Options: {available}", None

        feedback = feedbacks[key]

        # NAVIGATE_TO: teleport + image
        if action_name == "NAVIGATE_TO":
            target_key = normalized_arg
            nav_targets = self.task_config.get("exploration_nav_targets", {})
            nav_tracking = self.task_config.get("exploration_nav_tracking", {})
            nav_obj_name = nav_targets.get(target_key)
            track_obj_name = nav_tracking.get(target_key)

            if nav_obj_name:
                nav_obj = self._get_scene_object(nav_obj_name)
                track_obj = self._get_scene_object(track_obj_name) if track_obj_name else None
                if nav_obj:
                    try:
                        self._teleport_to_face(nav_obj, tracking_obj=track_obj)
                    except Exception as e:
                        self._log(f"  [Nav] Teleport failed: {e}")

            new_image = self._capture_image(f"phase0_step{self.step_count:03d}_after")
            return feedback, new_image

        # LOOK_CLOSER: zoom
        if action_name == "LOOK_CLOSER":
            look_targets = self.task_config.get("exploration_look_targets", {})
            scene_obj_name = look_targets.get(action_arg)
            if scene_obj_name:
                target_obj = self._get_scene_object(scene_obj_name)
                if target_obj:
                    self.controller._tracking_object = target_obj
            new_image = self._capture_image(f"phase0_step{self.step_count:03d}_look")
            return feedback, new_image

        # TOUCH: text only (sensor data from time_system or static feedback)
        if action_name == "TOUCH" and feedback is None:
            # Dynamic sensor from time_system
            feedback = self.time_system.get_observable_state(action_arg or "")

        return feedback or "Observation complete.", None

    def _format_history(self, history: List[dict], header: str) -> List[str]:
        """Format history entries with Thought for prompt construction."""
        lines = [f"=== {header} ==="]
        for i, entry in enumerate(history, 1):
            lines.append(f"Step {i}:")
            if entry.get("thought"):
                lines.append(f"  Thought: {entry['thought']}")
            lines.append(f"  Action: {entry['action']}")
            lines.append(f"  Result: {entry['feedback']}")
        return lines

    def _run_phase0(self) -> dict:
        """Phase 0: Observation — no time consumed."""
        self._log("\n" + "=" * 60)
        self._log("PHASE 0 — Observation")
        self._log("=" * 60)

        system_prompt = (
            f"You are a robot agent in a kitchen during a power outage.\n"
            f"Task: {self.task_config['instruction']}\n\n"
            f"{self.task_config.get('robot_rules', '')}\n\n"
            f"{self.task_config['exploration_primitives_desc']}"
        )
        observation_history: List[dict] = []

        pos, ori = self.robot.get_position_orientation()
        self.controller._anchored_pos = pos.clone()
        self.controller._anchored_ori = ori.clone()
        self.controller._tracking_object = None

        prev_image_path = self._capture_image("phase0_init")
        error_feedback = None

        for step in range(self.max_exploration_steps):
            self.step_count += 1
            self._log(f"\n[Phase 0 - Step {self.step_count}]")

            # Build step prompt with history
            lines = []
            if observation_history:
                lines.extend(self._format_history(observation_history, "Observation History"))
                lines.append("")
            if error_feedback:
                lines.append(f"\u26a0 {error_feedback}\n")
            lines.append("What do you want to observe next?")
            step_prompt = "\n".join(lines)

            response = self._call_llm(system_prompt, step_prompt, prev_image_path)
            self._log(f"  [LLM Response] {response}")
            thought, action_name, action_arg = self._parse_response(response)
            self._log(f"  Thought: {thought}")
            self._log(f"  Action: {action_name}[{action_arg}]")

            step_log = {
                "phase": 0, "step": self.step_count,
                "prompt": {"system": system_prompt, "user": step_prompt, "image": prev_image_path},
                "llm_response": response,
                "parsed": {"thought": thought, "action_name": action_name, "action_arg": action_arg},
            }

            if action_name in ("DONE_OBSERVING", "DONE_EXPLORING"):
                step_log["execution"] = {"status": "DONE_OBSERVING"}
                self._save_step(step_log)
                break

            if action_name is None:
                error_feedback = "Could not parse. Use: Action: ACTION_NAME[arg]"
                step_log["execution"] = {"status": "PARSE_ERROR"}
                self._save_step(step_log)
                continue

            error_feedback = None
            feedback, new_image = self._execute_exploration(action_name, action_arg)
            if new_image:
                prev_image_path = new_image

            observation_history.append({
                "thought": thought,
                "action": f"{action_name}[{action_arg or ''}]",
                "feedback": feedback or "(image only)",
            })
            self._log(f"  Feedback: {feedback}")
            step_log["execution"] = {"status": "SUCCESS", "feedback": feedback}
            self._save_step(step_log)

        return {
            "exploration_history": observation_history,
            "last_image": prev_image_path,
        }

    # ==================================================================
    # Phase 1 — Initial Scenario Prediction (verbal)
    # ==================================================================
    def _run_phase1(self, phase0_result: dict) -> dict:
        """SF Prediction 1: Initial scenario prediction (verbal, structured)."""
        self._log("\n" + "=" * 60)
        self._log("SF PREDICTION 1 — Initial Scenario Prediction")
        self._log("=" * 60)

        system_prompt = self.task_config.get("phase1_system_prompt", "").format(
            instruction=self.task_config["instruction"],
            robot_rules=self.task_config.get("robot_rules", ""),
        )
        history = phase0_result.get("exploration_history", [])
        user_lines = self._format_history(history, "Your Observation Findings (Phase 0)")
        user_lines.append("")
        user_lines.append(self.task_config.get("phase1_user_prompt", ""))
        user_prompt = "\n".join(user_lines)

        response = self._call_llm(system_prompt, user_prompt, phase0_result.get("last_image"))
        self._log(f"  SF Prediction 1 response:\n{response}")

        self._save_step({
            "phase": "sf_prediction1", "step": "prediction",
            "prompt": {"system": system_prompt, "user": user_prompt, "image": phase0_result.get("last_image")},
            "llm_response": response,
        })

        return {"prediction_text": response, "last_image": phase0_result.get("last_image")}

    # ==================================================================
    # Phase 2 — Rollout (sim.save/restore)
    # ==================================================================
    def _run_phase2(self, phase0_result: dict, phase1_result: dict) -> dict:
        """Phase 2: Investigation — irreversible, no save/restore."""
        self._log("\n" + "=" * 60)
        self._log("PHASE 2 — Investigation (irreversible)")
        self._log("=" * 60)

        # NO sim.save/restore — actions permanently change the environment.

        system_prompt = self.task_config.get("rollout_system_prompt", "").format(
            instruction=self.task_config["instruction"],
            robot_rules=self.task_config.get("robot_rules", ""),
        )
        investigation_history: List[dict] = []
        prev_image_path = phase0_result.get("last_image")
        error_feedback = None
        max_steps = self.task_config.get("rollout_max_steps", 4)
        allowed_actions = set(self.task_config.get(
            "rollout_allowed_actions", ["NAVIGATE_TO", "OPEN", "CLOSE", "TOUCH"]
        ))

        # Build context from Phase 0 + SF Prediction 1
        phase0_context = self._format_history(
            phase0_result.get("exploration_history", []),
            "Your Observation Findings (Phase 0)"
        )
        sf_pred1_context = [
            "",
            "=== Your Predictions (SF Prediction 1) ===",
            phase1_result.get("prediction_text", ""),
            "",
        ]

        for step in range(max_steps):
            self.step_count += 1
            self._log(f"\n[Phase 2 Investigation - Step {self.step_count}] (time_step={self.time_system.time_step})")

            lines = []
            lines.extend(phase0_context)
            lines.extend(sf_pred1_context)
            if investigation_history:
                lines.extend(self._format_history(investigation_history, "Investigation History"))
                lines.append("")
            # Time budget info
            steps_used = len(investigation_history)
            remaining_exec = self.task_config["time_system"]["max_steps"] - self.time_system.time_step
            minutes_elapsed = self.time_system.time_step * self.task_config["time_system"].get("step_duration_minutes", 5)
            lines.append(
                f"Current time: Step {steps_used + 1} of investigation "
                f"({steps_used} steps used of {max_steps} maximum. "
                f"{minutes_elapsed} minutes elapsed. "
                f"{remaining_exec} execution steps remaining.)"
            )
            if error_feedback:
                lines.append(f"\n\u26a0 {error_feedback}")
            lines.append("\nWhat do you want to investigate next?")
            step_prompt = "\n".join(lines)

            response = self._call_llm(system_prompt, step_prompt, prev_image_path)
            self._log(f"  [LLM Response] {response}")
            thought, action_name, action_arg = self._parse_response(response)
            self._log(f"  Thought: {thought}")
            self._log(f"  Action: {action_name}[{action_arg}]")

            step_log = {
                "phase": 2, "step": self.step_count,
                "time_step": self.time_system.time_step,
                "prompt": {"system": system_prompt, "user": step_prompt, "image": prev_image_path},
                "llm_response": response,
                "parsed": {"thought": thought, "action_name": action_name, "action_arg": action_arg},
            }

            if action_name in ("DONE_INVESTIGATING", "DONE_ROLLOUT", "DONE_EXPLORING", "DONE"):
                step_log["execution"] = {"status": "DONE_INVESTIGATING"}
                self._save_step(step_log)
                break

            if action_name is None:
                error_feedback = "Could not parse. Use: Action: ACTION_NAME[arg]"
                step_log["execution"] = {"status": "PARSE_ERROR"}
                self._save_step(step_log)
                continue

            if action_name not in allowed_actions:
                error_feedback = (
                    f"{action_name} is not allowed during investigation. "
                    f"Allowed: {sorted(allowed_actions)}"
                )
                step_log["execution"] = {"status": "BLOCKED"}
                self._save_step(step_log)
                continue

            error_feedback = None

            # Execute action FIRST (at current time_step)
            feedback, new_image = self._execute_rollout_action(action_name, action_arg, {})

            # THEN advance time (action consumes 1 step)
            events = self.time_system.advance_time()
            if events.get("power_restored"):
                feedback += "\n\u26a1 Power has been restored!"
            if new_image:
                prev_image_path = new_image

            investigation_history.append({
                "thought": thought,
                "action": f"{action_name}[{action_arg or ''}]",
                "feedback": feedback,
            })
            self._log(f"  Feedback: {feedback}")
            step_log["execution"] = {"status": "SUCCESS", "feedback": feedback}
            self._save_step(step_log)

        self._log(f"\n  Investigation complete. time_step={self.time_system.time_step}")

        return {
            "rollout_history": investigation_history,
            "last_image": prev_image_path,
        }

    def _execute_rollout_action(
        self, action_name: str, action_arg: Optional[str], events: dict
    ) -> Tuple[str, Optional[str]]:
        """Execute action during Phase 2 rollout.

        Same symbolic-first approach as Phase 4.
        Physics is best-effort for camera rendering only.
        """
        label = f"phase2_step{self.step_count:03d}_after"
        feedback_parts = []

        if events.get("power_restored"):
            feedback_parts.append("⚡ Power has been restored!")

        if action_name == "OPEN":
            if action_arg and "oven" in action_arg.lower():
                self.time_system.open_oven()
                feedback_parts.append("Oven door opened.")
            elif action_arg and "fridge" in action_arg.lower():
                self.time_system.open_fridge()
                feedback_parts.append("Fridge door opened.")
            self._try_physics("OPEN", action_arg)
            return "\n".join(feedback_parts), self._capture_image(label)

        if action_name == "CLOSE":
            if action_arg and "oven" in action_arg.lower():
                self.time_system.close_oven()
                feedback_parts.append("Oven door closed.")
            elif action_arg and "fridge" in action_arg.lower():
                self.time_system.close_fridge()
                feedback_parts.append("Fridge door closed.")
            self._try_physics("CLOSE", action_arg)
            return "\n".join(feedback_parts), self._capture_image(label)

        if action_name == "TOUCH":
            sensor = self.time_system.get_observable_state(action_arg or "")
            feedback_parts.append(sensor)
            return "\n".join(feedback_parts), None

        if action_name == "NAVIGATE_TO":
            self._navigate(action_arg)
            return "\n".join(feedback_parts) if feedback_parts else "Navigated.", self._capture_image(label)

        if action_name == "LOOK_CLOSER":
            self._navigate(action_arg)
            return "\n".join(feedback_parts) if feedback_parts else "Observed.", self._capture_image(label)

        return "Action completed.", None

    # ==================================================================
    # Phase 3 — Extended Prediction (SF core)
    # ==================================================================
    def _run_phase3(self, phase0_result: dict, phase1_result: dict, phase2_result: dict) -> dict:
        """SF Prediction 2: Extended prediction + 3 execution plans."""
        self._log("\n" + "=" * 60)
        self._log("SF PREDICTION 2 — Extended Scenario Prediction (SF Core)")
        self._log("=" * 60)

        system_prompt = self.task_config.get("phase3_system_prompt", "").format(
            instruction=self.task_config["instruction"],
            robot_rules=self.task_config.get("robot_rules", ""),
        )

        user_lines = []
        # Phase 0 findings with Thoughts
        user_lines.extend(self._format_history(
            phase0_result.get("exploration_history", []),
            "Your Observation Findings (Phase 0)"
        ))
        user_lines.append("")

        # SF Prediction 1 predictions
        user_lines.append("=== Your Earlier Predictions (SF Prediction 1) ===")
        user_lines.append(phase1_result.get("prediction_text", ""))
        user_lines.append("")

        # Phase 2 investigation results with Thoughts
        user_lines.extend(self._format_history(
            phase2_result.get("rollout_history", []),
            "Investigation Results (Phase 2)"
        ))
        user_lines.append("")

        # Current state + time budget
        steps_used = self.time_system.time_step
        max_steps = self.task_config["time_system"]["max_steps"]
        remaining = max_steps - steps_used
        duration = self.task_config["time_system"].get("step_duration_minutes", 5)
        minutes_used = steps_used * duration
        user_lines.append(
            f"Current state: Investigation used {steps_used} steps ({minutes_used} minutes)."
        )
        user_lines.append(
            f"{remaining} execution steps remaining (= {remaining * duration} minutes)."
        )
        user_lines.append("")

        # SF Prediction 2 prompt with dynamic available objects + remaining steps
        available_objs = self._get_available_objects_inline()
        prompt_template = self.task_config.get("phase3_user_prompt", "")
        prompt = prompt_template.format(
            available_objects=f"Available objects:\n    {available_objs}",
            remaining_info=f"You have {remaining} steps left.",
        )
        user_lines.append(prompt)
        user_prompt = "\n".join(user_lines)

        response = self._call_llm(
            system_prompt, user_prompt, phase2_result.get("last_image")
        )
        self._log(f"  SF Prediction 2 response:\n{response}")

        self._save_step({
            "phase": "sf_prediction2", "step": "extended_prediction",
            "prompt": {"system": system_prompt, "user": user_prompt, "image": phase2_result.get("last_image")},
            "llm_response": response,
        })

        return {"prediction_text": response, "last_image": phase2_result.get("last_image")}

    def _get_available_objects_inline(self) -> str:
        """Comma-separated list of key scene objects for plan prompts.

        Includes both movable objects and key fixed objects (oven, fridge, countertop)
        that the agent needs to reference in OPEN/CLOSE/PLACE actions.
        """
        names = []
        # Key fixed objects the agent needs to interact with
        key_fixed_patterns = ["oven", "fridge", "countertop"]
        for obj in self.env.scene.objects:
            if not obj.fixed_base:
                names.append(obj.name)
            else:
                for pattern in key_fixed_patterns:
                    if pattern in obj.name.lower():
                        names.append(obj.name)
                        break
        return ", ".join(sorted(names)) if names else "(no objects)"

    # ==================================================================
    # Phase 4 — Mechanical Plan Execution (no LLM calls)
    # ==================================================================
    def _parse_plans(self, text: str) -> Tuple[List[dict], Optional[List[str]]]:
        """Parse execution plans from SF Prediction 2 output.

        Supports Plan A through E (up to 5 plans).
        """
        plans = []

        # Strip markdown bold markers for easier parsing
        clean = re.sub(r'\*\*', '', text)

        # Split by "Plan [A-E]:" headers
        plan_blocks = re.split(r'(?=Plan\s+[A-E]:)', clean)
        for block in plan_blocks:
            header = re.match(r'Plan\s+([A-E]):\s*["\']?(.+?)["\']?\s*\n', block)
            if not header:
                continue
            plan_id = header.group(1)
            plan_name = header.group(2).strip().rstrip('"\'*')

            # Extract action steps — flexible format:
            #   "Step 1: ACTION[args]"  or  "Step 1: ACTION[args]"
            steps = []
            for step_match in re.finditer(r'Step\s+\d+:\s*(\w+)\[([^\]]*)\]', block):
                steps.append({
                    "action": step_match.group(1),
                    "arg": step_match.group(2).strip() or None,
                })

            if steps:  # only add plans that have parseable steps
                plans.append({
                    "id": plan_id,
                    "name": plan_name,
                    "steps": steps,
                    "raw": block.strip(),
                })

        # Parse ranking — flexible: 3 to 5 entries
        ranking = None
        rank_match = re.search(
            r'RANKING:\s*([A-E])\s*>\s*([A-E])\s*>\s*([A-E])'
            r'(?:\s*>\s*([A-E]))?'
            r'(?:\s*>\s*([A-E]))?',
            text,
        )
        if rank_match:
            ranking = [g for g in rank_match.groups() if g is not None]

        # Fallback: if no ranking parsed, use plan order
        if ranking is None and plans:
            ranking = [p["id"] for p in plans]

        return plans, ranking

    def _run_phase4(
        self, phase2_result: dict, sf_pred2_result: dict
    ) -> dict:
        """Phase 4: Mechanically execute each plan. No LLM calls."""
        self._log("\n" + "=" * 60)
        self._log("PHASE 4 \u2014 One-shot Plan Execution (mechanical)")
        self._log("=" * 60)

        prediction_text = sf_pred2_result.get("prediction_text", "")
        plans, ranking = self._parse_plans(prediction_text)

        if not plans:
            self._log("  ERROR: No plans could be parsed from SF Prediction 2!")
            return {"plans": [], "ranking": None, "plan_results": [], "error": "no_plans_parsed"}

        self._log(f"  Parsed {len(plans)} plans: {[p['id'] for p in plans]}")
        self._log(f"  Ranking: {ranking}")
        for p in plans:
            self._log(f"    Plan {p['id']} ({p['name']}): {len(p['steps'])} steps")

        # Save post-investigation state for plan execution
        self._log("  Saving post-investigation state...")
        self._sim_snapshot = og.sim.save(json_paths=None, as_dict=True)
        self.time_system.save_state()

        plan_results = []
        execution_order = ranking if ranking else [p["id"] for p in plans]

        for plan_id in execution_order:
            plan = next((p for p in plans if p["id"] == plan_id), None)
            if plan is None:
                self._log(f"  WARNING: Plan {plan_id} not found, skipping")
                continue

            self._log(f"\n  {'=' * 50}")
            self._log(f"  Executing Plan {plan_id}: {plan['name']}")
            self._log(f"  {'=' * 50}")

            # Restore to post-investigation state (symbolic load_state only — skip
            # full og.sim.restore which calls dump_state and can crash on NaN objects)
            from omnigibson.utils.python_utils import recursively_convert_to_torch
            for scene, scene_data in zip(og.sim.scenes, self._sim_snapshot):
                state = recursively_convert_to_torch(scene_data["state"])
                scene.load_state(state, serialized=False)
            self.time_system.restore_state()
            self._log(f"  Restored to post-investigation state (time_step={self.time_system.time_step})")

            step_results = []
            max_time = self.task_config["time_system"]["max_steps"]

            for i, step in enumerate(plan["steps"]):
                action_name = step["action"]
                action_arg = step["arg"]
                self.step_count += 1

                self._log(f"    Step {i + 1}: {action_name}[{action_arg or ''}] (time_step={self.time_system.time_step})")

                # Check time budget
                if self.time_system.time_step >= max_time:
                    self._log(f"    TIME EXHAUSTED at step {i + 1}")
                    step_results.append({
                        "action": f"{action_name}[{action_arg or ''}]",
                        "result": "TIME_EXHAUSTED: No steps remaining.",
                        "time_step": self.time_system.time_step,
                    })
                    break

                # Execute action
                result_text, new_image = self._execute_phase4_action(action_name, action_arg)

                # Advance time
                events = self.time_system.advance_time()
                if events.get("power_restored"):
                    result_text += "\n\u26a1 The power has been restored!"
                    self._log(f"    \u2605 POWER RESTORED!")

                self._log(f"    Result: {result_text}")
                self._log(f"    State: {repr(self.time_system)}")

                step_results.append({
                    "action": f"{action_name}[{action_arg or ''}]",
                    "result": result_text,
                    "time_step": self.time_system.time_step,
                    "time_system": repr(self.time_system),
                })

                self._save_step({
                    "phase": 4, "plan": plan_id, "plan_step": i + 1,
                    "step": self.step_count,
                    "time_step": self.time_system.time_step,
                    "action": f"{action_name}[{action_arg or ''}]",
                    "result": result_text,
                })

            # Score this plan
            score = self.time_system.compute_score()
            self._log(f"\n  Plan {plan_id} score: {score}")

            plan_results.append({
                "plan_id": plan_id,
                "plan_name": plan["name"],
                "steps_executed": step_results,
                "score": score,
                "time_steps_used": self.time_system.time_step,
            })

        return {
            "plans": [{"id": p["id"], "name": p["name"], "num_steps": len(p["steps"])} for p in plans],
            "ranking": ranking,
            "plan_results": plan_results,
        }

    def _execute_phase4_action(
        self, action_name: str, action_arg: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """Execute action during Phase 4.

        All judgements are SYMBOLIC (time_system decides outcomes).
        OmniGibson physics is best-effort for camera rendering only.
        If physics fails, symbolic result still stands.
        """
        label = f"phase4_step{self.step_count:03d}_after"

        # WAIT: just time passes
        if action_name == "WAIT":
            og.sim.step()  # 1 render for camera
            return "You waited. 5 minutes passed.", self._capture_image(label)

        # TOUCH: sensor from time_system (no physics needed)
        if action_name == "TOUCH":
            sensor = self.time_system.get_observable_state(action_arg or "")
            return sensor, None

        # LOOK_CLOSER: zoom camera on target (best-effort rendering)
        if action_name == "LOOK_CLOSER":
            self._navigate(action_arg)
            return "Observed.", self._capture_image(label)

        # OPEN: symbolic state change + best-effort physics for rendering
        if action_name == "OPEN":
            if action_arg and "oven" in action_arg.lower():
                self.time_system.open_oven()
            elif action_arg and "fridge" in action_arg.lower():
                self.time_system.open_fridge()
            self._try_physics("OPEN", action_arg)
            return "Door opened.", self._capture_image(label)

        # CLOSE: symbolic state change + best-effort physics
        if action_name == "CLOSE":
            if action_arg and "oven" in action_arg.lower():
                self.time_system.close_oven()
            elif action_arg and "fridge" in action_arg.lower():
                self.time_system.close_fridge()
            self._try_physics("CLOSE", action_arg)
            return "Door closed.", self._capture_image(label)

        # GRASP: symbolic tracking + best-effort physics
        if action_name == "GRASP":
            if action_arg and ("casserole" in action_arg.lower() or "cake" in action_arg.lower()):
                if self.time_system.cake_in_oven:
                    self.time_system.remove_cake_from_oven()
            if action_arg and "cream" in action_arg.lower():
                if self.time_system.cream_in_fridge:
                    self.time_system.remove_cream_from_fridge()
            self._try_physics("GRASP", action_arg)
            return "Grasped.", self._capture_image(label)

        # RELEASE / PLACE_ON_TOP / PLACE_INSIDE: best-effort physics
        if action_name in ("RELEASE", "PLACE_ON_TOP", "PLACE_INSIDE"):
            self._try_physics(action_name, action_arg)
            return "Done.", self._capture_image(label)

        # NAVIGATE_TO: teleport (always works) + image
        if action_name == "NAVIGATE_TO":
            self._navigate(action_arg)
            return "Navigated.", self._capture_image(label)

        # NEW_ACTION: dispatch to time_system handlers
        if action_name == "NEW_ACTION":
            return self._execute_sf_new_action(action_arg)

        # Direct custom action names (e.g., APPLY_CREAM[...] without NEW_ACTION wrapper)
        # Treat as NEW_ACTION with the action name as the label
        _DIRECT_ACTIONS = (
            "APPLY_CREAM", "APPLY_CHOCOLATE", "PREPARE_DECORATION", "TURN_ON_OVEN",
            "WASH_WHISK", "WHIP_CREAM", "POUR_HOT_WATER", "MELT_CHOCOLATE",
            "RETRIEVE_PLATTER", "USE_PLATTER",
        )
        if action_name in _DIRECT_ACTIONS:
            synthetic_arg = f"{action_name}, {action_arg}" if action_arg else action_name
            return self._execute_sf_new_action(synthetic_arg)

        return f"Unknown action: {action_name}", None

    def _try_physics(self, action_name: str, action_arg: Optional[str]):
        """Best-effort OmniGibson physics execution for rendering.

        If it fails, we log and continue — symbolic state is authoritative.
        """
        try:
            err = self._execute_base_action(action_name, action_arg)
            if err:
                self._log(f"    [physics] {action_name} soft-failed: {err} (symbolic state unaffected)")
        except Exception as e:
            self._log(f"    [physics] {action_name} exception: {e} (symbolic state unaffected)")

    def _navigate(self, action_arg: Optional[str]):
        """Teleport robot to face target. Always succeeds."""
        nav_targets = self.task_config.get("exploration_nav_targets", {})
        nav_tracking = self.task_config.get("exploration_nav_tracking", {})
        target_key = ", ".join(p.strip() for p in (action_arg or "").split(","))

        # Try task nav_targets first, then direct scene lookup
        nav_obj_name = nav_targets.get(target_key)
        if not nav_obj_name:
            nav_obj_name = action_arg

        track_obj_name = nav_tracking.get(target_key)
        if nav_obj_name:
            nav_obj = self._get_scene_object(nav_obj_name)
            track_obj = self._get_scene_object(track_obj_name) if track_obj_name else None
            if nav_obj:
                try:
                    self._teleport_to_face(nav_obj, tracking_obj=track_obj)
                except Exception as e:
                    self._log(f"    [nav] Teleport failed: {e}")

    def _execute_sf_new_action(self, action_arg: Optional[str]) -> Tuple[str, Optional[str]]:
        """Execute NEW_ACTION via time_system handlers."""
        parts = [p.strip() for p in (action_arg or "").split(",")]
        action_label = parts[0].lower() if len(parts) > 0 else ""
        tool_name = parts[1].lower() if len(parts) > 1 else ""
        target_name = parts[2].lower() if len(parts) > 2 else ""

        self._log(f"    [new_action] label={action_label}, tool={tool_name}, target={target_name}")

        # Match against handlers in task_config
        handlers = self.task_config.get("new_action_handlers", {})
        for key, handler in handlers.items():
            key_tool, key_target, key_context = key
            tool_match = key_tool.lower() in tool_name or tool_name in key_tool.lower()
            target_match = key_target.lower() in target_name or target_name in key_target.lower()
            context_match = key_context.lower() in action_label or action_label in key_context.lower()

            if tool_match and (target_match or context_match):
                handler_fn = handler.get("handler_fn")
                if handler_fn and hasattr(self.time_system, handler_fn):
                    result = getattr(self.time_system, handler_fn)()
                    if isinstance(result, tuple):
                        outcome, msg = result
                    else:
                        outcome, msg = "SUCCESS" if "SUCCESS" in str(result) else "FAILURE", str(result)
                    self._log(f"    [new_action] {handler_fn}() → {outcome}: {msg}")
                    new_image = self._capture_image(f"phase4_step{self.step_count:03d}_after")
                    return f"{outcome}: {msg}", new_image
                else:
                    outcome = handler.get("outcome", "FAILURE")
                    msg = handler.get("aux_text", "")
                    return f"{outcome}: {msg}", None

        self._log(f"    [new_action] NO HANDLER MATCHED")
        return "FAILURE: No handler for this action.", None

    def _execute_base_action(self, action_name: str, action_arg: Optional[str]) -> Optional[str]:
        """Execute OmniGibson base action. Returns error string or None."""
        primitive = _ACTION_PRIMITIVE_MAP.get(action_name)
        if primitive is None:
            return f"Unknown base action: {action_name}"

        objs = []
        if action_arg:
            for part in action_arg.split(","):
                part = part.strip()
                if not part:
                    continue
                obj = self._resolve_obj(part)
                if obj is None:
                    return f"Object '{part}' not found."
                objs.append(obj)

        try:
            ctrl_gen = self.controller.apply_ref(primitive, *objs)
            for action in ctrl_gen:
                self.env.step(action)
            return None
        except (ActionPrimitiveError, ActionPrimitiveErrorGroup) as e:
            return str(e).split(". Additional info:")[0][:300]
        except Exception as e:
            return f"{type(e).__name__}: {str(e)[:200]}"

    # ==================================================================
    # Helpers
    # ==================================================================
    def _get_available_objects_text(self) -> str:
        lines = ["=== Available Objects (use these exact names) ==="]
        for obj in self.env.scene.objects:
            if not obj.fixed_base:  # non-fixed objects
                lines.append(f"  {obj.name}")
        return "\n".join(lines)

    def _get_exploration_summary(self, phase0_result: dict) -> str:
        lines = ["=== Exploration Summary (Phase 0) ==="]
        for entry in phase0_result.get("exploration_history", []):
            lines.append(f"  {entry['action']} → {entry['feedback']}")
        return "\n".join(lines)

    # ==================================================================
    # Pause — show LLM plan before Phase 4 execution
    # ==================================================================
    def _pause_and_show_plan(
        self,
        phase0_result: dict,
        phase1_result: dict,
        phase2_result: dict,
        phase3_result: dict,
    ):
        """Print all LLM outputs and parsed plans, pause before Phase 4."""
        sep = "=" * 70

        self._log(f"\n{sep}")
        self._log("  PLAN REVIEW \u2014 Pausing before Phase 4 Execution")
        self._log(sep)

        # Phase 0: Observation history
        self._log(f"\n{'─' * 50}")
        self._log("  Phase 0: Observation Findings")
        self._log(f"{'─' * 50}")
        for i, entry in enumerate(phase0_result.get("exploration_history", []), 1):
            self._log(f"  Step {i}: {entry['action']}")
            if entry.get("thought"):
                self._log(f"    Thought: {entry['thought']}")
            self._log(f"    Result: {entry['feedback']}")

        # SF Prediction 1
        self._log(f"\n{'─' * 50}")
        self._log("  SF Prediction 1: Initial Scenarios")
        self._log(f"{'─' * 50}")
        self._log(phase1_result.get("prediction_text", "(empty)"))

        # Phase 2: Investigation
        self._log(f"\n{'─' * 50}")
        self._log("  Phase 2: Investigation Results")
        self._log(f"{'─' * 50}")
        for i, entry in enumerate(phase2_result.get("rollout_history", []), 1):
            self._log(f"  Step {i}: {entry['action']}")
            if entry.get("thought"):
                self._log(f"    Thought: {entry['thought']}")
            self._log(f"    Result: {entry['feedback']}")

        # SF Prediction 2: Scenarios + Plans
        self._log(f"\n{'─' * 50}")
        self._log("  SF Prediction 2: Updated Scenarios & Execution Plans")
        self._log(f"{'─' * 50}")
        prediction_text = phase3_result.get("prediction_text", "(empty)")
        self._log(prediction_text)

        # Parse and display plans summary
        plans, ranking = self._parse_plans(prediction_text)
        if plans:
            self._log(f"\n{'─' * 50}")
            self._log("  Parsed Plans Summary")
            self._log(f"{'─' * 50}")
            for p in plans:
                self._log(f"  Plan {p['id']}: {p['name']} ({len(p['steps'])} steps)")
                for j, s in enumerate(p["steps"], 1):
                    self._log(f"    Step {j}: {s['action']}[{s['arg'] or ''}]")
            if ranking:
                self._log(f"\n  Execution order (ranking): {' > '.join(ranking)}")

        # Time system state
        self._log(f"\n{'─' * 50}")
        self._log("  Current Time System State")
        self._log(f"{'─' * 50}")
        self._log(f"  {repr(self.time_system)}")
        self._log(f"  {self.time_system.get_time_info()}")

        self._log(f"\n{sep}")
        self._log("  Phase 4 will now execute each plan mechanically (no LLM calls).")
        self._log(sep)

    # ==================================================================
    # Phase 5 — System Verification (agent unaware)
    # ==================================================================
    def _run_phase5(self, phase1_result: dict, phase3_result: dict) -> dict:
        """Phase 5: Verify agent predictions against sim ground truth.

        This is a placeholder — full implementation requires prediction parsing
        and automated sim re-runs. For now, returns the raw prediction texts
        for manual evaluation.
        """
        self._log("\n" + "=" * 60)
        self._log("PHASE 5 — System Verification (placeholder)")
        self._log("=" * 60)

        return {
            "phase1_predictions": phase1_result.get("prediction_text", ""),
            "phase3_predictions": phase3_result.get("prediction_text", ""),
            "verification_status": "manual_required",
        }

    # ==================================================================
    # Main entry point
    # ==================================================================
    def run(self) -> dict:
        """Run the 5-phase SF evaluation pipeline."""
        run_start = time.time()
        self.llm.reset()

        self._log("=" * 60)
        self._log("SF Planner — Scenario Flexibility Evaluation")
        self._log(f"Task: {self.task_config['task_name']}")
        self._log(f"Instruction: {self.task_config['instruction']}")
        self._log("=" * 60)

        # Settle objects
        self._log("Settling objects (10 sim steps)...")
        for _ in range(10):
            og.sim.step()

        # --- Phase 0: Observation ---
        phase0_result = self._run_phase0()

        # --- SF Prediction 1: Initial Scenario Prediction ---
        phase1_result = self._run_phase1(phase0_result)

        # --- Phase 2: Investigation (irreversible) ---
        phase2_result = self._run_phase2(phase0_result, phase1_result)

        # --- SF Prediction 2: Extended Prediction + 3 Plans ---
        phase3_result = self._run_phase3(phase0_result, phase1_result, phase2_result)

        # --- Review LLM Plans before Execution ---
        self._pause_and_show_plan(phase0_result, phase1_result, phase2_result, phase3_result)

        # --- Phase 4: Mechanical Plan Execution ---
        phase4_result = self._run_phase4(phase2_result, phase3_result)

        # --- Phase 5: Verification ---
        phase5_result = self._run_phase5(phase1_result, phase3_result)

        # Combine results
        result = {
            "task_name": self.task_config["task_name"],
            "phase0": phase0_result,
            "sf_prediction1": phase1_result,
            "phase2": phase2_result,
            "sf_prediction2": phase3_result,
            "phase4": phase4_result,
            "phase5": phase5_result,
            "time_system_final": repr(self.time_system),
            "total_steps": self.step_count,
            "total_time_seconds": time.time() - run_start,
        }
        self._save_experiment(result)
        return result
