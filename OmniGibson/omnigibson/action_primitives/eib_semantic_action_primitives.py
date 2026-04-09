"""EIB (Embodied InsightBench) semantic action primitives."""

from enum import IntEnum, auto
from typing import List, Optional

import omnigibson as og
from omnigibson import object_states
from omnigibson.action_primitives.action_primitive_set_base import (
    ActionPrimitiveError,
    ActionPrimitiveErrorGroup,
)
from omnigibson.action_primitives.starter_semantic_action_primitives import (
    StarterSemanticActionPrimitives,
    StarterSemanticActionPrimitiveSet,
)
from omnigibson.objects import StatefulObject
from omnigibson.object_states.object_state_base import RelativeObjectState
from omnigibson.robots.robot_base import BaseRobot
from omnigibson.systems.system_base import BaseSystem
from omnigibson.transition_rules import SlicingRule, CookingPhysicalParticleRule
from omnigibson.systems.macro_particle_system import MacroPhysicalParticleSystem
from omnigibson.utils.object_state_utils import sample_cuboid_for_predicate
from omnigibson.utils.constants import PrimType
import omnigibson.utils.transform_utils as T
import torch

from omnigibson.envs.utils.eib_object_states_utils import (
    get_covered_systems,
    get_contained_systems,
    get_produced_systems,
    get_supported_systems,
    get_modified_systems,
    get_container,
    capture_attachments,
    recover_attachments,
    check_open_before_grasp,
    check_open_before_placement,
    check_close_before_toggle_on,
    check_toggle_off_before_open,
    check_heat_source_before_cook,
    get_cooked_system,
    is_cloth_place_on_other,
    get_placement_objects,
    is_visual_or_physical_particle_system,
    is_target_object_predicate_with_obj,
)
from omnigibson.envs.utils.eib_primitive_utils import find_task_related_object


# ---------------------------------------------------------------------------
# Primitive enum
# ---------------------------------------------------------------------------

class EIBSemanticActionPrimitiveSet(IntEnum):
    NAVIGATE_TO = auto()
    GRASP = auto()
    RELEASE = auto()
    PLACE_ON_TOP = auto()
    PLACE_INSIDE = auto()
    OPEN = auto()
    CLOSE = auto()
    TOGGLE_ON = auto()
    TOGGLE_OFF = auto()
    WIPE = auto()
    CUT = auto()
    SOAK_UNDER = auto()
    SOAK_INSIDE = auto()
    FILL_WITH = auto()
    POUR_INTO = auto()
    WAIT_FOR_COOKED = auto()
    WAIT_FOR_WASHED = auto()
    WAIT = auto()
    SPREAD = auto()
    WAIT_FOR_FROZEN = auto()
    DRAW = auto()
    PIERCE = auto()
    HAMMER = auto()
    PLACE_AGAINST = auto()
    PLACE_NEXT_TO = auto()
    SWEEP = auto()
    TEAR = auto()
    PUSH = auto()
    PULL = auto()
    PLACE_NEAR_HEATING_ELEMENT = auto()
    CLIMB_ON = auto()
    CLIMB_DOWN = auto()


