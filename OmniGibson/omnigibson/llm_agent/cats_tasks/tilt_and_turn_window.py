"""
CATS Decorative Pattern Task C: Tilt-and-Turn Window

Level: 2.3 (Insight-based technique selection + parameter adaptation)
Scene: Bedroom with a dual-hinge window and a small succulent on the inside
       sill. Task: move the succulent to the exterior ledge through the window.
       An external obstacle blocks full swing (52mm gap — pot D=95mm won't fit).
       Tilt mode opens ~150mm at top — pot fits. Binary success criterion.

Combination type: Mode selection + simultaneous hold
  Handle has 3 positions (pointing direction):
    - Horizontal (default): locked — nothing moves
    - Up:   SWING MODE — side hinges (but external obstacle blocks at 52mm)
    - Down: TILT MODE  — top brackets (correct answer)

  Physics model (consistent across exploration and execution):
    - Handle UP   + PUSH[window]     → swing, but blocked at 52mm (0.8 ACH)
    - Handle DOWN + PULL[window_top] → tilt inward (~150mm, 3.2 ACH)
    - Handle DOWN + PUSH[window]     → nothing (side hinges inactive in tilt mode)
    - Handle UP   + PULL[window_top] → nothing (top brackets inactive in swing mode)

  Discovery through exploration:
    - TWIST[handle, up]   → cams disengage for swing mode
    - TWIST[handle, down] → cams disengage for tilt mode (different internal sound)
    - PUSH[window]        → at handle-up: swing 52mm then external obstacle
                            at handle-down: side hinges inactive, no swing
    - PULL[window_top]    → at handle-up: top brackets inactive, no tilt
                            at handle-down: tilt starts but handle springs back

  The agent CANNOT complete "hold handle down + pull top" during exploration
  because handle springs back before they can reposition. The partial tilt
  discovery (brief tilt start then re-lock) is the key clue.

  Solution (Stage 3 only): HOLD handle down + PULL[window_top] simultaneously.

Visual trap: Demo 1 shows swing in obstacle-free space (attractive — breeze).
             Handle UP = swing partially works here: 52mm, 0.8 ACH (marginal).
             The trap is "works but suboptimal", not "physically fails".
             Tilt via handle DOWN opens ~150mm inward (3.2 ACH) — better,
             but requires the less intuitive handle direction + hold + pull.

No-demo expected success: 10-15%.
"""

import json


# ---------------------------------------------------------------------------
# Parameter checker
# ---------------------------------------------------------------------------
def _check_tilt_turn_params(description):
    """Validate tilt-and-turn window parameters.

    Required for success:
      handle_position:        must contain "down"
      hold_handle:            must be True (spring returns in ~3s)
      open_action:            must contain "pull" and "top" / "inward"
      pull_force_N:           2 ~ 8
      target_tilt_degrees:    10 ~ 25

    Failure modes:
      handle up         → swing mode (external obstacle, partial only)
      handle horizontal → locked
      hold = False      → handle springs back, window locks before pull
      push outward      → wrong action for tilt mode (side hinges inactive)
      pull > 10         → hinge damage
      tilt > 30         → restrictor arm limit
    """
    try:
        params = json.loads(description)
    except Exception:
        return {
            "outcome": "FAILURE",
            "aux_text": "Could not parse parameters. Provide valid JSON.",
        }

    position = str(params.get("handle_position", "")).lower()
    hold = params.get("hold_handle", False)
    action = str(params.get("open_action", "")).lower()
    pull_force = params.get("pull_force_N", 0)
    tilt_angle = params.get("target_tilt_degrees", 0)

    # --- Failure: handle up → swing mode (partial, blocked) ---
    if "up" in position:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You turn the handle upward (swing mode). The side "
                "hinges engage and you push the window outward. After "
                "52 mm of travel, the sash edge presses against an "
                "external metal bracket. The 52 mm gap is too narrow "
                "to pass the succulent pot (D=95 mm) through."
            ),
        }

    # --- Failure: handle horizontal or unspecified ---
    if "down" not in position:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Handle at '{position}' — the window remains in its "
                "default locked state. No mode is activated."
            ),
        }

    # --- Failure: not holding handle ---
    if not hold:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You turn the handle downward and hear a click, then "
                "release it to reposition your hands. The spring-loaded "
                "handle returns to horizontal within 3 seconds. By the "
                "time you reach for the window top, it is locked again."
            ),
        }

    # --- Failure: push outward instead of pull top ---
    if "push" in action or "outward" in action:
        if "pull" not in action:
            return {
                "outcome": "FAILURE",
                "aux_text": (
                    "You hold the handle down and push the window outward. "
                    "In the down-handle (tilt) position, the side hinges "
                    "are disengaged — pushing outward has no effect. Only "
                    "the top brackets are active in this mode."
                ),
            }

    # --- Failure: insufficient pull force ---
    if pull_force < 1.5:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Pull force too low ({pull_force:.1f} N). The window "
                "top barely separates from the gasket seal."
            ),
        }

    # --- Failure: excessive pull force ---
    if pull_force > 10:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Excessive pull force ({pull_force:.1f} N). The top "
                "restrictor arm strains under the load."
            ),
        }

    # --- Failure: tilt angle exceeds limit ---
    if tilt_angle > 30:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Tilt angle {tilt_angle:.0f} degrees exceeds the "
                "restrictor arm limit (~28 degrees). The arm catches "
                "and prevents further opening."
            ),
        }

    # --- SUCCESS ---
    optimal = (2 <= pull_force <= 8 and 10 <= tilt_angle <= 25)

    return {
        "outcome": "SUCCESS",
        "aux_text": (
            "You hold the handle in the down position. While "
            "maintaining handle pressure with one hand, you pull the "
            f"top of the window inward with {pull_force:.1f} N. The "
            f"upper edge tilts inward to approximately {tilt_angle:.0f} "
            "degrees. The gap at the top is wide enough to pass the "
            "succulent pot through. The window does not swing outward "
            "— no contact with any external obstacle."
        ),
        "optimal": optimal,
        "state_changes": [
            {"type": "set_flag", "flag": "window_tilted"},
        ],
    }


