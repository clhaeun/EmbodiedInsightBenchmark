"""Test script to visually verify symbolic action primitives in the simulator.

Loads an OmniGibson environment, executes each action primitive one by one,
and saves before/after screenshots so you can inspect the visual results.

Usage:
  # Test EIB primitives (default)
  /isaac-sim/python.sh omnigibson/examples/test_symbolic_actions.py --mode eib

  # Test OG symbolic primitives
  /isaac-sim/python.sh omnigibson/examples/test_symbolic_actions.py --mode symbolic

  # Test specific action only
  /isaac-sim/python.sh omnigibson/examples/test_symbolic_actions.py --only navigate_to,grasp

  # Use a specific task
  /isaac-sim/python.sh omnigibson/examples/test_symbolic_actions.py --task cook_kielbasa
"""

import argparse
import json
import os
import sys
import time
import traceback

os.environ.setdefault("OMNIGIBSON_HEADLESS", "0")  # show GUI by default
os.environ.setdefault("CUDA_HOME", "/usr/local/cuda-11.8")
os.environ.setdefault("TORCH_CUDA_ARCH_LIST", "8.9")

import numpy as np
import torch
import yaml
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EIB_DATA_DIR = os.path.join(os.path.dirname(__file__), "eib", "data")


def capture_screenshot(env_or_camera, save_dir, label, step_counter):
    """Save a screenshot and return the path. Works with both OmniGibsonKitchenEnv and raw og env."""
    import omnigibson as og

    os.makedirs(save_dir, exist_ok=True)
    filename = f"{step_counter:04d}_{label}.png"
    path = os.path.join(save_dir, filename)

    if hasattr(env_or_camera, "get_rgb"):
        # EIB env with CameraMixin
        rgb = env_or_camera.get_rgb()
    else:
        # Raw OG env — use viewer camera
        og.sim.render()
        og.sim.render()
        obs = og.sim.viewer_camera.get_obs()
        rgb = obs[0]["rgb"][:, :, :3].cpu().numpy().astype(np.uint8)

    Image.fromarray(rgb).save(path)
    print(f"    Screenshot saved: {filename}")
    return path


def run_primitive_generator(env, generator):
    """Consume a primitive generator, stepping the environment for each action."""
    step_count = 0
    for action in generator:
        env.step(action)
        step_count += 1
    return step_count


# ---------------------------------------------------------------------------
# EIB Primitive Tests — Independent Scenarios
# ---------------------------------------------------------------------------

