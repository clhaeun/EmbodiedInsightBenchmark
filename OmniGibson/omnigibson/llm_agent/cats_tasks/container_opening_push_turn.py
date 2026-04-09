"""
CATS Decorative Pattern Task A: Container Opening (Push-and-Turn)

Level: 2.3 (Insight-based technique selection + parameter adaptation)
Scene: Kitchen countertop with a hinged jar whose lid has decorative
       screw-thread grooves. The actual mechanism is push-and-turn
       (child-safety style), not screw-turn.

Combination type: Simultaneous (PRESS + TWIST at the same time)
  - Individual PRESS → reveals spring resistance (property)
  - Individual TWIST → reveals rotation without vertical rise (property)
  - PRESS_AND_TWIST simultaneously → unlocks lid (solution, Stage 3 only)

Visual trap: Decorative vertical grooves on lid surface strongly suggest
             screw-turn, but grooves are shallow (0.3mm) and non-helical.
"""

import json


# ---------------------------------------------------------------------------
# Parameter checker for push-and-turn technique
# ---------------------------------------------------------------------------
def _check_push_and_turn_params(description):
    """Validate push-and-turn parameters against physical constraints.

    Optimal range (from exploration data):
      downward_force_N:  2.5 ~ 4.5
      rotation_degrees:  100 ~ 140
      timing_delay_s:    0.2 ~ 0.6

    Acceptable range (SUCCESS):
      downward_force_N:  2.0 ~ 6.0
      rotation_degrees:  90  ~ 160

    Failure modes:
      force > 6.0  →  latch jams
      force < 2.0  →  latch does not disengage
      rotation > 160  →  re-engages latch
      rotation < 90   →  partial disengage, snaps back
    """
    try:
        params = json.loads(description)
    except Exception:
        return {
            "outcome": "FAILURE",
            "aux_text": "Could not parse parameters. Provide valid JSON.",
        }

    force = params.get("downward_force_N", 0)
    rotation = params.get("rotation_degrees", 0)
    timing = params.get("timing_delay_s", 0.3)
    simultaneous = params.get("simultaneous", False)

    # --- Failure: sequential press-then-twist (not simultaneous) ---
    if not simultaneous:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                "You press down first, then release to reposition your "
                "grip for rotation. As you release downward pressure, "
                "the spring pushes the lid back up and the latch "
                "re-engages. The lid remains locked. The downward "
                "force must be maintained during rotation."
            ),
        }

    # --- Failure: excessive force → latch jams ---
    if force > 6.0:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Excessive downward force ({force:.1f} N). The internal "
                "latch mechanism jams under the load. The lid is now stuck."
            ),
        }

    # --- Failure: insufficient force ---
    if force < 2.0:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Insufficient downward force ({force:.1f} N). The lid "
                "barely depresses. The latch does not disengage. "
                "Rotation is still blocked."
            ),
        }

    # --- Failure: insufficient rotation ---
    if rotation < 90:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Rotation insufficient ({rotation:.0f} deg). The latch "
                "partially disengages but snaps back before full release."
            ),
        }

    # --- Failure: over-rotation → re-engages latch ---
    if rotation > 160:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Over-rotation ({rotation:.0f} deg). The lid passes the "
                "release point and re-engages the latch on the far side."
            ),
        }

    # --- SUCCESS ---
    optimal = (2.5 <= force <= 4.5 and 100 <= rotation <= 140)

    return {
        "outcome": "SUCCESS",
        "aux_text": (
            f"You press down with {force:.1f} N and rotate {rotation:.0f} deg. "
            "Click! The lid depresses, the internal latch disengages, "
            "and the lid rotates freely. The lid separates from the "
            "container. Inside, you see a key."
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
    "task_name": "container_opening_push_turn",
    "level": "2.3",
    "instruction": (
        "Open the container on the kitchen countertop and retrieve "
        "the key inside. Place the key on the countertop."
    ),

    # === CA technique candidates (mapped as virtual tools) ===
    "correct_tool": "push_and_turn",
    "ca_tool_names": [
        "screw_turn",
        "vacuum_seal_release",
        "push_and_turn",
        "bayonet_quarter",
        "cork_rocking",
    ],
    "extra_object_names": [],

    # === Stage 1: Exploration ===
    "exploration_primitives_desc": (
        "Available exploration actions:\n"
        "- NAVIGATE_TO[target]: Move to observe from a different angle. "
        "Returns camera image.\n"
        "  Valid targets: container | container, close_up | countertop\n\n"
        "- TWIST[object, direction]: Rotate an object by hand. "
        "Returns torque and displacement data.\n"
        "  Valid: lid, counterclockwise | lid, clockwise\n\n"
        "- PRESS[object, direction]: Apply sustained pressure. "
        "Returns force-displacement data.\n"
        "  Valid: lid, downward\n\n"
        "- PULL[object, direction]: Pull an object. "
        "Returns force and displacement data.\n"
        "  Valid: lid, upward\n\n"
        "- TOUCH[surface]: Press fingertip sensor against a surface. "
        "Returns tactile sensor data.\n"
        "  Valid: lid_surface | lid_edge | container_body\n\n"
        "- LOOK_CLOSER[target]: Zoom in on a target. "
        "Returns zoomed camera image.\n"
        "  Valid: lid | lid_grooves | container_body\n\n"
        "- DONE_EXPLORING: Finish exploration phase."
    ),

    "exploration_nav_targets": {
        "container":           "hinged_jar_801",
        "container, close_up": "hinged_jar_801",
        "countertop":          "countertop_kelzer_0",
    },
    "exploration_nav_tracking": {
        "container":           "hinged_jar_801",
        "container, close_up": "hinged_jar_801",
    },
    "exploration_look_targets": {
        "lid":            "hinged_jar_801",
        "lid_grooves":    "hinged_jar_801",
        "container_body": "hinged_jar_801",
    },
    "exploration_direct_camera": {},

    # === Exploration feedbacks (v2: raw sensor data) ===
    "exploration_feedbacks": {
        # --- NAVIGATE_TO: visual feedback (image + scene description) ---
        "NAVIGATE_TO[container]": (
            "You see a glass container with a metallic lid on the countertop. "
            "The lid has visible vertical grooves around its circumference."
        ),
        "NAVIGATE_TO[container, close_up]": (
            "Close-up view. The vertical grooves on the lid are evenly spaced "
            "and appear similar to screw threads. The lid has a metallic finish."
        ),
        "NAVIGATE_TO[countertop]": (
            "You see the kitchen countertop. The glass container with the "
            "metallic lid is sitting on it."
        ),

        # --- Key finding 1: rotation without vertical rise ---
        "TWIST[lid, counterclockwise]": (
            "=== Torque Sensor Data ===\n"
            "Applied torque: 2.1 Nm\n"
            "Lid angular displacement: 15 degrees\n"
            "Lid vertical displacement: 0.0 mm\n"
            "Resistance pattern: smooth rotation with periodic catch "
            "every ~60 degrees\n"
            "Note: No progressive vertical rise detected during rotation\n"
            "=== Internal Contact Sensor ===\n"
            "At 45-degree rotation: internal protrusion contact detected\n"
            "Contact force: 3.2 N (radial direction)"
        ),
        "TWIST[lid, clockwise]": (
            "=== Torque Sensor Data ===\n"
            "Applied torque: 2.0 Nm\n"
            "Lid angular displacement: 15 degrees (clockwise)\n"
            "Lid vertical displacement: 0.0 mm\n"
            "Resistance pattern: identical to counterclockwise - "
            "smooth rotation, periodic catch every ~60 degrees\n"
            "Note: No vertical rise in either direction"
        ),

        # --- Key finding 2: spring-loaded lid ---
        "PRESS[lid, downward]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 3.5 N\n"
            "Vertical displacement: 2.1 mm\n"
            "Spring constant (estimated): 1667 N/m\n"
            "Displacement at 2.0 N: 1.2 mm\n"
            "Displacement at 4.0 N: 2.4 mm (linear response)\n"
            "Max displacement before hard stop: 3.0 mm (at ~5.0 N)\n"
            "=== Release behavior ===\n"
            "Upon release: lid returns to original position (spring-loaded)"
        ),

        # --- Supplementary: pull does not open ---
        "PULL[lid, upward]": (
            "=== Force Sensor Data ===\n"
            "Applied upward force: 8.0 N\n"
            "Lid vertical displacement: 0.0 mm\n"
            "The lid does not separate from the container body.\n"
            "Internal locking mechanism engaged."
        ),

        # --- Supplementary: grooves are decorative ---
        "TOUCH[lid_surface]": (
            "=== Tactile Sensor Array (4x4, kPa) ===\n"
            "[[  0.0,  0.0,  0.0,  0.0],\n"
            " [  0.0, 12.3, 11.8,  0.0],\n"
            " [  0.0, 11.5, 12.1,  0.0],\n"
            " [  0.0,  0.0,  0.0,  0.0]]\n"
            "Surface temperature: 22.3 C\n"
            "Surface material: metallic, smooth finish\n"
            "=== Visual-Tactile Discrepancy ===\n"
            "Vertical grooves visible on surface: present "
            "(8 grooves, evenly spaced)\n"
            "Groove depth (tactile): 0.3 mm (shallow, decorative)\n"
            "Thread pitch detection: NONE (grooves do not follow "
            "helical pattern)"
        ),
        "TOUCH[lid_edge]": (
            "=== Tactile Sensor Array ===\n"
            "Edge profile: smooth cylindrical rim\n"
            "No threading detected at rim-body junction\n"
            "Gap between lid and body: 0.8 mm (uniform)\n"
            "Slight vertical play: 0.5 mm when pressed"
        ),
        "TOUCH[container_body]": (
            "=== Tactile Sensor Array ===\n"
            "Material: glass, smooth exterior\n"
            "Temperature: 22.1 C\n"
            "Weight estimate (from lift resistance): ~350 g\n"
            "Internal content detected: small solid object shifting"
        ),
    },

    # === Demo configuration ===
    "demo_image_paths": [],   # Start with no demos for pipeline testing
    "demo_labels": [],        # v2: no labels provided

    # === Technique selection prompts ===
    "tool_selection_prompt": (
        "Based on your exploration findings and the demonstrations, "
        "determine the correct technique to open this container.\n\n"
        "Provide:\n"
        "(1) Which demonstration is most relevant and why\n"
        "(2) What technique you will use\n"
        "(3) What physical evidence from exploration supports this\n"
        "(4) Your execution plan with specific parameters "
        "(downward_force_N, rotation_degrees, timing_delay_s)\n\n"
        "IMPORTANT: At the very end, write ONLY:\n"
        "SELECTED_TOOL: <technique_name>\n"
        "where <technique_name> is one of: "
        "screw_turn, vacuum_seal_release, push_and_turn, "
        "bayonet_quarter, cork_rocking"
    ),
    "tool_selection_prompt_no_demo": (
        "Based on your exploration findings alone, determine the "
        "correct technique to open this container.\n\n"
        "Provide:\n"
        "(1) What physical principle guides your technique selection\n"
        "(2) What technique you will use\n"
        "(3) What sensor data supports this choice\n"
        "(4) Your execution plan with specific parameters "
        "(downward_force_N, rotation_degrees, timing_delay_s)\n\n"
        "IMPORTANT: At the very end, write ONLY:\n"
        "SELECTED_TOOL: <technique_name>\n"
        "where <technique_name> is one of: "
        "screw_turn, vacuum_seal_release, push_and_turn, "
        "bayonet_quarter, cork_rocking"
    ),

    # === Stage 3: Menu-based symbolic execution ===
    "stage3_action_menu": {
        # --- Correct technique: push_and_turn ---
        "APPLY_TECHNIQUE[lid]": {
            "tool_key": "push_and_turn",
            "description": (
                "Apply the push-and-turn technique to open the lid. "
                "Specify your approach and parameters in JSON format: "
                '{"downward_force_N": <float>, '
                '"rotation_degrees": <float>, '
                '"simultaneous": true or false, '
                '"timing_delay_s": <float>}'
            ),
            "param_checker": _check_push_and_turn_params,
        },

        # --- Visual trap: screw_turn ---
        "SCREW_TURN[lid]": {
            "tool_key": "screw_turn",
            "description": (
                "Rotate the lid counterclockwise to unscrew it."
            ),
            "outcome": "FAILURE",
            "feedback": (
                "The lid rotates but does not rise. No threading "
                "engagement detected. At certain angles, internal "
                "catching is felt. The lid remains sealed after "
                "multiple full rotations."
            ),
        },

        # --- Distractor: vacuum_seal_release ---
        "VACUUM_RELEASE[lid]": {
            "tool_key": "vacuum_seal_release",
            "description": (
                "Insert a thin tool at the lid edge to break "
                "the vacuum seal."
            ),
            "outcome": "FAILURE",
            "feedback": (
                "No vacuum seal detected. Inserting at the edge "
                "finds no gap or air resistance. The uniform 0.8 mm "
                "gap does not allow tool insertion. This is not a "
                "vacuum-sealed container."
            ),
        },

        # --- Distractor: bayonet_quarter ---
        "BAYONET_TURN[lid]": {
            "tool_key": "bayonet_quarter",
            "description": (
                "Rotate the lid exactly 90 degrees to release "
                "bayonet tabs."
            ),
            "outcome": "FAILURE",
            "feedback": (
                "Rotating exactly 90 degrees does not release the "
                "lid. No bayonet tabs or quarter-turn detents detected "
                "internally. The periodic catches every 60 degrees "
                "are decorative protrusions, not bayonet engagement "
                "points."
            ),
        },

        # --- Distractor: cork_rocking ---
        "CORK_ROCK[lid]": {
            "tool_key": "cork_rocking",
            "description": (
                "Rock the lid side to side to loosen it through "
                "alternating leverage."
            ),
            "outcome": "FAILURE",
            "feedback": (
                "Rocking the lid side to side does not loosen it. "
                "The lid is rigid and does not flex or tilt. The "
                "metal-to-glass junction is too tight for rocking "
                "leverage. This is not a friction-fit closure."
            ),
        },

        # --- Post-open actions ---
        "GRASP[key]": {
            "description": "Grasp the key from inside the open container.",
            "requires": "lid_opened",
            "outcome": "SUCCESS",
            "feedback": "You reach into the open container and grasp the key.",
        },
        "PLACE_ON_TOP[key, countertop]": {
            "description": "Place the key on the countertop.",
            "requires": "GRASP[key]",
            "outcome": "SUCCESS",
            "feedback": (
                "You place the key on the countertop. Task complete."
            ),
            "task_success": True,
            "state_changes": [
                {
                    "type": "teleport",
                    "object": "key_802",
                    "position": [6.5, -1.90, 0.92],
                },
            ],
        },
    },
    "one_shot_execution": True,

    # === Metacognitive probes ===
    "probes": {
        "stage1": (
            "What did you discover about this container's opening "
            "mechanism? Did the physical properties match what you "
            "expected from the visual appearance? What specific "
            "sensor readings informed your understanding?"
        ),
        "stage3": (
            "Did you apply the technique exactly as shown in the "
            "demo, or did you modify any parameters? If you modified "
            "parameters, what observations led you to make those "
            "adjustments?"
        ),
    },
}
