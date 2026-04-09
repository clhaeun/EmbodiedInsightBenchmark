import faulthandler
faulthandler.enable()

import os
import re
os.environ.setdefault("TORCH_CUDA_ARCH_LIST", "8.9")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch as th
import yaml

import omnigibson.macros as macros
from omnigibson.macros import gm
gm.USE_GPU_DYNAMICS = True
gm.GPU_PAIRS_CAPACITY = 128 * 1024
gm.GPU_AGGR_PAIRS_CAPACITY = (2**13) * 1024
gm.GPU_MAX_PARTICLE_CONTACTS = 512 * 1024
gm.GPU_MAX_RIGID_CONTACT_COUNT = 524288
gm.GPU_MAX_RIGID_PATCH_COUNT = 81920

import bddl
import omnigibson as og
from omnigibson.utils.bddl_utils import BEHAVIOR_ACTIVITIES
from bddl.activity import evaluate_goal_conditions
from omnigibson.envs.common.eib_camera import CameraMixin
from omnigibson.envs.eib_action import ActionMixin
from omnigibson.action_primitives.eib_semantic_action_primitives import EIBSemanticActionPrimitives

_INROOM_RE = re.compile(r"\(inroom\s+\S+\s+(\S+)\)")


def _parse_required_rooms(bddl_path):
    """Parse a BDDL file and return the set of room types used in inroom conditions."""
    with open(bddl_path) as f:
        return set(_INROOM_RE.findall(f.read()))


def _make_bddl_resolver(bddl_dir):
    """Return a definition filename resolver for the given BDDL directory."""
    def _resolver(behavior_activity, instance, domain=False):
        if domain:
            from bddl.config import ACTIVITY_CONFIGS_PATH
            return os.path.join(ACTIVITY_CONFIGS_PATH, "domain_igibson.bddl")
        return os.path.join(bddl_dir, behavior_activity, f"problem{instance}.bddl")
    return _resolver


