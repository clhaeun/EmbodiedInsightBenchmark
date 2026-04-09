"""CATS Task 2.3-A: Egg Retrieval from Narrow Gap.

Level: 2.3 (Insight-based selection)
Scene: house_single_floor (kitchen — stove + countertop with ~2-3cm gap)
Instruction: Retrieve the egg from the narrow gap between the stove and countertop.
Correct tool: spatula (thin, flat — can slide under egg)

Critical Context Features (discovered via exploration):
  - Gap is very narrow (~2-3cm) — only thin objects can enter
  - Hand cannot fit into the gap
  - Egg is on the floor at the bottom of the gap — must be scooped from below
  - Egg is fragile — cannot be pierced or crushed

Demo structure:
  Demo 1 (spatula):  Pizza peel retrieving pizza from oven       — structural match
  Demo 2 (fork):     Fishing with a hook                          — trap (pierces egg)
  Demo 3 (tongs):    Claw machine picking up a toy                — trap (can't open in gap)
  Demo 4 (spoon):    Archaeologist carefully excavating artifact   — partial (curved)
  Demo 5 (towel):    Rock climber lowering rope into crevice       — trap (can't grip egg)
"""

import os

# Base directory for demo assets (user provides actual videos/frames)
_DEMO_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "cats", "demos", "retrieve_egg_from_gap"
)


