import os

import cv2
import numpy as np
import torch
from PIL import Image


def _look_at_quat(eye, target, up=None):
    """Compute quaternion for a camera at `eye` looking at `target`."""
    if up is None:
        up = torch.tensor([0.0, 0.0, 1.0])
    forward = target - eye
    forward = forward / torch.norm(forward)
    right = torch.linalg.cross(forward, up)
    right_norm = torch.norm(right)
    if right_norm < 1e-6:
        right = torch.tensor([1.0, 0.0, 0.0])
    else:
        right = right / right_norm
    up_actual = torch.linalg.cross(right, forward)

    rot = torch.stack([right, up_actual, -forward], dim=1)  # 3x3

    trace = rot[0, 0] + rot[1, 1] + rot[2, 2]
    if trace > 0:
        s = 0.5 / torch.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (rot[2, 1] - rot[1, 2]) * s
        y = (rot[0, 2] - rot[2, 0]) * s
        z = (rot[1, 0] - rot[0, 1]) * s
    elif rot[0, 0] > rot[1, 1] and rot[0, 0] > rot[2, 2]:
        s = 2.0 * torch.sqrt(1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2])
        w = (rot[2, 1] - rot[1, 2]) / s
        x = 0.25 * s
        y = (rot[0, 1] + rot[1, 0]) / s
        z = (rot[0, 2] + rot[2, 0]) / s
    elif rot[1, 1] > rot[2, 2]:
        s = 2.0 * torch.sqrt(1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2])
        w = (rot[0, 2] - rot[2, 0]) / s
        x = (rot[0, 1] + rot[1, 0]) / s
        y = 0.25 * s
        z = (rot[1, 2] + rot[2, 1]) / s
    else:
        s = 2.0 * torch.sqrt(1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1])
        w = (rot[1, 0] - rot[0, 1]) / s
        x = (rot[0, 2] + rot[2, 0]) / s
        y = (rot[1, 2] + rot[2, 1]) / s
        z = 0.25 * s
    return torch.tensor([x, y, z, w])


_HEAD_HEIGHT = 1.4
_CEILING_Z = 2.4

_SKIP_CATEGORIES = {"floors", "ceilings", "carpet", "ground", "roof", "agent"}
_CAM_MARGIN = 0.1


def _quat_to_yaw(ori):
    """Extract yaw angle from quaternion (x, y, z, w)."""
    qx, qy, qz, qw = ori
    return torch.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def _direction_and_perp(from_pos_2d, to_pos_2d, fallback_ori=None):
    """Compute unit direction from_pos->to_pos and its perpendicular. Fallback to yaw if too close."""
    d = to_pos_2d - from_pos_2d
    dist = torch.norm(d)
    if dist > 1e-3:
        d = d / dist
    elif fallback_ori is not None:
        yaw = _quat_to_yaw(fallback_ori)
        d = torch.tensor([-torch.cos(yaw), -torch.sin(yaw)])
    else:
        d = torch.tensor([1.0, 0.0])
    perp = torch.tensor([-d[1].item(), d[0].item()])
    return d, perp


