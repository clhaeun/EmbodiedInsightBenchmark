"""CATS (Context-Adaptive Tool Selection) Planner for OmniGibson.

Four-stage planner that evaluates LLM agent's Context Adaptability:
  Stage 1: Exploration — discover critical context features via symbolic primitives
  Stage 2: Demo Observation & Comparison — observe demos, compare with current situation
  Tool Selection Step: explicit tool selection + execution plan (with NEW_ACTION)
  Stage 3: Adaptive Execution — execute plan with physical grounding in IsaacSim

Key constraint: One-Shot CA Tool Selection
  - Once the agent GRASPs a CA tool candidate, that tool is locked in.
  - Remaining CA tool candidates become unavailable.
  - This prevents trial-and-error and ensures success rate purely reflects CA.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
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
# from omnigibson.envs.common.eib_camera import CameraMixin  # original
from omnigibson.envs.common.syw_camera import CameraMixin
from omnigibson.llm_agent.llm import create_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Camera helper (reused from planner.py)
# ---------------------------------------------------------------------------
class _CameraHelper(CameraMixin):
    """Lightweight CameraMixin wrapper for the CATS planner."""

    def __init__(self, env, controller):
        self.robot = env.robots[0]
        self.scene = env.scene
        self.primitives = controller
        self.__init_camera__()


# ---------------------------------------------------------------------------
# CATS Planner
# ---------------------------------------------------------------------------
class CATSPlanner:
    """Four-stage CATS planner for Context Adaptability evaluation.

    Flow:
        Stage 1  Exploration           → Metacognitive Probe 1
        Stage 2  Demo Observation      → Metacognitive Probe 2
        Tool Selection Step            → CA tool committed
        Stage 3  Adaptive Execution    → Metacognitive Probe 3 → Success/Failure
    """

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

        # Direct camera flag (for viewer_camera bypass)
        self._direct_camera_active = False

        # --- One-Shot CA Tool Selection state ---
        self._ca_tool_names: List[str] = task_config.get("ca_tool_names", [])
        self._committed_tool: Optional[str] = None  # locked once agent GRASPs a CA tool

        # --- Demo preparation state ---
        self._prepared_demos: List[str] = []
        self._num_original_demos: int = 0

        # Logging
        self.step_logs: List[dict] = []
        self.step_count = 0
        self._log_file = None
        self._setup_file_logging()

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _setup_file_logging(self):
        if self.experiment_dir:
            os.makedirs(self.experiment_dir, exist_ok=True)
            self._log_file = open(
                os.path.join(self.experiment_dir, "run.log"), "w"
            )

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
        if self._log_file:
            self._log_file.write(msg + "\n")
            self._log_file.flush()

    # ------------------------------------------------------------------
    # Scene object helpers
    # ------------------------------------------------------------------
    def _get_scene_object(self, name: str):
        """Find a scene object by name. Tries exact match, then fuzzy."""
        # Exact match
        for obj in self.env.scene.objects:
            if obj.name == name:
                return obj
        # Fuzzy: compare base name (strip trailing _NNN suffix)
        name_lower = name.lower().replace(" ", "_")
        for obj in self.env.scene.objects:
            obj_base = re.sub(r"_\d+$", "", obj.name).lower()
            if name_lower == obj_base or name_lower in obj_base or obj_base in name_lower:
                self._log(f"    [resolve] Fuzzy matched '{name}' → {obj.name}")
                return obj
        return None

    def _teleport_to_face(self, target_obj, tracking_obj=None):
        """Teleport robot 1m in front of target_obj, facing it.

        Mimics _navigate_to_obj() but without apply_ref, so no unintended
        side effects. Sets _tracking_object so camera system auto-aims.

        Args:
            target_obj: scene object to navigate toward (robot placed 1m away)
            tracking_obj: object for camera to focus on (default: target_obj)
        """
        target_pos = target_obj.get_position_orientation()[0]
        robot_pos = self.robot.get_position_orientation()[0]

        # Direction from robot to target (XY plane)
        delta = target_pos[:2] - robot_pos[:2]
        dist = torch.norm(delta)
        if dist < 1e-3:
            direction = torch.tensor([1.0, 0.0])
        else:
            direction = delta / dist

        # Place robot 1m away from target, facing it
        new_pos = target_pos.clone()
        new_pos[0] = new_pos[0] - direction[0] * 1.0
        new_pos[1] = new_pos[1] - direction[1] * 1.0
        new_pos[2] = robot_pos[2]  # keep current Z (floor level)

        # Compute yaw facing target
        yaw = torch.atan2(direction[1], direction[0])
        new_ori = torch.tensor([0.0, 0.0, torch.sin(yaw / 2), torch.cos(yaw / 2)])

        # Teleport robot
        self.robot.set_position_orientation(position=new_pos, orientation=new_ori)
        self.robot.keep_still()

        # Update controller state for camera system
        self.controller._anchored_pos = new_pos.clone()
        self.controller._anchored_ori = new_ori.clone()
        self.controller._tracking_object = tracking_obj if tracking_obj else target_obj

        # Settle (1 physics step)
        og.sim.step()

    def _setup_direct_camera(self, robot_pos, cam_pos, cam_look_at):
        """Place robot body away and set up viewer_camera at exact absolute position.

        Bypasses CameraMixin — uses og.sim.viewer_camera directly with
        _look_at_quat from eib_camera.py (proven to work).

        Args:
            robot_pos: [x, y, z] — robot body position (away from camera)
            cam_pos:   [x, y, z] — exact absolute camera position
            cam_look_at: [x, y, z] — point the camera looks at
        """
        # from omnigibson.envs.common.eib_camera import _look_at_quat  # original
        from omnigibson.envs.common.syw_camera import _look_at_quat

        # Move robot body out of the way
        rpos = torch.tensor(robot_pos, dtype=torch.float32)
        robot_ori = torch.tensor([0.0, 0.0, -0.707, 0.707], dtype=torch.float32)
        self.robot.set_position_orientation(position=rpos, orientation=robot_ori)
        self.robot.keep_still()
        og.sim.step()

        # Compute look-at quaternion (same function as eib_camera.py)
        cp = torch.tensor(cam_pos, dtype=torch.float32)
        ct = torch.tensor(cam_look_at, dtype=torch.float32)
        cam_ori = _look_at_quat(cp, ct)

        # Set viewer camera at exact position
        og.sim.viewer_camera.set_position_orientation(
            position=cam_pos, orientation=cam_ori.tolist()
        )

        # Render frames to settle camera
        for _ in range(10):
            og.sim.render()

        self._direct_camera_active = True

    def _capture_direct_camera(self, label: str) -> Optional[str]:
        """Capture image from viewer_camera (after _setup_direct_camera)."""
        if not self._images_dir:
            return None
        try:
            import numpy as np
            from PIL import Image as _PILImage

            for _ in range(5):
                og.sim.render()
            obs = og.sim.viewer_camera.get_obs()
            rgb = obs[0]["rgb"][:, :, :3].cpu().numpy().astype(np.uint8)
            path = os.path.join(self._images_dir, f"{label}.png")
            _PILImage.fromarray(rgb).save(path)
            self._log(f"  Image saved (direct cam): {path}")
            self._direct_camera_active = False
            return path
        except Exception as e:
            self._log(f"  [WARN] Direct camera capture failed: {e}")
            self._direct_camera_active = False
            return None

    def _capture_zoomed(self, label: str, focal_length: float = 50.0) -> Optional[str]:
        """Capture zoomed image using viewer_camera with increased focal length.

        Uses the current CameraMixin view but re-renders with higher focal length
        for a zoom-in effect. Resets focal length afterward.
        """
        if not self._camera_helper or not self._images_dir:
            return None
        try:
            import numpy as np
            from PIL import Image as _PILImage

            # First, let CameraMixin settle the head/camera as normal
            # _settle_head_for_capture only exists in eib_camera; skip for syw_camera
            if hasattr(self._camera_helper, '_settle_head_for_capture'):
                self._camera_helper._settle_head_for_capture()

            # Override focal length for zoom
            og.sim.viewer_camera.prim.GetAttribute("focalLength").Set(focal_length)

            for _ in range(10):
                og.sim.render()

            obs = og.sim.viewer_camera.get_obs()
            rgb = obs[0]["rgb"][:, :, :3].cpu().numpy().astype(np.uint8)
            path = os.path.join(self._images_dir, f"{label}.png")
            _PILImage.fromarray(rgb).save(path)
            self._log(f"  Image saved (zoom {focal_length}): {path}")

            # Reset focal length to default
            og.sim.viewer_camera.prim.GetAttribute("focalLength").Set(18.0)
            return path
        except Exception as e:
            self._log(f"  [WARN] Zoomed capture failed: {e}")
            og.sim.viewer_camera.prim.GetAttribute("focalLength").Set(18.0)
            return None

    # ------------------------------------------------------------------
    # Image capture
    # ------------------------------------------------------------------
    def _capture_image(self, label: str) -> Optional[str]:
        """Capture RGB image and return file path, or None if no camera."""
        if not self._camera_helper or not self._images_dir:
            return None
        try:
            from PIL import Image as _PILImage
            rgb = self._camera_helper.get_rgb()
            path = os.path.join(self._images_dir, f"{label}.png")
            _PILImage.fromarray(rgb).save(path)
            self._log(f"  Image saved: {path}")
            return path
        except Exception as e:
            self._log(f"  [WARN] Image capture failed: {e}")
            return None

    # ------------------------------------------------------------------
    # LLM interaction helpers
    # ------------------------------------------------------------------
    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: Optional[str] = None,
        extra_images: Optional[List[str]] = None,
    ) -> str:
        """Call LLM with system + user prompt + optional images."""
        if extra_images:
            messages = [("system", system_prompt)]
            if image_path:
                messages.append(("user", user_prompt, image_path))
            else:
                messages.append(("user", user_prompt))
            for img in extra_images:
                if os.path.exists(img) or img.startswith("http://") or img.startswith("https://"):
                    messages.append(("user", "", img))
            return self.llm.generate(messages)
        else:
            prompt = [
                ("system", system_prompt),
                ("user", user_prompt, image_path),
            ]
            return self.llm.generate(prompt)

    def _parse_response(self, response: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Parse LLM response: (thought, action_name, action_arg)."""
        thought = ""
        action_name = None
        action_arg = None

        thought_match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\Z)", response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        action_match = re.search(r"Action:\s*(\w+)\[([^\]]*)\]", response)
        if action_match:
            action_name = action_match.group(1)
            action_arg = action_match.group(2).strip() or None

        return thought, action_name, action_arg

    # ------------------------------------------------------------------
    # Robust 6-DOF JSON extraction
    # ------------------------------------------------------------------
    _6DOF_KEYS = (
        "linear_velocity", "applied_force",
        "orientation_euler_angles", "orientation",
    )

    def _extract_6dof_json(self, text: str) -> str:
        """Extract 6-DOF parameter JSON from text using multiple strategies.

        Tries in order:
          1. Standard format:  ': '{...}'  (colon + single-quoted JSON)
          2. Balanced-brace scan for any valid JSON dict containing 6-DOF keys
        Returns the JSON string, or "" if nothing found.
        """
        if not text:
            return ""

        # --- Strategy 1: colon + single-quoted JSON ---
        sq_match = re.search(r":\s*'([^']+)'", text)
        if sq_match:
            candidate = sq_match.group(1)
            if any(k in candidate for k in self._6DOF_KEYS):
                try:
                    json.loads(candidate)
                    self._log(f"    [6dof] Extracted via single-quote pattern")
                    return candidate
                except json.JSONDecodeError:
                    pass

        # --- Strategy 2: colon + double-quoted JSON (escaped inner quotes) ---
        dq_match = re.search(r':\s*"(\{.+?\})"', text)
        if dq_match:
            candidate = dq_match.group(1)
            if any(k in candidate for k in self._6DOF_KEYS):
                try:
                    json.loads(candidate)
                    self._log(f"    [6dof] Extracted via double-quote pattern")
                    return candidate
                except json.JSONDecodeError:
                    pass

        # --- Strategy 3: balanced-brace scan for valid JSON with 6-DOF keys ---
        for i, ch in enumerate(text):
            if ch != '{':
                continue
            depth = 0
            for j in range(i, min(i + 2000, len(text))):
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        if any(k in candidate for k in self._6DOF_KEYS):
                            try:
                                json.loads(candidate)
                                self._log(
                                    f"    [6dof] Extracted via brace scan: "
                                    f"{candidate[:80]}..."
                                )
                                return candidate
                            except json.JSONDecodeError:
                                pass
                        break
        return ""

    # ------------------------------------------------------------------
    # One-Shot CA Tool Selection
    # ------------------------------------------------------------------
    def _is_ca_tool(self, object_name: str) -> bool:
        """Check if an object name matches any CA tool candidate."""
        name_lower = object_name.lower()
        for tool_name in self._ca_tool_names:
            if tool_name.lower() in name_lower or name_lower in tool_name.lower():
                return True
        return False

    def _check_ca_tool_grasp(self, action_name: str, action_arg: Optional[str]) -> Optional[str]:
        """Check One-Shot constraint when GRASP is attempted.

        Returns error string if blocked, None if allowed.
        Also commits the tool if this is the first CA tool GRASP.
        """
        if action_name != "GRASP" or action_arg is None:
            return None

        if not self._is_ca_tool(action_arg):
            return None  # not a CA tool — no constraint

        if self._committed_tool is None:
            # First CA tool GRASP — commit
            self._committed_tool = action_arg
            self._log(f"  [CA] Tool committed: {action_arg}")
            return None
        elif self._committed_tool.lower() == action_arg.lower():
            return None  # re-grasping same tool is OK
        else:
            # Trying to GRASP a different CA tool — blocked
            return (
                f"This tool is no longer available. "
                f"You already committed to {self._committed_tool}."
            )

    # ------------------------------------------------------------------
    # Step logging
    # ------------------------------------------------------------------
    def _save_step(self, step_log: dict):
        """Append step log and flush to disk."""
        self.step_logs.append(step_log)
        if self.experiment_dir:
            with open(os.path.join(self.experiment_dir, "steps.json"), "w") as f:
                json.dump(self.step_logs, f, indent=2, ensure_ascii=False)

    def _build_probe_user_message(
        self,
        exploration_history=None,
        tool_selection_response=None,
        execution_history=None,
    ) -> str:
        """Build probe user message with tool candidates + full history recap."""
        lines = []

        ca_tools = self.task_config.get("ca_tool_names", [])
        if ca_tools:
            lines.append("=== Available Tools ===")
            lines.append(", ".join(ca_tools))
            lines.append("")

        if exploration_history:
            lines.append("=== Stage 1: Exploration Findings ===")
            for i, entry in enumerate(exploration_history, 1):
                lines.append(f"Step {i}:")
                lines.append(f"  Thought: {entry['thought']}")
                lines.append(f"  Action: {entry['action']}")
                fb_key = "feedback" if "feedback" in entry else "result"
                lines.append(f"  Result: {entry[fb_key]}")
            lines.append("")

        if tool_selection_response:
            lines.append("=== Analysis & Tool Selection ===")
            lines.append(tool_selection_response)
            lines.append("")

        if execution_history:
            lines.append("=== Stage 3: Execution History ===")
            for i, entry in enumerate(execution_history, 1):
                lines.append(f"Step {i}:")
                lines.append(f"  Thought: {entry['thought']}")
                lines.append(f"  Action: {entry['action']}")
                lines.append(f"  Result: {entry['result']}")
            lines.append("")

        lines.append("Please provide your answer.")
        return "\n".join(lines)

    # ==================================================================
    # MAIN ENTRY POINT
    # ==================================================================
    def run(self) -> dict:
        """Run the 4-stage CATS evaluation pipeline."""
        run_start = time.time()
        self.llm.reset()

        self._log("=" * 60)
        self._log("CATS Planner — Context-Adaptive Tool Selection")
        self._log(f"Task: {self.task_config['task_name']}")
        self._log(f"Instruction: {self.task_config['instruction']}")
        self._log(f"CA tools: {self._ca_tool_names}")
        self._log("=" * 60)

        # Settle objects
        self._log("Settling objects (10 sim steps)...")
        for _ in range(10):
            og.sim.step()

        # --- Prepare demos & Probe 0 ---
        self._prepare_demos()
        probe0_result = self._run_probe0()

        # --- Stage 1: Exploration ---
        self._log("\n" + "=" * 60)
        self._log("STAGE 1 — Exploration")
        self._log("=" * 60)
        stage1_result = self._run_stage1()

        # --- Analysis & Tool Selection (single step) ---
        self._log("\n" + "=" * 60)
        self._log("ANALYSIS & TOOL SELECTION")
        self._log("=" * 60)
        tool_selection_result = self._run_analysis_and_selection(
            stage1_result, probe0_result=probe0_result,
        )

        # --- Stage 3: Adaptive Execution ---
        # Skip Stage 3 entirely if tool selection is wrong
        if not tool_selection_result.get("tool_selection_correct"):
            self._log("\n" + "=" * 60)
            self._log("STAGE 3 — SKIPPED (wrong tool selected)")
            self._log("=" * 60)
            stage3_result = {
                "skipped": True,
                "reason": "wrong_tool_selected",
                "task_success": False,
            }
        else:
            self._log("\n" + "=" * 60)
            if self.task_config.get("stage3_action_menu"):
                self._log("STAGE 3 — Menu-based Symbolic Execution")
                self._log("=" * 60)
                stage3_result = self._run_stage3_menu(
                    tool_selection_result,
                    stage1_result=stage1_result,
                )
            else:
                self._log("STAGE 3 — Adaptive Execution")
                self._log("=" * 60)
                stage3_result = self._run_stage3(
                    tool_selection_result,
                    stage1_result=stage1_result,
                )

        # --- Combine and save ---
        result = {
            "task_name": self.task_config["task_name"],
            "probe0": probe0_result,
            "stage1": stage1_result,
            "tool_selection": tool_selection_result,
            "stage3": stage3_result,
            "committed_tool": self._committed_tool,
            "total_steps": self.step_count,
            "total_time_seconds": time.time() - run_start,
        }
        self._save_experiment(result)
        return result

    # ==================================================================
    # PROBE 0: Demo Video Comprehension
    # ==================================================================
    def _prepare_demos(self):
        """Download YouTube URLs, collect local videos, and merge all into one.

        Stores result in self._prepared_demos for Probe 0 and Stage 2.
        Sets self._num_original_demos to the actual number of demos in the
        final prepared set (e.g. 5 if 3 YouTube + 2 local were merged into 1).
        """
        demo_image_paths = self.task_config.get("demo_image_paths", [])

        youtube_urls = [
            p for p in demo_image_paths
            if p.startswith("http://") or p.startswith("https://")
        ]
        local_demos = [
            p for p in demo_image_paths
            if not (p.startswith("http://") or p.startswith("https://"))
            and os.path.exists(p)
        ]

        # Download YouTube videos
        downloaded = self._download_youtube_videos(youtube_urls, self.experiment_dir)

        # Collect all video files (local mp4s first, then downloaded)
        all_videos = [
            p for p in local_demos if p.lower().endswith(".mp4")
        ] + downloaded
        non_video_demos = [
            p for p in local_demos if not p.lower().endswith(".mp4")
        ]

        num_demos = len(all_videos) + len(non_video_demos)

        if len(all_videos) > 1:
            merged = self._merge_demo_videos(all_videos, self.experiment_dir)
            self._prepared_demos = [merged] + non_video_demos
        elif len(all_videos) == 1:
            self._prepared_demos = all_videos + non_video_demos
        else:
            self._prepared_demos = non_video_demos

        self._num_original_demos = num_demos
        self._log(f"\n[Demo Prep] {self._num_original_demos} demo(s) prepared")

    def _run_probe0(self) -> dict:
        """Probe 0: Pre-exploration demo comprehension check.

        Show the merged demo video to the LLM and ask it to identify
        and describe each individual demo within the video.
        If demo_text_descriptions is set (no video), use text-only mode.
        """
        text_descs = self.task_config.get("demo_text_descriptions")
        if not self._prepared_demos and not text_descs:
            self._log("[Probe 0] No demos available — skipping.")
            return {"skipped": True}

        # --- Text-only demo mode (no video) ---
        if text_descs and not self._prepared_demos:
            self.step_count += 1
            step_start = time.time()
            self._log("\n" + "=" * 60)
            self._log("PROBE 0 — Demo Descriptions (text-only)")
            self._log("=" * 60)

            demo_text = "\n".join(
                f"Demo {i+1}: {desc}" for i, desc in enumerate(text_descs)
            )
            system_prompt = self.task_config.get(
                "demo_system_prompt",
                "You are reading descriptions of demonstration techniques "
                "before starting a task. Each demo shows a different "
                "approach to a physical problem.",
            )
            user_prompt = (
                f"You have {len(text_descs)} demonstration descriptions:\n\n"
                f"{demo_text}\n\n"
                "For each demo, identify the key physical principle and "
                "the specific sequence of actions involved."
            )
            response = self._call_llm(system_prompt, user_prompt)
            self._log(f"  Probe 0 response:\n{response}")

            step_log = {
                "stage": 0, "step": "probe0",
                "type": "metacognitive_probe",
                "question": user_prompt, "response": response,
                "num_demos": len(text_descs),
                "duration": time.time() - step_start,
            }
            self._save_step(step_log)
            self._num_original_demos = len(text_descs)
            return {"response": response, "num_demos": len(text_descs)}

        self.step_count += 1
        step_start = time.time()

        self._log("\n" + "=" * 60)
        self._log("PROBE 0 — Demo Video Comprehension")
        self._log("=" * 60)

        system_prompt = (
            "You are observing demonstration videos before starting a task."
        )
        user_prompt = (
            f"This video contains {self._num_original_demos} demo(s). "
            f"Briefly describe what each demo is about."
        )

        response = self._call_llm(
            system_prompt,
            user_prompt,
            extra_images=self._prepared_demos,
        )

        self._log(f"  Probe 0 response:\n{response}")

        step_log = {
            "stage": 0,
            "step": "probe0",
            "type": "metacognitive_probe",
            "question": user_prompt,
            "response": response,
            "num_demos": self._num_original_demos,
            "duration": time.time() - step_start,
        }
        self._save_step(step_log)

        return {
            "response": response,
            "num_demos": self._num_original_demos,
        }

    # ==================================================================
    # STAGE 1: Exploration
    # ==================================================================
    def _build_stage1_system_prompt(self) -> str:
        robot_type = type(self.robot).__name__
        exploration_desc = self.task_config.get("exploration_primitives_desc", "")

        return (
            f"You are a {robot_type} robot agent in a household environment.\n\n"
            f"Your task: {self.task_config['instruction']}\n\n"
            "IMPORTANT: Before using any tools, you must first EXPLORE the environment "
            "to understand the situation. You do NOT know the detailed properties of "
            "the environment yet — you must discover them through physical exploration.\n\n"
            "Available exploration actions:\n"
            f"{exploration_desc}\n\n"
            "When you have gathered enough information about the environment, say:\n"
            "  Action: DONE_EXPLORING[]\n\n"
            "You must respond in the following format:\n"
            "Thought: <your reasoning about what to explore next>\n"
            "Action: <ACTION_NAME>[<argument>]\n"
        )

    def _build_stage1_step_prompt(
        self, exploration_history: List[dict], error: Optional[str] = None
    ) -> str:
        lines = []
        lines.append("=== Exploration History ===\n")

        if exploration_history:
            for i, entry in enumerate(exploration_history, 1):
                lines.append(f"  Step {i}:")
                lines.append(f"    Thought: {entry['thought']}")
                lines.append(f"    Action: {entry['action']}")
                lines.append(f"    Result: {entry['feedback']}")
            lines.append("")
        else:
            lines.append("You have not explored anything yet.\n")

        if error:
            lines.append(f"Error from previous action: {error}\n")

        lines.append("What would you like to explore next? (or DONE_EXPLORING[] if ready)")
        return "\n".join(lines)

    def _resolve_feedback_key(
        self, action_name: str, action_arg: Optional[str]
    ) -> Optional[str]:
        """Resolve exploration action to feedback key, or None if invalid."""
        feedbacks = self.task_config.get("exploration_feedbacks", {})

        # Normalize whitespace in comma-separated args
        if action_arg:
            normalized_arg = ", ".join(p.strip() for p in action_arg.split(","))
        else:
            normalized_arg = ""
        key = f"{action_name}[{normalized_arg}]"

        if key in feedbacks:
            return key

        # Try raw (no normalization)
        raw_key = f"{action_name}[{action_arg or ''}]"
        if raw_key in feedbacks:
            return raw_key

        return None

    def _execute_exploration(
        self, action_name: str, action_arg: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """Execute a symbolic exploration primitive with camera integration.

        - NAVIGATE_TO: teleport robot via apply_ref (same as existing actions),
          which updates _tracking_object + _anchored_pos/ori → camera moves.
        - LOOK_CLOSER: update _tracking_object only → camera re-aims, no movement.
        - TOUCH / PUSH / OPEN: text feedback only, no robot/camera change.

        Returns (text_feedback, new_image_path_or_None).
        """
        # Block CA tool usage during exploration
        if action_name == "GRASP" and action_arg and self._is_ca_tool(action_arg):
            return (
                "You should explore the environment first before selecting a tool.",
                None,
            )

        # Resolve feedback text
        key = self._resolve_feedback_key(action_name, action_arg)
        if key is None:
            available = [
                k for k in self.task_config.get("exploration_feedbacks", {}).keys()
                if k.startswith(action_name)
            ]
            return (
                f"'{action_arg}' is not available during exploration. "
                f"This does NOT mean the object cannot be used later — "
                f"only that you cannot examine it in this stage. "
                f"Available exploration targets for {action_name}: {available}",
                None,
            )
        feedback = self.task_config["exploration_feedbacks"][key]

        # --- NAVIGATE_TO: overhead viewpoint OR teleport_to_face ---
        if action_name == "NAVIGATE_TO":
            if action_arg:
                target_key = ", ".join(p.strip() for p in action_arg.split(","))
            else:
                target_key = ""

            # Check for direct camera viewpoint first (exact absolute position)
            direct_cam = self.task_config.get("exploration_direct_camera", {}).get(target_key)
            if direct_cam:
                try:
                    self._setup_direct_camera(
                        direct_cam["robot_pos"],
                        direct_cam["cam_pos"],
                        direct_cam["cam_look_at"],
                    )
                    self._log(
                        f"  [Nav] Direct camera: cam={direct_cam['cam_pos']}, "
                        f"look_at={direct_cam['cam_look_at']}"
                    )
                except Exception as e:
                    self._log(f"  [Nav] Direct camera setup failed: {e}")
            else:
                # Fall back to teleport_to_face (auto 1m from target)
                nav_targets = self.task_config.get("exploration_nav_targets", {})
                nav_tracking = self.task_config.get("exploration_nav_tracking", {})

                nav_obj_name = nav_targets.get(target_key)
                track_obj_name = nav_tracking.get(target_key)

                if nav_obj_name:
                    nav_obj = self._get_scene_object(nav_obj_name)
                    track_obj = (
                        self._get_scene_object(track_obj_name)
                        if track_obj_name else None
                    )
                    if nav_obj:
                        try:
                            self._teleport_to_face(nav_obj, tracking_obj=track_obj)
                            self._log(
                                f"  [Nav] Face {nav_obj_name}"
                                + (f", tracking={track_obj_name}" if track_obj_name else "")
                            )
                        except Exception as e:
                            self._log(f"  [Nav] Teleport failed: {e}")
                    else:
                        self._log(f"  [Nav] Scene object '{nav_obj_name}' not found")

            # Capture image (skip if task uses text-only exploration)
            if self.task_config.get("exploration_no_image"):
                return feedback, None
            if getattr(self, '_direct_camera_active', False):
                new_image = self._capture_direct_camera(
                    f"stage1_step{self.step_count:03d}_after"
                )
            else:
                new_image = self._capture_image(
                    f"stage1_step{self.step_count:03d}_after"
                )
            return feedback, new_image

        # --- LOOK_CLOSER: re-aim camera + zoom in ---
        if action_name == "LOOK_CLOSER":
            look_targets = self.task_config.get("exploration_look_targets", {})
            scene_obj_name = look_targets.get(action_arg)
            if scene_obj_name:
                target_obj = self._get_scene_object(scene_obj_name)
                if target_obj:
                    self.controller._tracking_object = target_obj
                    self._log(f"  [Look] Camera tracking → {scene_obj_name}")

            # Zoomed capture (skip if task uses text-only exploration)
            if self.task_config.get("exploration_no_image"):
                return feedback, None
            zoom = self.task_config.get("look_closer_focal_length", 50.0)
            new_image = self._capture_zoomed(
                f"stage1_step{self.step_count:03d}_look", focal_length=zoom
            )
            return feedback, new_image

        # --- TOUCH / PUSH / OPEN: text only, no movement, no image change ---
        return feedback, None

    def _run_stage1(self) -> dict:
        """Run Stage 1: Exploration."""
        system_prompt = self._build_stage1_system_prompt()
        exploration_history: List[dict] = []

        # Initialize camera anchors from current robot pose
        pos, ori = self.robot.get_position_orientation()
        self.controller._anchored_pos = pos.clone()
        self.controller._anchored_ori = ori.clone()
        self.controller._tracking_object = None

        prev_image_path = self._capture_image("stage1_init")
        error_feedback = None

        for step in range(self.max_exploration_steps):
            self.step_count += 1
            step_start = time.time()

            self._log(f"\n[Stage 1 - Step {self.step_count}]")

            step_prompt = self._build_stage1_step_prompt(
                exploration_history, error_feedback
            )
            response = self._call_llm(system_prompt, step_prompt, prev_image_path)
            thought, action_name, action_arg = self._parse_response(response)

            self._log(f"  Thought: {thought}")
            self._log(f"  Action: {action_name}[{action_arg}]")

            step_log = {
                "stage": 1,
                "step": self.step_count,
                "prompt": {"system": system_prompt, "user": step_prompt},
                "llm_response": response,
                "parsed": {
                    "thought": thought,
                    "action_name": action_name,
                    "action_arg": action_arg,
                },
            }

            if action_name == "DONE_EXPLORING":
                self._log("  Agent declares: DONE_EXPLORING")
                step_log["execution"] = {"status": "DONE_EXPLORING"}
                step_log["duration"] = time.time() - step_start
                self._save_step(step_log)
                break

            if action_name is None:
                error_feedback = "Could not parse your response. Use: Action: ACTION_NAME[arg]"
                step_log["execution"] = {"status": "PARSE_ERROR"}
                step_log["duration"] = time.time() - step_start
                self._save_step(step_log)
                continue

            error_feedback = None
            feedback, new_image = self._execute_exploration(action_name, action_arg)
            if new_image:
                prev_image_path = new_image

            exploration_history.append({
                "thought": thought,
                "action": f"{action_name}[{action_arg or ''}]",
                "feedback": feedback,
            })

            self._log(f"  Feedback: {feedback}")
            step_log["execution"] = {"status": "SUCCESS", "feedback": feedback}
            step_log["duration"] = time.time() - step_start
            self._save_step(step_log)

        # --- Metacognitive Probe 1 ---
        probe_text = self.task_config.get("probes", {}).get(
            "stage1",
            "Based on your exploration, what are the key features of this situation "
            "that would affect how you approach the task? "
            "What makes this situation unique or challenging?"
        )

        self._log("\n[Stage 1 — Metacognitive Probe]")
        probe_user = self._build_probe_user_message(exploration_history=exploration_history)
        probe_response = self._call_llm(probe_text, probe_user)
        self._log(f"  Probe response: {probe_response[:300]}...")

        self._save_step({
            "stage": 1,
            "step": "probe",
            "type": "metacognitive_probe",
            "question": probe_text,
            "response": probe_response,
        })

        return {
            "exploration_history": exploration_history,
            "probe_response": probe_response,
            "last_image": prev_image_path,
        }

    # ==================================================================
    # Demo video helpers
    # ==================================================================
    def _download_youtube_videos(self, urls: List[str], out_dir: str) -> List[str]:
        """Download YouTube videos and return list of local mp4 paths.

        Requires ``yt-dlp`` to be installed.
        """
        if not urls:
            return []

        tmp_dir = os.path.join(out_dir, "_demo_videos")
        os.makedirs(tmp_dir, exist_ok=True)

        downloaded: List[str] = []
        for idx, url in enumerate(urls):
            out_path = os.path.join(tmp_dir, f"demo_{idx:02d}.mp4")
            try:
                subprocess.run(
                    [
                        "yt-dlp",
                        "-f", "best[ext=mp4][height<=480]/worst[ext=mp4]/worst",
                        "--no-playlist",
                        "-o", out_path,
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True,
                )
                if os.path.exists(out_path):
                    downloaded.append(out_path)
                    self._log(f"  [demo] Downloaded {idx + 1}/{len(urls)}: {url}")
                else:
                    self._log(f"  [demo] Download produced no file: {url}")
            except Exception as e:
                self._log(f"  [demo] Download failed for {url}: {e}")

        return downloaded

    def _merge_demo_videos(self, video_paths: List[str], out_dir: str) -> str:
        """Merge multiple mp4 files (YouTube downloads + local) into one.

        Returns path to merged video. Requires ``ffmpeg``.
        Audio is always stripped.
        """
        tmp_dir = os.path.join(out_dir, "_demo_videos")
        os.makedirs(tmp_dir, exist_ok=True)

        n = len(video_paths)
        merged_path = os.path.abspath(os.path.join(out_dir, "demos_merged.mp4"))

        # Build ffmpeg concat list
        list_path = os.path.join(tmp_dir, "concat_list.txt")
        with open(list_path, "w") as f:
            for p in video_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        # Attempt 1: fast concat (stream copy, no audio)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_path,
                    "-c", "copy",
                    "-an",
                    merged_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            self._log(f"  [demo] Merged {n} videos → {merged_path}")
            return merged_path
        except Exception as e:
            self._log(f"  [demo] ffmpeg concat (copy) failed: {e}")

        # Attempt 2: re-encode with scale+pad, no audio
        try:
            inputs = " ".join(f"-i {os.path.abspath(p)}" for p in video_paths)
            scales = ";".join(
                f"[{i}:v]scale=640:480:force_original_aspect_ratio=decrease,"
                f"pad=640:480:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v{i}]"
                for i in range(n)
            )
            streams = "".join(f"[v{i}]" for i in range(n))
            filter_str = f"{scales};{streams}concat=n={n}:v=1:a=0[outv]"
            cmd = (
                f"ffmpeg -y {inputs} "
                f"-filter_complex \"{filter_str}\" "
                f"-map \"[outv]\" -an {merged_path}"
            )
            subprocess.run(cmd, shell=True, capture_output=True, timeout=300, check=True)
            self._log(f"  [demo] Merged (re-encode, no audio) {n} videos → {merged_path}")
            return merged_path
        except Exception as e2:
            self._log(f"  [demo] ffmpeg re-encode failed: {e2}")

        raise RuntimeError(
            f"Failed to merge {n} demo videos after 2 attempts. "
            f"Cannot proceed with partial demos."
        )

    # ==================================================================
    # ANALYSIS & TOOL SELECTION (single step)
    # ==================================================================
    def _run_analysis_and_selection(
        self, stage1_result: dict, probe0_result: Optional[dict] = None
    ) -> dict:
        """Combined situation analysis and tool selection (single LLM call).

        Replaces the old Stage 2 + Probe 2 + Tool Selection pipeline.
        The LLM receives all context in one shot and produces:
          - Situation analysis (perception)
          - Tool suitability reasoning (analysis)
          - Final tool selection + action plan (decision)
        """
        self.step_count += 1
        step_start = time.time()

        has_demos = (
            (bool(self._prepared_demos)
             or bool(self.task_config.get("demo_text_descriptions")))
            and probe0_result is not None
            and probe0_result.get("response")
        )
        current_image = stage1_result.get("last_image")

        # --- System prompt ---
        if has_demos:
            system_prompt = (
                "You are a robot agent. You observed reference demonstrations "
                "earlier and explored the environment. Now analyze the "
                "demonstrations in context of your current situation and "
                "select the best tool to solve the task."
            )
        else:
            system_prompt = (
                "You are a robot agent. No reference demonstrations are "
                "available. Reason from your exploration and the available "
                "tools alone.\n\n"
                "Based on your exploration, what are the key features of this "
                "situation that would affect how you approach the task? "
                "What makes this situation unique or challenging? "
                "Select the tool needed to solve this task."
            )

        # --- User prompt ---
        lines = []

        # Available tools
        ca_tools = self.task_config.get("ca_tool_names", [])
        if ca_tools:
            lines.append("=== Available Tools ===")
            lines.append(", ".join(ca_tools))
            lines.append("")

        # Demo observations (demo branch only)
        if has_demos:
            lines.append("=== Your Demo Observations (from Probe 0) ===")
            lines.append(probe0_result["response"])
            lines.append("")

        # Exploration findings
        lines.append("=== Stage 1: Your Exploration Findings ===")
        for i, entry in enumerate(stage1_result.get("exploration_history", []), 1):
            lines.append(f"Step {i}:")
            lines.append(f"  Thought: {entry['thought']}")
            lines.append(f"  Action: {entry['action']}")
            lines.append(f"  Result: {entry['feedback']}")
        lines.append("")

        # Tool selection instructions (from task config or default)
        _BASE_ACTIONS = (
            "You may use the following base actions in your plan:\n"
            "    NAVIGATE_TO[object], GRASP[object], RELEASE[], "
            "PLACE_ON_TOP[surface], PUSH[object], PULL[object], OPEN[object], "
            "CUT[target_object, cutting_tool]\n\n"
            "    After cutting an object, it splits into two halves named "
            "half_<original_name>_0 and half_<original_name>_1.\n\n"
            "    If none of these base actions capture the required motion, "
            "you may define a new action:\n"
            "    NEW_ACTION[name, tool, target]: 'description of the physical motion'\n"
            "    This new action must be physically plausible."
        )

        if has_demos:
            selection_text = self.task_config.get("tool_selection_prompt", "")
            if not selection_text:
                selection_text = (
                    "Based on the demonstrations and your exploration, select "
                    "the tool you will use. Once you pick up a tool, you "
                    "cannot switch to another.\n\n"
                    "Provide:\n"
                    "(1) Which demo you referenced and why\n"
                    "(2) Which tool you select\n"
                    "(3) What features of the current situation make this tool "
                    "suitable\n"
                    "(4) Your action plan"
                )
        else:
            selection_text = self.task_config.get(
                "tool_selection_prompt_no_demo", ""
            )
            if not selection_text:
                selection_text = (
                    "Select the tool you will use. Once you pick up a tool, "
                    "you cannot switch to another.\n\n"
                    "Provide:\n"
                    "(1) What physical principle guides your tool selection\n"
                    "(2) Which tool you select\n"
                    "(3) What sensor data or physical properties make this "
                    "tool suitable (reference specific values from your "
                    "exploration)\n"
                    "(4) Your action plan"
                )

        lines.append(selection_text)
        lines.append("")
        lines.append(_BASE_ACTIONS)
        lines.append("")

        # SELECTED_TOOL structured output instruction
        tool_base_names = [
            name.rsplit("_", 1)[0] for name in self._ca_tool_names
        ]
        lines.append(
            "IMPORTANT: At the very end of your response, on a new line, "
            "write ONLY the tool name in this exact format:\n"
            "SELECTED_TOOL: <tool_name>\n"
            "where <tool_name> is one of: "
            + ", ".join(tool_base_names)
        )
        user_message = "\n".join(lines)

        # --- LLM call ---
        response = self._call_llm(system_prompt, user_message, current_image)
        self._log(f"  Analysis & selection response: {response[:500]}...")

        # --- Extract tool ---
        selected_tool = self._extract_tool_from_response(response)
        self._log(f"  Extracted tool: {selected_tool}")

        # --- Log ---
        step_log = {
            "stage": "analysis_and_selection",
            "step": self.step_count,
            "prompt": {"system": system_prompt, "user": user_message},
            "llm_response": response,
            "selected_tool": selected_tool,
            "demos_referenced": has_demos,
            "duration": time.time() - step_start,
        }
        self._save_step(step_log)

        # --- Evaluate ---
        correct_tool = self.task_config.get("correct_tool")
        tool_correct = (
            selected_tool is not None
            and correct_tool is not None
            and correct_tool.lower() in selected_tool.lower()
        )

        return {
            "selected_tool": selected_tool,
            "correct_tool": correct_tool,
            "tool_selection_correct": tool_correct,
            "full_response": response,
            "last_image": current_image,
        }

    def _extract_tool_from_response(self, response: str) -> Optional[str]:
        """Try to extract the selected tool name from the LLM response.

        Priority:
          0. Explicit "SELECTED_TOOL: <name>" — structured output, most reliable
          1. Explicit "I select/choose/pick/use <tool>" pattern
          2. GRASP of a CA tool candidate — filters out non-CA tools (e.g. knife)
          3. GRASP of any object — fallback
        """
        # 0. Look for explicit SELECTED_TOOL: <name> (structured format)
        st_match = re.search(r"SELECTED_TOOL:\s*(\S+)", response, re.IGNORECASE)
        if st_match:
            candidate = st_match.group(1).strip().strip(".,;:").lower()
            # Exact match first (critical for technique_A vs technique_B etc.)
            for tool_name in self._ca_tool_names:
                if tool_name.lower() == candidate:
                    self._log(f"  [extract] Matched via SELECTED_TOOL (exact): {tool_name}")
                    return tool_name
            # Fuzzy match fallback (for scene object names like potato_701)
            for tool_name in self._ca_tool_names:
                base = tool_name.rsplit("_", 1)[0].lower()
                if base == candidate or base in candidate or candidate in base:
                    self._log(f"  [extract] Matched via SELECTED_TOOL (fuzzy): {tool_name}")
                    return tool_name

        # 1. Look for explicit "I select/choose/pick/use <tool>" pattern
        select_match = re.search(
            r"(?:select|choose|pick|use)\s+(?:the\s+)?(?:a\s+)?(\w+)",
            response, re.IGNORECASE,
        )
        if select_match:
            candidate = select_match.group(1).lower()
            for tool_name in self._ca_tool_names:
                base = tool_name.rsplit("_", 1)[0].lower()
                if (tool_name.lower() in candidate or candidate in tool_name.lower()
                        or base == candidate or base in candidate or candidate in base):
                    self._log(f"  [extract] Matched via 'select/use' pattern: {tool_name}")
                    return tool_name

        # 2. Look for GRASP of a CA tool candidate (skip non-CA tools like knife)
        grasp_matches = re.findall(r"GRASP\[([^\]]+)\]", response)
        for grasp_name in grasp_matches:
            grasp_name = grasp_name.strip()
            if self._is_ca_tool(grasp_name):
                self._log(f"  [extract] Matched via GRASP of CA tool: {grasp_name}")
                return grasp_name

        # 3. Fallback: first GRASP of any object
        if grasp_matches:
            self._log(f"  [extract] Fallback to first GRASP: {grasp_matches[0].strip()}")
            return grasp_matches[0].strip()

        return None

    # ==================================================================
    # STAGE 3: Adaptive Execution
    # ==================================================================

    _ACTION_PRIMITIVE_MAP = {
        "NAVIGATE_TO": SymbolicSemanticActionPrimitiveSet.NAVIGATE_TO,
        "GRASP": SymbolicSemanticActionPrimitiveSet.GRASP,
        "RELEASE": SymbolicSemanticActionPrimitiveSet.RELEASE,
        "PLACE_ON_TOP": SymbolicSemanticActionPrimitiveSet.PLACE_ON_TOP,
        "PUSH": SymbolicSemanticActionPrimitiveSet.PUSH,
        "PULL": SymbolicSemanticActionPrimitiveSet.PULL,
        "OPEN": SymbolicSemanticActionPrimitiveSet.OPEN,
        "CLOSE": SymbolicSemanticActionPrimitiveSet.CLOSE,
        "CUT": SymbolicSemanticActionPrimitiveSet.CUT,
    }

    def _resolve_obj(self, name: str):
        """Resolve object name to scene object.

        Resolution order:
          1. tool_name_mapping (abstracted name → scene name, e.g. tool_A → potato_701)
          2. Task object scope (fuzzy substring match)
          3. Scene object by exact name
        """
        self._log(f"    [resolve] Looking up '{name}'...")

        # Try tool_name_mapping first (for abstracted tool names)
        mapping = self.task_config.get("tool_name_mapping", {})
        if name in mapping:
            mapped = mapping[name]
            self._log(f"    [resolve] Mapped '{name}' → '{mapped}' via tool_name_mapping")
            name = mapped

        # Try task object scope
        if hasattr(self.task, "object_scope"):
            for scope_name, entity in self.task.object_scope.items():
                if name in scope_name or scope_name in name:
                    obj = getattr(entity, "wrapped_obj", entity)
                    if obj is not None:
                        self._log(f"    [resolve] Found in task scope: {scope_name} → {obj.name}")
                        return obj
        # Fall back to scene object by name
        scene_obj = self._get_scene_object(name)
        if scene_obj:
            self._log(f"    [resolve] Found in scene: {scene_obj.name}")
        else:
            self._log(f"    [resolve] NOT FOUND: '{name}'")
        return scene_obj

    def _execute_base_action(self, action_name: str, action_arg: Optional[str]) -> Optional[str]:
        """Execute a base action via OmniGibson controller.

        Returns error string on failure, None on success.
        """
        primitive = self._ACTION_PRIMITIVE_MAP.get(action_name)
        if primitive is None:
            return f"Unknown base action: {action_name}"

        self._log(f"    [base_action] {action_name}[{action_arg}] → primitive={primitive}")

        # --- NAVIGATE_TO: try exploration nav targets first ---
        # This allows Stage 3 to reuse exploration locations like
        # "kitchen_floor, spill_area" that aren't individual scene objects.
        if action_name == "NAVIGATE_TO" and action_arg:
            target_key = ", ".join(p.strip() for p in action_arg.split(","))
            nav_targets = self.task_config.get("exploration_nav_targets", {})
            nav_tracking = self.task_config.get("exploration_nav_tracking", {})
            nav_obj_name = nav_targets.get(target_key)
            if nav_obj_name:
                nav_obj = self._get_scene_object(nav_obj_name)
                track_obj_name = nav_tracking.get(target_key)
                track_obj = (
                    self._get_scene_object(track_obj_name)
                    if track_obj_name else None
                )
                if nav_obj:
                    try:
                        self._teleport_to_face(nav_obj, tracking_obj=track_obj)
                        self._log(
                            f"    [base_action] NAVIGATE_TO via exploration target: "
                            f"{nav_obj_name}"
                        )
                        return None
                    except Exception as e:
                        self._log(f"    [base_action] Exploration nav failed: {e}")
                        # Fall through to standard resolution

        # Resolve object arguments
        objs = []
        if action_arg:
            for part in action_arg.split(","):
                part = part.strip()
                if not part:
                    continue
                obj = self._resolve_obj(part)
                if obj is None:
                    return f"Object '{part}' not found in scene."
                objs.append(obj)

        self._log(f"    [base_action] Resolved {len(objs)} objects: {[o.name for o in objs]}")

        # Debug: robot state before execution
        robot_pos = self.robot.get_position_orientation()[0]
        self._log(f"    [base_action] Robot pos: [{float(robot_pos[0]):.3f}, {float(robot_pos[1]):.3f}, {float(robot_pos[2]):.3f}]")
        grasped = getattr(self.controller, '_grasped_obj', None)
        self._log(f"    [base_action] Holding: {grasped.name if grasped else 'nothing'}")

        # Debug: proximity for GRASP
        if action_name == "GRASP" and objs:
            obj_pos = objs[0].get_position_orientation()[0]
            dist = float(torch.norm(robot_pos[:2] - obj_pos[:2]))
            self._log(f"    [base_action] Target obj pos: [{float(obj_pos[0]):.3f}, {float(obj_pos[1]):.3f}, {float(obj_pos[2]):.3f}], XY dist={dist:.3f}m")

        try:
            self._log(f"    [base_action] Calling apply_ref()...")
            ctrl_gen = self.controller.apply_ref(primitive, *objs)
            step_i = 0
            for action in ctrl_gen:
                step_i += 1
                self._log(f"    [base_action] env.step #{step_i} starting...")
                self.env.step(action)
                self._log(f"    [base_action] env.step #{step_i} done.")
            self._log(f"    [base_action] Completed ({step_i} steps)")
            return None
        except (ActionPrimitiveError, ActionPrimitiveErrorGroup) as e:
            err_msg = str(e).split(". Additional info:")[0][:300]
            self._log(f"    [base_action] ActionPrimitiveError: {err_msg}")
            return err_msg
        except Exception as e:
            import traceback
            self._log(f"    [base_action] Exception: {type(e).__name__}: {str(e)[:300]}")
            self._log(f"    [base_action] Traceback:\n{traceback.format_exc()}")
            return f"{type(e).__name__}: {str(e)[:200]}"

    def _execute_new_action(
        self, action_name: str, action_arg: Optional[str], description: str
    ) -> Tuple[str, Optional[str]]:
        """Execute a NEW_ACTION via symbolic handler.

        Looks up (tool, target, context) in task_config["new_action_handlers"].
        Applies state changes (teleport + set_state) then og.sim.step().
        Returns (outcome, aux_text).
        """
        handlers = self.task_config.get("new_action_handlers", {})

        # Parse args: NEW_ACTION[name, tool, target]
        parts = [p.strip() for p in (action_arg or "").split(",")]
        action_label = parts[0] if len(parts) > 0 else None
        tool_name = parts[1] if len(parts) > 1 else None
        target_name = parts[2] if len(parts) > 2 else None

        self._log(f"    [new_action] label={action_label}, tool={tool_name}, target={target_name}")
        self._log(f"    [new_action] description: {description}")
        self._log(f"    [new_action] Handlers available: {list(handlers.keys())}")

        # Try to find a matching handler
        for key, handler in handlers.items():
            key_tool, key_target, key_context = key
            tool_match = tool_name and (key_tool.lower() in tool_name.lower()
                                        or tool_name.lower() in key_tool.lower())
            target_match = target_name and (key_target.lower() in target_name.lower()
                                            or target_name.lower() in key_target.lower())
            context_match = target_name and (key_context.lower() in target_name.lower()
                                              or target_name.lower() in key_context.lower())
            self._log(f"    [new_action] Checking {key}: tool_match={tool_match}, target_match={target_match}, context_match={context_match}")
            if tool_match and (target_match or context_match):
                # Dynamic param_checker: evaluate 6-DOF or other parameters
                if callable(handler.get("param_checker")):
                    result = handler["param_checker"](description)
                    outcome = result.get("outcome", "FAILURE")
                    aux_text = result.get("aux_text", "")
                    for sc in result.get("state_changes", []):
                        if sc.get("type") == "teleport_underground":
                            self._teleport_objects_underground(sc["pattern"])
                            self._log(f"    [state] teleport_underground: {sc['pattern']}")
                else:
                    outcome = handler["outcome"]
                    aux_text = handler.get("aux_text", "")
                self._log(f"    [new_action] MATCHED → {outcome}")
                og.sim.step()
                return outcome, aux_text

        self._log(f"    [new_action] NO HANDLER MATCHED")
        og.sim.step()
        return "FAILURE", f"No handler for NEW_ACTION with tool={tool_name}, target={target_name}"

    def _build_stage3_system_prompt(
        self,
        stage1_result: Optional[dict] = None,
        tool_selection_result: Optional[dict] = None,
    ) -> str:
        robot_type = type(self.robot).__name__
        lines = [
            f"You are a {robot_type} robot agent executing your action plan.\n",
            f"Task: {self.task_config['instruction']}\n",
        ]

        # Available objects (so LLM uses correct names)
        ca_tools = self.task_config.get("ca_tool_names", [])
        extra_objects = self.task_config.get("extra_object_names", [])
        all_objects = list(ca_tools) + list(extra_objects)
        if all_objects:
            lines.append("=== Available Objects (use these exact names) ===")
            for name in all_objects:
                lines.append(f"  {name}")
            lines.append("")

        # Stage 1 exploration recap (brief)
        if stage1_result:
            lines.append("=== Stage 1: Exploration Findings ===")
            for i, entry in enumerate(stage1_result.get("exploration_history", []), 1):
                lines.append(f"  Step {i}: {entry['action']} → {entry['feedback']}")
            lines.append("")

        # Tool Selection plan
        if tool_selection_result and tool_selection_result.get("full_response"):
            lines.append("=== Your Tool Selection Plan ===")
            lines.append(tool_selection_result["full_response"])
            lines.append("")

        # One-shot execution mode
        one_shot = self.task_config.get("one_shot_execution", False)

        if one_shot:
            lines.extend([
                "Execute your planned actions one at a time. After each action, "
                "you will see the result as an image.\n",
                "CRITICAL: This is ONE-SHOT execution. You have exactly ONE "
                "attempt for the NEW_ACTION push. Setup actions (NAVIGATE_TO, "
                "GRASP) are allowed to position yourself, but once you issue "
                "a NEW_ACTION, that is your single attempt — there are NO "
                "retries. Make sure your 6-DOF parameters are correct BEFORE "
                "you issue the NEW_ACTION.\n",
                "Available actions:",
                "  NAVIGATE_TO[object], GRASP[object], RELEASE[], "
                "PLACE_ON_TOP[surface], PUSH[object], PULL[object], OPEN[object], "
                "CUT[target_object, cutting_tool]",
                "  NEW_ACTION[name, tool, target]: "
                "'{ JSON parameter dictionary }'\n",
                "CRITICAL FORMAT for NEW_ACTION:",
                "  The colon (:) and the single-quoted JSON MUST appear on the "
                "same Action line.",
                "  Correct:  Action: NEW_ACTION[PUSH, tool, target]: "
                "'{\"orientation_euler_angles\": {\"yaw\": 45.0}}'",
                "  Wrong:    Action: NEW_ACTION[PUSH, tool, target]",
                "  (missing colon and JSON = parse failure)\n",
                "IMPORTANT: Use exact object names from the Available Objects "
                "list above.\n",
                "When the task is complete, say: Action: DONE[]\n",
                "Respond in format:",
                "Thought: <reasoning>",
                "Action: <ACTION>[<args>]",
            ])
        else:
            lines.extend([
                "Execute your planned actions one at a time. After each action, "
                "you will see the result as an image.\n",
                "Available actions:",
                "  NAVIGATE_TO[object], GRASP[object], RELEASE[], "
                "PLACE_ON_TOP[surface], PUSH[object], PULL[object], OPEN[object], "
                "CUT[target_object, cutting_tool]",
                "  NEW_ACTION[name, tool, target]: "
                "'{ JSON parameter dictionary }'\n",
                "CRITICAL FORMAT for NEW_ACTION:",
                "  The colon (:) and the single-quoted JSON MUST appear on the "
                "same Action line.",
                "  Correct:  Action: NEW_ACTION[PUSH, tool, target]: "
                "'{\"orientation_euler_angles\": {\"yaw\": 45.0}}'",
                "  Wrong:    Action: NEW_ACTION[PUSH, tool, target]",
                "  (missing colon and JSON = parse failure)\n",
                "IMPORTANT: Use exact object names from the Available Objects "
                "list above.\n",
                "When the task is complete, say: Action: DONE[]\n",
                "Respond in format:",
                "Thought: <reasoning>",
                "Action: <ACTION>[<args>]",
            ])
        return "\n".join(lines)

    def _build_stage3_step_prompt(
        self, execution_history: List[dict], error: Optional[str] = None,
        steps_remaining: Optional[int] = None,
    ) -> str:
        lines = []
        if steps_remaining is not None:
            lines.append(f"⚠ Steps remaining: {steps_remaining}\n")
        lines.append("=== Execution History ===\n")
        if execution_history:
            for i, entry in enumerate(execution_history, 1):
                lines.append(f"  Step {i}:")
                lines.append(f"    Thought: {entry['thought']}")
                lines.append(f"    Action: {entry['action']}")
                lines.append(f"    Result: {entry['result']}")
            lines.append("")
        else:
            lines.append("No actions executed yet.\n")

        if error:
            lines.append(f"Error from previous action: {error}\n")

        lines.append("What is your next action?")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Stage 3: Menu-based symbolic execution
    # ------------------------------------------------------------------
    def _run_stage3_menu(
        self,
        tool_selection_result: dict,
        stage1_result: Optional[dict] = None,
    ) -> dict:
        """Stage 3: Menu-based symbolic execution.

        Instead of free-form action generation, present pre-defined action
        primitives and let the LLM choose from them.  All actions execute
        symbolically; state_changes update the OmniGibson scene for photos.
        """
        action_menu = self.task_config["stage3_action_menu"]
        completed_actions: set = set()
        execution_history: List[dict] = []
        prev_image_path = tool_selection_result.get("last_image")
        task_success = False
        max_steps = 10

        # Determine selected tool key for menu filtering
        selected_tool = tool_selection_result.get("selected_tool", "")
        # Extract base name: "potato_701" → "potato"
        # But keep full name too for technique-based tasks (no numeric suffix)
        selected_tool_base = selected_tool.rsplit("_", 1)[0] if selected_tool else ""
        self._selected_tool_keys = {selected_tool, selected_tool_base} - {""}
        self._log(f"  [menu] Filtering actions for tool: {self._selected_tool_keys}")

        # Build the static part of the system prompt once
        system_prompt = self._build_stage3_menu_system_prompt(
            stage1_result, tool_selection_result,
        )

        for step_i in range(max_steps):
            self.step_count += 1
            step_start = time.time()
            self._log(f"\n[Stage 3 Menu - Step {self.step_count}]")

            # Compute currently available actions (filtered by selected tool)
            available = []
            for key, defn in action_menu.items():
                if key in completed_actions:
                    continue
                req = defn.get("requires")
                if req and req not in completed_actions:
                    continue
                # Filter: only show actions for the selected tool
                tool_key = defn.get("tool_key", "")
                if tool_key and tool_key not in self._selected_tool_keys:
                    continue
                available.append(key)

            # Build step prompt
            step_prompt = self._build_stage3_menu_step_prompt(
                execution_history, available, action_menu,
            )

            response = self._call_llm(system_prompt, step_prompt, prev_image_path)
            thought, action_name, action_arg = self._parse_response(response)
            full_action = f"{action_name}[{action_arg}]" if action_name else response.strip()

            self._log(f"  Thought: {thought}")
            self._log(f"  Action: {full_action}")

            step_log = {
                "stage": 3,
                "step": self.step_count,
                "prompt": {"system": system_prompt, "user": step_prompt},
                "llm_response": response,
                "parsed": {"thought": thought, "action": full_action},
            }

            # --- DONE ---
            if action_name == "DONE":
                self._log("  Agent declares: DONE")
                step_log["execution"] = {"status": "DONE"}
                step_log["duration"] = time.time() - step_start
                self._save_step(step_log)
                break

            # --- Match to menu ---
            matched_key = self._match_menu_action(full_action, available, action_menu)

            if matched_key is None:
                result_text = (
                    f"INVALID: '{full_action}' is not in the available actions. "
                    "Choose from the listed actions."
                )
                self._log(f"  {result_text}")
                step_log["execution"] = {"status": "INVALID"}
                step_log["duration"] = time.time() - step_start
                self._save_step(step_log)
                execution_history.append({
                    "thought": thought,
                    "action": full_action,
                    "result": result_text,
                })
                new_image = self._capture_image(
                    f"stage3_step{self.step_count:03d}_after")
                if new_image:
                    prev_image_path = new_image
                continue

            defn = action_menu[matched_key]

            # --- Dynamic param_checker (for technique-based tasks) ---
            if callable(defn.get("param_checker")):
                description = self._extract_6dof_json(response) or ""
                # Fallback: extract any JSON dict from response
                if not description:
                    brace_match = re.search(r'\{[^{}]+\}', response)
                    if brace_match:
                        description = brace_match.group(0)
                        self._log(f"    [param] Extracted JSON via fallback: {description[:80]}")
                result = defn["param_checker"](description)
                outcome = result.get("outcome", "FAILURE")
                feedback = result.get("aux_text", "")
                for sc in result.get("state_changes", []):
                    sc_type = sc.get("type", "")
                    if sc_type == "set_flag":
                        completed_actions.add(sc["flag"])
                    elif sc_type == "teleport_underground":
                        self._teleport_objects_underground(sc["pattern"])
            else:
                outcome = defn["outcome"]
                feedback = defn["feedback"]

            # --- Execute sim_action (e.g. real CUT) ---
            sim_action = defn.get("sim_action")
            if sim_action:
                sa_type = sim_action[0]
                if sa_type == "CUT":
                    target_name, tool_name = sim_action[1], sim_action[2]
                    err = self._execute_base_action(
                        "CUT", f"{target_name}, {tool_name}")
                    if err:
                        self._log(
                            f"  [menu] CUT sim failed: {err} — "
                            "continuing symbolically")

            # --- Apply state changes ---
            for sc in defn.get("state_changes", []):
                if sc["type"] == "teleport_underground":
                    self._teleport_objects_underground(sc["pattern"])

            completed_actions.add(matched_key)
            # Also add any unlocked actions note (informational)
            self._log(f"  [menu] {matched_key} → {outcome}")

            og.sim.step()

            new_image = self._capture_image(
                f"stage3_step{self.step_count:03d}_after")
            if new_image:
                prev_image_path = new_image

            result_text = f"{outcome}: {feedback}"
            execution_history.append({
                "thought": thought,
                "action": matched_key,
                "result": result_text,
            })

            step_log["execution"] = {"status": outcome, "feedback": feedback}
            step_log["duration"] = time.time() - step_start
            self._save_step(step_log)

            if defn.get("task_success"):
                task_success = True
                break

        # --- Metacognitive Probe 3 ---
        has_demos = bool(self._prepared_demos)
        if has_demos:
            probe_text = self.task_config.get("probes", {}).get(
                "stage3",
                "Did you adapt the approach from the demo in any way? "
                "If so, what did you change and why?",
            )
        else:
            probe_text = (
                "Based on your execution history, did your plan work as "
                "expected? What succeeded, what failed, and why? "
                "If you would approach the task differently next time, "
                "explain how and why."
            )
        self._log("\n[Stage 3 Menu — Metacognitive Probe]")
        expl_hist = (stage1_result.get("exploration_history", [])
                     if stage1_result else [])
        ts_resp = tool_selection_result.get("full_response")
        probe_user = self._build_probe_user_message(
            exploration_history=expl_hist,
            tool_selection_response=ts_resp,
            execution_history=execution_history,
        )
        probe_response = self._call_llm(probe_text, probe_user)
        self._log(f"  Probe response: {probe_response[:300]}...")
        self._save_step({
            "stage": 3, "step": "probe",
            "type": "metacognitive_probe",
            "question": probe_text,
            "response": probe_response,
        })

        return {
            "status": "SUCCESS" if task_success else "COMPLETED",
            "execution_history": execution_history,
            "committed_tool": self._committed_tool
                              or tool_selection_result.get("selected_tool"),
            "probe_response": probe_response,
            "last_image": prev_image_path,
        }

    def _build_stage3_menu_system_prompt(
        self,
        stage1_result: Optional[dict],
        tool_selection_result: Optional[dict],
    ) -> str:
        robot_type = type(self.robot).__name__
        lines = [
            f"You are a {robot_type} robot agent executing your action plan.\n",
            f"Task: {self.task_config['instruction']}\n",
        ]

        # Exploration recap
        if stage1_result:
            lines.append("=== Exploration Findings ===")
            for i, entry in enumerate(
                    stage1_result.get("exploration_history", []), 1):
                lines.append(
                    f"  Step {i}: {entry['action']} → {entry['feedback']}")
            lines.append("")

        # Tool Selection plan
        if tool_selection_result and tool_selection_result.get("full_response"):
            lines.append("=== Your Tool Selection ===")
            lines.append(tool_selection_result["full_response"])
            lines.append("")

        lines.extend([
            "Execute your plan by choosing actions from the menu below.",
            "After each action you will see the result and a photo.",
            "When the task is complete, say: Action: DONE[]\n",
            "Respond in format:",
            "Thought: <your reasoning>",
            "Action: <exact action from the Available Actions list>",
        ])
        return "\n".join(lines)

    def _build_stage3_menu_step_prompt(
        self,
        execution_history: List[dict],
        available: List[str],
        action_menu: dict,
    ) -> str:
        lines = []

        # Execution history
        if execution_history:
            lines.append("=== Execution History ===")
            for i, entry in enumerate(execution_history, 1):
                lines.append(f"  Step {i}: {entry['action']}")
                lines.append(f"    Result: {entry['result']}")
            lines.append("")

        # Available actions
        lines.append("=== Available Actions ===")
        for key in available:
            desc = action_menu[key].get("description", "")
            lines.append(f"  {key}  — {desc}")
        lines.append("  DONE[]  — Declare the task complete")
        lines.append("")

        lines.append("What is your next action?")
        return "\n".join(lines)

    @staticmethod
    def _match_menu_action(
        full_action: str, available: List[str], action_menu: dict,
    ) -> Optional[str]:
        """Match LLM output to a menu key. Tries exact, then case-insensitive,
        then substring, then action-name prefix match."""
        fa = full_action.strip()
        # Exact (must be in filtered available list)
        if fa in available:
            return fa
        # Case-insensitive
        fa_lower = fa.lower()
        for key in available:
            if key.lower() == fa_lower:
                return key
        # Substring (LLM might add extra text)
        for key in available:
            if key.lower() in fa_lower or fa_lower in key.lower():
                return key
        # Action-name prefix match: "APPLY_TECHNIQUE[lid, {...}]" → "APPLY_TECHNIQUE[lid]"
        # LLM may embed parameters inside the brackets
        fa_name = fa.split("[")[0].lower() if "[" in fa else fa_lower
        for key in available:
            key_name = key.split("[")[0].lower() if "[" in key else key.lower()
            if fa_name == key_name:
                return key
        return None

    def _teleport_objects_underground(self, pattern: str):
        """Teleport all scene objects matching *pattern* to z=-10."""
        for obj in self.env.scene.objects:
            if pattern.lower() in obj.name.lower():
                pos = obj.get_position()
                obj.set_position([float(pos[0]), float(pos[1]), -10.0])
                self._log(f"    [state] Teleported {obj.name} underground")

    # ------------------------------------------------------------------
    # Stage 3: Free-form execution (original)
    # ------------------------------------------------------------------
    def _run_stage3(
        self,
        tool_selection_result: dict,
        stage1_result: Optional[dict] = None,
    ) -> dict:
        """Stage 3: Adaptive Execution — ReAct loop.

        Executes actions one at a time:
        - Base actions (NAVIGATE_TO, GRASP, etc.) → OmniGibson physics
        - NEW_ACTION → symbolic handler (teleport + state change)
        - One-Shot CA tool constraint enforced on GRASP
        - One-Shot execution: if task_config["one_shot_execution"] is True,
          the loop ends after the first NEW_ACTION (no retries)
        - Each step: LLM call with image observation
        """
        # Pre-extract 6-DOF params from Tool Selection response (fallback for Stage 3)
        ts_response = tool_selection_result.get("full_response", "")
        self._tool_selection_6dof = self._extract_6dof_json(ts_response)
        if self._tool_selection_6dof:
            self._log(f"  [Stage3] Cached 6-DOF from Tool Selection: "
                       f"{self._tool_selection_6dof[:80]}...")

        one_shot = self.task_config.get("one_shot_execution", False)

        system_prompt = self._build_stage3_system_prompt(
            stage1_result=stage1_result,
            tool_selection_result=tool_selection_result,
        )
        execution_history: List[dict] = []
        prev_image_path = tool_selection_result.get("last_image")
        error_feedback = None
        max_execution_steps = 15

        for step in range(max_execution_steps):
            self.step_count += 1
            step_start = time.time()

            self._log(f"\n[Stage 3 - Step {self.step_count}]")

            step_prompt = self._build_stage3_step_prompt(
                execution_history, error_feedback,
                steps_remaining=max_execution_steps - step,
            )
            response = self._call_llm(system_prompt, step_prompt, prev_image_path)
            thought, action_name, action_arg = self._parse_response(response)

            self._log(f"  Thought: {thought}")
            self._log(f"  Action: {action_name}[{action_arg}]")

            step_log = {
                "stage": 3,
                "step": self.step_count,
                "prompt": {"system": system_prompt, "user": step_prompt},
                "llm_response": response,
                "parsed": {
                    "thought": thought,
                    "action_name": action_name,
                    "action_arg": action_arg,
                },
            }

            # DONE
            if action_name == "DONE":
                self._log("  Agent declares: DONE")
                step_log["execution"] = {"status": "DONE"}
                step_log["duration"] = time.time() - step_start
                self._save_step(step_log)
                break

            # Parse error
            if action_name is None:
                error_feedback = "Could not parse. Use: Action: ACTION_NAME[arg]"
                step_log["execution"] = {"status": "PARSE_ERROR"}
                step_log["duration"] = time.time() - step_start
                self._save_step(step_log)
                continue

            error_feedback = None
            result_text = "SUCCESS"

            # --- One-Shot CA tool check on GRASP ---
            if action_name == "GRASP" and action_arg:
                ca_error = self._check_ca_tool_grasp(action_name, action_arg)
                if ca_error:
                    error_feedback = ca_error
                    result_text = f"BLOCKED: {ca_error}"
                    self._log(f"  [CA] {ca_error}")
                    step_log["execution"] = {"status": "CA_BLOCKED", "error": ca_error}
                    step_log["duration"] = time.time() - step_start
                    self._save_step(step_log)
                    execution_history.append({
                        "thought": thought,
                        "action": f"{action_name}[{action_arg}]",
                        "result": result_text,
                    })
                    continue

            # --- NEW_ACTION ---
            if action_name == "NEW_ACTION":
                # Robust 6-DOF extraction: try response first, then tool_selection fallback
                description = self._extract_6dof_json(response)
                if not description and hasattr(self, '_tool_selection_6dof'):
                    description = self._tool_selection_6dof
                    self._log(f"  [NEW_ACTION] Using 6-DOF params from Tool Selection step")
                outcome, aux_text = self._execute_new_action(action_name, action_arg, description)
                result_text = f"{outcome}: {aux_text}"
                self._log(f"  [NEW_ACTION] {outcome}: {aux_text}")
                step_log["execution"] = {
                    "status": outcome,
                    "feedback": aux_text,
                    "description": description,
                }

                # --- One-Shot execution: end after first NEW_ACTION ---
                if one_shot:
                    self._log(f"  [One-Shot] NEW_ACTION executed — ending Stage 3 "
                              f"(outcome: {outcome})")
                    new_image = self._capture_image(
                        f"stage3_step{self.step_count:03d}_after")
                    if new_image:
                        prev_image_path = new_image
                    execution_history.append({
                        "thought": thought,
                        "action": f"{action_name}[{action_arg or ''}]",
                        "result": result_text,
                    })
                    step_log["duration"] = time.time() - step_start
                    self._save_step(step_log)
                    break

            # --- Base action ---
            elif action_name in self._ACTION_PRIMITIVE_MAP:
                err = self._execute_base_action(action_name, action_arg)
                if err:
                    error_feedback = err
                    result_text = f"FAILED: {err}"
                    self._log(f"  [Exec] FAILED: {err}")
                    step_log["execution"] = {"status": "FAILED", "error": err}
                else:
                    result_text = "SUCCESS"
                    self._log(f"  [Exec] SUCCESS")
                    step_log["execution"] = {"status": "SUCCESS"}
            else:
                error_feedback = f"Unknown action: {action_name}"
                result_text = f"ERROR: Unknown action"
                step_log["execution"] = {"status": "ERROR", "error": error_feedback}

            # Capture image after action
            new_image = self._capture_image(f"stage3_step{self.step_count:03d}_after")
            if new_image:
                prev_image_path = new_image

            execution_history.append({
                "thought": thought,
                "action": f"{action_name}[{action_arg or ''}]",
                "result": result_text,
            })

            step_log["duration"] = time.time() - step_start
            self._save_step(step_log)

        # --- Metacognitive Probe 3 ---
        has_demos = bool(self._prepared_demos)
        if has_demos:
            probe_text = self.task_config.get("probes", {}).get(
                "stage3",
                "Did you adapt the approach from the demo in any way? "
                "If so, what did you change and why?"
            )
        else:
            probe_text = (
                "Based on your execution history, did your plan work as expected? "
                "What succeeded, what failed, and why? "
                "If you would approach the task differently next time, explain how and why."
            )

        self._log("\n[Stage 3 — Metacognitive Probe]")
        expl_hist = stage1_result.get("exploration_history", []) if stage1_result else []
        ts_resp = tool_selection_result.get("full_response")
        probe_user = self._build_probe_user_message(
            exploration_history=expl_hist,
            tool_selection_response=ts_resp,
            execution_history=execution_history,
        )
        probe_response = self._call_llm(probe_text, probe_user)
        self._log(f"  Probe response: {probe_response[:300]}...")

        self._save_step({
            "stage": 3,
            "step": "probe",
            "type": "metacognitive_probe",
            "question": probe_text,
            "response": probe_response,
        })

        return {
            "status": "COMPLETED",
            "execution_history": execution_history,
            "committed_tool": self._committed_tool,
            "probe_response": probe_response,
            "last_image": prev_image_path,
        }

    # ==================================================================
    # Experiment saving
    # ==================================================================
    def _save_experiment(self, result: dict):
        if not self.experiment_dir:
            return

        with open(os.path.join(self.experiment_dir, "result.json"), "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        config = {
            "task_name": self.task_config["task_name"],
            "instruction": self.task_config["instruction"],
            "correct_tool": self.task_config.get("correct_tool"),
            "ca_tool_names": self._ca_tool_names,
            "max_exploration_steps": self.max_exploration_steps,
            "timestamp": datetime.now().isoformat(),
        }
        with open(os.path.join(self.experiment_dir, "config.json"), "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._log(f"\nExperiment saved to: {self.experiment_dir}")

        if self._log_file:
            self._log_file.close()
            self._log_file = None
