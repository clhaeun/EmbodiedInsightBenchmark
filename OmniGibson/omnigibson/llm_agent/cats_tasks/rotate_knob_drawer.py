"""
CATS Decorative Pattern Task F: Push-Turn-Pull Knob Drawer

Level: 2.3 (Insight-based technique selection + parameter adaptation)
Scene: Kitchen cabinet with a drawer that has a round knob handle with
       a hidden center button. The button must be pressed while rotating,
       and then the rotated state must be held while pulling.

Combination type: 3-step sequential hold
  - Individual PULL[knob] → locked (property)
  - Individual TWIST[knob] → won't rotate, blocked (property — KEY DIFFERENCE)
  - Individual PRESS[knob_center] → subtle 0.5mm compliance, no click (property)
  - PRESS[center] + TWIST simultaneously → knob rotates 90° (intermediate)
  - Hold rotation + PULL → drawer opens (solution, Stage 3 only)

Visual trap: Round knob → "just grab and pull" seems obvious.
             Even after discovering the button, "press button then pull"
             seems more natural than the 3-step press→twist→pull chain.
"""

import json


def _check_press_twist_pull_params(description):
    """Validate 3-step press-twist-pull parameters.

    Required for success:
      press_center:        must be True (button must be engaged)
      hold_press_while_twist: must be True (release → button resets)
      rotation_degrees:    85 ~ 95 (quarter turn)
      rotation_direction:  must contain "clockwise"
      hold_twist_while_pull: must be True (release → spring resets knob)
      pull_force_N:        5 ~ 15
    """
    try:
        params = json.loads(description)
    except Exception:
        return {
            "outcome": "FAILURE",
            "aux_text": "Could not parse parameters. Provide valid JSON.",
        }

    press_center = params.get("press_center", False)
    hold_press = params.get("hold_press_while_twist", False)
    rotation = params.get("rotation_degrees", 0)
    direction = str(params.get("rotation_direction", "")).lower()
    hold_twist = params.get("hold_twist_while_pull", False)
    pull_force = params.get("pull_force_N", 0)

    # --- Failure: no center press ---
    if not press_center:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You attempt to rotate the knob without pressing the "
                "center button. The knob is locked and does not rotate. "
                "The internal pin blocks rotation until the button is "
                "depressed."
            ),
        }

    # --- Failure: not holding press during twist ---
    if not hold_press:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You press the center button, hear a click, then release "
                "it to reposition your grip for rotation. The button "
                "springs back immediately and the rotation lock "
                "re-engages. The knob does not rotate."
            ),
        }

    # --- Failure: wrong direction ---
    if "counter" in direction:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "With the button depressed, you attempt counterclockwise "
                "rotation. The knob hits a hard stop after 5 degrees. "
                "The cam only clears in the clockwise direction."
            ),
        }

    # --- Failure: insufficient rotation ---
    if rotation < 80:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Rotation insufficient ({rotation:.0f} deg). The cam "
                "does not fully clear the lock position."
            ),
        }

    # --- Failure: over-rotation ---
    if rotation > 100:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Over-rotation ({rotation:.0f} deg). The cam passes "
                "the unlock position and re-engages on the far side."
            ),
        }

    # --- Failure: not holding twist during pull ---
    if not hold_twist:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You rotate the knob 90 degrees successfully, but "
                "release it to reposition for pulling. The spring "
                "returns the knob to 0 degrees within 2 seconds, "
                "re-engaging the cam lock. When you pull, the drawer "
                "is locked again."
            ),
        }

    # --- Failure: insufficient pull ---
    if pull_force < 3:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Pull force too low ({pull_force:.1f} N). The drawer "
                "barely moves."
            ),
        }

    # --- Failure: excessive pull ---
    if pull_force > 20:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Excessive pull force ({pull_force:.1f} N). The drawer "
                "jerks open violently."
            ),
        }

    # --- SUCCESS ---
    optimal = (85 <= rotation <= 95 and 5 <= pull_force <= 15)

    return {
        "outcome": "SUCCESS",
        "aux_text": (
            "You press the center button, hold it, and rotate the knob "
            f"{rotation:.0f} degrees clockwise. Click! While maintaining "
            f"the rotation, you pull with {pull_force:.1f} N. The drawer "
            "slides open smoothly. Inside, you see a screwdriver."
        ),
        "optimal": optimal,
        "state_changes": [
            {"type": "set_flag", "flag": "drawer_opened"},
        ],
    }


