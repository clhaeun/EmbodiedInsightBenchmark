"""
CATS Decorative Pattern Task G: Tilt-to-Release Storage Bench

Level: 2.3 (Insight-based technique selection + parameter adaptation)
Scene: Living room with a cedar chest (storage bench). The lid has a
       decorative metal latch on the front and a real hinge at the rear.
       The actual locking mechanism is a gravity latch (hidden pin on
       the underside of the front edge).

Combination type: Indirect force transfer
  - Individual LIFT[front] → blocked by gravity latch (property)
  - Individual PUSH[latch] → doesn't move, decorative (property)
  - Individual PRESS[rear] → pivot detected + front click (property)
  - PRESS[rear] sustained + LIFT[front] → gravity latch releases → opens

Visual trap: Decorative metal latch on front + visible hinge at rear
             → "flip the latch and lift the front" seems obvious

This is the highest-difficulty task: the agent must discover that pressing
the REAR (indirect) releases the FRONT latch (3-step causal chain).
No-demo expected success: 5-15%.
"""

import json


# ---------------------------------------------------------------------------
# Parameter checker for tilt-to-release technique
# ---------------------------------------------------------------------------
def _check_tilt_release_params(description):
    """Validate tilt-to-release parameters.

    Required for success:
      rear_press_force_N:  8 ~ 20
      press_position:      must contain "rear" (rear edge for pivot effect)
      hold_while_lift:     must be True (release → latch re-engages)
      front_lift_force_N:  3 ~ 15

    Failure modes:
      hold_while_lift = False  →  latch re-engages before lift
      press_position != rear   →  insufficient pivot effect
      rear force < 5           →  pin doesn't rise enough
      rear force > 25          →  hinge damage
      lift force < 2           →  can't open lid
      lift force > 20          →  hinge stress
    """
    try:
        params = json.loads(description)
    except Exception:
        return {
            "outcome": "FAILURE",
            "aux_text": "Could not parse parameters. Provide valid JSON.",
        }

    rear_force = params.get("rear_press_force_N", 0)
    position = str(params.get("press_position", "")).lower()
    hold = params.get("hold_while_lift", False)
    lift_force = params.get("front_lift_force_N", 0)

    # --- Failure: not holding rear press during lift ---
    if not hold:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You press the rear, then release to reposition for "
                "lifting the front. Upon releasing rear pressure, the "
                "gravity latch pin drops back into the catch. When you "
                "attempt to lift the front, it is locked again."
            ),
        }

    # --- Failure: wrong press position ---
    if "rear" not in position:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"You press at '{position}', but the pivot effect is "
                "insufficient. The hinge axis is at the rear edge — "
                "pressing near the center or front does not create enough "
                "angular displacement to lift the front edge and release "
                "the gravity latch pin."
            ),
        }

    # --- Failure: insufficient rear force ---
    if rear_force < 5:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Rear press force too low ({rear_force:.1f} N). The lid "
                "tilts slightly but the front edge does not rise enough "
                "for the gravity latch pin to clear the catch."
            ),
        }

    # --- Failure: excessive rear force ---
    if rear_force > 25:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Excessive rear force ({rear_force:.1f} N). The hinge "
                "mechanism strains under the load. Risk of damage."
            ),
        }

    # --- Failure: insufficient lift force ---
    if lift_force < 2:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Front lift force too low ({lift_force:.1f} N). The lid "
                "barely moves after latch release."
            ),
        }

    # --- Failure: excessive lift force ---
    if lift_force > 20:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Excessive lift force ({lift_force:.1f} N). The hinge "
                "mechanism is stressed beyond safe limits."
            ),
        }

    # --- SUCCESS ---
    optimal = (8 <= rear_force <= 20 and 3 <= lift_force <= 15)

    return {
        "outcome": "SUCCESS",
        "aux_text": (
            f"You press the rear edge with {rear_force:.1f} N. The lid "
            "tilts slightly — the front edge rises. You hear a faint "
            "metallic click as the gravity latch pin clears the catch. "
            f"While maintaining rear pressure, you lift the front with "
            f"{lift_force:.1f} N. The lid swings open on its rear hinge. "
            "Inside the chest, you see a necklace."
        ),
        "optimal": optimal,
        "state_changes": [
            {"type": "set_flag", "flag": "lid_opened"},
        ],
    }


