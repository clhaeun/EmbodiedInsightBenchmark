import json
import os

import numpy as np
import torch
from PIL import Image


def _look_at_quat(eye, target, up=None):
    """Compute quaternion for a camera at `eye` looking at `target`."""
    if up is None:
        up = torch.tensor([0.0, 0.0, 1.0])
    forward = target - eye
    forward = forward / torch.norm(forward)
    right = torch.cross(forward, up)
    right_norm = torch.norm(right)
    if right_norm < 1e-6:
        right = torch.tensor([1.0, 0.0, 0.0])
    else:
        right = right / right_norm
    up_actual = torch.cross(right, forward)

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
_CAM_MARGIN = 0.3


def _quat_to_yaw(ori):
    """Extract yaw angle from quaternion (x, y, z, w)."""
    qx, qy, qz, qw = ori
    return torch.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def _direction_and_perp(from_pos_2d, to_pos_2d, fallback_ori=None):
    """Compute unit direction from_pos→to_pos and its perpendicular. Fallback to yaw if too close."""
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
        self._nav_cam_cache = {}  # display_name → {cam_pos, look_target, open_cam_pos, open_look_target}
        self._load_nav_cam_cache()

    def _load_nav_cam_cache(self):
        """Load pre-computed camera positions from nav_cache."""
        cache_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "data", "env", "nav_cache")
        scene_model = getattr(getattr(self, 'env', None), 'scene', None)
        if scene_model is None:
            return
        scene_name = getattr(scene_model, 'scene_model', None)
        if scene_name is None:
            return
        scene_dir = os.path.join(cache_base, scene_name)
        if not os.path.isdir(scene_dir):
            return
        for room in os.listdir(scene_dir):
            nav_json = os.path.join(scene_dir, room, "nav_positions.json")
            if not os.path.exists(nav_json):
                continue
            with open(nav_json) as f:
                data = json.load(f)
            for name, entry in data.get("receptacles", {}).items():
                if "camera_position" not in entry:
                    continue
                cached = {
                    "cam_pos": torch.tensor(entry["camera_position"]),
                    "look_target": torch.tensor(entry["camera_look_target"]),
                }
                if "open_camera_position" in entry:
                    cached["open_cam_pos"] = torch.tensor(entry["open_camera_position"])
                    cached["open_look_target"] = torch.tensor(entry["open_camera_look_target"])
                if "robot_position" in entry and entry["robot_position"] is not None:
                    cached["robot_pos"] = torch.tensor(entry["robot_position"])
                if "robot_orientation" in entry and entry["robot_orientation"] is not None:
                    cached["robot_ori"] = torch.tensor(entry["robot_orientation"])
                # Key by room/name to avoid collisions (e.g. "countertop 1" in multiple rooms)
                self._nav_cam_cache[(room, name)] = cached

    def _get_cached_cam(self, obj):
        """Look up cached camera position for the given object, matching by room."""
        if not self._nav_cam_cache:
            return None
        registry = getattr(self, '_object_registry', {})
        obj_rooms = getattr(obj, 'in_rooms', None) or []
        for display_name, reg_obj in registry.items():
            if reg_obj is not obj:
                continue
            # Try each room the object belongs to
            for room in obj_rooms:
                key = (room, display_name)
                if key in self._nav_cam_cache:
                    return self._nav_cam_cache[key]
            # Fallback: try matching display_name across all rooms
            for (cached_room, cached_name), cached_val in self._nav_cam_cache.items():
                if cached_name == display_name:
                    return cached_val
        return None

    # ------------------------------------------------------------------
    # External (viewer) camera helpers
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

        # FOV 90° → focalLength 18mm (sensor_width 36mm 기준)
        og.sim.viewer_camera.prim.GetAttribute("focalLength").Set(18.0)

        # Pin robot to anchored position during rendering to prevent drift
        anchored_pos = getattr(self.primitives, '_anchored_pos', None)
        anchored_ori = getattr(self.primitives, '_anchored_ori', None)

        def _pin_all():
            self._pin_movable_objects()
            if anchored_pos is not None:
                self.robot.set_position_orientation(position=anchored_pos, orientation=anchored_ori)
                self.robot.keep_still()
            # Pin grasped objects to EEF position
            grasped = getattr(self.primitives, '_grasped', {})
            for hand, obj in grasped.items():
                if obj is not None:
                    eef_pos = self.robot.get_eef_position(hand)
                    obj.set_position_orientation(position=eef_pos)
                    obj.keep_still()

        # Hide robot, grasped objects, and stacked objects during rendering
        self.robot.visible = False
        grasped = getattr(self.primitives, '_grasped', {})
        hidden_objs = []
        for hand, obj in grasped.items():
            if obj is not None:
                obj.visible = False
                hidden_objs.append(obj)
        stacked_map = getattr(self.primitives, '_stacked_objs', {})
        for hand, sobjs in stacked_map.items():
            for sobj in sobjs:
                sobj.visible = False
                hidden_objs.append(sobj)

        _pin_all()
        if not self._camera_warmed_up:
            for _ in range(30):
                og.sim.render()
                _pin_all()
            self._camera_warmed_up = True
        for _ in range(render_frames):
            og.sim.render()
            _pin_all()
        obs = og.sim.viewer_camera.get_obs()
        rgb = obs[0]["rgb"][:, :, :3].cpu().numpy().astype(np.uint8)

        # Restore visibility
        self.robot.visible = True
        for obj in hidden_objs:
            obj.visible = True

        return rgb

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
        """Return camera offset candidates relative to target center.
        No pure overhead (0,0,h) — top-down views are useless for tall furniture.
        """
        base = [
            (1.2,  0.4, 0.5),
            (1.2, -0.4, 0.5),
            (1.0,  0.3, 0.3),
            (1.0, -0.3, 0.3),
            (0.8,  0.5, 0.6),
            (0.8, -0.5, 0.6),
            (1.5,  0.0, 0.3),
            (1.5,  0.5, 0.4),
            (1.5, -0.5, 0.4),
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
        """Over-the-shoulder camera: behind robot looking toward surface."""
        aabb_lo, aabb_hi = tracking.aabb
        surface_z = aabb_hi[2]

        surface_center = (aabb_lo[:2] + aabb_hi[:2]) / 2.0
        # Robot facing direction: from robot toward surface center
        facing, perp = _direction_and_perp(robot_pos[:2], surface_center, fallback_ori=robot_ori)

        look_target = torch.tensor([surface_center[0], surface_center[1], surface_z + 0.05])

        # Camera behind robot (over-the-shoulder), elevated
        candidates = [
            (-0.5, 0.0, 0.8),
            (-0.3, 0.0, 0.7),
            (-0.5, 0.3, 0.8),
            (-0.5,-0.3, 0.8),
            (-0.3, 0.3, 0.7),
            (-0.3,-0.3, 0.7),
            ( 0.0, 0.0, 1.0),
            ( 0.0, 0.0, 1.5),
        ]

        for behind_d, lat, h in candidates:
            cam_pos = robot_pos.clone()
            cam_pos[:2] += facing * behind_d
            cam_pos[:2] += perp * lat
            cam_pos[2] = surface_z + h
            cam_pos[2] = min(cam_pos[2].item(), _CEILING_Z)
            if not self._cam_collides(cam_pos, exclude=tracking):
                return self._render_at(cam_pos, look_target)

        cam_pos = robot_pos.clone()
        cam_pos[2] = surface_z + 1.0
        return self._render_at(cam_pos, look_target)

    # --- Dedicated camera: open container (fridge, cabinet) ---

    def _get_rgb_open_container(self, tracking, robot_pos, robot_ori):
        """Use external camera for open containers — brighten for dark interiors."""
        rgb = self._get_rgb_external()
        if rgb.mean() < 80:
            return self._brighten(rgb, gamma=0.50)
        return rgb

    # --- External camera fallback (old get_rgb logic) ---

    def _get_rgb_external(self):
        """Third-person view: target-centric camera (fallback when no head sensor)."""
        # Use get_position_orientation() — the "stale" initial position gives a
        # distant vantage point in the room interior, producing better framing
        # than the anchored position (which is right next to the target).
        robot_pos, robot_ori = self.robot.get_position_orientation()

        tracking = getattr(self.primitives, '_tracking_object', None)
        grasped_dict = getattr(self.primitives, '_grasped', {})
        grasped_objs = set(v for v in grasped_dict.values() if v is not None)

        if tracking is not None and tracking in grasped_objs:
            tracking = None

        obj_type = self._classify_tracking(tracking)

        # No dispatch to specialized cameras here — _get_rgb_external is a
        # standalone third-person view used as fallback by other cameras.

        look_target = self._compute_look_target(tracking, obj_type, robot_pos, robot_ori)

        if tracking is not None:
            try:
                aabb_lo, aabb_hi = tracking.aabb
                target_center = (aabb_lo + aabb_hi) / 2.0
            except Exception:
                target_center = look_target
        else:
            target_center = robot_pos

        # Try frontal direction first (anchored_pos = robot's actual position = object front),
        # then fall back to stale initial position direction (room interior).
        anchored_pos = getattr(self.primitives, '_anchored_pos', None)
        if anchored_pos is not None and tracking is not None:
            front_dir, front_perp = self._compute_cam_direction(target_center, robot_ori, anchored_pos)
            candidates = self._get_candidates(obj_type, tracking=tracking)
            for behind, lateral, height in candidates:
                pos = self._make_cam_pos(target_center, front_dir, front_perp, behind, lateral, height)
                if not self._cam_collides(pos, exclude=tracking):
                    return self._render_at(pos, look_target)

        # Fallback: stale position direction (wider room-interior view)
        cam_dir, perp = self._compute_cam_direction(target_center, robot_ori, robot_pos)
        candidates = self._get_candidates(obj_type, tracking=tracking)
        for behind, lateral, height in candidates:
            pos = self._make_cam_pos(target_center, cam_dir, perp, behind, lateral, height)
            if not self._cam_collides(pos, exclude=tracking):
                return self._render_at(pos, look_target)

        pos = self._make_cam_pos(target_center, cam_dir, perp, 1.5, 0.0, 1.0)
        return self._render_at(pos, look_target)

    # --- Main entry point ---

    def get_rgb(self):
        """Capture RGB from a virtual camera. Uses cached camera positions if available."""
        anchored_pos = getattr(self.primitives, '_anchored_pos', None)
        anchored_ori = getattr(self.primitives, '_anchored_ori', None)
        tracking = getattr(self.primitives, '_tracking_object', None)

        # Try cached camera position for the navigated receptacle
        nav_target = getattr(self.primitives, '_last_navigated_to', None)
        if nav_target is not None:
            cached = self._get_cached_cam(nav_target)
            if cached is not None:
                # Check if object is currently open → use open camera if available
                from omnigibson import object_states
                is_open = (object_states.Open in nav_target.states
                           and nav_target.states[object_states.Open].get_value())
                if is_open and "open_cam_pos" in cached:
                    return self._render_at(cached["open_cam_pos"], cached["open_look_target"])
                import logging
                logging.getLogger(__name__).info(
                    f"[CAM] cached: {nav_target.name} → pos={cached['cam_pos'].tolist()}, look={cached['look_target'].tolist()}")
                return self._render_at(cached["cam_pos"], cached["look_target"])

        if anchored_pos is None or anchored_ori is None:
            robot_pos, robot_ori = self.robot.get_position_orientation()
            yaw = _quat_to_yaw(robot_ori)
            cam_pos = robot_pos.clone()
            cam_pos[2] = 1.6
            look_target = robot_pos.clone()
            look_target[0] += torch.cos(yaw) * 2.0
            look_target[1] += torch.sin(yaw) * 2.0
            look_target[2] = 0.3
            return self._render_at(cam_pos, look_target)

        # Exclude grasped objects from tracking (AABB unreliable)
        grasped_dict = getattr(self.primitives, '_grasped', {})
        grasped_objs = set(v for v in grasped_dict.values() if v is not None)
        if tracking is not None and tracking in grasped_objs:
            tracking = getattr(self.primitives, '_grasp_container', None)

        # Classify tracking object to pick the best camera strategy
        obj_type = self._classify_tracking(tracking)

        # Use anchored position as the authoritative robot position.
        # self.robot.get_position_orientation() may return stale values when no
        # og.sim.step() has occurred since the last set_position_orientation call.
        robot_pos = anchored_pos.clone()
        robot_ori = anchored_ori.clone()

        if obj_type == "surface" and tracking is not None:
            return self._get_rgb_surface(tracking, robot_pos, robot_ori)
        if obj_type == "open_container" and tracking is not None:
            return self._get_rgb_open_container(tracking, robot_pos, robot_ori)

        # For furniture: use external camera (room-interior vantage point).
        # Robot is squeezed next to the target — bad for photography.
        return self._get_rgb_external()

    def save_image(self, save_dir, step_id=0):
        os.makedirs(save_dir, exist_ok=True)
        # Reset arms to neutral pose before capture to avoid awkward limb positions
        default_q = getattr(self.primitives, '_default_joint_pos', None)
        if default_q is not None:
            self.robot.set_joint_positions(default_q)
            self.robot.set_position_orientation(*self.robot.get_position_orientation())
            self.robot.keep_still()
        rgb = self.get_rgb()
        path = os.path.join(save_dir, f"step_{step_id:04d}.png")
        Image.fromarray(rgb).save(path)
        return path