VALID_PRIMITIVES = {
    "NAVIGATE_TO": 1,
    "GRASP": 1,
    "RELEASE": 0,
    "PLACE_ON_TOP": 2,
    "PLACE_INSIDE": 2,
    "OPEN": 1,
    "CLOSE": 1,
    "TOGGLE_ON": 1,
    "TOGGLE_OFF": 1,
    "WIPE": 2,
    "CUT": 2,
    "SOAK_UNDER": 2,
    "SOAK_INSIDE": 2,
    "FILL_WITH": 2,
    "POUR_INTO": 2,
    "WAIT_FOR_COOKED": 1,
    "WAIT_FOR_WASHED": 1,
    "WAIT": 1,
    "SPREAD": 2,
    "WAIT_FOR_FROZEN": 2,
    "DRAW": 2,
    "PIERCE": 2,
    "HAMMER": 2,
    "PLACE_AGAINST": 1,
    "PLACE_NEXT_TO": 1,
    "SWEEP": 1,
    "TEAR": 1,
    "PUSH": 1,
    "PULL": 1,
    "PLACE_NEAR_HEATING_ELEMENT": 1,
    "CLIMB_ON": 1,
    "CLIMB_DOWN": 0,
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class EIBSemanticActionPrimitives(StarterSemanticActionPrimitives):

    PROXIMITY_THRESHOLD = 2.0

    # Default push/pull distance in meters
    PUSH_PULL_DISTANCE = 0.5

    # Maximum object mass (kg) for push/pull. None = no limit.
    MAX_PUSHABLE_MASS = None

    # Object categories the robot is allowed to climb on
    CLIMBABLE_CATEGORIES = {"chair", "stool", "stepstool", "bench", "ottoman", "box", "crate"}

    def __init__(self, env, robot, enable_head_tracking=True):
        super().__init__(env, robot, enable_head_tracking=enable_head_tracking, skip_curobo_initilization=True)
        self._grasped_obj = None
        self._tracking_object = None
        self._anchored_pos = None
        self._anchored_ori = None
        self._grasp_container = None

        # Climb state
        self._climb_obj = None
        self._climb_z_offset = 0.0
        self._pre_climb_z = None

        self.controller_functions = {
            # Robot-based (delegate to parent)
            EIBSemanticActionPrimitiveSet.NAVIGATE_TO: self._eib_navigate_to,
            EIBSemanticActionPrimitiveSet.GRASP: self._eib_grasp,
            EIBSemanticActionPrimitiveSet.RELEASE: self._eib_release,
            # State manipulation
            EIBSemanticActionPrimitiveSet.PLACE_ON_TOP: self._place_on_top,
            EIBSemanticActionPrimitiveSet.PLACE_INSIDE: self._place_inside,
            EIBSemanticActionPrimitiveSet.OPEN: self._open,
            EIBSemanticActionPrimitiveSet.CLOSE: self._close,
            EIBSemanticActionPrimitiveSet.TOGGLE_ON: self._toggle_on,
            EIBSemanticActionPrimitiveSet.TOGGLE_OFF: self._toggle_off,
            EIBSemanticActionPrimitiveSet.WIPE: self._wipe,
            EIBSemanticActionPrimitiveSet.CUT: self._cut,
            EIBSemanticActionPrimitiveSet.SOAK_UNDER: self._soak_under,
            EIBSemanticActionPrimitiveSet.SOAK_INSIDE: self._soak_inside,
            EIBSemanticActionPrimitiveSet.FILL_WITH: self._fill_with,
            EIBSemanticActionPrimitiveSet.POUR_INTO: self._pour_into,
            EIBSemanticActionPrimitiveSet.WAIT_FOR_COOKED: self._wait_for_cooked,
            EIBSemanticActionPrimitiveSet.WAIT_FOR_WASHED: self._wait_for_washed,
            EIBSemanticActionPrimitiveSet.WAIT: self._wait,
            EIBSemanticActionPrimitiveSet.SPREAD: self._spread,
            EIBSemanticActionPrimitiveSet.WAIT_FOR_FROZEN: self._wait_for_frozen,
            EIBSemanticActionPrimitiveSet.DRAW: self._draw,
            EIBSemanticActionPrimitiveSet.PIERCE: self._pierce,
            EIBSemanticActionPrimitiveSet.HAMMER: self._hammer,
            EIBSemanticActionPrimitiveSet.PLACE_AGAINST: self._place_against,
            EIBSemanticActionPrimitiveSet.PLACE_NEXT_TO: self._place_next_to,
            EIBSemanticActionPrimitiveSet.SWEEP: self._sweep,
            EIBSemanticActionPrimitiveSet.TEAR: self._tear,
            EIBSemanticActionPrimitiveSet.PUSH: self._push,
            EIBSemanticActionPrimitiveSet.PULL: self._pull,
            EIBSemanticActionPrimitiveSet.PLACE_NEAR_HEATING_ELEMENT: self._place_near_heating_element,
            EIBSemanticActionPrimitiveSet.CLIMB_ON: self._climb_on,
            EIBSemanticActionPrimitiveSet.CLIMB_DOWN: self._climb_down,
        }
        self.env = env
        self.attachments = []
        self._custom_success_feedback = None

    def _settle_robot(self):
        """Minimal settle — single step with base position pinning.

        One physics step is sufficient for a teleport-based system.
        More steps increase the risk of CUDA error 700 on complex articulations.
        """
        pos, ori = self.robot.get_position_orientation()
        # Guard against NaN orientation (can happen after physics explosion)
        if torch.isnan(ori).any():
            ori = torch.tensor([0.0, 0.0, 0.0, 1.0])
            self.robot.set_position_orientation(position=pos, orientation=ori)
        self.robot.set_position_orientation(position=pos, orientation=ori)
        self.robot.keep_still()
        # Keep held object pinned to EEF (no AG constraint system used)
        if self._grasped_obj is not None:
            eef_pos = self.robot.get_eef_position(self.robot.default_arm)
            self._grasped_obj.set_position_orientation(position=eef_pos)
            self._grasped_obj.keep_still()
            # Pin objects pierced through the held object (e.g. nail in carton)
            self._sync_pierced_to(self._grasped_obj)
        # Pin all pierced relationships (even when not holding anything)
        self._pin_all_pierced()
        action = self._build_noop_action()
        yield self._postprocess_action(action)
        self.robot.set_position_orientation(position=pos, orientation=ori)

    def _no_op(self):
        """Yield a single no-op action (1 physics step). Lighter than _settle_robot."""
        yield self._postprocess_action(self._build_noop_action())

    def _build_noop_action(self):
        """Build a no-op action using each controller's own compute_no_op_action."""
        action = th.zeros(self.robot.action_dim)
        control_dict = self.robot.get_control_dict()
        for name, controller in self.robot._controllers.items():
            action_idx = self.robot.controller_action_idx[name]
            action[action_idx] = controller.compute_no_op_action(control_dict)
        return action

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def apply_ref(self, primitive, *args):
        if any(isinstance(arg, BaseRobot) for arg in args):
            raise ActionPrimitiveErrorGroup(
                [
                    ActionPrimitiveError(
                        ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                        "Cannot call a symbolic semantic action primitive with a robot as an argument.",
                    )
                ]
            )

        # Update tracking target (last object arg) for camera
        if args:
            self._tracking_object = args[-1]

        # Store last action name for camera strategy selection
        self._last_action_name = primitive.name if hasattr(primitive, 'name') else ''

        # Anchor robot position before action for camera positioning
        pos, ori = self.robot.get_position_orientation()
        # [NaN-guard] Robot orientation can be NaN from previous settle
        if torch.isnan(ori).any() or torch.isnan(pos).any():
            ori = torch.tensor([0.0, 0.0, 0.0, 1.0])
            if torch.isnan(pos).any():
                pos = self._anchored_pos if self._anchored_pos is not None else torch.tensor([0.0, 0.0, 0.0])
            self.robot.set_position_orientation(position=pos, orientation=ori)
            self.robot.keep_still()
        self._anchored_pos = pos.clone()
        self._anchored_ori = ori.clone()

        try:
            yield from self.controller_functions[primitive](*args)
        except ActionPrimitiveErrorGroup:
            raise
        except ActionPrimitiveError as e:
            raise ActionPrimitiveErrorGroup([e])

        try:
            yield from self._settle_robot()
        except ActionPrimitiveError:
            pass

    # ------------------------------------------------------------------
    # Proximity check helper
    # ------------------------------------------------------------------

    def _check_proximity(self, target_obj):
        """Raise PRE_CONDITION_ERROR if robot is too far from target_obj."""
        robot_pos = self.robot.get_position_orientation()[0]
        target_pos = target_obj.get_position_orientation()[0]
        dist = torch.norm(robot_pos[:2] - target_pos[:2]).item()
        if dist > self.PROXIMITY_THRESHOLD:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Too far from {target_obj.name} (dist={dist:.1f}m).",
                {"target": target_obj.name, "distance": dist},
            )

    # ------------------------------------------------------------------
    # Camera helper methods
    # ------------------------------------------------------------------

    @property
    def _grasped(self):
        """Dict-style access to grasped objects for camera compatibility."""
        return {self.robot.default_arm: self._grasped_obj}

    def _get_body_aabb(self, target_obj):
        """Return body AABB (without door). If open, temporarily close."""
        if (object_states.Open in target_obj.states
                and target_obj.states[object_states.Open].get_value()):
            target_obj.states[object_states.Open].set_value(False, fully=True)
            aabb = target_obj.aabb
            target_obj.states[object_states.Open].set_value(True, fully=True)
            return aabb
        return target_obj.aabb

    # ------------------------------------------------------------------
    # Pierced-object sync helpers
    # ------------------------------------------------------------------

    def _find_pierced_children(self, obj):
        """Return list of objects that are pierced through *obj*."""
        children = []
        for scene_obj in self.env.scene.objects:
            if not hasattr(scene_obj, 'states'):
                continue
            if object_states.Pierced not in scene_obj.states:
                continue
            ps = scene_obj.states[object_states.Pierced]
            if ps.get_value() and getattr(ps, 'pierced_through', None) is obj:
                children.append(scene_obj)
        return children

    @staticmethod
    def _apply_pierce_relative_pose(parent, child):
        """Compute child world pose from parent world pose + stored relative pose."""
        ps = child.states[object_states.Pierced]
        rel_pos = getattr(ps, 'pierce_rel_pos', None)
        rel_ori = getattr(ps, 'pierce_rel_ori', None)
        parent_pos, parent_ori = parent.get_position_orientation()
        if rel_pos is not None and rel_ori is not None:
            child_pos, child_ori = T.pose_transform(parent_pos, parent_ori, rel_pos, rel_ori)
            child.set_position_orientation(position=child_pos, orientation=child_ori)
        else:
            child.set_position_orientation(position=parent_pos)
        child.keep_still()

    def _sync_pierced_to(self, obj):
        """Move any objects pierced through *obj* using stored relative pose."""
        for child in self._find_pierced_children(obj):
            self._apply_pierce_relative_pose(obj, child)

    def _pin_all_pierced(self):
        """Pin every pierced child to its parent, regardless of grasp state."""
        for scene_obj in self.env.scene.objects:
            if not hasattr(scene_obj, 'states'):
                continue
            if object_states.Pierced not in scene_obj.states:
                continue
            ps = scene_obj.states[object_states.Pierced]
            parent = getattr(ps, 'pierced_through', None)
            if ps.get_value() and parent is not None:
                self._apply_pierce_relative_pose(parent, scene_obj)

    # Maximum distance (m) an object may move during a single settle step
    # before we consider it a physics explosion and reset it.
    MAX_SETTLE_DISPLACEMENT = 5.0

    def _release_ag(self):
        """Clear assisted-grasp registration and internal grasped_obj.

        Saves the object's pre-release position so that _recover_if_flew()
        can restore it if physics sends it flying.
        """
        arm = self.robot.default_arm
        obj = self._grasped_obj
        if obj is not None:
            self._pre_release_pos = obj.get_position_orientation()[0].clone()
            self._pre_release_obj = obj
        else:
            self._pre_release_pos = None
            self._pre_release_obj = None
        self._grasped_obj = None

    def _recover_if_flew(self):
        """Check if the most recently released object flew away and reset it.

        Should be called after _settle_robot() following a _release_ag().
        Returns True if the object was recovered.
        """
        obj = getattr(self, "_pre_release_obj", None)
        saved_pos = getattr(self, "_pre_release_pos", None)
        if obj is None or saved_pos is None:
            return False
        try:
            cur_pos = obj.get_position_orientation()[0]
            if torch.isnan(cur_pos).any():
                displacement = float("inf")
            else:
                displacement = torch.norm(cur_pos - saved_pos).item()
        except Exception:
            displacement = float("inf")

        if displacement > self.MAX_SETTLE_DISPLACEMENT:
            obj.set_position_orientation(position=saved_pos)
            obj.keep_still()
            og.sim.step()
            self._pre_release_obj = None
            self._pre_release_pos = None
            return True

        self._pre_release_obj = None
        self._pre_release_pos = None
        return False

    def _check_and_reset_object(self, obj, saved_pos):
        """Reset obj to saved_pos if it flew away during physics settle."""
        try:
            cur_pos = obj.get_position_orientation()[0]
            if torch.isnan(cur_pos).any():
                displacement = float("inf")
            else:
                displacement = torch.norm(cur_pos - saved_pos).item()
        except Exception:
            displacement = float("inf")

        if displacement > self.MAX_SETTLE_DISPLACEMENT:
            obj.set_position_orientation(position=saved_pos)
            obj.keep_still()
            og.sim.step()
            return True
        return False

    # ------------------------------------------------------------------
    # Symbolic primitives — navigate / grasp / release
    # ------------------------------------------------------------------

    def _find_nearest_fixed_object(self, obj):
        """Find the nearest fixed-base object to the given object."""
        obj_pos = obj.get_position_orientation()[0]
        best, best_dist = None, float('inf')
        for scene_obj in self.env.scene.objects:
            if not getattr(scene_obj, 'fixed_base', False):
                continue
            if scene_obj.category in ("floors", "ceilings", "carpet", "ground", "roof", "walls", "agent"):
                continue
            try:
                so_pos = scene_obj.get_position_orientation()[0]
                d = torch.norm(obj_pos[:2] - so_pos[:2]).item()
                if d < best_dist:
                    best, best_dist = scene_obj, d
            except Exception:
                continue
        return best

    def _eib_navigate_to(self, target_obj):
        """Teleport robot near the target object, facing it.

        If target is a movable object, navigate to the nearest fixed object instead.
        """
        # --- ORIGINAL (rollback: uncomment below, remove the if-block above) ---
        # if not target_obj.fixed_base:
        #     raise ActionPrimitiveError(
        #         ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
        #         f"{target_obj.name} is not a furniture or appliance. Navigate only to fixed objects.",
        #         {"target": target_obj.name},
        #     )
        # --- END ORIGINAL ---
        if not target_obj.fixed_base:
            nearest = self._find_nearest_fixed_object(target_obj)
            if nearest is not None:
                target_obj = nearest
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
        offset_pos = target_pos.clone()
        offset_pos[0] -= direction[0] * 1.0
        offset_pos[1] -= direction[1] * 1.0
        offset_pos[2] = robot_pos[2]  # keep robot z

        # Yaw angle facing target
        yaw = torch.atan2(direction[1], direction[0])
        ori = torch.tensor([0.0, 0.0, torch.sin(yaw / 2), torch.cos(yaw / 2)])

        self.robot.set_position_orientation(position=offset_pos, orientation=ori)
        self.robot.keep_still()

        # Update anchored position after teleport
        self._anchored_pos = offset_pos.clone()
        self._anchored_ori = ori.clone()

        yield from self._settle_robot()

    def _eib_grasp(self, target_obj):
        """Symbolically grasp: teleport object to eef. Track manually, no AG constraints."""
        # Record the container the object is being grasped from (for camera).
        # get_container() may fail for non-particle objects; gracefully fallback.
        try:
            self._grasp_container = get_container(target_obj, self.env)
        except (AttributeError, TypeError):
            self._grasp_container = None
        if isinstance(target_obj, BaseSystem):
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"{target_obj.name} is a particle system and cannot be grasped directly.",
                {"target_object": target_obj.name},
            )
        if self._grasped_obj is not None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Hand is full (holding {self._grasped_obj.name}). Release first.",
                {"held_object": self._grasped_obj.name},
            )
        self._check_proximity(target_obj)

        arm = self.robot.default_arm
        # Teleport object to end-effector position
        eef_pos = self.robot.get_eef_position(arm)
        target_obj.set_position_orientation(position=eef_pos)
        # Move objects pierced through this one (e.g. nail in carton)
        self._sync_pierced_to(target_obj)
        # Track in our own field only — do NOT set _ag_obj_in_hand to avoid
        # _handle_assisted_grasping → _release_grasp → KeyError on missing ag_joint_prim_path.
        self._grasped_obj = target_obj

        yield from self._settle_robot()

    def _eib_release(self):
        """Detach held object from robot's hand."""
        # Track the object being released so camera can show it
        if self._grasped_obj is not None:
            self._tracking_object = self._grasped_obj
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Not holding anything.",
            )
        self._release_ag()
        yield from self._settle_robot()
        self._recover_if_flew()

    # ------------------------------------------------------------------
    # Open / Close
    # ------------------------------------------------------------------

    def _open(self, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref
        self._check_proximity(target_obj)
        yield from self._open_or_close(target_obj, should_open=True)

    def _close(self, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref
        self._check_proximity(target_obj)
        yield from self._open_or_close(target_obj, should_open=False)

    def _open_or_close(self, target_obj, should_open):
        if object_states.Open not in target_obj.states:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not openable.",
                {"target object": target_obj.name},
            )

        if should_open == target_obj.states[object_states.Open].get_value():
            return

        if should_open is True:
            check_toggle_off_before_open(target_obj)

        inside_placements = get_placement_objects(target_obj, self.env, object_states.Inside)

        # Save positions of inside objects before opening (door physics can launch them)
        saved_poses = {}
        if inside_placements and should_open:
            for placement in inside_placements:
                obj = placement.object
                if obj == target_obj:
                    continue
                saved_poses[obj] = obj.get_position_orientation()

        # Save robot pose — door physics can push the robot and cause NaN orientation
        robot_pos, robot_ori = self.robot.get_position_orientation()

        target_obj.states[object_states.Open].set_value(should_open, fully=True)

        # Immediately re-pin robot before any physics step to prevent NaN
        self.robot.set_position_orientation(position=robot_pos, orientation=robot_ori)
        self.robot.keep_still()
        # Use _no_op (1 step) instead of _settle_robot (3 steps) to avoid
        # CUDA error 700 on complex articulations like dishwashers
        yield from self._no_op()

        # Restore inside objects to their pre-open positions
        if saved_poses:
            for obj, (pos, ori) in saved_poses.items():
                obj.set_position_orientation(position=pos, orientation=ori)
            # Re-pin robot again after restoring objects
            self.robot.set_position_orientation(position=robot_pos, orientation=robot_ori)
            self.robot.keep_still()
            yield from self._no_op()

        if target_obj.states[object_states.Open].get_value() != should_open:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.POST_CONDITION_ERROR,
                "The object did not open or close as expected. Maybe try again",
                {"target object": target_obj.name, "is it currently open": target_obj.states[object_states.Open].get_value()},
            )

    # ------------------------------------------------------------------
    # Toggle
    # ------------------------------------------------------------------

    def _toggle_on(self, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref
        self._check_proximity(target_obj)
        yield from self._toggle(target_obj, value=True)

    def _toggle_off(self, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref
        self._check_proximity(target_obj)
        yield from self._toggle(target_obj, value=False)

    def _toggle(self, target_obj, value):
        if object_states.ToggledOn not in target_obj.states:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not toggleable.",
                {"target object": target_obj.name},
            )

        if target_obj.states[object_states.ToggledOn].get_value() == value:
            return

        if value is True:
            check_close_before_toggle_on(target_obj)

        target_obj.states[object_states.ToggledOn].set_value(value)
        yield from self._no_op()

        if target_obj.states[object_states.ToggledOn].get_value() != value:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.POST_CONDITION_ERROR,
                "The object did not toggle as expected - maybe try again",
                {
                    "target object": target_obj.name,
                    "is it currently toggled on": target_obj.states[object_states.ToggledOn].get_value(),
                },
            )

    # ------------------------------------------------------------------
    # Place
    # ------------------------------------------------------------------

    def _place_on_top(self, target_obj, surface, **kwargs):
        # self._tracking_object = surface  # now set in apply_ref
        if not kwargs.get("skip_check", False):
            if self._grasped_obj is None:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    "Not holding anything. Grasp an object first.",
                )
            self._check_proximity(surface)
            self._release_ag()
        yield from self._place_with_predicate(target_obj, surface, object_states.OnTop, **kwargs)
        # Ensure placed object stays within reach of the robot
        self._ensure_reachable(target_obj, surface)

    def _ensure_reachable(self, target_obj, surface, max_dist=1.5):
        """If the placed object ended up too far from the robot, move it closer on the same surface."""
        robot_pos = self.robot.get_position_orientation()[0]
        obj_pos, obj_ori = target_obj.get_position_orientation()
        xy_dist = torch.norm(robot_pos[:2] - obj_pos[:2])

        if xy_dist <= max_dist:
            return

        # Compute a new XY position ~1.0m from robot, along the robot→object direction
        direction = (obj_pos[:2] - robot_pos[:2]) / xy_dist
        new_xy = robot_pos[:2] + direction * 1.0

        # Clamp to surface AABB so the object stays on the surface
        surf_aabb_lo, surf_aabb_hi = surface.aabb
        new_xy[0] = torch.clamp(new_xy[0], float(surf_aabb_lo[0]) + 0.05, float(surf_aabb_hi[0]) - 0.05)
        new_xy[1] = torch.clamp(new_xy[1], float(surf_aabb_lo[1]) + 0.05, float(surf_aabb_hi[1]) - 0.05)

        new_pos = obj_pos.clone()
        new_pos[0] = new_xy[0]
        new_pos[1] = new_xy[1]
        target_obj.set_position_orientation(position=new_pos, orientation=obj_ori)
        target_obj.keep_still()

    def _place_inside(self, target_obj, container, **kwargs):
        # self._tracking_object = container  # now set in apply_ref
        if not kwargs.get("skip_check", False):
            if self._grasped_obj is None:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    "Not holding anything. Grasp an object first.",
                )
            self._check_proximity(container)
            self._release_ag()
        yield from self._place_with_predicate(target_obj, container, object_states.Inside, **kwargs)

    def _sample_on_top_heat_source(self, target_obj, heat_source):
        heating_element = heat_source.states[object_states.HeatSourceOrSink].link
        heating_element_positions = heating_element.get_position_orientation()[0] + torch.tensor([0, 0, 0.1])
        target_obj.set_position_orientation(position=heating_element_positions)
        target_obj.keep_still()
        saved_pos = heating_element_positions.clone()
        yield from self._settle_robot()
        self._check_and_reset_object(target_obj, saved_pos)

    def _sample_placement_with_predicate(self, target_obj, placement_obj, predicate):
        placement_obj_pose = placement_obj.get_position_orientation()

        attempts = 0
        while attempts < 5:
            attempts += 1
            try:
                predicated_pose = self._sample_pose_with_object_and_predicate(
                    predicate, target_obj, placement_obj,
                )
            except Exception as e:
                continue

            target_obj.set_position_orientation(*predicated_pose)
            target_obj.keep_still()
            saved_pos = predicated_pose[0].clone()
            yield from self._settle_robot()
            # Recover if target flew away during settle
            self._check_and_reset_object(target_obj, saved_pos)

            if target_obj.states[predicate].get_value(placement_obj):
                break
            else:
                placement_obj.set_position_orientation(*placement_obj_pose)
                placement_obj.keep_still()
                yield from self._settle_robot()

    def _place_with_predicate(self, target_obj, placement_obj, predicate, skip_check=False):
        if isinstance(target_obj, BaseSystem) and is_visual_or_physical_particle_system(target_obj.scene, target_obj):
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Cannot place system to desired position, perhaps place its container like bottle to the position",
                {"system (target object)": target_obj.name},
            )

        if predicate == object_states.OnTop and is_cloth_place_on_other(target_obj, placement_obj):
            predicate = object_states.Overlaid
        if predicate not in [object_states.OnTop, object_states.Inside, object_states.Overlaid]:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Only support place the target object OnTop, OverLaid or Inside the placement object.",
                {"provided_predicate": predicate.__class__.__name__},
            )

        if not skip_check:
            # Skip the "open container first" check when the robot is already
            # holding the target object — its Inside predicate is stale.
            if self._grasped_obj is None or self._grasped_obj != target_obj:
                check_open_before_grasp(target_obj, self.env)
            if predicate == object_states.Inside:
                check_open_before_placement(placement_obj)

        attachments = capture_attachments(target_obj, self.env)

        has_heat = object_states.HeatSourceOrSink in placement_obj.states

        if has_heat and predicate == object_states.OnTop and \
                not placement_obj.states[object_states.HeatSourceOrSink].requires_inside:
            yield from self._sample_on_top_heat_source(target_obj, placement_obj)

        elif predicate == object_states.Overlaid:
            placement_pose = placement_obj.get_position_orientation()[0]
            position = placement_pose + torch.tensor([0, 0, 0.1])
            target_obj.set_position_orientation(position=position)
            yield from self._settle_robot()

        else:
            yield from self._sample_placement_with_predicate(target_obj, placement_obj, predicate)

            if not target_obj.states[predicate].get_value(placement_obj):
                if predicate == object_states.OnTop:
                    placement_pose = placement_obj.get_position_orientation()[0]
                    position = placement_pose + torch.tensor([0, 0, 0.1])
                else:
                    placement_obj_center = placement_obj.get_base_aligned_bbox()[0]
                    position = placement_obj_center

                target_obj.set_position_orientation(position=position)
                target_obj.keep_still()
                yield from self._settle_robot()

        if attachments:
            recover_attachments(attachments)
            yield from self._settle_robot()

        error = ActionPrimitiveError(
            ActionPrimitiveError.Reason.EXECUTION_ERROR,
            "Failed to place target object at the desired place (probably dropped).",
            {"dropped object": target_obj.name, "placement object": placement_obj.name, "predicate": predicate.__class__.__name__},
        )
        if predicate == object_states.OnTop:
            adjacency = target_obj.states[object_states.VerticalAdjacency].get_value()
            if not placement_obj in adjacency.negative_neighbors or placement_obj in adjacency.positive_neighbors:
                raise error
        elif predicate == object_states.Inside and not target_obj.states[predicate].get_value(placement_obj):
            raise error
        elif predicate == object_states.Overlaid and not target_obj.states[object_states.Touching].get_value(placement_obj):
            raise error

    # ------------------------------------------------------------------
    # Wipe
    # ------------------------------------------------------------------

    def _wipe(self, target_obj, cleaning_tool):
        self._tracking_object = target_obj
        self._check_proximity(target_obj)
        if object_states.ParticleRemover not in cleaning_tool.states:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The cleaning tool is not a particle remover.",
                {"cleaning tool": cleaning_tool.name},
            )

        covered_systems = get_covered_systems(target_obj)
        if covered_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not coverable by any particles, so there is no need to wipe it.",
                {"target object": target_obj.name},
            )

        check_open_before_grasp(target_obj, self.env)
        check_open_before_grasp(cleaning_tool, self.env)

        if not covered_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not covered by any particles.",
                {"target object": target_obj.name},
            )

        supported_systems = get_supported_systems(
            cleaning_tool, covered_systems, object_states.ParticleRemover,
        )
        if not supported_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is covered only by particles that this cleaning tool cannot remove.",
                {
                    "target object": target_obj.name,
                    "cleaning tool": cleaning_tool.name,
                    "particles the target object is covered by": sorted(x.name for x in covered_systems),
                    "particles the cleaning tool can remove": sorted(
                        [x for x in cleaning_tool.states[object_states.ParticleRemover].conditions.keys()]
                    ),
                },
            )

        removed_systems = get_modified_systems(
            cleaning_tool, supported_systems, object_states.ParticleRemover,
        )
        if not removed_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is covered by some particles that this cleaning tool can normally remove, but needs to be in a different state to do so.",
                {
                    "target object": target_obj.name,
                    "cleaning tool": cleaning_tool.name,
                    "particles the target object is covered by": sorted(x.name for x in covered_systems),
                },
            )

        MAX_WIPE_NUMS = 3
        for i in range(MAX_WIPE_NUMS):
            for system in removed_systems:
                target_obj.states[object_states.Covered].set_value(system, False)
                yield from self._settle_robot()
            if not get_covered_systems(target_obj):
                break

    # ------------------------------------------------------------------
    # Cut
    # ------------------------------------------------------------------

    def _cut(self, target_obj, cutting_tool):
        self._tracking_object = target_obj
        self._check_proximity(target_obj)
        if "slicer" not in cutting_tool._abilities:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The cutting tool cannot slice object.",
                {"cutting tool": cutting_tool.name},
            )

        if "sliceable" not in target_obj._abilities and "diceable" not in target_obj._abilities:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not sliceable or diceable.",
                {"target object": target_obj.name},
            )

        check_open_before_grasp(target_obj, self.env)
        check_open_before_grasp(cutting_tool, self.env)

        added_obj_attrs, removed_objs = [], []
        (slicing_rule,) = [
            rule
            for rule in target_obj.scene.transition_rule_api.active_rules
            if isinstance(rule, SlicingRule)
        ]
        output = slicing_rule.transition({"sliceable": [target_obj]})

        added_obj_attrs += output.add
        removed_objs += output.remove
        target_obj.scene.transition_rule_api.execute_transition(
            added_obj_attrs=added_obj_attrs, removed_objs=removed_objs,
        )
        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Soak
    # ------------------------------------------------------------------

    def _soak_with_fluid_systems(self, target_obj, systems):
        supported_systems = get_supported_systems(
            target_obj, systems, object_states.ParticleRemover,
        )
        if not supported_systems:
            return None

        removed_systems = get_modified_systems(
            target_obj, supported_systems, object_states.ParticleRemover,
        )
        if not removed_systems:
            return None

        return removed_systems

    def _soak_under(self, target_obj, fluid_source):
        # self._tracking_object = fluid_source  # now set in apply_ref (args[-1])
        self._check_proximity(target_obj)
        if object_states.Saturated not in target_obj.states:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The currently grasped object cannot soak particles.",
                {"object in hand": target_obj.name},
            )

        check_open_before_grasp(target_obj, self.env)

        produced_systems = get_produced_systems(fluid_source)
        if produced_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid source is not a particle producer, so you can not soak target object.",
                {"fluid source": fluid_source.name},
            )
        if not produced_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid source currently does not produce particles, may be some conditions for producing particles not met, e.g., the fluid source should be toggled on.",
                {"fluid source": fluid_source.name},
            )

        removed_produced_systems = self._soak_with_fluid_systems(target_obj, produced_systems)
        if removed_produced_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object cannot soak with particles from fluid source, maybe target object cannot support the particles or saturation reaches upper limit",
                {
                    "target object": target_obj.name,
                    "fluid source": fluid_source.name,
                    "particles the target object can soak:": sorted(
                        [x for x in target_obj.states[object_states.ParticleRemover].conditions.keys()]
                    ),
                    "particles the fluid source produces": sorted(x.name for x in produced_systems) if produced_systems else None,
                },
            )

        for system in removed_produced_systems:
            target_obj.states[object_states.Saturated].set_value(system, True)

        yield from self._settle_robot()

    def _soak_inside(self, target_obj, fluid_container):
        # self._tracking_object = fluid_container  # now set in apply_ref (args[-1])
        self._check_proximity(target_obj)
        if object_states.Saturated not in target_obj.states:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The currently grasped object cannot soak particles.",
                {"target object": target_obj.name},
            )

        check_open_before_grasp(target_obj, self.env)
        check_open_before_grasp(fluid_container, self.env)

        contained_systems = get_contained_systems(fluid_container)
        if contained_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid container is not a particle container, so you can not soak target object.",
                {"fluid container": fluid_container.name},
            )

        if not contained_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid source currently does not contain any particles.",
                {"fluid container": fluid_container.name},
            )

        removed_contained_systems = self._soak_with_fluid_systems(target_obj, contained_systems)
        if removed_contained_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object cannot soak with particles from fluid container, maybe target object cannot support the particles or saturation reaches upper limit",
                {
                    "target object": target_obj.name,
                    "fluid container": fluid_container.name,
                    "particles the target object can soak:": sorted(
                        [x for x in target_obj.states[object_states.ParticleRemover].conditions.keys()]
                    ),
                    "particles in the fluid container": sorted(x.name for x in contained_systems) if contained_systems else None,
                },
            )

        for system in removed_contained_systems:
            target_obj.states[object_states.Saturated].set_value(system, True)

        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Fill / Pour
    # ------------------------------------------------------------------

    def _fill_with(self, target_obj, fluid_source):
        self._tracking_object = target_obj
        self._check_proximity(target_obj)
        contained_systems = get_contained_systems(target_obj)
        if contained_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not fillable by particles, so you can not fill anything in it.",
                {"target object": target_obj.name},
            )

        check_open_before_grasp(target_obj, self.env)

        produced_systems = get_produced_systems(fluid_source)
        if produced_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid source is not a particle producer, so you can not fill target object.",
                {"fluid source": fluid_source.name},
            )
        if not produced_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid source currently does not produce any particles, may be some conditions for producing particles not met, e.g., the fluid source should be toggled on.",
                {"fluid source": fluid_source.name},
            )

        for system in produced_systems:
            target_obj.states[object_states.Filled].set_value(system, True)
            yield from self._settle_robot()

    def _pour_into(self, fluid_container, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])
        self._check_proximity(target_obj)
        contained_systems = get_contained_systems(target_obj)
        if contained_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not fillable by particles, so you can not fill anything in it.",
                {"target object": target_obj.name},
            )

        check_open_before_grasp(target_obj, self.env)
        check_open_before_grasp(fluid_container, self.env)

        contained_systems = get_contained_systems(fluid_container)
        if contained_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid container is not a particle container, so you can not fill target object.",
                {"fluid container": fluid_container.name},
            )
        if not contained_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The fluid container currently does not contain any particles.",
                {"fluid container": fluid_container.name},
            )

        for system in contained_systems:
            target_obj.states[object_states.Filled].set_value(system, True)
            yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Spread
    # ------------------------------------------------------------------

    def _spread(self, fluid_container, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])
        self._check_proximity(target_obj)

        # Precondition: target must be on a rubber_mat to prevent sliding during spread
        stabilized = False
        if object_states.OnTop in target_obj.states:
            for obj in self.env.scene.objects:
                if getattr(obj, "category", None) == "rubber_mat":
                    if target_obj.states[object_states.OnTop].get_value(obj):
                        stabilized = True
                        break
        if not stabilized:
            # Find what surface the target is currently on
            surface_name = None
            if object_states.OnTop in target_obj.states:
                for obj in self.env.scene.objects:
                    if obj.name != target_obj.name and target_obj.states[object_states.OnTop].get_value(obj):
                        surface_name = obj.name
                        break
            if surface_name:
                msg = f"SPREAD failed: {target_obj.name} slid on {surface_name} during spreading."
                # msg = (f"SPREAD failed: {target_obj.name} slid on {surface_name} during spreading. "
                #        f"The surface is too slippery to hold {target_obj.name} in place.")
            else:
                msg = f"SPREAD failed: {target_obj.name} slid during spreading."
                # msg = (f"SPREAD failed: {target_obj.name} slid during spreading. "
                #        f"The surface is too slippery to hold {target_obj.name} in place.")
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.EXECUTION_ERROR,
                msg,
                {"target_object": target_obj.name},
            )

        # Case 1: fluid_container is itself a particle system (e.g., melted__butter future substance)
        if isinstance(fluid_container, BaseSystem):
            # Ensure system is initialized (force_init handles uninitialized future substances)
            fluid_container = self.env.scene.get_system(fluid_container.name, force_init=True)

            # Validate both the USD Scope prim and the PhysX particle system prim.
            # PhysX may GC the particle system prim between steps if it has 0 particles.
            scope_prim = og.sim.stage.GetPrimAtPath(fluid_container.prim_path)
            physx_prim = og.sim.stage.GetPrimAtPath(fluid_container.system_prim_path)
            if (not scope_prim or not scope_prim.IsValid() or
                    not physx_prim or not physx_prim.IsValid()):
                log.warning("System prim for %s invalidated, re-initializing", fluid_container.name)
                try:
                    self.env.scene.system_registry.remove(fluid_container)
                except Exception:
                    pass
                fluid_container.initialized = False
                fluid_container = self.env.scene.get_system(fluid_container.name, force_init=True)

            yield from self._settle_robot()

            for attempt in range(3):
                # Remove any partial instancer scope left by a previous failed attempt.
                inst_name = fluid_container.particle_instancer_idn_to_name(
                    idn=fluid_container.default_instancer_idn
                )
                scope_path = f"{fluid_container.prim_path}/{inst_name}"
                if og.sim.stage.GetPrimAtPath(scope_path):
                    og.sim.stage.RemovePrim(scope_path)

                try:
                    if target_obj.prim_type != PrimType.CLOTH:
                        target_obj.states[object_states.Covered].set_value(fluid_container, True)
                    else:
                        target_obj.states[object_states.Saturated].set_value(fluid_container, True)
                    break  # success
                except (RuntimeError, AssertionError):
                    if attempt < 2:
                        yield from self._settle_robot()
                        continue
                    raise ActionPrimitiveError(
                        ActionPrimitiveError.Reason.EXECUTION_ERROR,
                        "Failed to spread fluid after retries. System may not be properly initialized.",
                        {"fluid_container": fluid_container.name},
                    )

            yield from self._settle_robot()
            return

        # Case 2: fluid_container is a physical object — look for contained particles
        contained_systems = get_contained_systems(fluid_container)
        if contained_systems is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The current container object is not fillable by particles, so you can not use it to spread",
                {"target object": fluid_container.name},
            )
        if not contained_systems:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The current container object does not contain any particles.",
                {"target object": fluid_container.name},
            )

        check_open_before_grasp(fluid_container, self.env)
        check_open_before_grasp(target_obj, self.env)

        for system in contained_systems:
            if target_obj.prim_type != PrimType.CLOTH:
                target_obj.states[object_states.Covered].set_value(system, True)
            else:
                target_obj.states[object_states.Saturated].set_value(system, True)
            yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    # Minimum mass (kg) an object must have to stabilize a ruler for drawing.
    RULER_STABILIZE_MIN_MASS_KG = 0.1

    def _draw(self, drawing_tool, target_obj):
        """Draw on *target_obj* using *drawing_tool* (e.g. pen on paper).

        The action always succeeds if the robot is holding a writing tool.
        However, ink (Covered state) is only applied when a ruler is on the
        paper AND a sufficiently heavy object stabilizes the ruler — i.e. a
        straight line is drawn.  Otherwise the action succeeds but the goal
        condition (straight line) remains unsatisfied.
        """
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])
        self._check_proximity(target_obj)

        # --- Pre-condition: robot must be holding a writing instrument ---
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "DRAW failed: you are not holding anything. Grasp a pen or pencil first.",
                {"target_object": target_obj.name},
            )

        held_category = getattr(self._grasped_obj, "category", "")
        if held_category not in ("pen", "pencil", "colored_pencil"):
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"DRAW failed: you are holding '{self._grasped_obj.name}' which is not a writing tool. "
                "Grasp a pen or pencil first.",
                {"held_object": self._grasped_obj.name},
            )

        # --- Check 1: is there a ruler on the paper? ---
        ruler_on_paper = None
        for obj in self.env.scene.objects:
            if getattr(obj, "category", None) == "ruler":
                if object_states.OnTop in obj.states and obj.states[object_states.OnTop].get_value(target_obj):
                    ruler_on_paper = obj
                    break

        if ruler_on_paper is None:
            # No ruler → action succeeds but no Covered state (line not straight)
            self._custom_success_feedback = "Drew a curvy line on the paper."
            yield from self._settle_robot()
            return

        # --- Check 2: is there a heavy-enough object on the ruler? ---
        stabilized = False
        if object_states.OnTop in ruler_on_paper.states:
            for obj in self.env.scene.objects:
                if obj.name in (ruler_on_paper.name, target_obj.name):
                    continue
                if object_states.OnTop in obj.states and obj.states[object_states.OnTop].get_value(ruler_on_paper):
                    obj_mass = obj.mass if hasattr(obj, "mass") else 0.0
                    if obj_mass >= self.RULER_STABILIZE_MIN_MASS_KG:
                        stabilized = True
                        break

        if not stabilized:
            # Ruler present but not held down → action succeeds but no Covered state
            self._custom_success_feedback = "Drew a curvy line on the paper."
            yield from self._settle_robot()
            return

        # --- All checks passed: straight line — generate ink on the paper ---
        if isinstance(drawing_tool, BaseSystem):
            ink_system = self.env.scene.get_system(drawing_tool.name, force_init=True)
        else:
            ink_system = drawing_tool
            if not isinstance(ink_system, BaseSystem):
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    f"DRAW failed: '{drawing_tool.name}' is not a valid ink/fluid system.",
                    {"drawing_tool": drawing_tool.name},
                )
            ink_system = self.env.scene.get_system(ink_system.name, force_init=True)

        yield from self._settle_robot()

        for attempt in range(3):
            inst_name = ink_system.particle_instancer_idn_to_name(
                idn=ink_system.default_instancer_idn
            )
            scope_path = f"{ink_system.prim_path}/{inst_name}"
            if og.sim.stage.GetPrimAtPath(scope_path):
                og.sim.stage.RemovePrim(scope_path)

            try:
                target_obj.states[object_states.Covered].set_value(ink_system, True)
                break
            except (RuntimeError, AssertionError):
                if attempt < 2:
                    yield from self._settle_robot()
                    continue
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.EXECUTION_ERROR,
                    "DRAW failed: could not generate ink on the paper after retries.",
                    {"ink_system": ink_system.name},
                )

        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Cook
    # ------------------------------------------------------------------

    def _cook_particle_system(self, target_system):
        container = get_container(target_system, self.env)
        if container is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target particle waiting for cooked should be contained in a container",
                {"target particle": target_system.name},
            )

        check_heat_source_before_cook(container, self.env)

        system_name = target_system.name
        cooked_system_name = f"cooked__{system_name}"
        cooked_system = get_cooked_system(cooked_system_name, self.env)
        if cooked_system is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Cannot cook target particle.",
                {"target particle": target_system.name},
            )

        contained_particles = container.states[object_states.ContainedParticles].get_value(target_system)
        in_volume_idx = torch.where(contained_particles.in_volume)[0]
        if len(in_volume_idx) < 1:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Container does not contain any target particles.",
                {"target particle": target_system.name, "container": container.name},
            )

        target_system.remove_particles(idxs=in_volume_idx)

        particle_positions = contained_particles.positions[in_volume_idx]
        cooked_system.generate_particles(positions=particle_positions)

        yield from self._settle_robot()

        cooked_system = find_task_related_object(
            self.env, cooked_system_name, retain_wrapper=True,
        )
        if not cooked_system.exists:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Fail to add cooked particles.",
                {"target system": target_system.name, "cooked system": cooked_system_name},
            )

    def _cook_non_particle_object(self, target_obj):
        heating_temperature = -1.0
        if object_states.Cooked in target_obj.states:
            heating_temperature = max(
                heating_temperature, target_obj.states[object_states.Cooked].cook_temperature,
            )
        if object_states.Heated in target_obj.states:
            heating_temperature = max(
                heating_temperature, target_obj.states[object_states.Heated].heat_temperature,
            )

        if heating_temperature < 0:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Target object is not cookable or heatable.",
                {"target object": target_obj.name},
            )
        heating_temperature = heating_temperature + 15

        check_heat_source_before_cook(target_obj, self.env)

        target_obj.states[object_states.Temperature].set_value(heating_temperature)
        target_obj.states[object_states.MaxTemperature].set_value(heating_temperature)
        yield from self._settle_robot()

        if not (
            (object_states.Cooked in target_obj.states and target_obj.states[object_states.Cooked].get_value())
            or (object_states.Heated in target_obj.states and target_obj.states[object_states.Heated].get_value())
        ):
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Target object is not cooked and heated.",
                {"target object": target_obj.name},
            )

    def _wait_for_cooked(self, target_obj):
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])
        if isinstance(target_obj, BaseSystem):
            yield from self._cook_particle_system(target_obj)
        else:
            if object_states.Cooked in target_obj.states:
                yield from self._cook_non_particle_object(target_obj)
            else:
                contained_systems = get_contained_systems(target_obj)
                if contained_systems:
                    for particle_system in contained_systems:
                        if hasattr(particle_system, "is_fluid") and particle_system.is_fluid:
                            yield from self._cook_particle_system(particle_system)

                placement_objects = get_placement_objects(target_obj, self.env)
                if placement_objects:
                    for placement_object in placement_objects:
                        if object_states.Cooked in placement_object.states:
                            yield from self._cook_non_particle_object(placement_object)

    # ------------------------------------------------------------------
    # Wash
    # ------------------------------------------------------------------

    def _wait_for_washed(self, wash_machine):
        # self._tracking_object = wash_machine  # now set in apply_ref (args[-1])
        if not (wash_machine.name.split("_")[0] == "washer" or wash_machine.name.split("_")[0] == "dishwasher"):
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Wait_for_washed api must input with a wash_machine named 'washer'.",
                {"target object": wash_machine.name},
            )

        if wash_machine.states[object_states.Open].get_value():
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The washer is still open so you are not able to toggle on to wash",
                {"target object": wash_machine.name},
            )

        if not wash_machine.states[object_states.ToggledOn].get_value():
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The washer is not toggled on so you are not able to wash",
                {"target object": wash_machine.name},
            )

        inside_placements = get_placement_objects(wash_machine, self.env, object_states.Inside)
        if not inside_placements:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "There are no objects inside the wash machine, so there is no need to wash",
                {"target object": wash_machine.name},
            )

        for inside_placement in inside_placements:
            inside_obj = inside_placement.object
            covered_systems = get_covered_systems(inside_obj)
            if covered_systems is None:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    "The target object inside the washer is not coverable by any particles, so there is no need to wipe it.",
                    {"target object": inside_obj.name},
                )
            if not covered_systems:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    "The target object inside the washer is not covered by any particles, so there is no need to wipe it.",
                    {"target object": inside_obj.name},
                )
            for system in covered_systems:
                inside_obj.states[object_states.Covered].set_value(system, False)
                yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Wait / Freeze
    # ------------------------------------------------------------------

    def _wait(self, target_obj=None):
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])
        if target_obj is not None and hasattr(target_obj, "states"):
            if object_states.Frozen in target_obj.states:
                target_obj.states[object_states.Frozen].set_value(False)
            if object_states.Heated in target_obj.states:
                target_obj.states[object_states.Heated].set_value(False)

        yield from self._settle_robot()

    def _wait_for_frozen(self, target_obj, refrigerator_obj):
        # self._tracking_object = refrigerator_obj  # now set in apply_ref (args[-1])
        if "fridge" not in refrigerator_obj.name:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The second argument should be a refrigerator",
                {"refrigerator_obj": refrigerator_obj.name},
            )

        if hasattr(target_obj, "states") and object_states.Frozen in target_obj.states:
            if target_obj.states[object_states.Inside].get_value(refrigerator_obj):
                target_obj.states[object_states.Frozen].set_value(True)
                yield from self._settle_robot()
            else:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    "The target object is not inside the refrigerator",
                    {"target_obj": target_obj.name},
                )
        else:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object has no frozen state to make it frozen",
                {"target_obj": target_obj.name},
            )

    # ------------------------------------------------------------------
    # Pierce / Hammer / Place Against
    # ------------------------------------------------------------------

    HEAVY_CATEGORIES = {
        "textbook", "brick", "vase", "pot", "jar", "dumbbell", "free_weight",
        "weight_bar", "mug", "can", "book", "stapler", "canister", "canned_food",
        "bookend", "fuel_can",
    }
    MIN_CONSTRAINTS_FOR_HAMMER = 3

    _intentional_constraints: dict = None

    def _get_intentional_constraints(self):
        if self._intentional_constraints is None:
            self._intentional_constraints = {}
        return self._intentional_constraints

    def _register_constraint(self, holder_name, constraining_obj_name, heavy=True):
        constraints = self._get_intentional_constraints()
        if holder_name not in constraints:
            constraints[holder_name] = {}
        constraints[holder_name][constraining_obj_name] = heavy

    def _remove_constraint(self, holder_name, constraining_obj_name):
        constraints = self._get_intentional_constraints()
        if holder_name in constraints:
            constraints[holder_name].pop(constraining_obj_name, None)

    def _get_constraint_info(self, holder_name):
        constraints = self._get_intentional_constraints()
        entries = constraints.get(holder_name, {})
        light_names = [name for name, is_heavy in entries.items() if not is_heavy]
        return len(entries), light_names

    def _pierce(self, target_obj, piercing_tool):
        """Pierce *target_obj* (e.g. carton) with *piercing_tool* (e.g. nail).
        All symbolic — no physics."""
        self._tracking_object = target_obj

        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "PIERCE failed: you are not holding anything. Grasp the piercing tool first.",
                {"target_object": target_obj.name},
            )
        if self._grasped_obj.name != piercing_tool.name:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"PIERCE failed: you are holding '{self._grasped_obj.name}', not '{piercing_tool.name}'.",
                {"held_object": self._grasped_obj.name, "expected": piercing_tool.name},
            )

        pierceable_categories = {"carton", "cardboard", "paper_sheet", "sheet"}
        soft_but_useless = {"sponge", "rubber_mat"}
        too_thick = {"plywood", "wood_plank", "cutting_board", "chopping_board"}
        target_cat = getattr(target_obj, "category", "")

        if target_cat in too_thick:
            self._custom_success_feedback = (
                f"You tried to pierce {target_obj.name}, but it is too thick. "
                f"The {piercing_tool.name} could not penetrate through it."
            )
            yield from self._settle_robot()
            return

        if target_cat == "sponge":
            self._custom_success_feedback = (
                f"You pierced {target_obj.name} with {piercing_tool.name}, but the sponge is too soft and squishy. "
                f"The {piercing_tool.name} slid right through and fell out the other side."
            )
            yield from self._settle_robot()
            return

        if target_cat not in pierceable_categories and target_cat not in soft_but_useless:
            self._custom_success_feedback = (
                f"You tried to pierce {target_obj.name}, but it is too hard and rigid. "
                f"The {piercing_tool.name} could not penetrate it."
            )
            yield from self._settle_robot()
            return

        is_weak_holder = target_cat in soft_but_useless

        if object_states.Pierced in piercing_tool.states:
            piercing_tool.states[object_states.Pierced].set_value(True)
            piercing_tool.states[object_states.Pierced].pierced_through = target_obj

        self._release_ag()

        # Teleport the piercing tool into the target (visual: nail pierced through)
        # The nail's long axis (pointy-to-head) is along its local X-axis.
        # We rotate it so the long axis aligns with the cardboard's thinnest
        # dimension (surface normal), with the tip pointing inward.
        try:
            aabb_lo, aabb_hi = target_obj.aabb
            nail_pos = ((aabb_lo + aabb_hi) / 2.0).clone()
            extents = aabb_hi - aabb_lo
            thin_dim = torch.argmin(extents).item()

            # Rotate nail's local X-axis → thin_dim direction (tip inward)
            # thin_dim 0 (X): nail already along X, just use identity
            # thin_dim 1 (Y): rotate 90° around Z  (X→Y)
            # thin_dim 2 (Z): rotate -90° around Y (X→Z, tip pointing down)
            s = 0.7071067811865476  # sin(45°) = cos(45°) = sqrt(2)/2
            if thin_dim == 0:
                nail_ori = torch.tensor([0.0, 0.0, 0.0, 1.0])  # identity
            elif thin_dim == 1:
                nail_ori = torch.tensor([0.0, 0.0, s, s])       # 90° around Z
            else:
                nail_ori = torch.tensor([0.0, -s, 0.0, s])      # -90° around Y

            # Offset nail so only the tip is inside the cardboard, head sticks out
            # Nail length ~0.054m; embed ~40% of tip
            try:
                nail_half_len = max(piercing_tool.aabb[1][0] - piercing_tool.aabb[0][0],
                                    piercing_tool.native_bbox[0].item()) / 2.0
            except Exception:
                nail_half_len = 0.027
            embed_depth = nail_half_len * 0.4
            nail_pos[thin_dim] += (nail_half_len - embed_depth)
        except Exception:
            nail_pos = target_obj.get_position_orientation()[0]
            nail_ori = torch.tensor([0.0, 0.0, 0.0, 1.0])

        piercing_tool.set_position_orientation(position=nail_pos, orientation=nail_ori)
        piercing_tool.keep_still()

        # Store relative pose (in parent's local frame) so sync preserves it
        # when cardboard is moved/rotated (e.g. PLACE_AGAINST)
        parent_pos, parent_ori = target_obj.get_position_orientation()
        if object_states.Pierced in piercing_tool.states:
            rel_pos, rel_ori = T.relative_pose_transform(nail_pos, nail_ori, parent_pos, parent_ori)
            piercing_tool.states[object_states.Pierced].pierce_rel_pos = rel_pos
            piercing_tool.states[object_states.Pierced].pierce_rel_ori = rel_ori

        self._custom_success_feedback = (
            f"Successfully pierced {piercing_tool.name} through {target_obj.name}. "
            f"The {piercing_tool.name} is now embedded in the {target_obj.name}."
        )
        yield from self._settle_robot()

    def _hammer(self, target_nail, hammer_tool):
        """Hammer *target_nail* using *hammer_tool*. All symbolic."""
        self._tracking_object = target_nail

        # 1. Must be holding the hammer
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "HAMMER failed: you are not holding anything. Grasp the hammer first.",
                {"target_nail": target_nail.name},
            )
        held_cat = getattr(self._grasped_obj, "category", "")
        if held_cat != "hammer" and self._grasped_obj.name != hammer_tool.name:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"HAMMER failed: you are holding '{self._grasped_obj.name}', not a hammer.",
                {"held_object": self._grasped_obj.name},
            )

        # 2. Nail must be pierced through something (i.e. held in place by a fixture)
        if object_states.Pierced not in target_nail.states or not target_nail.states[object_states.Pierced].get_value():
            self._custom_success_feedback = (
                f"You swung the hammer at {target_nail.name}, but the nail is not fixed in place "
                f"and is too unstable to be hammered. The nail flew away on impact. "
                f"You need to find a way to hold the nail steady before striking it."
            )
            return

        holder = target_nail.states[object_states.Pierced].pierced_through
        if holder is None:
            self._custom_success_feedback = (
                f"You struck {target_nail.name}, but it is not secured properly and the impact had no effect."
            )
            return

        # 3. Holder must be placed against a wall
        placed_against_wall = False
        wall_obj = None
        if object_states.PlacedAgainst in holder.states:
            for obj in self.env.scene.objects:
                cat = getattr(obj, "category", "")
                if cat in ("wall", "walls"):
                    if holder.states[object_states.PlacedAgainst].get_value(obj):
                        placed_against_wall = True
                        wall_obj = obj
                        break

        if not placed_against_wall:
            self._custom_success_feedback = (
                f"You struck {target_nail.name}, but there is no solid surface behind it to receive the nail. "
                f"The nail was not driven into anything."
            )
            return

        # 4. Holder must be constrained by heavy objects intentionally placed next to it
        total_count, light_names = self._get_constraint_info(holder.name)

        if total_count < self.MIN_CONSTRAINTS_FOR_HAMMER:
            self._custom_success_feedback = (
                f"You struck {target_nail.name}, but the {holder.name} slipped and toppled over from the impact. "
                f"The {holder.name} is not stable enough to withstand hammering."
            )
            return

        if light_names:
            light_str = ", ".join(light_names)
            self._custom_success_feedback = (
                f"You struck {target_nail.name}, but {light_str} was too light to hold the {holder.name} in place. "
                f"The {holder.name} toppled over in that direction from the impact."
            )
            return

        # All preconditions met
        if object_states.Nailed in target_nail.states:
            target_nail.states[object_states.Nailed].set_value(True)

        self._custom_success_feedback = (
            f"Successfully hammered {target_nail.name} into the wall through {holder.name}. "
            "The nail is now firmly secured."
        )

    def _place_against(self, surface):
        """Place the currently held object against *surface*. All symbolic."""
        # self._tracking_object = surface  # now set in apply_ref (args[-1])
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "PLACE_AGAINST failed: not holding anything. Grasp an object first.",
            )

        target_obj = self._grasped_obj

        # Small objects cannot stand upright against a wall
        small_categories = {"clout_nail", "nail", "pencil", "screw", "pin"}
        # Floppy/flexible objects cannot stand upright
        floppy_categories = {"rubber_mat", "sponge", "towel", "cloth"}
        target_cat = getattr(target_obj, "category", "")

        if target_cat in floppy_categories:
            self._release_ag()
            self._custom_success_feedback = (
                f"You tried to place {target_obj.name} against {surface.name}, "
                f"but it is too floppy and flexible to stand upright. "
                f"It sagged and collapsed onto the floor."
            )
            yield from self._settle_robot()
            return

        if target_cat in small_categories:
            self._release_ag()
            self._custom_success_feedback = (
                f"You tried to place {target_obj.name} against {surface.name}, "
                f"but it is too small and has no way to stay upright. "
                f"It slid down and fell to the ground."
            )
            yield from self._settle_robot()
            return

        self._release_ag()

        if object_states.PlacedAgainst in target_obj.states:
            target_obj.states[object_states.PlacedAgainst].set_value(surface, True)

        try:
            if object_states.NextTo in target_obj.states:
                target_obj.states[object_states.NextTo].set_value(surface, True)
        except NotImplementedError:
            pass

        self._custom_success_feedback = (
            f"Placed {target_obj.name} upright against {surface.name}."
        )
        yield from self._settle_robot()

    def _place_next_to(self, target_obj):
        """Place the currently held object next to *target_obj*. All symbolic."""
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "PLACE_NEXT_TO failed: not holding anything. Grasp an object first.",
            )

        placed_obj = self._grasped_obj
        placed_cat = getattr(placed_obj, "category", "")

        self._release_ag()

        # Register constraint — track whether it's heavy or light
        is_heavy = placed_cat in self.HEAVY_CATEGORIES
        self._register_constraint(target_obj.name, placed_obj.name, heavy=is_heavy)

        self._custom_success_feedback = (
            f"Placed {placed_obj.name} next to {target_obj.name}."
        )
        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # SWEEP — sweep breadcrumbs toward a target using a broom
    # ------------------------------------------------------------------

    SWEEPABLE_TOOL_CATEGORIES = {"broom", "brush"}

    def _sweep(self, target_obj):
        """Sweep breadcrumbs toward *target_obj* using the held broom.

        Two usage modes:
        1. SWEEP[floor_landing] — gather crumbs from the floor to the landing area.
        2. SWEEP[dustpan] — sweep gathered crumbs from the landing into the dustpan.
           Dustpan must be on stair_first_step for success; otherwise fails with
           physical-constraint feedback.
        """
        # self._tracking_object = target_obj  # now set in apply_ref (args[-1])

        # --- Pre-condition: must be holding a sweeping tool ---
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "SWEEP failed: you are not holding anything. Grasp a broom or brush first.",
                {"target_object": target_obj.name},
            )

        held_category = getattr(self._grasped_obj, "category", "")
        if held_category not in self.SWEEPABLE_TOOL_CATEGORIES:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"SWEEP failed: you are holding '{self._grasped_obj.name}' which is not a sweeping tool. "
                "Grasp a broom or brush first.",
                {"held_object": self._grasped_obj.name},
            )

        # --- Find breadcrumb particle system ---
        breadcrumb_system = None
        for system_name in ["breadcrumb"]:
            try:
                breadcrumb_system = self.env.scene.get_system(system_name, force_init=True)
                break
            except Exception:
                pass
        if breadcrumb_system is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.EXECUTION_ERROR,
                "SWEEP failed: no breadcrumb particle system found in the scene.",
                {"target_object": target_obj.name},
            )

        # --- Find which objects currently have breadcrumbs Covered ---
        covered_sources = []
        for obj in self.env.scene.objects:
            if object_states.Covered in obj.states:
                try:
                    if obj.states[object_states.Covered].get_value(breadcrumb_system):
                        covered_sources.append(obj)
                except Exception:
                    pass

        target_category = getattr(target_obj, "category", "")

        # --- Mode 2: SWEEP[dustpan] — final sweep into dustpan ---
        if target_category == "dustpan":
            dustpan_on_stair_step = False
            dustpan_next_to_support = False

            if object_states.OnTop in target_obj.states:
                for obj in self.env.scene.objects:
                    obj_cat = getattr(obj, "category", "")
                    if obj_cat == "stair_first_step":
                        if target_obj.states[object_states.OnTop].get_value(obj):
                            dustpan_on_stair_step = True
                            break

            if not dustpan_on_stair_step:
                support_cats = {
                    "walls", "wall", "table", "desk", "cabinet", "fridge",
                    "refrigerator", "countertop", "shelf", "bookshelf",
                }
                if object_states.NextTo in target_obj.states:
                    for obj in self.env.scene.objects:
                        obj_cat = getattr(obj, "category", "")
                        if obj_cat in support_cats:
                            try:
                                if target_obj.states[object_states.NextTo].get_value(obj):
                                    dustpan_next_to_support = True
                                    break
                            except Exception:
                                pass

                if dustpan_next_to_support:
                    # Method 1 check: is there a heavy object on top of the dustpan?
                    heavy_on_dustpan = False
                    heavy_cats = {"textbook", "stapler", "mug", "vase", "book", "pot", "kettle"}
                    for obj in self.env.scene.objects:
                        obj_cat = getattr(obj, "category", "")
                        if obj_cat in heavy_cats:
                            if object_states.OnTop in obj.states:
                                try:
                                    if obj.states[object_states.OnTop].get_value(target_obj):
                                        heavy_on_dustpan = True
                                        break
                                except Exception:
                                    pass

                    if not heavy_on_dustpan:
                        raise ActionPrimitiveError(
                            ActionPrimitiveError.Reason.EXECUTION_ERROR,
                            "SWEEP failed: breadcrumbs went under the dustpan because "
                            "the entrance was slightly lifted off the ground. "
                            "Try weighing down the dustpan with a heavy object.",
                            {"target_object": target_obj.name},
                        )
                    # else: Method 1 success — dustpan supported + weighed down
                else:
                    raise ActionPrimitiveError(
                        ActionPrimitiveError.Reason.EXECUTION_ERROR,
                        "SWEEP failed: the dustpan slid away because nothing was "
                        "supporting it from behind.",
                        {"target_object": target_obj.name},
                    )

            landing_source = None
            for src in covered_sources:
                if getattr(src, "category", "") == "floor_landing":
                    landing_source = src
                    break

            if landing_source is None:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.EXECUTION_ERROR,
                    "SWEEP failed: no breadcrumbs found near the dustpan area. "
                    "Gather them to the floor landing first.",
                    {"target_object": target_obj.name},
                )

            yield from self._settle_robot()
            landing_source.states[object_states.Covered].set_value(breadcrumb_system, False)

            for attempt in range(3):
                success = target_obj.states[object_states.Covered].set_value(breadcrumb_system, True)
                if success:
                    self._freeze_particle_physics(breadcrumb_system)
                    break
                if attempt < 2:
                    yield from self._settle_robot()
                    continue
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.EXECUTION_ERROR,
                    "SWEEP failed: could not deposit breadcrumbs onto the dustpan.",
                    {"target_object": target_obj.name},
                )

            self._custom_success_feedback = (
                "Successfully swept breadcrumbs into the dustpan."
            )
            return

        # --- Mode 1: SWEEP[floor_landing] — gather crumbs from floor to target ---
        floor_sources = [
            src for src in covered_sources
            if getattr(src, "category", "") == "floors"
        ]
        if not floor_sources:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.EXECUTION_ERROR,
                "SWEEP failed: no breadcrumbs found on the floor to sweep.",
                {"target_object": target_obj.name},
            )

        yield from self._settle_robot()

        for src in floor_sources:
            try:
                src.states[object_states.Covered].set_value(breadcrumb_system, False)
            except Exception:
                pass

        for attempt in range(3):
            success = target_obj.states[object_states.Covered].set_value(breadcrumb_system, True)
            if success:
                self._freeze_particle_physics(breadcrumb_system)
                break
            if attempt < 2:
                yield from self._settle_robot()
                continue
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.EXECUTION_ERROR,
                f"SWEEP failed: could not deposit breadcrumbs onto {target_obj.name}.",
                {"target_object": target_obj.name},
            )

        self._custom_success_feedback = (
            f"Swept breadcrumbs from the floor to {target_obj.name}."
        )

    # ------------------------------------------------------------------
    # TEAR — tear paper along a ruler
    # ------------------------------------------------------------------

    # Reuse RULER_STABILIZE_MIN_MASS_KG from symbolic primitives
    RULER_STABILIZE_MIN_MASS_KG = 0.1

    def _tear(self, target_obj):
        """Tear *target_obj* (paper) along a ruler.

        The action succeeds if the paper is accessible (grasped or nearby).
        The Torn state (clean straight tear) is only applied when a ruler
        is on a surface AND a sufficiently heavy object stabilizes the
        ruler.  Otherwise the action succeeds but the goal condition
        (straight tear) remains unsatisfied.
        """
        self._check_proximity(target_obj)

        # --- Check 1: is there a ruler on a surface? ---
        ruler_on_surface = None
        for obj in self.env.scene.objects:
            if getattr(obj, "category", None) == "ruler":
                if object_states.VerticalAdjacency in obj.states:
                    adj = obj.states[object_states.VerticalAdjacency].get_value()
                    if len(adj.negative_neighbors) > 0:
                        ruler_on_surface = obj
                        break

        if ruler_on_surface is None:
            self._custom_success_feedback = "Tore a jagged line on the paper."
            yield from self._settle_robot()
            return

        # --- Check 2: is there a heavy-enough object on the ruler? ---
        stabilized = False
        for obj in self.env.scene.objects:
            if obj.name in (ruler_on_surface.name, target_obj.name):
                continue
            if object_states.VerticalAdjacency in obj.states:
                adj = obj.states[object_states.VerticalAdjacency].get_value()
                is_on_ruler = ruler_on_surface in adj.negative_neighbors
                obj_mass = obj.mass if hasattr(obj, "mass") else 0.0
                if is_on_ruler and obj_mass >= self.RULER_STABILIZE_MIN_MASS_KG:
                    stabilized = True
                    break

        if not stabilized:
            self._custom_success_feedback = "Tore a jagged line — the ruler slid during tearing."
            yield from self._settle_robot()
            return

        # --- All checks passed: clean straight tear ---
        if object_states.Torn in target_obj.states:
            target_obj.states[object_states.Torn].set_value(True)
        else:
            from omnigibson.object_states.torn import Torn
            state_instance = Torn(target_obj)
            state_instance.initialize()
            target_obj.states[object_states.Torn] = state_instance
            target_obj.states[object_states.Torn].set_value(True)

        # --- Visual representation of the tear ---
        import os as _os
        tear_visual = _os.environ.get("TEAR_VISUAL", "")
        if tear_visual.upper() == "A":
            yield from self._tear_visual_a(target_obj, ruler_on_surface)
        elif tear_visual.upper() == "B":
            yield from self._tear_visual_b(target_obj)
        elif tear_visual.upper() == "C":
            yield from self._tear_visual_c(target_obj, ruler_on_surface)
        elif tear_visual.upper() == "D":
            yield from self._tear_visual_d(target_obj, ruler_on_surface)
        # else: no visual change (original behaviour)

        self._custom_success_feedback = "Tore a clean straight line along the ruler."
        yield from self._settle_robot()
        return

    # ------------------------------------------------------------------
    # Tear visual helpers
    # ------------------------------------------------------------------

    def _tear_visual_a(self, target_obj, ruler_obj):
        """Approach A: two torn pieces on the countertop.

        Reuse the original sheet as one half (reposition to one side of
        the ruler) and spawn a second piece on the other side.  A visible
        gap between the two pieces conveys 'torn along the ruler'.

        Note: Runtime ``obj.scale`` changes crash PhysX, so we keep the
        original at full size and spawn the second piece at full size too.
        The visual "tear" is communicated by the gap and slight rotation.
        """
        from omnigibson.objects import DatasetObject

        self._release_ag()

        # Find countertop surface
        countertop = None
        for obj in self.env.scene.objects:
            if getattr(obj, "category", "") == "countertop":
                countertop = obj
                break
        if countertop is None:
            yield from self._no_op()
            return

        ct_top_z = float(countertop.aabb[1][2])
        ruler_pos = ruler_obj.get_position_orientation()[0]
        rx, ry = float(ruler_pos[0]), float(ruler_pos[1])

        # Place original sheet on one side of the ruler (left, slight tilt)
        pos_left = torch.tensor([rx - 0.12, ry, ct_top_z + 0.005])
        ori_left = torch.tensor([0.0, 0.0, -0.05, 0.9987])
        ori_left = ori_left / ori_left.norm()
        target_obj.set_position_orientation(position=pos_left, orientation=ori_left)
        target_obj.keep_still()

        # Spawn second piece on the other side of the ruler (right, opposite tilt)
        obj_model = getattr(target_obj, "model", "paper_sheet")
        obj_category = getattr(target_obj, "category", "paper_sheet")

        piece2 = DatasetObject(
            name="torn_piece_right",
            category=obj_category,
            model=obj_model,
        )
        self.env.scene.add_object(piece2)
        og.sim.step()

        pos_right = torch.tensor([rx + 0.12, ry, ct_top_z + 0.005])
        ori_right = torch.tensor([0.01, 0.0, 0.06, 0.9981])
        ori_right = ori_right / ori_right.norm()
        piece2.set_position_orientation(position=pos_right, orientation=ori_right)
        piece2.keep_still()

        # Use PLACE_ON_TOP camera style for tear result
        self._tracking_object = target_obj
        self._last_action_name = 'PLACE_ON_TOP'

        yield from self._no_op()

    def _tear_visual_b(self, target_obj):
        """Approach B: release sheet onto countertop, spawn a smaller
        torn-off piece nearby.

        The original sheet stays at full size on the countertop.  A new
        smaller piece is spawned next to it — the 'torn-off scrap'.
        """
        from omnigibson.objects import DatasetObject

        self._release_ag()

        # Find countertop
        countertop = None
        for obj in self.env.scene.objects:
            if getattr(obj, "category", "") == "countertop":
                countertop = obj
                break
        if countertop is None:
            yield from self._no_op()
            return

        ct_top_z = float(countertop.aabb[1][2])
        ct_pos = countertop.get_position_orientation()[0]
        cx, cy = float(ct_pos[0]), float(ct_pos[1])

        # Place original sheet on the countertop
        target_obj.set_position_orientation(
            position=torch.tensor([cx, cy, ct_top_z + 0.005]),
            orientation=torch.tensor([0.0, 0.0, 0.0, 1.0]),
        )
        target_obj.keep_still()

        # Spawn a smaller torn-off scrap beside it
        obj_model = getattr(target_obj, "model", "paper_sheet")
        obj_category = getattr(target_obj, "category", "paper_sheet")
        orig_bb = target_obj.aabb_extent.clone()
        scrap_bb = orig_bb.clone()
        scrap_bb[0] = orig_bb[0] * 0.4  # narrower
        scrap_bb[1] = orig_bb[1] * 0.5  # shorter

        scrap = DatasetObject(
            name="torn_scrap",
            category=obj_category,
            model=obj_model,
            bounding_box=scrap_bb,
        )
        self.env.scene.add_object(scrap)
        og.sim.step()

        # Place scrap offset and slightly rotated
        scrap_pos = torch.tensor([cx + 0.15, cy + 0.05, ct_top_z + 0.005])
        scrap_ori = torch.tensor([0.0, 0.0, 0.17, 0.985])
        scrap_ori = scrap_ori / scrap_ori.norm()
        scrap.set_position_orientation(position=scrap_pos, orientation=scrap_ori)
        scrap.keep_still()

        # Use PLACE_ON_TOP camera style for tear result
        self._tracking_object = target_obj
        self._last_action_name = 'PLACE_ON_TOP'

        yield from self._no_op()

    def _tear_visual_c(self, target_obj, ruler_obj):
        """Approach C: release + reposition with twisted orientation.

        Release the sheet from the gripper, place it on the countertop near
        the ruler with a slightly twisted orientation to convey 'torn & dropped'.
        """
        self._release_ag()

        countertop = None
        for obj in self.env.scene.objects:
            if getattr(obj, "category", "") == "countertop":
                countertop = obj
                break

        if countertop is not None:
            ct_top_z = float(countertop.aabb[1][2])
            ruler_pos = ruler_obj.get_position_orientation()[0]

            drop_pos = torch.tensor([
                float(ruler_pos[0]) + 0.10,
                float(ruler_pos[1]) - 0.05,
                ct_top_z + 0.005,
            ])
            twisted_ori = torch.tensor([0.02, 0.01, 0.12, 0.9926])
            twisted_ori = twisted_ori / twisted_ori.norm()

            target_obj.set_position_orientation(position=drop_pos, orientation=twisted_ori)
            target_obj.keep_still()

        # Use PLACE_ON_TOP camera style for tear result
        self._tracking_object = target_obj
        self._last_action_name = 'PLACE_ON_TOP'

        yield from self._no_op()

    def _tear_visual_d(self, target_obj, ruler_obj):
        """Approach D: shrink sheet along the ruler's tear line.

        Compute the ruler's short-edge axis and reduce the sheet along
        that axis to ``(ruler_short + sheet_parallel) / 2``.  This makes
        the sheet look like it was torn along the ruler's long edge.

        Since runtime ``obj.scale`` crashes PhysX, we hide the original
        and spawn a replacement with the adjusted ``bounding_box``.
        """
        from omnigibson.objects import DatasetObject

        if self._grasped_obj is not None:
            self._release_ag()

        # --- Snapshot all scene object poses BEFORE any changes ---
        _SKIP_CATS = {"walls", "floors", "ceilings", "carpet", "agent",
                      "roof", "ground"}
        pose_snapshot = {}
        for obj in self.env.scene.objects:
            cat = getattr(obj, "category", "").lower()
            if cat in _SKIP_CATS or obj.name == target_obj.name:
                continue
            try:
                pos, ori = obj.get_position_orientation()
                pose_snapshot[obj.name] = (pos.clone(), ori.clone())
            except Exception:
                pass

        # --- Measure ruler and sheet extents ---
        ruler_ext = ruler_obj.aabb_extent.clone()   # (x, y, z)
        sheet_ext = target_obj.aabb_extent.clone()
        sheet_pos = target_obj.get_position_orientation()[0].clone()
        sheet_ori = target_obj.get_position_orientation()[1].clone()

        # Ruler short edge = min of x, y; determine which axis
        if ruler_ext[0] < ruler_ext[1]:
            short_axis = 0  # ruler is narrow along X
        else:
            short_axis = 1  # ruler is narrow along Y

        ruler_short = float(ruler_ext[short_axis])
        sheet_parallel = float(sheet_ext[short_axis])

        # New sheet size along the short axis
        new_size = (ruler_short + sheet_parallel) / 2.0

        # Build new bounding box
        new_bb = sheet_ext.clone()
        new_bb[short_axis] = new_size

        # Hide original underground
        target_obj.set_position_orientation(
            position=torch.tensor([0.0, 0.0, -10.0]))
        target_obj.keep_still()

        # Also move snapshotted objects far away so og.sim.step() doesn't
        # settle them onto the new sheet at physics-relative positions.
        for obj in self.env.scene.objects:
            if obj.name in pose_snapshot:
                obj.set_position_orientation(position=torch.tensor([0.0, 0.0, -10.0]))
                obj.keep_still()

        # Spawn resized replacement
        obj_model = getattr(target_obj, "model", "paper_sheet")
        obj_category = getattr(target_obj, "category", "paper_sheet")

        torn_sheet = DatasetObject(
            name="torn_sheet_d",
            category=obj_category,
            model=obj_model,
            bounding_box=new_bb,
        )
        self.env.scene.add_object(torn_sheet)
        og.sim.step()  # initialises new object physics — nothing else nearby

        # Place torn sheet at the original sheet position
        torn_sheet.set_position_orientation(position=sheet_pos, orientation=sheet_ori)
        torn_sheet.keep_still()

        # Restore all other objects to their exact pre-tear absolute poses
        for obj in self.env.scene.objects:
            if obj.name in pose_snapshot:
                saved_pos, saved_ori = pose_snapshot[obj.name]
                obj.set_position_orientation(position=saved_pos, orientation=saved_ori)
                obj.keep_still()

        # Use PLACE_ON_TOP camera style for tear result
        self._tracking_object = torn_sheet
        self._last_action_name = 'PLACE_ON_TOP'

        yield from self._no_op()

    # ------------------------------------------------------------------
    # Push / Pull
    # ------------------------------------------------------------------

    def _check_pushable(self, obj):
        """Validate that an object can be pushed/pulled. Raises ActionPrimitiveError if not."""
        if self._get_obj_in_hand():
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Cannot push/pull an object while holding another object.",
                {"object in hand": self._get_obj_in_hand().name},
            )

        # Check mass limit if configured
        if self.MAX_PUSHABLE_MASS is not None:
            obj_mass = getattr(obj, "mass", None)
            if obj_mass is not None and obj_mass > self.MAX_PUSHABLE_MASS:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    f"Object '{obj.name}' is too heavy to push/pull "
                    f"(mass: {obj_mass:.1f}kg, limit: {self.MAX_PUSHABLE_MASS:.1f}kg).",
                    {"target object": obj.name, "mass": obj_mass, "limit": self.MAX_PUSHABLE_MASS},
                )

        # Check that it's not a fixed object (e.g., wall, floor, counter)
        if hasattr(obj, "fixed_base") and obj.fixed_base:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Object '{obj.name}' is fixed in place and cannot be pushed or pulled.",
                {"target object": obj.name},
            )

    def _get_robot_forward_direction(self):
        """Get the robot's forward direction as a unit vector on the XY plane."""
        import math
        _, ori = self.robot.get_position_orientation()
        x, y, z, w = float(ori[0]), float(ori[1]), float(ori[2]), float(ori[3])
        yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        return torch.tensor([math.cos(yaw), math.sin(yaw), 0.0])

    def _push(self, obj):
        """Push an object away from the robot along the floor."""
        self._check_pushable(obj)

        robot_pos = self.robot.get_position_orientation()[0]
        obj_pos, obj_ori = obj.get_position_orientation()

        direction = obj_pos - robot_pos
        direction[2] = 0.0
        dist = float(torch.norm(direction))
        if dist < 1e-3:
            direction = self._get_robot_forward_direction()
        else:
            direction = direction / dist

        new_pos = obj_pos + direction * self.PUSH_PULL_DISTANCE
        new_pos[2] = float(obj_pos[2])
        obj.set_position_orientation(position=new_pos, orientation=obj_ori)

        yield from self._settle_robot()

    def _pull(self, obj):
        """Pull an object toward the robot along the floor."""
        self._check_pushable(obj)

        robot_pos = self.robot.get_position_orientation()[0]
        obj_pos, obj_ori = obj.get_position_orientation()

        direction = robot_pos - obj_pos
        direction[2] = 0.0
        dist = float(torch.norm(direction))
        if dist < 1e-3:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Object '{obj.name}' is already at the robot's position.",
                {"target object": obj.name},
            )

        direction = direction / dist

        move_dist = min(self.PUSH_PULL_DISTANCE, max(0.0, dist - 0.3))
        if move_dist < 0.05:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Object '{obj.name}' is already close enough to the robot (distance: {dist:.2f}m).",
                {"target object": obj.name, "distance": dist},
            )

        new_pos = obj_pos + direction * move_dist
        new_pos[2] = float(obj_pos[2])
        obj.set_position_orientation(position=new_pos, orientation=obj_ori)

        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Freeze particle physics
    # ------------------------------------------------------------------

    @staticmethod
    def _freeze_particle_physics(system):
        """Disable PhysX simulation on a particle system's instancers."""
        for inst in system.particle_instancers.values():
            inst.particle_velocities = torch.zeros(inst.n_particles, 3)
            attr = inst.prim.GetAttribute("physxParticle:particleEnabled")
            if attr:
                attr.Set(False)

    # ------------------------------------------------------------------
    # Place near heating element
    # ------------------------------------------------------------------

    def _place_near_heating_element(self, heat_source_obj):
        if self._grasped_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Not holding anything. Grasp an object first.",
                {"heat source": heat_source_obj.name},
            )
        held_obj = self._grasped_obj
        self._release_ag()

        if object_states.HeatSourceOrSink not in heat_source_obj.states:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The target object is not a heat source or sink.",
                {"target object": heat_source_obj.name},
            )

        if object_states.Broken in heat_source_obj.states and heat_source_obj.states[object_states.Broken].get_value():
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"The {heat_source_obj.name} is broken and cannot be used for cooking.",
                {"target object": heat_source_obj.name, "broken": True},
            )

        if heat_source_obj.states[object_states.HeatSourceOrSink].requires_inside:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "The heat source object has no explicit heating element, it just requires the cookable object to be placed inside it.",
                {"target object": heat_source_obj.name},
            )

        heating_element_positions = torch.stack(
            [
                link.get_position_orientation()[0]
                for link in heat_source_obj.states[object_states.HeatSourceOrSink].links.values()
            ]
        )
        heating_distance_threshold = float(heat_source_obj.states[object_states.HeatSourceOrSink].distance_threshold)

        yield from self._place_with_predicate(
            held_obj,
            heat_source_obj,
            object_states.OnTop,
            near_poses=heating_element_positions,
            near_poses_threshold=heating_distance_threshold,
        )

    # ------------------------------------------------------------------
    # Climb on / Climb down
    # ------------------------------------------------------------------

    def _check_high_surface(self, obj):
        """Check if obj is on/inside a High surface."""
        obj_pos = obj.get_position_orientation()[0]
        for scene_obj in self.env.scene.objects:
            if object_states.High not in scene_obj.states:
                continue
            if not scene_obj.states[object_states.High].get_value():
                continue
            surface_pos = scene_obj.get_position_orientation()[0]
            xy_dist = float(torch.norm(obj_pos[:2] - surface_pos[:2]))
            z_diff = float(obj_pos[2] - surface_pos[2])
            if xy_dist < 1.0 and -0.1 < z_diff < 0.5:
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    f"The {obj.name} is on a high surface ({scene_obj.name}) that the robot cannot reach from the floor.",
                    {"target object": obj.name, "high surface": scene_obj.name},
                )

    def _climb_on(self, obj):
        """Symbolically climb on top of an object, raising the robot's reach height."""
        if self._climb_obj is not None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Robot is already standing on an object.",
                {"currently on": self._climb_obj.name},
            )

        obj_category = getattr(obj, "category", "")
        if obj_category and obj_category.lower() not in self.CLIMBABLE_CATEGORIES:
            obj_name_lower = obj.name.lower()
            if not any(cat in obj_name_lower for cat in self.CLIMBABLE_CATEGORIES):
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                    f"Cannot climb on '{obj.name}' (category: {obj_category}). "
                    f"Only climbable objects are allowed: {sorted(self.CLIMBABLE_CATEGORIES)}",
                    {"target object": obj.name, "category": obj_category},
                )

        aabb_lo, aabb_hi = obj.aabb
        obj_height = float(aabb_hi[2] - aabb_lo[2])

        if obj_height < 0.1:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Object '{obj.name}' is too short to climb on (height: {obj_height:.2f}m).",
                {"target object": obj.name, "height": obj_height},
            )

        robot_pos, robot_ori = self.robot.get_position_orientation()
        self._pre_climb_z = float(robot_pos[2])
        self._climb_z_offset = obj_height
        self._climb_obj = obj

        obj_pos = obj.get_position_orientation()[0]
        new_pos = torch.tensor([
            float(obj_pos[0]),
            float(obj_pos[1]),
            self._pre_climb_z + obj_height,
        ])
        self.robot.set_position_orientation(position=new_pos, orientation=robot_ori)
        self.robot.keep_still()

        obj_in_hand = self._get_obj_in_hand()
        if obj_in_hand is not None:
            obj_in_hand.set_position_orientation(position=self.robot.get_eef_position(self.arm))

        yield from self._settle_robot()

    def _climb_down(self):
        """Climb down from the object the robot is currently standing on."""
        if self._climb_obj is not None:
            self._tracking_object = self._climb_obj
        if self._climb_obj is None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Robot is not standing on any object. Nothing to climb down from.",
                {"currently on": None},
            )

        robot_pos, robot_ori = self.robot.get_position_orientation()
        restored_z = self._pre_climb_z if self._pre_climb_z is not None else float(robot_pos[2]) - self._climb_z_offset
        new_pos = torch.tensor([float(robot_pos[0]), float(robot_pos[1]), restored_z])
        self.robot.set_position_orientation(position=new_pos, orientation=robot_ori)
        self.robot.keep_still()

        obj_in_hand = self._get_obj_in_hand()
        if obj_in_hand is not None:
            obj_in_hand.set_position_orientation(position=self.robot.get_eef_position(self.arm))

        self._climb_obj = None
        self._climb_z_offset = 0.0
        self._pre_climb_z = None

        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Navigate to pose
    # ------------------------------------------------------------------

    def _navigate_to_pose(self, pose_2d, **kwargs):
        """Teleport robot to 2d pose (x, y, yaw) with pure yaw orientation."""
        import math
        if self._climb_obj is not None:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                f"Cannot navigate while standing on '{self._climb_obj.name}'. Use CLIMB_DOWN first.",
                {"currently on": self._climb_obj.name},
            )
        x, y, yaw = float(pose_2d[0]), float(pose_2d[1]), float(pose_2d[2])
        robot_z = float(self.robot.get_position_orientation()[0][2])
        pos = torch.tensor([x, y, robot_z], dtype=torch.float32)
        ori = torch.tensor([0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)], dtype=torch.float32)
        self.robot.set_position_orientation(position=pos, orientation=ori)
        self.robot.keep_still()

        self._anchored_pos = pos.clone()
        self._anchored_ori = ori.clone()

        yield from self._settle_robot()

    # ------------------------------------------------------------------
    # Sample pose (cuRobo-free override)
    # ------------------------------------------------------------------

    def _sample_pose_with_object_and_predicate(
        self, predicate, held_obj, target_obj, near_poses=None, near_poses_threshold=None, **kwargs
    ):
        """Ray-cast sampling first, then geometric fallback. No cuRobo."""
        pred_map = {object_states.OnTop: "onTop", object_states.Inside: "inside"}

        max_attempts = 100
        for _ in range(max_attempts):
            _, _, bb_extents, bb_pos_in_base = held_obj.get_base_aligned_bbox()
            bb_orn_in_base = torch.tensor([0, 0, 0, 1], dtype=torch.float32)

            sampling_results = sample_cuboid_for_predicate(pred_map[predicate], target_obj, bb_extents)
            if sampling_results[0][0] is None:
                continue

            sampled_bb_center = sampling_results[0][0] + torch.tensor([0, 0, 0.005])
            sampled_bb_orn = sampling_results[0][2]

            sampled_obj_pose = T.pose2mat((sampled_bb_center, sampled_bb_orn)) @ T.pose_inv(
                T.pose2mat((bb_pos_in_base, bb_orn_in_base))
            )

            sampled_pos, sampled_orn = T.mat2pose(sampled_obj_pose)

            if near_poses is not None:
                if not torch.any(torch.norm(near_poses - sampled_pos.unsqueeze(0), dim=1) < near_poses_threshold):
                    continue

            return sampled_pos, sampled_orn

        # Geometric fallback
        target_aabb_lo, target_aabb_hi = target_obj.aabb
        target_center = (target_aabb_lo + target_aabb_hi) / 2.0
        held_extent = held_obj.aabb_extent

        if predicate == object_states.Inside:
            pos = target_center.clone()
            pos[2] = float(target_aabb_lo[2]) + float(held_extent[2]) / 2.0 + 0.01
        elif predicate == object_states.OnTop:
            pos = target_center.clone()
            pos[2] = float(target_aabb_hi[2]) + float(held_extent[2]) / 2.0 + 0.01
        else:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.SAMPLING_ERROR,
                f"Unsupported predicate: {predicate}",
                {"predicate": str(predicate), "target object": target_obj.name, "held object": held_obj.name},
            )

        pos[0] += (torch.rand(1).item() - 0.5) * 0.02
        pos[1] += (torch.rand(1).item() - 0.5) * 0.02

        if near_poses is not None:
            if not torch.any(torch.norm(near_poses - pos.unsqueeze(0), dim=1) < near_poses_threshold):
                raise ActionPrimitiveError(
                    ActionPrimitiveError.Reason.SAMPLING_ERROR,
                    "Could not find a position near the heating element.",
                    {"target object": target_obj.name, "object in hand": held_obj.name},
                )

        ori = held_obj.get_position_orientation()[1]
        return pos, ori

    # ------------------------------------------------------------------
    # Force cooking particle transitions
    # ------------------------------------------------------------------

    def _force_cooking_particle_transitions(self, heated_containers):
        """Directly execute cooking particle transitions in symbolic mode."""
        import omnigibson as og

        if not heated_containers:
            return

        has_heated = any(
            object_states.Heated in c.states and c.states[object_states.Heated].get_value()
            for c in heated_containers if hasattr(c, 'states')
        )
        if not has_heated:
            return

        scene = self.env.scene
        transition_api = scene.transition_rule_api
        active_sys_names = set(scene.active_systems.keys())

        for rule in transition_api.all_rules:
            if not isinstance(rule, CookingPhysicalParticleRule):
                continue

            for recipe_name, recipe in rule._recipes.items():
                input_sys_name = recipe["input_systems"][0]
                output_sys_name = recipe["output_systems"][0]

                if input_sys_name not in active_sys_names:
                    continue

                input_system = scene.active_systems[input_sys_name]
                if input_system.n_particles == 0:
                    continue

                og.log.info(f"[EIB] Executing cooking recipe '{recipe_name}': "
                            f"{input_sys_name}({input_system.n_particles} particles) -> {output_sys_name}")

                target_container = None
                for c in heated_containers:
                    if hasattr(c, 'states') and object_states.Heated in c.states:
                        if c.states[object_states.Heated].get_value():
                            target_container = c
                            break

                n_particles = input_system.n_particles
                original_positions = input_system.get_particles_position_orientation()[0].clone()
                all_idx = torch.arange(n_particles)

                try:
                    output_system = scene.get_system(output_sys_name)
                except Exception as e:
                    og.log.warning(f"[EIB] Could not initialize output system '{output_sys_name}': {e}. "
                                  f"Input particles preserved.")
                    continue

                input_system.remove_particles(idxs=all_idx)

                if target_container is not None:
                    aabb_lo, aabb_hi = target_container.aabb
                    aabb_center = (aabb_lo + aabb_hi) / 2.0
                    aabb_extent = aabb_hi - aabb_lo
                    offsets = (torch.rand(n_particles, 3) - 0.5) * aabb_extent * 0.6
                    positions = aabb_center.unsqueeze(0) + offsets
                else:
                    positions = original_positions

                output_system.generate_particles(positions=positions)

                if isinstance(output_system, MacroPhysicalParticleSystem):
                    lin_vel, ang_vel = output_system.get_particles_velocities()
                    lin_vel[:] = 0
                    ang_vel[:] = 0
                    output_system.set_particles_velocities(lin_vels=lin_vel, ang_vels=ang_vel)

                og.log.info(f"[EIB] Cooking transition complete: {input_sys_name} -> {output_sys_name} "
                            f"({len(all_idx)} particles converted)")

                transition_api.refresh_all_rules()

    # ------------------------------------------------------------------
    # Move fingers to limit (symbolic override)
    # ------------------------------------------------------------------

    def _move_fingers_to_limit(self, limit_type):
        """Instantly set finger joint positions in one physics step."""
        target_joint_positions = self._get_joint_position_with_fingers_at_limit(limit_type)
        self.robot.set_joint_positions(target_joint_positions)
        action = self.robot.q_to_action(target_joint_positions)
        yield self._postprocess_action(action)