# ---------------------------------------------------------------------------
# TASK_CONFIG
# ---------------------------------------------------------------------------
TASK_CONFIG = {
    # === Basic info ===
    "task_name": "tilt_to_release_bench",
    "level": "2.3",
    "instruction": (
        "Open the storage chest in the living room and retrieve "
        "the necklace inside."
    ),

    # === CA technique candidates (neutral names — no hints) ===
    "correct_tool": "technique_B",
    "ca_tool_names": [
        "technique_A",   # Demo 1: 시각적 함정 (래치 올리기)
        "technique_B",   # Demo 2: 정답 (뒤 눌러서 앞 열기)
        "technique_C",   # Demo 3: distractor (슬라이드)
        "technique_D",   # Demo 4: distractor (전체 들기)
    ],
    "extra_object_names": [],

    # === Stage 1: Exploration ===
    "exploration_primitives_desc": (
        "Available exploration actions:\n"
        "- NAVIGATE_TO[target]: Move to observe. "
        "Returns camera image.\n"
        "  Valid targets: chest | chest, close_up | chest, rear_view\n\n"
        "- LIFT[object, position]: Try to lift. "
        "Returns force and obstruction data.\n"
        "  Valid: lid, front | lid, rear\n\n"
        "- PRESS[object, position]: Apply downward pressure. "
        "Returns force-displacement data.\n"
        "  Valid: lid, rear_end | lid, center\n\n"
        "- PUSH[object, direction]: Push an object. "
        "Returns force data.\n"
        "  Valid: latch, upward | lid, forward\n\n"
        "- TOUCH[surface]: Feel surface properties. "
        "Returns tactile data.\n"
        "  Valid: latch | lid_front_edge | hinge | lid_surface\n\n"
        "- DONE_EXPLORING: Finish exploration phase."
    ),

    "exploration_nav_targets": {
        "chest":             "cedar_chest_901",
        "chest, close_up":   "cedar_chest_901",
        "chest, rear_view":  "cedar_chest_901",
    },
    "exploration_nav_tracking": {
        "chest":             "cedar_chest_901",
        "chest, close_up":   "cedar_chest_901",
        "chest, rear_view":  "cedar_chest_901",
    },
    "exploration_look_targets": {},
    "exploration_direct_camera": {},
    "exploration_no_image": False,

    # === Exploration feedbacks (v2: raw sensor/spatial data) ===
    "exploration_feedbacks": {
        # --- NAVIGATE_TO: spatial scan data (no image) ---
        "NAVIGATE_TO[chest]": (
            "=== Spatial Scan (depth + RGB point cloud) ===\n"
            "Object detected: rectangular solid against wall\n"
            "Bounding box: 0.40 x 0.53 x 0.26 m (W x D x H)\n"
            "Material: wood (cedar), dark brown finish\n"
            "Position: floor level, rear face against wall\n"
            "=== Front face (facing observer) ===\n"
            "  Metal plate: center of front face, 85 x 40 x 4 mm\n"
            "    Pattern: scroll/ornamental, oxidized iron\n"
            "    Mounting: flush to surface, no visible gap or hinge\n"
            "=== Top surface (lid) ===\n"
            "  Flat panel, 0.40 x 0.53 m, smooth wood\n"
            "  Seam detected: 2 mm gap between lid and base body\n"
            "    Seam runs along front, left, and right edges\n"
            "    No seam at rear edge (continuous material)\n"
            "=== Rear edge ===\n"
            "  Two metal brackets: steel, zinc-plated, spacing 300 mm\n"
            "  Bracket profile: continuous strip, 25 mm wide\n"
            "  Brackets connect lid panel to base body"
        ),
        "NAVIGATE_TO[chest, close_up]": (
            "=== Close-Range Scan (50 cm distance) ===\n"
            "=== Front face detail ===\n"
            "  Metal plate: scroll pattern, 4 weld points at corners\n"
            "  Surface: oxidized patina, Ra ~12 um roughness\n"
            "  No gap between plate and wood substrate (0.0 mm)\n"
            "  No visible hinge, pivot, or sliding track on plate\n"
            "=== Lid front edge detail ===\n"
            "  Wood-to-wood seam: 2.0 mm gap, uniform\n"
            "  Edge profile: square cut, no bevel or lip\n"
            "  No visible latch, hook, or button along seam"
        ),
        "NAVIGATE_TO[chest, rear_view]": (
            "=== Rear Scan ===\n"
            "  Two steel brackets along rear edge:\n"
            "    Bracket 1: position (0.10, 0.53, 0.22) m from front-left corner\n"
            "    Bracket 2: position (0.30, 0.53, 0.22) m from front-left corner\n"
            "    Each bracket spans lid-to-base junction\n"
            "  No seam at rear edge — lid and base share continuous bracket axis\n"
            "  Wall contact: rear face flush against wall, 0 mm clearance"
        ),

        # --- LIFT: force-displacement ---
        "LIFT[lid, front]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 15.0 N (upward, front edge)\n"
            "Displacement Z (front): 0.0 mm\n"
            "Displacement Z (rear): 0.0 mm\n"
            "Strain distribution: front 0.92, center 0.31, rear 0.04\n"
            "Reaction force at front edge: 15.0 N (equal to applied)\n"
            "Net movement: none"
        ),
        "LIFT[lid, rear]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 10.0 N (upward, rear edge)\n"
            "Displacement Z (rear): 0.0 mm\n"
            "Displacement Z (front): 0.0 mm\n"
            "Rear edge constrained by brackets\n"
            "Net movement: none"
        ),

        # --- PUSH[latch]: force data ---
        "PUSH[latch, upward]": (
            "=== Force Sensor Data ===\n"
            "Applied force: 8.0 N (upward on metal plate)\n"
            "Displacement: 0.0 mm\n"
            "Stiffness: > 10000 N/m (rigid connection)\n"
            "Material: ferrous metal, oxidized surface\n"
            "Joint detection: none (welded to substrate)"
        ),

        # --- PRESS[rear]: displacement + vibration + noisy front reading ---
        "PRESS[lid, rear_end]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 12.0 N (downward, rear quadrant)\n"
            "Displacement Z (rear): -3.2 mm\n"
            "Displacement Z (center): -0.8 mm\n"
            "Displacement Z (front): +0.5 mm\n"
            "Stiffness (rear): 3750 N/m\n"
            "=== Accelerometer (lid-mounted, 3-axis) ===\n"
            "Transient event #1 at t=0.42 s:\n"
            "  Peak acceleration: 2.3 m/s^2\n"
            "  Dominant frequency: 1180 Hz\n"
            "  Duration: 4.2 ms\n"
            "  Axis: primarily Z\n"
            "=== Release (force removed) ===\n"
            "Return time to Z=0: 0.15 s (all measurement points)\n"
            "Transient event #2 at t=0.58 s:\n"
            "  Peak acceleration: 2.1 m/s^2\n"
            "  Dominant frequency: 1210 Hz\n"
            "  Duration: 3.8 ms"
        ),
        "PRESS[lid, center]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 12.0 N (downward, center)\n"
            "Displacement Z (rear): -0.1 mm\n"
            "Displacement Z (center): -0.4 mm\n"
            "Displacement Z (front): -0.1 mm\n"
            "Stiffness (center): 30000 N/m\n"
            "=== Accelerometer ===\n"
            "Transient event at t=0.35 s:\n"
            "  Peak acceleration: 0.8 m/s^2\n"
            "  Dominant frequency: 980 Hz\n"
            "  Duration: 1.5 ms\n"
            "  Axis: Z"
        ),

        # --- PUSH[lid]: force data ---
        "PUSH[lid, forward]": (
            "=== Force Sensor Data ===\n"
            "Applied force: 10.0 N (horizontal, +Y direction)\n"
            "Displacement Y: 0.0 mm\n"
            "Displacement X: 0.0 mm\n"
            "Rear constraint detected (bracket axis)"
        ),

        # --- TOUCH: tactile arrays ---
        "TOUCH[lid_front_edge]": (
            "=== Tactile Sensor Array (4x4, kPa) ===\n"
            "Upper surface scan:\n"
            "[[  2.1,  2.0,  2.1,  2.0],\n"
            " [  2.0,  2.1,  2.0,  2.1],\n"
            " [  2.1,  2.0,  2.1,  2.0],\n"
            " [  2.0,  2.1,  2.0,  2.1]]\n"
            "Uniform contact, wood grain texture\n"
            "=== Underside probe (fingertip, 1x1) ===\n"
            "Contact at offset (0.19, 0.0, -0.008) m from lid center\n"
            "Geometry: small cylindrical protrusion, D=5.1 mm, L=7.8 mm\n"
            "Orientation: vertical (pointing downward)\n"
            "Material: metal\n"
            "Mobility: slight vertical play under lateral force"
        ),

        "TOUCH[hinge]": (
            "=== Tactile Sensor Array ===\n"
            "Rear edge hardware:\n"
            "  Count: 2 brackets, spacing 300 mm\n"
            "  Material: steel, zinc-plated\n"
            "  Profile: continuous strip, width 25 mm\n"
            "  Rotational resistance: 0.12 Nm (low)\n"
            "  Rotational range: approximately 110 degrees\n"
            "  Current position: 0 degrees (closed)"
        ),

        "TOUCH[latch]": (
            "=== Tactile Sensor Array ===\n"
            "Material: ferrous metal, oxidized surface\n"
            "Surface roughness: Ra 12.5 um\n"
            "Temperature: 21.6 C\n"
            "Geometry: scroll-shaped plate, 85 x 40 x 4 mm\n"
            "Joint detection: none\n"
            "Gap to substrate: 0.0 mm\n"
            "Weld points detected: 4 (corners)"
        ),

        "TOUCH[lid_surface]": (
            "=== Tactile Sensor Array ===\n"
            "Material: softwood (estimated density 380 kg/m^3)\n"
            "Surface finish: oil/wax coating\n"
            "Temperature: 21.8 C\n"
            "Thickness (acoustic tap): ~18 mm\n"
            "Mass estimate (inertial): ~2.5 kg\n"
            "Compliance: < 0.01 mm/N (rigid)"
        ),
    },

    # === Demo configuration ===
    "demo_image_paths": [],   # No video files yet
    "demo_labels": [],        # v2: no labels provided
    # Text-only demo descriptions (used when demo_image_paths is empty)
    "demo_text_descriptions": [
        (
            "A metal toolbox with a spring-loaded clasp on the front. "
            "The person flips the clasp upward with their thumb, "
            "releasing the lid. They then lift the lid open from the front."
        ),
        (
            "A playground see-saw. A child steps onto one end, pushing "
            "it down to the ground. The opposite end rises up into the "
            "air, launching a ball that was sitting on it."
        ),
        (
            "A low wooden toy chest with a flat top. The person grips "
            "the front edge of the top panel and slides it forward "
            "along built-in grooves until the inside is fully exposed."
        ),
        (
            "A cardboard gift box with no hinges or latches. The person "
            "grabs both sides of the lid and lifts it straight up, "
            "completely separating it from the base."
        ),
    ],

    # === Technique selection prompts ===
    "tool_selection_prompt": (
        "Based on your exploration findings and the demonstrations, "
        "determine the correct technique to open this storage chest.\n\n"
        "Provide:\n"
        "(1) Which demonstration is most relevant and why\n"
        "(2) What technique you will use\n"
        "(3) What physical evidence from exploration supports this\n"
        "(4) Your execution plan with specific parameters\n\n"
        "IMPORTANT: At the very end, write ONLY:\n"
        "SELECTED_TOOL: <technique_name>\n"
        "where <technique_name> is one of: "
        "technique_A, technique_B, technique_C, technique_D"
    ),
    "tool_selection_prompt_no_demo": (
        "Based on your exploration findings alone, determine the "
        "correct technique to open this storage chest.\n\n"
        "Provide:\n"
        "(1) What physical principle guides your technique selection\n"
        "(2) What technique you will use\n"
        "(3) What sensor data supports this choice\n"
        "(4) Your execution plan with specific parameters\n\n"
        "IMPORTANT: At the very end, write ONLY:\n"
        "SELECTED_TOOL: <technique_name>\n"
        "where <technique_name> is one of: "
        "technique_A, technique_B, technique_C, technique_D"
    ),

    # === Stage 3: Menu-based symbolic execution ===
    "stage3_action_menu": {
        # --- Correct technique: technique_B ---
        "APPLY_TECHNIQUE[lid]": {
            "tool_key": "technique_B",
            "description": (
                "Apply the tilt-and-lift technique to open the lid. "
                "Specify your approach and parameters in JSON format: "
                '{"rear_press_force_N": <float>, '
                '"press_position": "<string>", '
                '"hold_while_lift": true or false, '
                '"front_lift_force_N": <float>}'
            ),
            "param_checker": _check_tilt_release_params,
        },

        # --- Visual trap: technique_A ---
        "FLIP_LATCH[latch]": {
            "tool_key": "technique_A",
            "description": "Flip the metal latch upward to unlock, then lift the lid.",
            "outcome": "FAILURE",
            "feedback": (
                "You attempt to flip the metal latch upward, but it does "
                "not move. The latch is rigidly welded to the lid surface — "
                "it is purely decorative. There is no pivot or sliding "
                "mechanism. The lid remains locked."
            ),
        },

        # --- Distractor: technique_C ---
        "SLIDE_FORWARD[lid]": {
            "tool_key": "technique_C",
            "description": "Slide the lid forward to open.",
            "outcome": "FAILURE",
            "feedback": (
                "You push the lid forward but it does not slide. "
                "The rear hinge constrains the lid to rotational "
                "movement only. Sliding is not possible."
            ),
        },

        # --- Distractor: technique_D ---
        "FULL_LIFT[lid]": {
            "tool_key": "technique_D",
            "description": "Lift the entire lid straight up to open.",
            "outcome": "FAILURE",
            "feedback": (
                "You apply upward force across the lid but it does not "
                "rise. The internal catch at the front edge blocks "
                "rotation. The rear hinge prevents vertical translation. "
                "The lid remains locked."
            ),
        },

        # --- Post-open actions ---
        "GRASP[necklace]": {
            "description": "Grasp the necklace from inside the open chest.",
            "requires": "lid_opened",
            "outcome": "SUCCESS",
            "feedback": "You reach into the open chest and grasp the necklace.",
        },
        "PLACE_ON_TOP[necklace, floor]": {
            "description": "Place the necklace on the floor next to the chest.",
            "requires": "GRASP[necklace]",
            "outcome": "SUCCESS",
            "feedback": (
                "You place the necklace on the floor. "
                "The necklace has been retrieved from the chest. Task complete."
            ),
            "task_success": True,
            "state_changes": [
                {
                    "type": "teleport",
                    "object": "necklace_902",
                    "position": [1.8, 2.0, 0.02],
                },
            ],
        },
    },
    "one_shot_execution": True,

    # === Metacognitive probes ===
    "probes": {
        "stage1": (
            "What did you discover about this chest's opening mechanism? "
            "The front has a metal latch and the rear has hinges — did "
            "the physical properties match what you expected? What "
            "specific sensor readings were most informative?"
        ),
        "stage3": (
            "Did you apply the technique exactly as shown in the demo, "
            "or did you modify any parameters? How did you determine "
            "the correct force and position for pressing?"
        ),
    },
}