class OmniGibsonKitchenEnv(CameraMixin, ActionMixin):

    EXCLUDED_CATEGORIES = {"walls", "floors", "ceilings", "carpet", "agent", "roof", "ground"}

    def __init__(self, config_path, bddl_file=None, task_name=None, scene_name=None, bddl_dir=None, exclude_categories=None):
        with open(config_path) as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)

        if task_name:
            # activity_name 기반 로딩
            self._setup_activity_config(cfg, task_name, scene_name, bddl_dir=bddl_dir, exclude_categories=exclude_categories)
        elif bddl_file:
            with open(bddl_file) as f:
                cfg["task"]["predefined_problem"] = f.read()

        self._viewer_width = cfg.get("render", {}).get("viewer_width", 1280)
        self._viewer_height = cfg.get("render", {}).get("viewer_height", 720)
        self.env = og.Environment(configs=cfg)
        self.scene = self.env.scene
        self.robot = self.env.robots[0]

        for arm_name in self.robot.gripper_control_idx.keys():
            gripper_idx = self.robot.gripper_control_idx[arm_name]
            self.robot.set_joint_positions(
                th.ones_like(gripper_idx), indices=gripper_idx, normalized=True
            )
        self.robot.keep_still()
        for _ in range(5):
            og.sim.step()

        self.scene.update_initial_file()
        self.scene.reset()
        for _ in range(30):
            og.sim.step()

        # Scale up small objects (e.g. nails) 2x for camera visibility
        _SCALE_UP_CATEGORIES = {"clout_nail", "wall_nail"}
        for obj in self.scene.objects:
            if obj.category in _SCALE_UP_CATEGORIES:
                obj.scale = obj.scale * 2.0

        has_head = hasattr(self.robot, "camera_control_idx") and len(self.robot.camera_control_idx) > 0
        self.primitives = EIBSemanticActionPrimitives(self.env, self.robot, enable_head_tracking=has_head)

        self.__init_camera__()
        self._object_registry = self._build_object_registry()
        self.language_skill_set = self._build_language_skill_set()

    def _setup_activity_config(self, cfg, task_name, scene_name=None, bddl_dir=None, exclude_categories=None):
        """activity_name + scene 기반 BDDL 로딩."""
        # CustomBehaviorTask import → Registerable 메타클래스로 자동 등록
        from omnigibson.tasks.eib_custom_behavior_task import CustomBehaviorTask  # noqa: F401

        # BDDL 파일 경로 오버라이드
        if task_name not in BEHAVIOR_ACTIVITIES:
            og.tasks.behavior_task.BEHAVIOR_ACTIVITIES.append(task_name)
        # OG imports get_definition_filename via `from bddl.config import ...`
        # so we must patch both the source module AND OG's local reference.
        resolver = _make_bddl_resolver(bddl_dir)
        bddl.config.get_definition_filename = resolver
        from omnigibson.utils import bddl_utils as _og_bddl_utils
        _og_bddl_utils.get_definition_filename = resolver

        if scene_name:
            cfg["scene"]["scene_model"] = scene_name
        # Load all rooms so adjacent rooms provide walls/floor (no sky holes)
        cfg["scene"]["load_room_types"] = None
        cfg["scene"].pop("load_room_instances", None)
        base_exclude = cfg["scene"].get("not_load_object_categories", [])
        extra_exclude = ["ceilings", "roof"]
        if exclude_categories:
            extra_exclude += list(exclude_categories)
        cfg["scene"]["not_load_object_categories"] = list(set(base_exclude + extra_exclude))
        cfg["scene"]["load_task_relevant_only"] = False

        cfg["task"] = {
            "type": "CustomBehaviorTask",
            "activity_name": task_name,
            "activity_definition_id": 0,
            "activity_instance_id": 0,
            "predefined_problem": None,
            "online_object_sampling": True,
            "use_presampled_robot_pose": False,
        }

    @staticmethod
    def check_scene_compatibility(bddl_path, scene):
        """Check if a scene has all room types required by a BDDL task.

        Returns (ok, missing_rooms). If ok is False, missing_rooms lists
        the room types the scene does not have.
        """
        required = _parse_required_rooms(bddl_path)
        available = set(scene.seg_map.room_sem_name_to_ins_name.keys())
        missing = required - available
        return len(missing) == 0, missing

    def is_goal_satisfied(self):
        task = self.env.task
        if not hasattr(task, "ground_goal_state_options") or task.ground_goal_state_options is None:
            return False
        _, satisfied_predicates = evaluate_goal_conditions(task.ground_goal_state_options[0])
        return len(satisfied_predicates["unsatisfied"]) == 0

    def _build_object_registry(self):
        category_objects = {}
        for obj in self.scene.objects:
            cat = obj.category
            if cat in self.EXCLUDED_CATEGORIES:
                continue
            if cat not in category_objects:
                category_objects[cat] = []
            category_objects[cat].append(obj)

        registry = {}
        for cat, objs in category_objects.items():
            display_cat = cat.replace("__", " ").replace("_", " ")
            if len(objs) == 1:
                registry[display_cat] = objs[0]
            else:
                for i, obj in enumerate(objs, 1):
                    registry[f"{display_cat} {i}"] = obj
        return registry

    def _build_language_skill_set(self):
        return [
            # 0-target
            "release — release the held object",
            # 1-target
            "navigate <furniture/appliance> — move to a furniture or appliance",
            "grasp <object> — pick up an object",
            "open <object> — open a door, drawer, or container",
            "close <object> — close a door, drawer, or container",
            "toggle_on <object> — turn on an appliance",
            "toggle_off <object> — turn off an appliance",
            "wait <object> — wait for temperature/frozen state to change",
            "wait_for_cooked <object> — wait for cooking to finish",
            "wait_for_washed <machine> — wait for wash cycle to finish",
            # 2-target
            "place_on_top <object> <surface> — place the held object on top of a surface (pan, table, oven, countertop, plate)",
            "place_inside <object> <container> — place the held object inside an enclosed container (fridge, cabinet, pot, bowl, drawer)",
            "wipe <object> <tool> — wipe an object with a cleaning tool",
            "cut <object> <tool> — cut/slice an object with a cutting tool",
            "soak_under <object> <source> — soak an object under a fluid source",
            "soak_inside <object> <container> — soak an object inside a fluid container",
            "fill_with <container> <source> — fill a container from a fluid source",
            "pour_into <container> <target> — pour from a container into another",
            "spread <container> <surface> — spread particles onto a surface",
            "wait_for_frozen <object> <fridge> — wait for an object to freeze in fridge",
            # terminal
            "abstain — give up if the task is impossible with the above actions",
            "terminate — declare task complete",
        ]

    def reset(self):
        obs, info = self.env.reset()
        for _ in range(10):
            og.sim.step()
        return obs

    def get_scene_objects(self):
        return dict(self._object_registry)

    def get_receptacle_names(self):
        """Return display names of fixed-base objects only (furniture/structures)."""
        return [name for name, obj in self._object_registry.items() if obj.fixed_base]

    def close(self):
        # Prevent segfault: VisionSensor.remove() calls render() after sim.stop(),
        # which crashes in og.app.update(). Patch render to no-op during clear.
        from omnigibson.sensors import vision_sensor as _vs
        _orig_render = _vs.render
        _vs.render = lambda: None
        if og.sim is not None and hasattr(og.sim, "_viewer_camera"):
            og.sim._viewer_camera = None
        try:
            og.clear()
        finally:
            _vs.render = _orig_render
        # Reset viewer dimensions so next Environment() init doesn't hit assertion
        if og.sim is not None:
            og.sim.viewer_width = self._viewer_width
            og.sim.viewer_height = self._viewer_height

    @staticmethod
    def shutdown():
        og.shutdown()