class CameraMixin:

    def __init_camera__(self):
        self._camera_warmed_up = False
        self._head_sensor = None
        self._head_sensor_searched = False
        self._recording = False
        self._frames = []

    # ------------------------------------------------------------------
    # Onboard head sensor helpers
    # ------------------------------------------------------------------

    def _get_head_sensor(self):
        """Find and cache the VisionSensor on the robot's head (xtion camera)."""
        if self._head_sensor is not None:
            return self._head_sensor
        if self._head_sensor_searched:
            return None
        self._head_sensor_searched = True
        from omnigibson.sensors import VisionSensor
        for name, sensor in self.robot.sensors.items():
            if isinstance(sensor, VisionSensor):
                self._head_sensor = sensor
                return sensor
        return None

    def _settle_head_for_capture(self, n_sim_steps=5, n_render_steps=5):
        """Point the head at _tracking_object (or reset pose) and settle."""
        import omnigibson as og

        tracking = getattr(self.primitives, '_tracking_object', None)

        # Get anchored body pose so we can pin body during sim steps
        anchored_pos = getattr(self.primitives, '_anchored_pos', None)
        anchored_ori = getattr(self.primitives, '_anchored_ori', None)

        # Pin body to anchored pose BEFORE computing head_q
        # (_get_head_goal_q reads robot.get_position_orientation() internally)
        if anchored_pos is not None:
            self.robot.set_position_orientation(position=anchored_pos, orientation=anchored_ori)
            self.robot.keep_still()

        if tracking is not None:
            target_pose = tracking.get_position_orientation()
            head_q = self.primitives._get_head_goal_q(target_pose)

            # If head pan hit joint limit (returned default pose), rotate body to face target
            default_head = self.robot.reset_joint_pos[self.robot.controller_action_idx["camera"]]
            if torch.allclose(head_q, default_head, atol=1e-3):
                target_pos = target_pose[0]
                face_dir = target_pos[:2] - anchored_pos[:2] if anchored_pos is not None else target_pos[:2] - self.robot.get_position_orientation()[0][:2]
                if torch.norm(face_dir) > 1e-3:
                    face_yaw = torch.atan2(face_dir[1], face_dir[0])
                    anchored_ori = torch.tensor([0.0, 0.0, torch.sin(face_yaw / 2), torch.cos(face_yaw / 2)])
                    self.robot.set_position_orientation(position=anchored_pos, orientation=anchored_ori)
                    self.robot.keep_still()
                    # Recompute head_q with new body orientation
                    head_q = self.primitives._get_head_goal_q(target_pose)
        else:
            # Default: look straight ahead (pan=0, tilt=0)
            head_q = torch.tensor([0.0, 0.0])

        # Debug: print camera state
        import sys as _sys
        _out = getattr(_sys, '_real_stdout', _sys.stdout)
        actual_pos, actual_ori = self.robot.get_position_orientation()
        _yaw = _quat_to_yaw(actual_ori).item()
        _tname = tracking.category if tracking is not None else "None"
        _tpos = target_pose[0] if tracking is not None else None
        _out.write(f"[CAM] tracking={_tname} robot=[{actual_pos[0]:.2f},{actual_pos[1]:.2f}] yaw={_yaw:.2f}rad"
                   f" anchored=[{anchored_pos[0]:.2f},{anchored_pos[1]:.2f}]" if anchored_pos is not None else "")
        if _tpos is not None:
            _out.write(f" target=[{_tpos[0]:.2f},{_tpos[1]:.2f},{_tpos[2]:.2f}]")
        _out.write(f" head_q=[{head_q[0]:.3f},{head_q[1]:.3f}]\n")
        _out.flush()

        # Directly set head joint positions
        self.robot.set_joint_positions(head_q, indices=self.robot.camera_control_idx)
        if anchored_pos is not None:
            self.robot.set_position_orientation(position=anchored_pos, orientation=anchored_ori)
        self.robot.keep_still()

        # Pin all movable objects so physics steps don't disturb the scene
        self._pin_movable_objects()

        for _ in range(n_sim_steps):
            og.sim.step()
            # Re-pin body + head to prevent drift
            self.robot.set_joint_positions(head_q, indices=self.robot.camera_control_idx)
            if anchored_pos is not None:
                self.robot.set_position_orientation(position=anchored_pos, orientation=anchored_ori)
            self.robot.keep_still()
            self._pin_movable_objects()

        for _ in range(n_render_steps):
            og.sim.render()

    # ------------------------------------------------------------------
    # External (viewer) camera helpers — kept as fallback
    # ------------------------------------------------------------------

    def _pin_movable_objects(self):
        """Pin all non-fixed objects (including robot) so og.sim.render() physics doesn't move them."""
        for obj in self.scene.objects:
            if getattr(obj, 'fixed_base', False):
                continue
            if obj.category in _SKIP_CATEGORIES:
                continue
            try:
                obj.keep_still()
            except Exception:
                pass

    def _render_at(self, cam_pos, look_target, render_frames=30):
        """Set camera, render, return RGB numpy array."""
        import omnigibson as og
        cam_ori = _look_at_quat(cam_pos, look_target)
        og.sim.viewer_camera.set_position_orientation(cam_pos, cam_ori)

        # FOV 90 deg -> focalLength 18mm (sensor_width 36mm)
        og.sim.viewer_camera.prim.GetAttribute("focalLength").Set(18.0)
        self._pin_movable_objects()
        if not self._camera_warmed_up:
            for _ in range(30):
                og.sim.render()
            self._camera_warmed_up = True
        for _ in range(render_frames):
            og.sim.render()
        obs = og.sim.viewer_camera.get_obs()
        return obs[0]["rgb"][:, :, :3].cpu().numpy().astype(np.uint8)

    @staticmethod
    def _brighten(rgb, gamma=0.55):
        table = np.array(
            [((i / 255.0) ** gamma) * 255 for i in range(256)],
            dtype=np.uint8,
        )
        return table[rgb]

    def _get_room_bounds(self):
        """Return (min_x, min_y, max_x, max_y) from floor objects. Cached."""
        if hasattr(self, '_room_bounds_cache'):
            return self._room_bounds_cache
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        for obj in self.scene.objects:
            if obj.category in ("floors", "ground"):
                try:
                    lo, hi = obj.aabb
                    min_x = min(min_x, lo[0].item())
                    min_y = min(min_y, lo[1].item())
                    max_x = max(max_x, hi[0].item())
                    max_y = max(max_y, hi[1].item())
                except Exception:
                    pass
        self._room_bounds_cache = (min_x, min_y, max_x, max_y) if min_x != float('inf') else None
        return self._room_bounds_cache

    def _cam_collides(self, pos, exclude=None):
        """Check if a camera position is inside any fixed object's AABB, above ceiling, or outside room."""
        if pos[2] > _CEILING_Z:
            return True
        # Room boundary check
        bounds = self._get_room_bounds()
        if bounds is not None:
            min_x, min_y, max_x, max_y = bounds
            if pos[0] < min_x or pos[0] > max_x or pos[1] < min_y or pos[1] > max_y:
                return True
        for obj in self.scene.objects:
            if exclude is not None and obj is exclude:
                continue
            if not getattr(obj, 'fixed_base', False):
                continue
            if obj.category in _SKIP_CATEGORIES:
                continue
            try:
                aabb_lo, aabb_hi = obj.aabb
            except Exception:
                continue
            if (pos[0] > aabb_lo[0] - _CAM_MARGIN and pos[0] < aabb_hi[0] + _CAM_MARGIN and
                pos[1] > aabb_lo[1] - _CAM_MARGIN and pos[1] < aabb_hi[1] + _CAM_MARGIN and
                pos[2] > aabb_lo[2] - _CAM_MARGIN and pos[2] < aabb_hi[2] + _CAM_MARGIN):
                return True
        return False

    def _make_cam_pos(self, anchor_pos, cam_dir, perp, behind, lateral, height):
        cam_pos = anchor_pos.clone()
        cam_pos[:2] += cam_dir * behind
        cam_pos[:2] += perp * lateral
        cam_pos[2] += height
        cam_pos[2] = min(cam_pos[2].item(), _CEILING_Z)
        return cam_pos

    def _get_candidates(self, obj_type, tracking=None):
        """Return camera offset candidates relative to target center."""
        base = [
            (1.2,  0.4, 0.5),
            (1.2, -0.4, 0.5),
            (1.0,  0.3, 0.3),
            (1.0, -0.3, 0.3),
            (0.8,  0.5, 0.6),
            (0.8, -0.5, 0.6),
            (0.0,  0.0, 1.2),
            (1.5,  0.0, 0.3),
        ]
        # Scale behind/height for tall furniture so the whole object fits in frame
        if obj_type == "furniture" and tracking is not None:
            try:
                aabb_lo, aabb_hi = tracking.aabb
                obj_h = (aabb_hi[2] - aabb_lo[2]).item()
                s = max(1.0, obj_h / 1.2)
                return [(b * s, l, h * s) for b, l, h in base]
            except Exception:
                pass
        return base

    def _compute_cam_direction(self, anchor_pos, robot_ori, robot_pos):
        """Compute cam_dir (anchor->robot) and perpendicular vector."""
        return _direction_and_perp(anchor_pos[:2], robot_pos[:2], fallback_ori=robot_ori)

    def _compute_look_target(self, tracking, obj_type, robot_pos, robot_ori):
        """Compute where the camera should look at."""
        if tracking is not None:
            aabb_lo, aabb_hi = tracking.aabb
            return ((aabb_lo + aabb_hi) / 2.0).clone()
        yaw = _quat_to_yaw(robot_ori)
        look_target = robot_pos.clone()
        look_target[0] += torch.cos(yaw) * 2.0
        look_target[1] += torch.sin(yaw) * 2.0
        look_target[2] += _HEAD_HEIGHT * 0.6
        return look_target

    def _classify_tracking(self, tracking):
        """Classify tracking object for camera positioning."""
        if tracking is None:
            return "none"
        if not (hasattr(tracking, 'fixed_base') and tracking.fixed_base):
            return "object"
        from omnigibson import object_states as _os
        is_openable = (hasattr(tracking, 'states') and _os.Open in tracking.states)
        is_open = is_openable and tracking.states[_os.Open].get_value()
        if is_open:
            return "open_container"
        flat_categories = {"countertop", "table", "desk", "breakfast_table", "coffee_table"}
        if hasattr(tracking, 'category') and tracking.category in flat_categories:
            return "surface"
        return "furniture"

    # --- Dedicated camera: surface (countertop, table, desk) ---

    def _get_rgb_surface(self, tracking, robot_pos, robot_ori):
        """Camera on robot's side of surface, looking down at it."""
        aabb_lo, aabb_hi = tracking.aabb
        surface_z = aabb_hi[2]

        surface_center = (aabb_lo[:2] + aabb_hi[:2]) / 2.0
        away, perp = _direction_and_perp(surface_center, robot_pos[:2], fallback_ori=robot_ori)

        look_target = torch.clamp(robot_pos, aabb_lo, aabb_hi).clone()
        look_target[2] = surface_z + 0.05

        candidates = [
            (0.8,  0.0, 0.6),
            (0.8,  0.3, 0.6),
            (0.8, -0.3, 0.6),
            (0.6,  0.0, 0.8),
            (0.6,  0.4, 0.8),
            (0.6, -0.4, 0.8),
            (0.4,  0.0, 1.0),
            (0.0,  0.0, 1.5),
        ]

        for away_d, lat, h in candidates:
            cam_pos = look_target.clone()
            cam_pos[:2] += away * away_d
            cam_pos[:2] += perp * lat
            cam_pos[2] = surface_z + h
            cam_pos[2] = min(cam_pos[2].item(), _CEILING_Z)
            if not self._cam_collides(cam_pos, exclude=tracking):
                return self._render_at(cam_pos, look_target)

        cam_pos = robot_pos.clone()
        cam_pos[:2] += away * 0.5
        cam_pos[2] = surface_z + 0.8
        return self._render_at(cam_pos, look_target)

    # --- Dedicated camera: open container (fridge, cabinet) ---

    def _get_rgb_open_container(self, tracking, robot_pos, robot_ori):
        """Camera on robot's side, looking INTO the container interior."""
        aabb_lo, aabb_hi = tracking.aabb
        container_center = (aabb_lo + aabb_hi) / 2.0

        away, perp = _direction_and_perp(container_center[:2], robot_pos[:2], fallback_ori=robot_ori)

        look_target = container_center.clone()
        look_target[:2] -= away * 0.3
        look_target[2] = aabb_lo[2] + 0.5 * (aabb_hi[2] - aabb_lo[2])

        candidates = [
            (1.2,  0.25, 0.6),
            (1.2, -0.25, 0.6),
            (1.0,  0.4,  0.7),
            (1.0, -0.4,  0.7),
            (1.5,  0.0,  0.5),
            (0.8,  0.0,  0.8),
        ]

        for away_d, lat, z_frac in candidates:
            cam_pos = container_center.clone()
            cam_pos[:2] += away * away_d
            cam_pos[:2] += perp * lat
            cam_pos[2] = aabb_lo[2] + z_frac * (aabb_hi[2] - aabb_lo[2])
            cam_pos[2] = min(cam_pos[2].item(), _CEILING_Z)
            if not self._cam_collides(cam_pos, exclude=tracking):
                rgb = self._render_at(cam_pos, look_target)
                return self._brighten(rgb, gamma=0.60)

        cam_pos = robot_pos.clone()
        cam_pos[2] += 0.8
        return self._brighten(self._render_at(cam_pos, look_target), gamma=0.60)

    # --- External camera fallback (old get_rgb logic) ---

    def _get_rgb_external(self):
        """Third-person view: target-centric camera (fallback when no head sensor)."""
        robot_pos, robot_ori = self.robot.get_position_orientation()

        tracking = getattr(self.primitives, '_tracking_object', None)
        grasped_dict = getattr(self.primitives, '_grasped', {})
        grasped_objs = set(v for v in grasped_dict.values() if v is not None)

        if tracking is not None and tracking in grasped_objs:
            tracking = None

        obj_type = self._classify_tracking(tracking)

        if obj_type == "surface" and tracking is not None:
            return self._get_rgb_surface(tracking, robot_pos, robot_ori)
        if obj_type == "open_container" and tracking is not None:
            return self._get_rgb_open_container(tracking, robot_pos, robot_ori)

        look_target = self._compute_look_target(tracking, obj_type, robot_pos, robot_ori)

        if tracking is not None:
            try:
                aabb_lo, aabb_hi = tracking.aabb
                target_center = (aabb_lo + aabb_hi) / 2.0
            except Exception:
                target_center = look_target
        else:
            target_center = robot_pos

        cam_dir, perp = self._compute_cam_direction(target_center, robot_ori, robot_pos)

        candidates = self._get_candidates(obj_type, tracking=tracking)
        for behind, lateral, height in candidates:
            pos = self._make_cam_pos(target_center, cam_dir, perp, behind, lateral, height)
            if not self._cam_collides(pos, exclude=tracking):
                return self._render_at(pos, look_target)

        pos = self._make_cam_pos(target_center, cam_dir, perp, 1.5, 0.0, 1.0)
        return self._render_at(pos, look_target)

    # --- Main entry point ---

    _CAM_Z_OFFSET = 1.5  # fixed height above robot base for overhead camera

    def get_rgb(self):
        """Capture RGB from a virtual camera at the robot's XY with fixed height, looking at target."""
        anchored_pos = getattr(self.primitives, '_anchored_pos', None)
        anchored_ori = getattr(self.primitives, '_anchored_ori', None)
        tracking = getattr(self.primitives, '_tracking_object', None)

        if anchored_pos is None or anchored_ori is None:
            return self._get_rgb_external()

        # Classify tracking object to pick the best camera strategy
        obj_type = self._classify_tracking(tracking)

        # Use specialized cameras for surfaces and open containers
        robot_pos, robot_ori = self.robot.get_position_orientation()
        _last_action = getattr(self.primitives, '_last_action_name', '')
        # For PLACE_ON_TOP / NAVIGATE_TO on a surface, skip _get_rgb_surface
        # (robot body blocks the view); use default overhead with extra height instead.
        _surface_overhead_actions = ('PLACE_ON_TOP', 'NAVIGATE_TO')
        if obj_type == "surface" and tracking is not None and _last_action not in _surface_overhead_actions:
            return self._get_rgb_surface(tracking, robot_pos, robot_ori)
        if obj_type == "open_container" and tracking is not None:
            return self._get_rgb_open_container(tracking, robot_pos, robot_ori)

        # Default: fixed-height overhead camera with collision fallback
        # --- ORIGINAL (rollback: uncomment below, remove the offset block) ---
        # cam_pos = anchored_pos.clone()
        # cam_pos[2] = anchored_pos[2] + self._CAM_Z_OFFSET
        # --- END ORIGINAL ---
        # Offset camera toward tracking object so the robot body doesn't block the view.
        # Try toward-tracking first; if that collides (e.g. wall), try opposite side.
        cam_pos = anchored_pos.clone()
        _cam_offset_dir = None
        if tracking is not None:
            try:
                aabb_lo, aabb_hi = tracking.aabb
                target_xy = (aabb_lo[:2] + aabb_hi[:2]) / 2.0
                toward = target_xy - anchored_pos[:2]
                dist = torch.norm(toward)
                if dist > 0.1:
                    _cam_offset_dir = toward / dist
            except Exception:
                pass
        cam_pos[2] = anchored_pos[2] + self._CAM_Z_OFFSET

        def _clamp_to_room(pos):
            bounds = self._get_room_bounds()
            if bounds is not None:
                min_x, min_y, max_x, max_y = bounds
                margin = 1.0
                pos[0] = pos[0].clamp(min_x + margin, max_x - margin)
                pos[1] = pos[1].clamp(min_y + margin, max_y - margin)
            return pos

        # Action-specific camera adjustments
        # (_last_action already fetched above for surface check)
        _is_topdown = _last_action in ('GRASP', 'PLACE_NEXT_TO', 'PLACE_AGAINST', 'NAVIGATE_TO')

        if _last_action == 'PLACE_AGAINST':
            # Wall tracking: raise camera higher to see placement area
            cam_pos[2] = anchored_pos[2] + self._CAM_Z_OFFSET + 0.5
        elif _last_action in _surface_overhead_actions and obj_type == "surface":
            # Surface overhead: raise camera to clear robot body
            cam_pos[2] = anchored_pos[2] + self._CAM_Z_OFFSET + 1.0
        # else: default height (_CAM_Z_OFFSET)

        _side_view_actions = ('GRASP', 'PLACE_ON_TOP')
        # _force_overhead: set externally to suppress side view (for dual-capture in planner)
        if getattr(self, '_force_overhead', False):
            _side_view_actions = ('GRASP',)  # only GRASP keeps side view
        if _cam_offset_dir is not None:
            offset_amount = min(dist * 0.5, 0.5)
            cam_pos[:2] += _cam_offset_dir * offset_amount

            # Side view at gripper height for GRASP and PLACE_ON_TOP
            # Orientation-aware: camera to the left of robot + slight forward
            # Try left side first; if collides (wall), try right side; fallback to overhead
            if _last_action in _side_view_actions:
                eef_pos = self.robot.get_eef_position(self.robot.default_arm)
                robot_pos_g, robot_ori_g = self.robot.get_position_orientation()
                yaw = _quat_to_yaw(robot_ori_g)
                sin_y, cos_y = torch.sin(yaw).item(), torch.cos(yaw).item()
                # Left side
                left_pos = cam_pos.clone()
                left_pos[0] = eef_pos[0].item() - sin_y * 1.0 + cos_y * 0.3
                left_pos[1] = eef_pos[1].item() + cos_y * 1.0 + sin_y * 0.3
                left_pos[2] = eef_pos[2].item()
                # Right side
                right_pos = cam_pos.clone()
                right_pos[0] = eef_pos[0].item() + sin_y * 1.0 + cos_y * 0.3
                right_pos[1] = eef_pos[1].item() - cos_y * 1.0 + sin_y * 0.3
                right_pos[2] = eef_pos[2].item()
                if not self._cam_collides(left_pos):
                    cam_pos = left_pos
                elif not self._cam_collides(right_pos):
                    cam_pos = right_pos
                # else: keep default overhead cam_pos (fallback)
        cam_pos = _clamp_to_room(cam_pos)

        # Compute look target (use body AABB for opened containers)
        if tracking is not None:
            try:
                body_aabb_fn = getattr(self.primitives, '_get_body_aabb', None)
                if body_aabb_fn is not None:
                    aabb_lo, aabb_hi = body_aabb_fn(tracking)
                else:
                    aabb_lo, aabb_hi = tracking.aabb
                look_target = ((aabb_lo + aabb_hi) / 2.0).clone()
                if _last_action in _side_view_actions:
                    # Look at the EEF position (gripper + grasped/placed object)
                    eef_pos = self.robot.get_eef_position(self.robot.default_arm)
                    look_target = eef_pos.clone()
                elif _is_topdown:
                    look_target[2] = 0.0  # look at floor level
                else:
                    look_target[2] = aabb_hi[2].clone()
            except Exception:
                look_target = None
        else:
            look_target = None

        if look_target is None:
            yaw = _quat_to_yaw(anchored_ori)
            look_target = anchored_pos.clone()
            look_target[0] += torch.cos(yaw) * 2.0
            look_target[1] += torch.sin(yaw) * 2.0
            look_target[2] = 1.0

        rgb = self._render_at(cam_pos, look_target)
        if rgb.mean() < 30:
            rgb = self._brighten(rgb, gamma=0.3)
        return rgb

    # ------------------------------------------------------------------
    # Image / Video recording (from original eib_camera.py)
    # ------------------------------------------------------------------

    def save_image(self, save_dir, step_id=0):
        os.makedirs(save_dir, exist_ok=True)

        # Save all lateral variants for comparison (0=none, 1=left, 2=right, 3=more_forward)
        _variant_names = {0: "base", 1: "left", 2: "right", 3: "forward"}
        paths = []
        for var in (0, 1, 2, 3):
            self._lateral_variant = var
            rgb = self.get_rgb()
            suffix = _variant_names[var]
            path = os.path.join(save_dir, f"step_{step_id:04d}_{suffix}.png")
            Image.fromarray(rgb).save(path)
            paths.append(path)
        self._lateral_variant = 0  # reset
        return paths[0]

    def start_recording(self):
        self._recording = True
        self._frames = []

    def stop_recording(self):
        self._recording = False

    def capture_frame(self):
        if self._recording:
            self._frames.append(self.get_rgb())

    def save_video(self, path, fps=10):
        if not self._frames:
            return None
        h, w = self._frames[0].shape[:2]
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h))
        for frame in self._frames:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        writer.release()
        self._frames = []
        return path
