"""Verify which episodes are compatible with their assigned scene.

Usage:
  /isaac-sim/python.sh omnigibson/examples/eib/verify_scenes.py --meta IH
"""
import argparse
import json
import os

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")
os.environ.setdefault("CUDA_HOME", "/usr/local/cuda-11.8")
os.environ.setdefault("TORCH_CUDA_ARCH_LIST", "8.9")

from omnigibson.envs.eib_omnigibson_kitchen_env import _parse_required_rooms

# Base directory for EIB data files
EIB_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", type=str, required=True)
    parser.add_argument("--scene", type=str, default=None,
                        help="Override scene_name for all episodes")
    args = parser.parse_args()

    meta_lower = args.meta.lower()
    episodes_path = os.path.join(EIB_DATA_DIR, "task", args.meta, f"{meta_lower}_episodes.json")
    bddl_dir = os.path.join(EIB_DATA_DIR, "task", args.meta, "bddl")

    with open(episodes_path) as f:
        episodes = json.load(f)["episodes"]

    # Load scene once to get available rooms
    import omnigibson as og
    import yaml

    config_path = os.path.join(EIB_DATA_DIR, "env", "env.yaml")
    with open(config_path) as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)

    scene_name = args.scene or episodes[0].get("scene_name", "Rs_int")
    cfg["scene"]["scene_model"] = scene_name
    cfg["scene"].pop("load_room_instances", None)
    cfg["scene"]["not_load_object_categories"] = ["ceilings", "roof"]
    cfg["task"]["type"] = "DummyTask"

    env = og.Environment(configs=cfg)
    available_rooms = set(env.scene.seg_map.room_sem_name_to_ins_name.keys())
    og.clear()

    print(f"Scene: {scene_name}")
    print(f"Available rooms: {sorted(available_rooms)}")
    print()

    ok_count = 0
    fail_count = 0

    for ep in episodes:
        task_name = ep.get("task_name")
        ep_scene = args.scene or ep.get("scene_name", "Rs_int")

        if not task_name:
            print(f"  [{ep['episode_id']}] SKIP (no task_name)")
            continue

        bddl_path = os.path.join(bddl_dir, task_name, "problem0.bddl")
        if not os.path.exists(bddl_path):
            print(f"  [{ep['episode_id']}] MISSING BDDL: {bddl_path}")
            fail_count += 1
            continue

        required = _parse_required_rooms(bddl_path)
        missing = required - available_rooms

        if missing:
            print(f"  [{ep['episode_id']}] FAIL  {task_name}  (missing: {sorted(missing)})")
            fail_count += 1
        else:
            print(f"  [{ep['episode_id']}] OK    {task_name}  (rooms: {sorted(required)})")
            ok_count += 1

    print()
    print(f"OK: {ok_count}  FAIL: {fail_count}  TOTAL: {len(episodes)}")


if __name__ == "__main__":
    main()