def test_eib_primitives(eib_env, save_dir, only_actions=None):
    """Test EIB semantic action primitives as independent scenarios.

    Each action is tested in its own self-contained scenario:
      - Setup steps run silently (no screenshots)
      - Only the target action gets before/after screenshots
      - If one scenario fails, the others still run independently
    """
    from omnigibson.action_primitives.eib_semantic_action_primitives import (
        EIBSemanticActionPrimitiveSet,
    )
    from omnigibson import object_states as os_mod

    prims = eib_env.primitives
    env = eib_env.env
    scene = eib_env.scene

    results = []
    step = [0]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def screenshot(label):
        step[0] += 1
        return capture_screenshot(eib_env, save_dir, label, step[0])

    def _run_action(action_name, *args):
        """Execute an action primitive (raises on failure)."""
        primitive_enum = getattr(EIBSemanticActionPrimitiveSet, action_name.upper())
        gen = prims.apply_ref(primitive_enum, *args)
        run_primitive_generator(env, gen)

    def _setup(action_name, *args):
        """Run an action as silent setup. Returns True on success."""
        try:
            _run_action(action_name, *args)
            return True
        except Exception as e:
            print(f"    [setup {action_name}] FAILED: {str(e)[:100]}")
            return False

    def _reset_open(obj, should_be_open):
        """Directly set Open state without primitive."""
        if os_mod.Open in obj.states:
            if obj.states[os_mod.Open].get_value() != should_be_open:
                obj.states[os_mod.Open].set_value(should_be_open, fully=True)

    def _reset_toggle(obj, should_be_on):
        """Directly set ToggledOn state."""
        if os_mod.ToggledOn in obj.states:
            if obj.states[os_mod.ToggledOn].get_value() != should_be_on:
                obj.states[os_mod.ToggledOn].set_value(should_be_on)

    def _cleanup_grasp():
        """Release any held object between scenarios."""
        if prims._grasped_obj is not None:
            try:
                _run_action("release")
            except Exception:
                prims._release_ag()

    def _ensure_grasp(obj):
        """Ensure the robot is holding obj. If not, navigate + grasp automatically.
        Returns True on success."""
        if prims._grasped_obj is obj:
            return True
        # Release anything currently held
        _cleanup_grasp()
        # Navigate to a nearby surface first
        navigated = False
        obj_pos = obj.get_position_orientation()[0]
        for s in surfaces:
            try:
                s_pos = s.get_position_orientation()[0]
                if float(torch.norm(s_pos[:2] - obj_pos[:2])) < 5.0:
                    if _setup("navigate_to", s):
                        navigated = True
                        break
            except Exception:
                continue
        if not navigated:
            # Navigate to appliance or container as fallback
            for fallback in [appliance, container]:
                if fallback is not None:
                    if _setup("navigate_to", fallback):
                        break
        _run_action("grasp", obj)
        return prims._grasped_obj is obj

    # Save initial robot pose for recovery between scenarios
    _initial_robot_pos, _initial_robot_ori = eib_env.robot.get_position_orientation()
    _initial_robot_pos = _initial_robot_pos.clone()
    _initial_robot_ori = _initial_robot_ori.clone()

    def _recover_robot():
        """Reset robot to initial position if it drifted outside the scene."""
        pos, ori = eib_env.robot.get_position_orientation()
        if torch.isnan(ori).any() or float(pos[2]) > 3.0 or float(pos[2]) < -1.0:
            print("    [recovery] Robot drifted — resetting to initial pose")
            eib_env.robot.set_position_orientation(
                position=_initial_robot_pos, orientation=_initial_robot_ori)
            eib_env.robot.keep_still()

    def run_scenario(name, test_fn, desc=""):
        """Run a single independent scenario with error isolation."""
        if only_actions and name.lower() not in only_actions:
            print(f"\n--- SKIP: {name} (filtered) ---")
            return

        print(f"\n{'='*60}")
        print(f"SCENARIO: {name}")
        if desc:
            print(f"  {desc}")
        print(f"{'='*60}")

        # Reset tracking before each scenario
        prims._tracking_object = None

        try:
            test_fn()
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"  SCENARIO FAILED: {error_msg}")
            traceback.print_exc()
            results.append({"action": name, "status": "SCENARIO_FAILED", "error": error_msg})

        # Always clean up grasp state and recover robot between scenarios
        _cleanup_grasp()
        _recover_robot()
        prims._tracking_object = None

    # ------------------------------------------------------------------
    # Survey the scene (use task.object_scope for accurate objects)
    # ------------------------------------------------------------------
    task = env.task
    openable, toggleable, surfaces = [], [], []

    for obj in scene.objects:
        if not hasattr(obj, "states"):
            continue
        is_fixed = getattr(obj, "fixed_base", False)
        cat = getattr(obj, "category", "").lower()
        if cat in ("walls", "floors", "ceilings", "carpet", "agent", "roof", "ground"):
            continue
        if is_fixed:
            if os_mod.Open in obj.states:
                openable.append(obj)
            if os_mod.ToggledOn in obj.states:
                toggleable.append(obj)
            surfaces.append(obj)

    def _resolve_obj(name_hint):
        """Find object from task scope or scene by name."""
        for obj_name, entity in task.object_scope.items():
            if entity is None:
                continue
            if name_hint.lower() in obj_name.lower():
                return getattr(entity, "wrapped_obj", entity)
        for obj in scene.objects:
            if name_hint.lower() in obj.name.lower():
                return obj
        return None

    # Pick key objects — prefer fridge for container, oven for appliance
    container = None
    for pref in ("fridge", "refrigerator", "cabinet"):
        for o in openable:
            if pref in getattr(o, "category", "").lower() or pref in o.name.lower():
                container = o
                break
        if container:
            break
    if container is None and openable:
        container = openable[0]

    appliance = None
    for o in toggleable:
        if "oven" in getattr(o, "category", "").lower() or "oven" in o.name.lower():
            appliance = o
            break
    if appliance is None and toggleable:
        appliance = toggleable[0]

    surface = None
    for s in surfaces:
        if s is not container and s is not appliance:
            surface = s
            break
    if surface is None and surfaces:
        surface = surfaces[0]

    # Find small graspable objects from task scope (NOT generic movable scan)
    # Prefer task-specific objects; exclude large furniture like tables
    _LARGE_CATEGORIES = {"table", "desk", "bed", "sofa", "couch", "shelf", "cabinet",
                         "counter", "countertop", "chair", "bench"}
    small_obj, second_obj = None, None
    _small_candidates = []
    for obj_name, entity in task.object_scope.items():
        if entity is None:
            continue
        obj = getattr(entity, "wrapped_obj", entity)
        if obj is None:
            continue
        if getattr(obj, "fixed_base", False):
            continue
        cat = getattr(obj, "category", "").lower()
        if cat in ("agent", "walls", "floors", "ceilings", "carpet", "roof", "ground"):
            continue
        if cat in _LARGE_CATEGORIES:
            continue
        # Skip if name suggests large furniture
        name_lower = obj.name.lower()
        if any(lg in name_lower for lg in _LARGE_CATEGORIES):
            continue
        _small_candidates.append(obj)
    # Deduplicate by name
    _seen_names = set()
    for obj in _small_candidates:
        if obj.name not in _seen_names:
            _seen_names.add(obj.name)
            if small_obj is None:
                small_obj = obj
            elif second_obj is None and obj is not small_obj:
                second_obj = obj
    # Fallback: scan scene movable objects (exclude large furniture)
    if small_obj is None:
        for obj in scene.objects:
            if not hasattr(obj, "states"):
                continue
            if getattr(obj, "fixed_base", False):
                continue
            cat = getattr(obj, "category", "").lower()
            if cat in ("walls", "floors", "ceilings", "carpet", "agent", "roof", "ground"):
                continue
            if cat in _LARGE_CATEGORIES:
                continue
            if any(lg in obj.name.lower() for lg in _LARGE_CATEGORIES):
                continue
            if small_obj is None:
                small_obj = obj
            elif second_obj is None and obj is not small_obj:
                second_obj = obj

    print("\n=== Scene Survey ===")
    print(f"  Openable:  {[o.name for o in openable]}")
    print(f"  Toggleable: {[o.name for o in toggleable]}")
    print(f"  Surfaces:  {len(surfaces)} total")
    print(f"\n  container={getattr(container, 'name', 'NONE')}")
    print(f"  appliance={getattr(appliance, 'name', 'NONE')}")
    print(f"  surface={getattr(surface, 'name', 'NONE')}")
    print(f"  small_obj={getattr(small_obj, 'name', 'NONE')}")
    print(f"  second_obj={getattr(second_obj, 'name', 'NONE')}")

    screenshot("initial_state")

    # ==================================================================
    # SCENARIO 1: NAVIGATE_TO
    # Setup: none
    # Test: navigate to appliance, then to container
    # ==================================================================
    def scenario_navigate_to():
        targets = [t for t in [appliance, container] if t is not None]
        if not targets:
            print("  No fixed objects to navigate to")
            results.append({"action": "navigate_to", "status": "SKIP"})
            return
        for target in targets:
            prims._tracking_object = target
            screenshot(f"before_navigate_to_{target.name}")
            _run_action("navigate_to", target)
            prims._tracking_object = target
            screenshot(f"after_navigate_to_{target.name}")
            print(f"  SUCCESS: navigate_to {target.name}")
            results.append({"action": "navigate_to", "args": [target.name], "status": "SUCCESS"})

    run_scenario("navigate_to", scenario_navigate_to,
                 desc="Teleport robot to different fixed objects")

    # ==================================================================
    # SCENARIO 2: OPEN
    # Setup: ensure closed, navigate to container
    # Test: open container
    # ==================================================================
    def scenario_open():
        if not container:
            results.append({"action": "open", "status": "SKIP"})
            return
        _reset_open(container, False)
        _setup("navigate_to", container)
        prims._tracking_object = container
        screenshot(f"before_open_{container.name}")
        _run_action("open", container)
        screenshot(f"after_open_{container.name}")
        print(f"  SUCCESS: open {container.name}")
        results.append({"action": "open", "args": [container.name], "status": "SUCCESS"})

    run_scenario("open", scenario_open, desc="Open a container (fridge/cabinet)")

    # ==================================================================
    # SCENARIO 3: CLOSE
    # Setup: ensure open, navigate to container
    # Test: close container
    # ==================================================================
    def scenario_close():
        if not container:
            results.append({"action": "close", "status": "SKIP"})
            return
        _reset_open(container, True)
        _setup("navigate_to", container)
        prims._tracking_object = container
        screenshot(f"before_close_{container.name}")
        _run_action("close", container)
        screenshot(f"after_close_{container.name}")
        print(f"  SUCCESS: close {container.name}")
        results.append({"action": "close", "args": [container.name], "status": "SUCCESS"})

    run_scenario("close", scenario_close, desc="Close a container (fridge/cabinet)")

    # ==================================================================
    # SCENARIO 4: GRASP
    # Setup: navigate near movable object
    # Test: grasp it
    # ==================================================================
    def scenario_grasp():
        if not small_obj:
            results.append({"action": "grasp", "status": "SKIP"})
            return
        # Navigate to appliance or container near the object
        if appliance:
            _setup("navigate_to", appliance)
        elif container:
            _setup("navigate_to", container)
        prims._tracking_object = small_obj
        screenshot(f"before_grasp_{small_obj.name}")
        _run_action("grasp", small_obj)
        screenshot(f"after_grasp_{small_obj.name}")
        print(f"  SUCCESS: grasp {small_obj.name}")
        results.append({"action": "grasp", "args": [small_obj.name], "status": "SUCCESS"})

    run_scenario("grasp", scenario_grasp, desc="Pick up a movable object")

    # ==================================================================
    # SCENARIO 5: RELEASE
    # Setup: grasp small_obj
    # Test: release it
    # ==================================================================
    def scenario_release():
        if not small_obj:
            results.append({"action": "release", "status": "SKIP"})
            return
        _ensure_grasp(small_obj)
        prims._tracking_object = small_obj
        screenshot(f"before_release_{small_obj.name}")
        _run_action("release")
        screenshot(f"after_release_{small_obj.name}")
        print(f"  SUCCESS: release {small_obj.name}")
        results.append({"action": "release", "args": [small_obj.name], "status": "SUCCESS"})

    run_scenario("release", scenario_release, desc="Release a held object")

    # ==================================================================
    # SCENARIO 6: PLACE_ON_TOP
    # Setup: grasp small_obj, navigate to appliance/surface
    # Test: place on top
    # ==================================================================
    def scenario_place_on_top():
        if not small_obj:
            results.append({"action": "place_on_top", "status": "SKIP"})
            return
        place_target = appliance or surface
        if not place_target:
            results.append({"action": "place_on_top", "status": "SKIP"})
            return
        _ensure_grasp(small_obj)
        _setup("navigate_to", place_target)
        prims._tracking_object = place_target
        screenshot(f"before_place_on_top_{small_obj.name}_on_{place_target.name}")
        _run_action("place_on_top", small_obj, place_target)
        screenshot(f"after_place_on_top_{small_obj.name}_on_{place_target.name}")
        print(f"  SUCCESS: place_on_top {small_obj.name} on {place_target.name}")
        results.append({"action": "place_on_top", "args": [small_obj.name, place_target.name], "status": "SUCCESS"})

    run_scenario("place_on_top", scenario_place_on_top,
                 desc="Place a held object on top of a surface/appliance")

    # ==================================================================
    # SCENARIO 7: PLACE_INSIDE
    # Setup: grasp object, navigate to container, open it
    # Test: place inside container
    # ==================================================================
    def scenario_place_inside():
        if not container:
            results.append({"action": "place_inside", "status": "SKIP"})
            return
        obj_to_place = second_obj or small_obj
        if not obj_to_place:
            results.append({"action": "place_inside", "status": "SKIP"})
            return
        _ensure_grasp(obj_to_place)
        _setup("navigate_to", container)
        _reset_open(container, True)
        prims._tracking_object = container
        screenshot(f"before_place_inside_{obj_to_place.name}_in_{container.name}")
        _run_action("place_inside", obj_to_place, container)
        screenshot(f"after_place_inside_{obj_to_place.name}_in_{container.name}")
        print(f"  SUCCESS: place_inside {obj_to_place.name} in {container.name}")
        results.append({"action": "place_inside", "args": [obj_to_place.name, container.name], "status": "SUCCESS"})

    run_scenario("place_inside", scenario_place_inside,
                 desc="Place a held object inside a container")

    # ==================================================================
    # SCENARIO 8: TOGGLE_ON
    # Setup: ensure off + closed, navigate to appliance
    # Test: toggle on
    # ==================================================================
    def scenario_toggle_on():
        if not appliance:
            results.append({"action": "toggle_on", "status": "SKIP"})
            return
        _reset_open(appliance, False)
        _reset_toggle(appliance, False)
        _setup("navigate_to", appliance)
        prims._tracking_object = appliance
        screenshot(f"before_toggle_on_{appliance.name}")
        _run_action("toggle_on", appliance)
        screenshot(f"after_toggle_on_{appliance.name}")
        print(f"  SUCCESS: toggle_on {appliance.name}")
        results.append({"action": "toggle_on", "args": [appliance.name], "status": "SUCCESS"})

    run_scenario("toggle_on", scenario_toggle_on, desc="Turn on an appliance")

    # ==================================================================
    # SCENARIO 9: TOGGLE_OFF
    # Setup: ensure on + closed, navigate to appliance
    # Test: toggle off
    # ==================================================================
    def scenario_toggle_off():
        if not appliance:
            results.append({"action": "toggle_off", "status": "SKIP"})
            return
        _reset_open(appliance, False)
        _reset_toggle(appliance, True)
        _setup("navigate_to", appliance)
        prims._tracking_object = appliance
        screenshot(f"before_toggle_off_{appliance.name}")
        _run_action("toggle_off", appliance)
        screenshot(f"after_toggle_off_{appliance.name}")
        print(f"  SUCCESS: toggle_off {appliance.name}")
        results.append({"action": "toggle_off", "args": [appliance.name], "status": "SUCCESS"})

    run_scenario("toggle_off", scenario_toggle_off, desc="Turn off an appliance")

    # ==================================================================
    # SCENARIO 10: WAIT_FOR_COOKED
    # Setup: place object on heat source, toggle on
    # Test: wait_for_cooked
    # ==================================================================
    def scenario_wait_for_cooked():
        if not appliance or not small_obj:
            results.append({"action": "wait_for_cooked", "status": "SKIP"})
            return
        _reset_open(appliance, False)
        _reset_toggle(appliance, False)
        _ensure_grasp(small_obj)
        _setup("navigate_to", appliance)
        _setup("place_on_top", small_obj, appliance)
        _reset_toggle(appliance, True)
        prims._tracking_object = small_obj
        screenshot(f"before_wait_for_cooked_{small_obj.name}")
        _run_action("wait_for_cooked", small_obj)
        screenshot(f"after_wait_for_cooked_{small_obj.name}")
        print(f"  SUCCESS: wait_for_cooked {small_obj.name}")
        results.append({"action": "wait_for_cooked", "args": [small_obj.name], "status": "SUCCESS"})

    run_scenario("wait_for_cooked", scenario_wait_for_cooked,
                 desc="Cook an object on a heat source")

    # ==================================================================
    # SCENARIO 11: WAIT
    # Setup: none
    # Test: wait on an object
    # ==================================================================
    def scenario_wait():
        target = small_obj
        if not target:
            results.append({"action": "wait", "status": "SKIP"})
            return
        prims._tracking_object = target
        screenshot(f"before_wait_{target.name}")
        _run_action("wait", target)
        screenshot(f"after_wait_{target.name}")
        print(f"  SUCCESS: wait {target.name}")
        results.append({"action": "wait", "args": [target.name], "status": "SUCCESS"})

    run_scenario("wait", scenario_wait, desc="Wait for state changes to settle")

    # ==================================================================
    # SCENARIO 12: WAIT_FOR_FROZEN (if fridge exists)
    # Setup: place object inside fridge
    # Test: wait_for_frozen
    # ==================================================================
    def scenario_wait_for_frozen():
        if not container or "fridge" not in container.name:
            results.append({"action": "wait_for_frozen", "status": "SKIP"})
            return
        obj_to_freeze = small_obj
        if not obj_to_freeze:
            results.append({"action": "wait_for_frozen", "status": "SKIP"})
            return
        if not (hasattr(obj_to_freeze, "states") and os_mod.Frozen in obj_to_freeze.states):
            print(f"  {obj_to_freeze.name} has no Frozen state, skipping")
            results.append({"action": "wait_for_frozen", "status": "SKIP"})
            return
        _ensure_grasp(obj_to_freeze)
        _setup("navigate_to", container)
        _reset_open(container, True)
        _setup("place_inside", obj_to_freeze, container)
        prims._tracking_object = obj_to_freeze
        screenshot(f"before_wait_for_frozen_{obj_to_freeze.name}")
        _run_action("wait_for_frozen", obj_to_freeze, container)
        screenshot(f"after_wait_for_frozen_{obj_to_freeze.name}")
        print(f"  SUCCESS: wait_for_frozen {obj_to_freeze.name}")
        results.append({"action": "wait_for_frozen", "args": [obj_to_freeze.name, container.name], "status": "SUCCESS"})

    run_scenario("wait_for_frozen", scenario_wait_for_frozen,
                 desc="Freeze an object inside a refrigerator")

    screenshot("final_state")
    return results