TASK_CONFIG = {
    "task_name": "rotate_knob_drawer",
    "level": "2.3",
    "instruction": (
        "Open the kitchen drawer and retrieve the screwdriver inside. "
        "Place it on the countertop."
    ),

    # === CA technique candidates (neutral names) ===
    "correct_tool": "technique_B",
    "ca_tool_names": [
        "technique_A",   # Demo 1: just pull (시각적 함정)
        "technique_B",   # Demo 2: press-center + twist + pull (정답)
        "technique_C",   # Demo 3: push to open (distractor)
        "technique_D",   # Demo 4: twist then pull, no button (distractor)
    ],
    "extra_object_names": [],

    # === Stage 1: Exploration ===
    "exploration_primitives_desc": (
        "Available exploration actions:\n"
        "- NAVIGATE_TO[target]: Move to observe. "
        "Returns spatial scan data.\n"
        "  Valid targets: drawer | drawer, close_up\n\n"
        "- TWIST[object, direction]: Rotate by hand. "
        "Returns torque and displacement data.\n"
        "  Valid: knob, clockwise | knob, counterclockwise\n\n"
        "- PULL[object]: Pull outward. "
        "Returns force and displacement data.\n"
        "  Valid: knob | drawer\n\n"
        "- PRESS[object]: Press inward. "
        "Returns force-displacement data.\n"
        "  Valid: knob_center | drawer_face\n\n"
        "- TOUCH[surface]: Feel surface properties. "
        "Returns tactile data.\n"
        "  Valid: knob | knob_center | drawer_face | drawer_frame\n\n"
        "- DONE_EXPLORING: Finish exploration phase."
    ),

    "exploration_nav_targets": {
        "drawer":           "bottom_cabinet_xqmipa_0",
        "drawer, close_up": "bottom_cabinet_xqmipa_0",
    },
    "exploration_nav_tracking": {
        "drawer":           "bottom_cabinet_xqmipa_0",
        "drawer, close_up": "bottom_cabinet_xqmipa_0",
    },
    "exploration_look_targets": {},
    "exploration_direct_camera": {},
    "exploration_no_image": False,

    # === Exploration feedbacks (raw sensor data ONLY — no interpretation) ===
    "exploration_feedbacks": {
        # --- NAVIGATE_TO: spatial scan ---
        "NAVIGATE_TO[drawer]": (
            "=== Spatial Scan (depth + RGB point cloud) ===\n"
            "Object: rectangular unit against wall\n"
            "Bounding box: 0.69 x 2.35 x 0.81 m (W x D x H)\n"
            "Material: wood, painted white\n"
            "=== Target panel (top-left, 0.30 x 0.25 m) ===\n"
            "  Cylindrical protrusion at center: D=35 mm, H=20 mm\n"
            "    Material: brushed metal\n"
            "    Protrusion from face: 22 mm\n"
            "  Seam around panel: 3 mm gap, uniform"
        ),
        "NAVIGATE_TO[drawer, close_up]": (
            "=== Close-Range Scan (30 cm distance) ===\n"
            "=== Cylindrical protrusion detail ===\n"
            "  Outer ring: D=35.2 mm, H=19.8 mm, brushed metal\n"
            "  Center shaft: D=6 mm, into panel face\n"
            "  Center face region: D=8 mm\n"
            "    Recess depth: 0.5 mm below outer ring surface\n"
            "    Surface texture: smoother than outer ring\n"
            "=== Panel face ===\n"
            "  Material: painted MDF, smooth\n"
            "  Seam: 3.0 mm gap to frame, uniform all sides"
        ),

        # --- TWIST: torque + displacement only ---
        "TWIST[knob, clockwise]": (
            "=== Torque Sensor Data ===\n"
            "Applied torque: 1.5 Nm (clockwise)\n"
            "Angular displacement: 0 degrees\n"
            "Reaction torque: 1.5 Nm (equal to applied)\n"
            "=== Accelerometer ===\n"
            "No transient events detected\n"
            "Background noise: 0.04 m/s^2"
        ),
        "TWIST[knob, counterclockwise]": (
            "=== Torque Sensor Data ===\n"
            "Applied torque: 1.5 Nm (counterclockwise)\n"
            "Angular displacement: 0 degrees\n"
            "Reaction torque: 1.5 Nm (equal to applied)\n"
            "=== Accelerometer ===\n"
            "No transient events detected"
        ),

        # --- PULL: force + displacement only ---
        "PULL[knob]": (
            "=== Force Sensor Data ===\n"
            "Applied force: 12.0 N (outward)\n"
            "Displacement (knob): 0.0 mm\n"
            "Displacement (panel): 0.0 mm\n"
            "Reaction force: 12.0 N (equal to applied)"
        ),
        "PULL[drawer]": (
            "=== Force Sensor Data ===\n"
            "Applied force: 15.0 N (outward, on panel edge)\n"
            "Displacement: 0.0 mm\n"
            "Reaction force: 15.0 N (equal to applied)"
        ),

        # --- PRESS: force-displacement + accelerometer ---
        "PRESS[knob_center]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 5.0 N (inward, on D=8 mm center region)\n"
            "Center displacement: 0.5 mm (inward)\n"
            "Outer ring displacement: 0.0 mm\n"
            "=== Accelerometer ===\n"
            "No transient events detected\n"
            "Background noise: 0.04 m/s^2\n"
            "=== Release (force removed) ===\n"
            "Center returns to 0.0 mm within 0.4 s\n"
            "Panel displacement: 0.0 mm"
        ),
        "PRESS[drawer_face]": (
            "=== Force Sensor Data ===\n"
            "Applied force: 10.0 N (inward, on panel surface)\n"
            "Displacement: 0.0 mm\n"
            "Reaction force: 10.0 N (equal to applied)\n"
            "=== Accelerometer ===\n"
            "No transient events detected"
        ),

        # --- TOUCH: tactile arrays only ---
        "TOUCH[knob]": (
            "=== Tactile Sensor Array (4x4, kPa) ===\n"
            "Shape: cylindrical, D=35 mm\n"
            "Material: brushed metal, circumferential grain\n"
            "Rotational play: 0 degrees\n"
            "Axial play: 0.0 mm\n"
            "Temperature: 22.0 C\n"
            "Center region (D~8 mm): recess 0.5 mm, different texture"
        ),
        "TOUCH[knob_center]": (
            "=== Tactile Sensor Array (1x1, kPa) ===\n"
            "Contact area: circular, D=7.8 mm\n"
            "Surface: smooth metal, recessed 0.5 mm\n"
            "Compliance: 0.10 mm/N (inward)\n"
            "Material: brushed metal (same as outer ring)"
        ),
        "TOUCH[drawer_face]": (
            "=== Tactile Sensor Array ===\n"
            "Material: painted MDF, smooth\n"
            "Temperature: 22.1 C\n"
            "Compliance: < 0.01 mm/N"
        ),
        "TOUCH[drawer_frame]": (
            "=== Tactile Sensor Array ===\n"
            "Frame material: solid wood\n"
            "Top/bottom edges: 2 horizontal channels detected\n"
            "  Channel profile: U-shaped, width 12 mm, depth 5 mm\n"
            "  Orientation: front-to-back\n"
            "  Surface: smooth, low friction coefficient"
        ),
    },

    # === Demo configuration ===
    "demo_image_paths": [],
    "demo_labels": [],
    "demo_text_descriptions": [
        (
            "A bedside table with a small round metal knob on the "
            "drawer front. The person grabs the knob and pulls. The "
            "drawer slides open smoothly. Inside are some books and "
            "a phone charger."
        ),
        (
            "A gas stove burner knob. The person pushes the knob "
            "inward against the panel, and while holding it pushed "
            "in, turns it to the left. A clicking sound is heard "
            "and the burner ignites."
        ),
        (
            "A kitchen cabinet with a flat front panel and no visible "
            "handle. The person pushes the panel inward. It clicks "
            "and pops back out slightly. They grab the edge and pull "
            "it open."
        ),
        (
            "A wooden desk drawer with a round knob. The person "
            "grips the knob and turns it clockwise about a quarter "
            "turn. They hear a click, then pull the drawer open."
        ),
    ],

    # === Technique selection prompts ===
    "tool_selection_prompt": (
        "Based on your exploration findings and the demonstrations, "
        "determine the correct technique to open this drawer.\n\n"
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
        "correct technique to open this drawer.\n\n"
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
        # --- Correct: technique_B (press center + twist + pull) ---
        "APPLY_TECHNIQUE[drawer]": {
            "tool_key": "technique_B",
            "description": (
                "Apply the press-twist-pull technique. "
                "Specify parameters in JSON format: "
                '{"press_center": true/false, '
                '"hold_press_while_twist": true/false, '
                '"rotation_degrees": <float>, '
                '"rotation_direction": "<string>", '
                '"hold_twist_while_pull": true/false, '
                '"pull_force_N": <float>}'
            ),
            "param_checker": _check_press_twist_pull_params,
        },

        # --- Visual trap: technique_A (just pull) ---
        "PULL_KNOB[drawer]": {
            "tool_key": "technique_A",
            "description": "Grab the knob and pull outward to open.",
            "outcome": "FAILURE",
            "feedback": (
                "You grab the knob and pull firmly, but the drawer "
                "does not move. The knob is locked against both "
                "rotation and outward force."
            ),
        },

        # --- Distractor: technique_C (push to open) ---
        "PUSH_TO_OPEN[drawer]": {
            "tool_key": "technique_C",
            "description": "Push the drawer face inward to trigger spring release.",
            "outcome": "FAILURE",
            "feedback": (
                "You push the drawer face inward but nothing happens. "
                "No spring or push-to-open mechanism detected."
            ),
        },

        # --- Distractor: technique_D (simple twist+pull, no button) ---
        "TWIST_AND_PULL[drawer]": {
            "tool_key": "technique_D",
            "description": "Rotate the knob 90 degrees then pull, without pressing any button.",
            "outcome": "FAILURE",
            "feedback": (
                "You attempt to rotate the knob directly, but it is "
                "locked against rotation. Without pressing the center "
                "button first, the internal pin prevents any rotation."
            ),
        },

        # --- Post-open actions ---
        "GRASP[screwdriver]": {
            "description": "Grasp the screwdriver from inside the open drawer.",
            "requires": "drawer_opened",
            "outcome": "SUCCESS",
            "feedback": "You reach into the open drawer and grasp the screwdriver.",
        },
        "PLACE_ON_TOP[screwdriver, countertop]": {
            "description": "Place the screwdriver on the countertop.",
            "requires": "GRASP[screwdriver]",
            "outcome": "SUCCESS",
            "feedback": (
                "You place the screwdriver on the countertop. Task complete."
            ),
            "task_success": True,
            "state_changes": [
                {
                    "type": "teleport",
                    "object": "screwdriver_811",
                    "position": [6.5, -1.90, 0.92],
                },
            ],
        },
    },
    "one_shot_execution": True,

    # === Metacognitive probes ===
    "probes": {
        "stage1": (
            "What did you discover about this drawer's opening mechanism? "
            "The knob appears to be a simple pull handle — did the "
            "physical properties match that expectation? What specific "
            "sensor readings were most informative?"
        ),
        "stage3": (
            "Did you apply the technique exactly as shown in the demo, "
            "or did you modify any parameters? How did you determine "
            "the correct sequence and parameters?"
        ),
    },
}