TASK_CONFIG = {
    # ---- Basic info ----
    "task_name": "retrieve_egg_from_gap",
    "level": "2.3",
    "instruction": (
        "fridge와 cabinet 사이 틈에 빠진 egg을 꺼내라"
    ),
    "correct_tool": "spatula",

    # ---- One-Shot CA Tool Selection ----
    # Scene object names of CA tool candidates (must match scene template)
    "ca_tool_names": [
        "spatula_602",
        "tablefork_603",
        "tongs_604",
        "tablespoon_605",
        "dishtowel_606",
    ],

    # ---- Stage 1: Exploration — Navigation & Camera Tracking ----
    #
    # Scene layout (fridge + cabinet gap, ROTATION-CORRECTED):
    #   fridge_dszchb_0:           pos=[7.808, -1.966, 0.864]  87.4° rotated
    #     AABB: X=[7.551, 8.192], Y=[-2.305, -1.624], Z=[-0.007, 1.713]
    #   bottom_cabinet_fancyy_0:   pos=[8.739, -1.964, 0.997]  90° rotated
    #     AABB: X=[8.217, 9.449], Y=[-2.275, -1.625], Z=[-0.000, 1.972]
    #   gap:    X=[8.192, 8.217], width=2.5cm
    #   egg:    [8.205, -1.965, 0.03]
    #   countertop_kelzer_0: [6.030, -1.984, 0.870]  (tools on X=[6.5,7.1], Y~-1.9)
    #
    # Custom camera views: robot body placed away from gap, camera anchor at gap.
    #   anchor_ori facing -Y (toward gap): quat [0, 0, -0.707, 0.707] = yaw -90°
    #   Camera looks horizontally toward gap (parallel to floor).
    #
    # gap: use teleport_to_face (direct camera was too dark inside the gap)
    "exploration_direct_camera": {},
    "exploration_nav_targets": {
        "gap":            "fridge_dszchb_0",    # robot 1m from fridge, tracking fridge
        "gap, low_angle": "fridge_dszchb_0",    # robot 1m from fridge, tracking egg
        "countertop":     "countertop_kelzer_0",
        "fridge":         "fridge_dszchb_0",
    },
    "exploration_nav_tracking": {
        "gap":            "fridge_dszchb_0",     # tracking fridge → fridge+gap 전체가 보임
        "gap, low_angle": "egg_601",             # tracking egg → 틈 바닥 방향으로 내려다봄
    },
    "exploration_look_targets": {
        "egg":                    "egg_601",
        "gap":                    "fridge_dszchb_0",
        "objects_on_countertop":  "countertop_kelzer_0",
    },

    # ---- Stage 1: Exploration — Primitives Description ----
    "exploration_primitives_desc": (
        "NAVIGATE_TO[target] or NAVIGATE_TO[target, modifier]\n"
        "  Move to a position to observe from a different angle.\n"
        "  Valid: gap | gap, low_angle | countertop | fridge\n\n"
        "TOUCH[surface]\n"
        "  Reach out and feel a surface to sense physical properties.\n"
        "  Valid: gap_walls | egg | countertop_surface | fridge_surface\n\n"
        "PUSH[object, target]\n"
        "  Try to push or insert something.\n"
        "  Valid: hand, gap | fridge\n\n"
        "LOOK_CLOSER[target]\n"
        "  Examine an object or area more carefully from current position.\n"
        "  Valid: egg | gap | objects_on_countertop\n\n"
        "OPEN[object]\n"
        "  Open a container or door.\n"
        "  Valid: cabinet"
    ),

    "exploration_feedbacks": {
        # --- NAVIGATE_TO ---
        "NAVIGATE_TO[gap]":
            "A narrow dark gap between the fridge and the cabinet. Something small is visible at the bottom.",
        "NAVIGATE_TO[gap, low_angle]":
            "An egg is sitting on the floor inside the gap, about 15cm deep. It appears intact.",
        "NAVIGATE_TO[countertop]":
            "You see several objects arranged on the countertop.",
        "NAVIGATE_TO[fridge]":
            "The fridge is a large, tall appliance. The gap is on its right side, between the fridge and an adjacent cabinet.",

        # --- TOUCH ---
        "TOUCH[gap_walls]":
            "The gap is approximately 2-3cm wide. Both walls are hard and smooth.",
        "TOUCH[egg]":
            "You cannot reach the egg. It is too deep inside the narrow gap.",
        "TOUCH[countertop_surface]":
            "Smooth, flat surface at standard kitchen height.",
        "TOUCH[fridge_surface]":
            "Hard, cold metal surface. The fridge is fixed in place.",

        # --- PUSH ---
        "PUSH[hand, gap]":
            "Your hand cannot fit into the gap. The opening is too narrow.",
        "PUSH[fridge]":
            "The fridge does not move. It is too heavy and fixed in place.",

        # --- LOOK_CLOSER ---
        "LOOK_CLOSER[egg]":
            "A standard chicken egg. Fragile — would break on impact or piercing. Resting on the floor, not wedged.",
        "LOOK_CLOSER[gap]":
            "The gap runs from the top of the fridge down to the floor. Uniformly narrow (~2-3cm) throughout.",
        "LOOK_CLOSER[objects_on_countertop]":
            "Several kitchen utensils and objects are arranged on the countertop, within easy reach.",

        # --- OPEN (distractor) ---
        "OPEN[cabinet]":
            "The cabinet door opens. Inside are dishes and cups. Nothing relevant to the task.",
    },

    # ---- Stage 2: Demo Observation ----
    "demo_system_prompt": (
        "Here are some reference demonstrations showing different tools "
        "being used in various situations."
    ),
    # Labels: tool name only, NO text description of video content
    "demo_labels": [
        "Demo 1 — spatula",
        "Demo 2 — fork",
        "Demo 3 — tongs",
        "Demo 4 — spoon",
        "Demo 5 — towel",
    ],
    "demo_image_paths": [
        os.path.join(_DEMO_DIR, "demo1_spatula_pizza_peel.mp4"),
        os.path.join(_DEMO_DIR, "demo2_fork_fishing.mp4"),
        os.path.join(_DEMO_DIR, "demo3_tongs_claw_machine.mp4"),
        os.path.join(_DEMO_DIR, "demo4_spoon_archaeology.mp4"),
        os.path.join(_DEMO_DIR, "demo5_towel_rope_crevice.mp4"),
    ],

    # ---- Tool Selection Step ----
    "tool_selection_prompt": (
        "Now select the tool you will use. "
        "Once you pick up a tool, you cannot switch to another.\n\n"
        "Provide:\n"
        "(1) Which demo you referenced and why\n"
        "(2) Which tool you select\n"
        "(3) What features of the current situation make this tool suitable\n"
        "(4) Your action plan — you may use the following base actions:\n"
        "    NAVIGATE_TO[object], GRASP[object], RELEASE, "
        "PLACE_ON_TOP[object, surface], PUSH[object], PULL[object], OPEN[object]\n"
        "If none of these base actions capture the required motion, "
        "you may define a new action:\n"
        "    NEW_ACTION[name, tool, target]: 'description of the physical motion'\n"
        "This new action must be physically plausible."
    ),

    # ---- Stage 3: NEW_ACTION handlers (for physical grounding) ----
    # Each handler defines how to change IsaacSim state for a (tool, target) pair.
    # Implementation: teleport objects + set states + og.sim.step()
    "new_action_handlers": {
        # spatula → SUCCESS: egg moves to spatula surface, then outside gap
        ("spatula", "egg", "narrow_gap"): {
            "outcome": "SUCCESS",
            "state_changes": [
                # 1. Teleport spatula under egg
                # 2. Place egg on spatula
                # 3. Move spatula+egg outside gap
                # 4. og.sim.step()
            ],
            "aux_text": "The spatula slid under the egg. The egg is now on the spatula.",
        },
        # fork → FAILURE: egg becomes Broken
        ("fork", "egg", "narrow_gap"): {
            "outcome": "FAILURE",
            "state_changes": [
                # 1. egg.states[Broken].set_value(True)
                # 2. og.sim.step()
            ],
            "aux_text": "The fork pierced the egg, causing it to break.",
        },
        # tongs → FAILURE: no state change (can't open in gap)
        ("tongs", "egg", "narrow_gap"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The tongs cannot open wide enough in the narrow gap. "
                "The egg remains in the gap."
            ),
        },
        # spoon → FAILURE: no state change or egg pushed deeper
        ("spoon", "egg", "narrow_gap"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The spoon's curved shape could not slide flat under the egg. "
                "The egg remains in the gap."
            ),
        },
        # towel → FAILURE: no state change (can't grip smooth egg)
        ("towel", "egg", "narrow_gap"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The towel cannot grip the smooth egg surface effectively. "
                "The egg remains in the gap."
            ),
        },
    },

    # ---- Metacognitive Probes (single question per spec) ----
    "probes": {
        "stage1": (
            "Based on your exploration, what are the key features of this situation "
            "that would affect how you approach the task? "
            "What makes this situation unique or challenging?"
        ),
        "stage2": (
            "For each demo, explain how the demonstrated situation is similar to "
            "or different from your current situation."
        ),
        "stage3": (
            "Did you adapt the approach from the demo in any way? "
            "If so, what did you change and why?"
        ),
    },
}