# ---------------------------------------------------------------------------
# OG Symbolic Primitive Tests
# ---------------------------------------------------------------------------

def test_og_symbolic_primitives(eib_env, save_dir, only_actions=None):
    """Test OmniGibson's SymbolicSemanticActionPrimitives.

    Uses OmniGibsonKitchenEnv (with CameraMixin) for screenshots so camera
    auto-positions to show the robot and target object clearly.
    """
    from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
        SymbolicSemanticActionPrimitives,
        SymbolicSemanticActionPrimitiveSet,
    )

    og_env = eib_env.env
    robot = eib_env.robot
    scene = eib_env.scene
    prims = eib_env.primitives  # EIB prims — used only for camera tracking
    controller = SymbolicSemanticActionPrimitives(og_env, robot)
    task = og_env.task

    # Print available objects
    print("\n=== Task Object Scope ===")
    for obj_name, entity in task.object_scope.items():
        if entity is None:
            continue
        obj = getattr(entity, "wrapped_obj", entity)
        if obj is None:
            continue
        fixed = "FIXED" if getattr(obj, "fixed_base", False) else "movable"
        print(f"  {obj_name}: {getattr(obj, 'name', '?')} ({fixed})")

    results = []
    step = [0]

    def screenshot(label):
        step[0] += 1
        # Use eib_env (CameraMixin) for screenshots — auto-positions camera
        return capture_screenshot(eib_env, save_dir, label, step[0])

    def resolve_obj(name_hint):
        """Find an object from task scope by partial name match."""
        for obj_name, entity in task.object_scope.items():
            if entity is None:
                continue
            if name_hint.lower() in obj_name.lower():
                obj = getattr(entity, "wrapped_obj", entity)
                return obj
        for obj in scene.objects:
            if name_hint.lower() in obj.name.lower():
                return obj
        return None

    def try_action(action_name, *args, desc="", track_obj=None):
        if only_actions and action_name.lower() not in only_actions:
            print(f"\n--- SKIP: {action_name} ---")
            return

        arg_names = [getattr(a, "name", str(a)) for a in args]
        print(f"\n{'='*60}")
        print(f"ACTION: {action_name} [{', '.join(arg_names)}]")
        if desc:
            print(f"  {desc}")
        print(f"{'='*60}")

        # Set camera tracking for "before" screenshot
        if action_name.lower() == "navigate_to":
            prims._tracking_object = None
        elif track_obj is not None:
            prims._tracking_object = track_obj
        elif args:
            prims._tracking_object = args[0]

        screenshot(f"before_{action_name}")

        primitive_enum = getattr(SymbolicSemanticActionPrimitiveSet, action_name.upper(), None)
        if primitive_enum is None:
            print(f"  ERROR: Unknown primitive {action_name}")
            results.append({"action": action_name, "status": "UNKNOWN_PRIMITIVE"})
            return

        try:
            gen = controller.apply_ref(primitive_enum, *args)
            n_steps = run_primitive_generator(og_env, gen)

            # Update camera tracking for "after" screenshot
            if args:
                prims._tracking_object = args[0]

            screenshot(f"after_{action_name}")
            print(f"  SUCCESS ({n_steps} env steps)")
            results.append({"action": action_name, "args": arg_names, "status": "SUCCESS", "env_steps": n_steps})
        except Exception as e:
            screenshot(f"failed_{action_name}")
            error_msg = str(e)[:200]
            print(f"  FAILED: {error_msg}")
            results.append({"action": action_name, "args": arg_names, "status": "FAILED", "error": error_msg})

    # --- Resolve objects ---
    oven = resolve_obj("oven")
    fridge = resolve_obj("refrigerator") or resolve_obj("fridge")
    frying_pan = resolve_obj("frying_pan")
    kielbasa = resolve_obj("kielbasa")

    print(f"\n=== Resolved Test Objects ===")
    print(f"  oven: {getattr(oven, 'name', None)}")
    print(f"  fridge: {getattr(fridge, 'name', None)}")
    print(f"  frying_pan: {getattr(frying_pan, 'name', None)}")
    print(f"  kielbasa: {getattr(kielbasa, 'name', None)}")

    screenshot("initial_state")

    # ---- Test sequence (OG Symbolic) ----

    # 1. NAVIGATE_TO
    if oven:
        try_action("navigate_to", oven, desc="Teleport robot near the oven")

    # 2. OPEN
    if fridge:
        try_action("navigate_to", fridge, desc="Navigate to fridge")
        try_action("open", fridge, desc="Open fridge door")

    # 3. GRASP
    if kielbasa:
        try_action("grasp", kielbasa, desc="Grasp kielbasa")

    # 4. CLOSE
    if fridge:
        try_action("close", fridge, desc="Close fridge door")

    # 5. NAVIGATE_TO oven
    if oven:
        try_action("navigate_to", oven, desc="Navigate to oven")

    # 6. PLACE_ON_TOP (EIB signature: target_obj, surface)
    if frying_pan and kielbasa:
        try_action("place_on_top", kielbasa, frying_pan, desc="Place kielbasa on frying pan",
                    track_obj=frying_pan)

    # 7. RELEASE
    if frying_pan and controller._get_obj_in_hand() is None:
        try_action("grasp", frying_pan, desc="Grasp pan for release test")
    try_action("release", desc="Release held object")

    # 8. TOGGLE_ON
    if oven:
        try_action("toggle_on", oven, desc="Toggle oven on")

    # 9. TOGGLE_OFF
    if oven:
        try_action("toggle_off", oven, desc="Toggle oven off")

    # 10. PLACE_INSIDE (EIB signature: target_obj, container)
    if kielbasa and fridge:
        try_action("grasp", kielbasa, desc="Grasp kielbasa for place_inside")
        try_action("navigate_to", fridge, desc="Navigate to fridge")
        try_action("open", fridge, desc="Open fridge")
        try_action("place_inside", kielbasa, fridge, desc="Place kielbasa inside fridge",
                    track_obj=fridge)

    # 11. PLACE_NEAR_HEATING_ELEMENT
    if oven and frying_pan:
        try_action("grasp", frying_pan, desc="Grasp pan for heating element test")
        try_action("navigate_to", oven, desc="Navigate to oven")
        try_action("place_near_heating_element", oven,
                    desc="Place pan near oven heating element")

    # 12. PUSH
    if frying_pan and controller._get_obj_in_hand() is None:
        try_action("push", frying_pan, desc="Push frying pan away")

    # 13. PULL
    if frying_pan and controller._get_obj_in_hand() is None:
        try_action("pull", frying_pan, desc="Pull frying pan toward robot")

    # 14. CLIMB_ON / CLIMB_DOWN
    climbable = None
    for obj in scene.objects:
        cat = getattr(obj, "category", "").lower()
        if cat in {"chair", "stool", "stepstool", "bench", "ottoman"}:
            climbable = obj
            break
    if climbable:
        try_action("navigate_to", climbable, desc="Navigate to climbable object")
        try_action("climb_on", climbable, desc="Climb on object")
        try_action("climb_down", desc="Climb down from object")
    else:
        print("\n--- SKIP: CLIMB_ON/CLIMB_DOWN (no climbable object in scene) ---")

    screenshot("final_state")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test symbolic action primitives visually")
    parser.add_argument("--mode", choices=["eib", "symbolic", "both"], default="eib",
                        help="Which primitive set to test")
    parser.add_argument("--task", default="cook_kielbasa",
                        help="BDDL task name (default: cook_kielbasa)")
    parser.add_argument("--scene", default="Rs_int",
                        help="Scene model (default: Rs_int)")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated action names to test (e.g., navigate_to,grasp)")
    parser.add_argument("--output", default=None,
                        help="Output directory (default: auto-generated)")
    args = parser.parse_args()

    only_actions = None
    if args.only:
        only_actions = [a.strip().lower() for a in args.only.split(",")]
        print(f"Filtering to actions: {only_actions}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_base = args.output or os.path.join(
        os.path.dirname(__file__), "..", "..", "experiments",
        f"test_actions_{args.mode}_{args.task}_{timestamp}",
    )
    os.makedirs(output_base, exist_ok=True)
    print(f"\nOutput directory: {output_base}")

    all_results = {}

    from omnigibson.envs.eib_omnigibson_kitchen_env import OmniGibsonKitchenEnv

    eib_env_config_path = os.path.join(EIB_DATA_DIR, "env", "env.yaml")
    eib_bddl_dir = os.path.join(EIB_DATA_DIR, "task", "IH", "bddl")

    # Create OmniGibsonKitchenEnv once — used by both EIB and OG Symbolic tests
    # (CameraMixin ensures good camera positioning for all screenshots)
    eib_env = None
    _saved_robot_pos = None  # saved at env creation time (always valid)
    _saved_robot_ori = None

    def _ensure_env():
        nonlocal eib_env, _saved_robot_pos, _saved_robot_ori
        if eib_env is None:
            eib_env = OmniGibsonKitchenEnv(
                config_path=eib_env_config_path,
                task_name=args.task,
                scene_name=args.scene,
                bddl_dir=eib_bddl_dir,
            )
            # Save initial robot pose — guaranteed clean at this point
            pos, ori = eib_env.robot.get_position_orientation()
            _saved_robot_pos = pos.clone()
            _saved_robot_ori = ori.clone()
            print(f"  Initial robot pose saved: pos={pos.tolist()}, ori={ori.tolist()}")
        return eib_env

    # ======================================================================
    # Test EIB primitives
    # ======================================================================
    if args.mode in ("eib", "both"):
        print(f"\n{'#'*60}")
        print(f"# Testing EIB Semantic Action Primitives")
        print(f"# Task: {args.task}, Scene: {args.scene}")
        print(f"{'#'*60}")

        _ensure_env()
        eib_save_dir = os.path.join(output_base, "eib")
        try:
            results = test_eib_primitives(eib_env, eib_save_dir, only_actions)
            all_results["eib"] = results
        except Exception as e:
            print(f"\nEIB test failed with error: {e}")
            traceback.print_exc()
            all_results["eib"] = [{"error": str(e)}]

    # ======================================================================
    # Test OG Symbolic primitives
    # ======================================================================
    if args.mode in ("symbolic", "both"):
        print(f"\n{'#'*60}")
        print(f"# Testing OG Symbolic Semantic Action Primitives")
        print(f"# Task: {args.task}, Scene: {args.scene}")
        print(f"{'#'*60}")

        _ensure_env()

        # Reset scene for a clean OG Symbolic test
        if args.mode == "both":
            print("  Resetting scene for OG Symbolic test...")
            import omnigibson as og
            # Release any held objects
            try:
                eib_env.primitives._release_ag()
            except Exception:
                pass
            eib_env.primitives._grasped_obj = None
            eib_env.primitives._tracking_object = None
            eib_env.scene.reset()
            # Use SAVED initial pose (not current — current may be NaN after EIB tests)
            robot = eib_env.robot
            robot_pos = _saved_robot_pos.clone()
            robot_ori = _saved_robot_ori.clone()
            robot.set_position_orientation(position=robot_pos, orientation=robot_ori)
            robot.keep_still()
            for _ in range(10):
                robot.set_position_orientation(position=robot_pos, orientation=robot_ori)
                robot.keep_still()
                og.sim.step()
            # Final pin to ensure clean state
            robot.set_position_orientation(position=robot_pos, orientation=robot_ori)
            robot.keep_still()
            print(f"  Robot reset to initial pose: pos={robot_pos.tolist()}, ori={robot_ori.tolist()}")

        sym_save_dir = os.path.join(output_base, "symbolic")
        try:
            results = test_og_symbolic_primitives(eib_env, sym_save_dir, only_actions)
            all_results["symbolic"] = results
        except Exception as e:
            print(f"\nSymbolic test failed with error: {e}")
            traceback.print_exc()
            all_results["symbolic"] = [{"error": str(e)}]

    # Clean up
    if eib_env is not None:
        try:
            eib_env.close()
        except Exception:
            pass

    # ======================================================================
    # Summary
    # ======================================================================
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")

    for mode, results in all_results.items():
        print(f"\n--- {mode.upper()} ---")
        if not results:
            print("  No results")
            continue
        success = sum(1 for r in results if r.get("status") == "SUCCESS")
        failed = sum(1 for r in results if r.get("status") in ("FAILED", "SCENARIO_FAILED"))
        skipped = sum(1 for r in results if r.get("status") in ("UNKNOWN_PRIMITIVE", "SKIP"))
        print(f"  SUCCESS: {success}  FAILED: {failed}  SKIPPED: {skipped}")
        for r in results:
            status = r.get("status", "?")
            action = r.get("action", "?")
            args_str = ", ".join(r.get("args", []))
            steps = r.get("env_steps", "")
            error = r.get("error", "")
            mark = "OK" if status == "SUCCESS" else "FAIL" if "FAIL" in status else "SKIP"
            line = f"  [{mark}] {action}[{args_str}]"
            if steps:
                line += f" ({steps} steps)"
            if error:
                line += f" - {error[:80]}"
            print(line)

    # Save results JSON
    results_path = os.path.join(output_base, "results.json")
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {results_path}")
    print(f"Screenshots saved to: {output_base}")


if __name__ == "__main__":
    main()