# ---------------------------------------------------------------------------
# TASK_CONFIG
# ---------------------------------------------------------------------------
TASK_CONFIG = {
    # === Basic info ===
    "task_name": "tilt_and_turn_window",
    "level": "2.3",
    "instruction": (
        "Move the small potted succulent from the inside windowsill "
        "to the exterior ledge so it gets direct sunlight."
    ),

    # === CA technique candidates ===
    "correct_tool": "technique_B",
    "ca_tool_names": [
        "technique_A",   # Demo 1: swing open (맥락적 함정)
        "technique_B",   # Demo 2: tilt open (정답, cross-domain)
        "technique_C",   # Demo 3: sliding (distractor)
        "technique_D",   # Demo 4: crank (distractor)
    ],
    "extra_object_names": [],

    # === Stage 1: Exploration ===
    "exploration_primitives_desc": (
        "Available exploration actions:\n"
        "- NAVIGATE_TO[target]: Move to observe. "
        "Returns spatial scan data.\n"
        "  Valid targets: window | window, close_up\n\n"
        "- TWIST[object, direction]: Turn handle to a position. "
        "Returns torque and detent data.\n"
        "  Valid: handle, up | handle, down\n\n"
        "- PUSH[object]: Push outward. "
        "Returns force, displacement, and trajectory data.\n"
        "  Valid: window\n\n"
        "- PULL[object]: Pull inward. "
        "Returns force and displacement data.\n"
        "  Valid: window_top\n\n"
        "- TOUCH[surface]: Feel surface properties. "
        "Returns tactile data.\n"
        "  Valid: handle | window_frame | window_glass\n\n"
        "- DONE_EXPLORING: Finish exploration phase."
    ),

    "exploration_nav_targets": {
        "window":            "window_801",
        "window, close_up":  "window_801",
    },
    "exploration_nav_tracking": {
        "window":            "window_801",
        "window, close_up":  "window_801",
    },
    "exploration_look_targets": {},
    "exploration_direct_camera": {},
    "exploration_no_image": False,

    # === Exploration feedbacks ===
    #
    # KEY DESIGN: Each handle position enables exactly ONE mode.
    #   Handle UP   → side hinges active  (swing)  → PUSH works, PULL top doesn't
    #   Handle DOWN → top brackets active (tilt)   → PULL top works, PUSH doesn't
    #
    # PUSH and PULL feedbacks show what happens at BOTH handle positions
    # (the system does a quick twist-then-action before handle springs back).
    #
    "exploration_feedbacks": {
        # --- NAVIGATE_TO ---
        "NAVIGATE_TO[window]": (
            "=== Spatial Scan (depth + RGB point cloud) ===\n"
            "Object: rectangular window panel set in wall\n"
            "Dimensions: 1.20 x 1.50 m (W x H)\n"
            "Frame material: uPVC, white, double-glazed\n"
            "Sill height from floor: 0.85 m\n"
            "=== Handle ===\n"
            "  Type: lever, left side of frame\n"
            "  Current position: horizontal (default)\n"
            "=== Hinge survey ===\n"
            "  Left edge: 2 hinges (vertical axis)\n"
            "  Top edge: 2 brackets (horizontal axis)\n"
            "=== Inside windowsill ===\n"
            "  Object: small potted succulent\n"
            "    Ceramic pot: D=95 mm, H=80 mm, terracotta\n"
            "    Plant height above pot rim: ~40 mm\n"
            "    Total height: ~120 mm\n"
            "    Estimated mass: 0.35 kg\n"
            "=== Room side ===\n"
            "  No furniture directly in front of window\n"
            "  Floor area clear\n"
            "=== Exterior (through glass, partially visible) ===\n"
            "  Some structure attached to exterior wall near window\n"
            "  Details unclear through double glazing"
        ),
        "NAVIGATE_TO[window, close_up]": (
            "=== Close-Range Scan (30 cm distance) ===\n"
            "=== Handle detail ===\n"
            "  Lever: 120 mm, die-cast zinc alloy\n"
            "  Current angle: horizontal (0 degrees from horizontal)\n"
            "  Spindle: 7 mm square, through frame\n"
            "=== Frame-to-sash junction ===\n"
            "  Rubber gasket: continuous, 8 mm profile\n"
            "  Sash overlap: 12 mm on all four edges\n"
            "=== Locking points ===\n"
            "  3 mushroom-head cams detected (top, bottom, far side)\n"
            "  All cams in locked position\n"
            "=== Exterior (through glass) ===\n"
            "  Metal bracket or shelf visible ~0.3 m from glass surface\n"
            "  Exact geometry unclear due to glazing distortion\n"
            "=== Exterior ledge ===\n"
            "  Concrete sill extends ~0.15 m outward from wall\n"
            "  Width matches window width (~1.20 m)\n"
            "  Currently empty, receives direct sunlight"
        ),

        # --- TWIST: each position enables a different mode ---
        "TWIST[handle, up]": (
            "=== Torque Sensor Data ===\n"
            "Rotation: handle moves from horizontal to up position\n"
            "Applied torque: 0.6 Nm (counterclockwise)\n"
            "At up position: firm click, detent engaged\n"
            "=== Locking mechanism ===\n"
            "Mushroom cams: rotated to DISENGAGED position (swing mode)\n"
            "Side locking points: cleared\n"
            "Top locking points: remain engaged\n"
            "=== Release behavior ===\n"
            "Handle returns to horizontal within 3.2 s\n"
            "Spring return force at tip: 1.8 N"
        ),
        "TWIST[handle, down]": (
            "=== Torque Sensor Data ===\n"
            "Rotation: handle moves from horizontal to down position\n"
            "Applied torque: 0.7 Nm (clockwise)\n"
            "At down position: firm click, detent engaged\n"
            "=== Locking mechanism ===\n"
            "Mushroom cams: rotated to DISENGAGED position (tilt mode)\n"
            "Side locking points: remain engaged\n"
            "Top locking points: cleared\n"
            "=== Accelerometer ===\n"
            "Transient at detent: 1.5 m/s^2, 920 Hz, 2.8 ms\n"
            "=== Release behavior ===\n"
            "Handle returns to horizontal within 2.9 s\n"
            "Spring return force at tip: 2.1 N"
        ),

        # --- PUSH: tests both handle positions ---
        "PUSH[window]": (
            "=== Force-Displacement Sensor ===\n"
            "=== Test 1: Push at horizontal (default) ===\n"
            "Applied force: 10.0 N (outward)\n"
            "Window displacement: 0.0 mm\n"
            "Status: LOCKED (all cams engaged)\n\n"
            "=== Test 2: Quick twist UP then push ===\n"
            "Handle turned up → side cams disengage (swing mode)\n"
            "Push initiated before handle returns:\n"
            "  Hinge axis: left-side vertical hinges engaged\n"
            "  Window begins to swing outward\n"
            "  At 0 mm opening: gasket seal breaks\n"
            "  At 22 mm opening: smooth swing\n"
            "  At 48 mm opening: increasing resistance\n"
            "    External structure making contact\n"
            "  At 52 mm opening: firm resistance — can hold here\n"
            "    Gap between sash and frame: 52 mm\n"
            "    Some air movement detectable through gap\n"
            "  Window returned to closed on handle spring-back\n\n"
            "=== Gap analysis (swing at 52 mm) ===\n"
            "  Gap width: 52 mm along full window height\n"
            "  Objects wider than 52 mm cannot pass through gap\n"
            "  Succulent pot (D=95 mm): CANNOT FIT through 52 mm gap\n\n"
            "=== Test 3: Quick twist DOWN then push ===\n"
            "Handle turned down → top cams disengage (tilt mode)\n"
            "Push initiated before handle returns:\n"
            "  Side hinges: INACTIVE in this handle position\n"
            "  Window displacement: 0.0 mm (push outward has no effect)\n"
            "  Note: only top brackets are active in down-handle mode"
        ),

        # --- PULL: tests both handle positions ---
        "PULL[window_top]": (
            "=== Force-Displacement Sensor ===\n"
            "=== Test 1: Pull at horizontal (default) ===\n"
            "Applied force: 8.0 N (inward, top edge)\n"
            "Displacement: 0.0 mm\n"
            "Status: LOCKED (all cams engaged)\n\n"
            "=== Test 2: Quick twist UP then pull top ===\n"
            "Handle turned up → side cams disengage (swing mode)\n"
            "Pull initiated on top edge:\n"
            "  Top brackets: INACTIVE in this handle position\n"
            "  Displacement: 0.0 mm (pull top has no effect in swing mode)\n\n"
            "=== Test 3: Quick twist DOWN then pull top ===\n"
            "Handle turned down → top cams disengage (tilt mode)\n"
            "Pull initiated on top edge before handle returns:\n"
            "  Hinge axis: top horizontal brackets engaged\n"
            "  Upper edge displacement: 18 mm inward (tilt started)\n"
            "  Lower edge displacement: 0.0 mm (fixed at sill)\n"
            "  Tilt angle: ~2 degrees\n"
            "  Projected gap at full tilt (15 deg): ~150 mm at top edge\n"
            "  Succulent pot (D=95 mm): WOULD FIT through projected gap\n"
            "  === Handle spring-back ===\n"
            "  Handle returned to horizontal at t=2.9 s\n"
            "  Top cams re-engaged → window pulled shut\n"
            "  Final displacement: 0.0 mm (closed)\n"
            "  Note: tilt motion began but was cut short by handle return"
        ),

        # --- TOUCH ---
        "TOUCH[handle]": (
            "=== Tactile Sensor Array ===\n"
            "Material: die-cast zinc alloy, powder-coated\n"
            "Shape: lever, 120 mm, tapered grip\n"
            "Temperature: 21.5 C\n"
            "Spring-loaded: yes (returns to horizontal)\n"
            "Detent positions: 2 (up and down from horizontal)\n"
            "  Up detent: counterclockwise from horizontal\n"
            "  Down detent: clockwise from horizontal\n"
            "  Both detents spring-return in ~3 s"
        ),
        "TOUCH[window_frame]": (
            "=== Tactile Sensor Array ===\n"
            "Frame material: uPVC, multi-chamber profile\n"
            "=== Left edge ===\n"
            "  2 hinges: steel, vertical axis (for swing)\n"
            "=== Top edge ===\n"
            "  2 brackets: steel, horizontal axis (for tilt)\n"
            "=== Dual-hinge system ===\n"
            "  Two independent hinge sets on different edges\n"
            "  Only one set active at a time (handle-position-dependent)"
        ),
        "TOUCH[window_glass]": (
            "=== Tactile Sensor Array ===\n"
            "Material: glass, double-glazed unit\n"
            "Surface temperature: 19.2 C\n"
            "Thickness (tap test): ~24 mm total\n"
            "Exterior side: shadow/shape visible through glass\n"
            "  Appears to be a mounted structure ~0.3 m from glass"
        ),
    },

    # === Demo configuration ===
    "demo_image_paths": [],
    "demo_labels": [],
    "demo_text_descriptions": [
        # Demo 1: swing open — contextual trap (deliberately attractive)
        (
            "A window in a spacious room with nothing nearby. The "
            "person turns the handle upward and pushes the window "
            "outward. It swings wide open on its side hinges, nearly "
            "90 degrees. A strong cross-breeze immediately fills the "
            "room. The person takes a deep breath of fresh air."
        ),
        # Demo 2: cross-domain — correct principle
        (
            "A car parked under a tree on a warm day. The person "
            "reaches up to the sunroof control and pushes the switch "
            "downward. They keep their finger on it while the rear "
            "edge of the glass panel rises a few centimeters. Air "
            "comes in through the gap."
        ),
        # Demo 3: sliding — distractor (longer, more detailed)
        (
            "A bathroom with a frosted glass window above the "
            "bathtub. The person reaches up, grips the right side "
            "of the window frame with both hands, and pushes it to "
            "the left. The window slides smoothly along a horizontal "
            "track recessed into the top and bottom of the frame. "
            "It stops about halfway, leaving an opening on the right "
            "side. Steam from the bath drifts out through the gap."
        ),
        # Demo 4: crank — distractor (longer, more detailed)
        (
            "A small window above a kitchen sink. There is a metal "
            "crank handle folded flat against the bottom of the "
            "frame. The person unfolds the crank, then turns it "
            "clockwise. With each turn, a scissor-style arm extends "
            "and slowly pushes the bottom edge of the window outward. "
            "After about ten turns, the window is angled open roughly "
            "30 degrees from the wall. The person stops cranking and "
            "folds the handle back flat."
        ),
    ],

    # === Technique selection prompts ===
    "tool_selection_prompt": (
        "Based on your exploration findings and the demonstrations, "
        "determine the correct technique to open this window wide "
        "enough to move the succulent pot to the exterior ledge.\n\n"
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
        "correct technique to open this window for ventilation.\n\n"
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
        # --- Correct: technique_B (tilt mode via handle-down) ---
        "APPLY_TECHNIQUE[window]": {
            "tool_key": "technique_B",
            "description": (
                "Apply the tilt-open technique. "
                "Specify parameters in JSON format: "
                '{"handle_position": "<string>", '
                '"hold_handle": true or false, '
                '"open_action": "<string>", '
                '"pull_force_N": <float>, '
                '"target_tilt_degrees": <float>}'
            ),
            "param_checker": _check_tilt_turn_params,
        },

        # --- Contextual trap: technique_A (swing — partial success) ---
        "SWING_OPEN[window]": {
            "tool_key": "technique_A",
            "description": "Turn handle up and push window outward to swing open.",
            "outcome": "PARTIAL",
            "feedback": (
                "You turn the handle up (swing mode) and push the "
                "window outward. The window swings on its side hinges. "
                "After about 52 mm of travel, the sash edge presses "
                "against an external metal bracket. The gap is 52 mm "
                "wide. You try to pass the succulent pot (D=95 mm) "
                "through the gap, but it does not fit. The pot is "
                "wider than the opening."
            ),
        },

        # --- Distractor: technique_C (sliding) ---
        "SLIDE_OPEN[window]": {
            "tool_key": "technique_C",
            "description": "Slide the window sideways along a track.",
            "outcome": "FAILURE",
            "feedback": (
                "You try to push the window sideways but there is no "
                "sliding track. This is a hinged window, not a slider."
            ),
        },

        # --- Distractor: technique_D (crank) ---
        "CRANK_OPEN[window]": {
            "tool_key": "technique_D",
            "description": "Turn a crank handle to push the window out.",
            "outcome": "FAILURE",
            "feedback": (
                "There is no crank mechanism on this window. It has "
                "a lever handle, not a rotating crank."
            ),
        },

        # --- Post-open actions ---
        "GRASP[succulent]": {
            "description": "Pick up the succulent from the inside windowsill.",
            "requires": "window_tilted",
            "outcome": "SUCCESS",
            "feedback": (
                "You pick up the small potted succulent from the "
                "inside windowsill."
            ),
        },
        "PLACE_ON_LEDGE[succulent]": {
            "description": "Place the succulent on the exterior ledge through the tilted window.",
            "requires": "GRASP[succulent]",
            "outcome": "SUCCESS",
            "feedback": (
                "You reach through the tilted window gap and place "
                "the succulent on the exterior concrete ledge. The "
                "pot fits through the opening with room to spare. "
                "The plant is now in direct sunlight. Task complete."
            ),
            "task_success": True,
            "state_changes": [
                {
                    "type": "teleport",
                    "object": "succulent_803",
                    "position": [2.0, 0.5, 1.0],
                },
            ],
        },
    },
    "one_shot_execution": True,

    # === Metacognitive probes ===
    "probes": {
        "stage1": (
            "What did you discover about this window's opening mechanism? "
            "The handle has two detent positions (up and down) — what "
            "mode does each one activate? Can the succulent pot fit "
            "through the opening in each mode?"
        ),
        "stage3": (
            "Did you apply the technique exactly as shown in the demo, "
            "or did you modify parameters? Why did you choose or reject "
            "the swing-open approach?"
        ),
    },
}
