"""CATS Task 2.3-E: Slatted Grill Cleaning — 6-DOF Parameter Adaptation.

Level: 2.3 (Insight-based — cross-dimensional abstraction of physical parameters)
Scene: house_single_floor (kitchen — BBQ grill grate on countertop)
Instruction: Clean the grill surface in a single forward push using the provided scraper.
Tool: scraper_801 (ONLY tool — given, not selected)

This task does NOT evaluate tool selection. The scraper is the only tool provided.
The sole evaluation target is whether the agent can derive the correct 6-DOF
physical parameters (specifically, yaw rotation) from demo observation and
raw sensor data.

Critical Context Features (discovered via exploration):
  - Grill surface has deep parallel gaps running along X-axis
  - Pushing straight (yaw=0) causes blade to drop into gaps (z_displacement = -0.020m)
  - Increasing force (150N) approaches material strain limit (0.94) — no progress
  - Scraper blade is wider than grill width and far wider than gap width
  - Metal guide walls on both sides prevent any X-axis movement

Demo structure (NO labels — agent must identify principles from video):
  Demo 1: Bicycle crossing train tracks at diagonal    — structural match (yaw rotation)
  Demo 2: Toothbrush cleaning keyboard crevices        — attractive trap
  Demo 3: Wet sponge wiping flat glass window          — material trap
  Demo 4: Vacuum cleaning flat carpet                  — suction trap
  Demo 5: Towel wiping restaurant table                — intuitive trap

Key CA challenge:
  Agent must extract the principle "linear motion trapped by parallel gaps can be
  freed by rotating in the orthogonal yaw axis" from Demo 1 (bicycle/train tracks),
  and apply it to define the correct 6-DOF parameters for the scraper.
  Y-axis resistance -> Z-axis yaw rotation (NOT force increase or Z-axis lift).

  The 6-DOF parameter API (9 values) hides the yaw hint among roll, pitch, and
  linear velocity/force parameters. Agent must geometrically reason which
  specific rotation axis solves the problem.

Evaluation:
  - Primary metric: Parameter accuracy — yaw_angle in [20, 49] degrees = SUCCESS
  - The scraper is given, so there is no tool selection decision to make.
  - Wrong parameter (yaw=0, yaw>49, pitch/roll deviation, etc.) = FAILURE
"""

import json
import os
from math import cos, radians, sin

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEMO_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "cats", "demos",
    "slatted_grill_cleaning",
)

# Physical constants for symbolic evaluation
_BLADE_LENGTH = 0.30       # m  — scraper blade length
_BLADE_THICKNESS = 0.005   # m  — scraper blade thickness
_GRILL_WIDTH = 0.20        # m  — grill cleaning surface width (between guide walls)
_GAP_WIDTH = 0.105         # m  — individual gap width

# 6-DOF parameter template (shown to agent in prompt)
_6DOF_TEMPLATE = (
    '{"linear_velocity": {"x": 0.0, "y": 0.0, "z": 0.0}, '
    '"applied_force": {"x": 0.0, "y": 0.0, "z": 0.0}, '
    '"orientation_euler_angles": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}}'
)

# ---------------------------------------------------------------------------
# Dynamic param_checker for 6-DOF parameter evaluation
# ---------------------------------------------------------------------------


def _check_push_params(params):
    """Symbolic 6-DOF parameter checker for PUSH_FORWARD on slatted grill.

    Evaluates the agent's parameter choice against physical constraints:
      1. velocity_x != 0        -> collision with metal guide walls
      2. |pitch| > 5            -> blade lifts off surface, no cleaning contact
      3. |roll| > 5             -> edge contact only, insufficient coverage
      4. yaw ~ 0                -> blade drops into gaps (exploration showed this)
      5. yaw too large (>~49)   -> effective width < grill width
      6. yaw in [~5, ~49]       -> blade bridges gaps AND covers full width
         (practical success range: [20, 49])

    Args:
        params: Parsed JSON dict with 6-DOF parameters, or JSON string.

    Returns:
        dict with "outcome" (SUCCESS/FAILURE), "aux_text", and optionally
        "state_changes".
    """
    # --- Parse params (may be string from regex capture) ---
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except (json.JSONDecodeError, TypeError):
            return {
                "outcome": "FAILURE",
                "aux_text": (
                    "Invalid parameter format. Could not parse 6-DOF JSON. "
                    "Ensure the parameter dictionary is valid JSON enclosed "
                    "in single quotes."
                ),
            }
    if not isinstance(params, dict):
        params = {}

    oe = params.get("orientation_euler_angles", {})
    lv = params.get("linear_velocity", {})
    af = params.get("applied_force", {})

    yaw = float(oe.get("yaw", 0))
    roll = float(oe.get("roll", 0))
    pitch = float(oe.get("pitch", 0))
    vx = float(lv.get("x", 0))
    vy = float(lv.get("y", 0))

    # --- Check 1: X-axis movement -> guide wall collision ---
    if abs(vx) > 0.01:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Sensor feedback:\n"
                f"  displacement_x: 0.000 m\n"
                f"  contact_force_x: {abs(vx) * 800:.1f} N (lateral)\n"
                f"  displacement_y: 0.000 m\n"
                f"  velocity_y: 0.0 m/s\n"
                f"  collision_detected: True (rigid boundary, X-axis)"
            ),
        }

    # --- Check 2: Pitch -> blade lifts off surface ---
    if abs(pitch) > 5:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Sensor feedback:\n"
                f"  blade_surface_contact_area: 0.000 m^2\n"
                f"  contact_pressure: 0.0 kPa\n"
                f"  blade_surface_clearance_z: {abs(pitch) * 0.002:.4f} m\n"
                f"  displacement_y: 0.000 m\n"
                f"  residue_removed: 0%"
            ),
        }

    # --- Check 3: Roll -> edge-only contact ---
    if abs(roll) > 5:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Sensor feedback:\n"
                f"  blade_surface_contact_area: 0.0008 m^2\n"
                f"  contact_pressure: 420.0 kPa (concentrated)\n"
                f"  effective_cleaning_width: 0.005 m\n"
                f"  displacement_y: 0.022 m\n"
                f"  velocity_y: 0.0 m/s\n"
                f"  residue_removed: 2%"
            ),
        }

    # --- Check 4: Y velocity must be positive (forward push) ---
    if vy <= 0:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Sensor feedback:\n"
                f"  displacement_y: 0.000 m\n"
                f"  velocity_y: 0.0 m/s\n"
                f"  force_y: 0.0 N\n"
                f"  residue_removed: 0%"
            ),
        }

    # --- Check 5: Bridge check (blade Y-projection must span gaps) ---
    bridge_y = (_BLADE_LENGTH * sin(radians(abs(yaw)))
                + _BLADE_THICKNESS * cos(radians(yaw)))
    if bridge_y < _GAP_WIDTH:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Sensor feedback:\n"
                f"  displacement_y: 0.016 m\n"
                f"  velocity_y: 0.0 m/s\n"
                f"  z_displacement: -0.020 m\n"
                f"  force_y: 88.0 N\n"
                f"  blade_y_projection: {bridge_y:.4f} m\n"
                f"  structural_stress_y: 88.0 N/m^2"
            ),
        }

    # --- Check 6: Effective cleaning width (must cover full grill) ---
    effective_w = (_BLADE_LENGTH * cos(radians(yaw))
                   + _BLADE_THICKNESS * sin(radians(abs(yaw))))
    if effective_w < _GRILL_WIDTH:
        return {
            "outcome": "FAILURE",
            "aux_text": (
                f"Sensor feedback:\n"
                f"  displacement_y: 0.300 m (full stroke)\n"
                f"  velocity_y: 0.10 m/s\n"
                f"  z_displacement: 0.000 m\n"
                f"  force_y: 12.3 N\n"
                f"  blade_effective_width: {effective_w:.4f} m\n"
                f"  grill_cleaning_width: {_GRILL_WIDTH:.3f} m\n"
                f"  residue_removed: {effective_w / _GRILL_WIDTH * 100:.0f}%\n"
                f"  uncleaned_strip_width: {_GRILL_WIDTH - effective_w:.4f} m"
            ),
        }

    # --- SUCCESS ---
    return {
        "outcome": "SUCCESS",
        "state_changes": [
            {"type": "teleport_underground", "pattern": "grill_debris"},
        ],
        "aux_text": (
            f"The scraper blade, angled at {yaw:.1f} degrees, bridges across the "
            "grill gaps smoothly. The blade maintains full surface contact while "
            "sliding forward in a single push. Sticky residue is scraped off the "
            "grill surface. The grill is now clean."
        ),
    }


# ---------------------------------------------------------------------------
# TASK_CONFIG
# ---------------------------------------------------------------------------

TASK_CONFIG = {
    # ---- Basic info ----
    "task_name": "slatted_grill_cleaning",
    "level": "2.3",
    "instruction": (
        "A BBQ grill grate is on the kitchen countertop with sticky residue "
        "on its surface. You have a flat scraper (scraper_801). "
        "Clean the grill by placing the scraper at the front edge "
        "and pushing it forward in a single motion to the end. "
        "You must complete the cleaning in one push.\n\n"
        "You will need to define the exact 6-DOF physical parameters "
        "(linear velocity, applied force, orientation angles) for the push."
    ),
    # Parameter accuracy is the sole evaluation metric.
    # The scraper is the only tool — no tool selection decision.
    "correct_tool": "scraper",

    # ---- One-Shot Execution ----
    # Stage 3 allows only ONE NEW_ACTION attempt. The agent must derive
    # the correct 6-DOF parameters from exploration + demos BEFORE execution.
    # Basic setup actions (NAVIGATE_TO, GRASP) are still allowed.
    "one_shot_execution": True,

    # ---- Single Tool (NO tool selection) ----
    # Only the scraper is provided. This task evaluates parameter adaptation,
    # not tool selection. The ca_tool_names list is kept for planner_ca.py
    # compatibility (one-shot GRASP constraint still applies).
    "ca_tool_names": [
        "scraper_801",
    ],
    "extra_object_names": ["charcoal_grill_806"],
    # # --- Disabled: multi-tool candidates (tool selection is NOT evaluated) ---
    # "ca_tool_names": [
    #     "scraper_801",
    #     "scrub_brush_802",
    #     "sponge_803",
    #     "vacuum_804",
    #     "dishtowel_805",
    # ],

    # ---- Stage 1: Exploration — Navigation & Camera Tracking ----
    #
    # Scene layout (house_single_floor kitchen):
    #   countertop_kelzer_0:  pos=[6.030, -1.984, 0.870]
    #     charcoal_grill_806 on countertop: pos ~[6.5, -1.9, 0.95]
    #     grill_debris_811~818 on grill surface (small flat residue objects)
    #     Metal guide walls on grill sides: grill cleaning width = 0.20m
    #     scraper_801 placed next to grill on countertop
    #   Robot start: pos=[5.21, -0.14, 0.0] (kitchen center)
    #
    "exploration_direct_camera": {},
    "exploration_nav_targets": {
        "countertop, grill": "charcoal_grill_806",
    },
    "exploration_nav_tracking": {
        "countertop, grill": "charcoal_grill_806",
    },
    "exploration_look_targets": {},

    # ---- Stage 1: Exploration — Primitives Description ----
    "exploration_primitives_desc": (
        "You have one tool: scraper_801 (a flat metal scraper).\n\n"
        "NAVIGATE_TO[location, modifier]\n"
        "  Move to a location to observe from a different angle. "
        "Returns camera image.\n"
        "  Valid: countertop, grill\n\n"
        "INSPECT[object]\n"
        "  Closely examine an object's physical properties. "
        "Returns qualitative description.\n"
        "  Valid: grill_surface | scraper\n\n"
        "PROBE_STRAIGHT[]\n"
        "  Execute a minimal test push on the grill with the scraper held "
        "straight (all 6-DOF parameters at default). "
        "Returns raw sensor feedback.\n\n"
        "PROBE_HARD_STRAIGHT[]\n"
        "  Execute a high-force test push on the grill with the scraper held "
        "straight (default orientation, increased Y-force). "
        "Returns raw sensor feedback.\n\n"
        "NAVIGATE_TO returns an image. "
        "INSPECT and PROBE actions return sensor data only.\n\n"
        "IMPORTANT: These are the ONLY exploration actions available. "
        "You cannot modify probe parameters or test other orientations."
    ),

    # ---- Stage 1: Exploration — Sensor Feedbacks ----
    # NAVIGATE_TO: visual (camera image + brief scene description)
    # INSPECT: qualitative physical data (NO exact measurements — prevents math bypass)
    # PROBE: raw sensor data (NO interpretive labels — agent must interpret numbers)
    "exploration_feedbacks": {
        # --- NAVIGATE_TO: visual + scene description ---
        "NAVIGATE_TO[countertop, grill]": (
            "A charcoal grill grate sits on the countertop, positioned between "
            "two metal guide walls. The grill surface has dark, sticky residue. "
            "You can see parallel gaps running across the surface from left to right. "
            "A flat scraper is placed beside the grill."
        ),

        # --- INSPECT: qualitative physical data (NO exact numbers) ---
        "INSPECT[grill_surface]": (
            "Surface topology: Multiple deep parallel gaps running along the "
            "X-axis across the entire grill surface.\n"
            "Gap structure: Uniform spacing. Gaps are deep relative to their width.\n"
            "Surface condition: Sticky residue coating the raised surfaces "
            "between gaps.\n"
            "Side walls: Rigid metal guide walls on both left and right edges."
        ),
        "INSPECT[scraper]": (
            "Blade profile: A flat, rigid metal blade with a thin edge.\n"
            "Blade dimension: Wider than the grill width. The blade can span "
            "the full grill surface when placed straight across.\n"
            "Blade vs gap: The blade is significantly wider than individual "
            "gap width.\n"
            "Material: Rigid metal — will not deform or compress."
        ),

        # --- PROBE_STRAIGHT: raw sensor data (yaw=0, NO interpretive labels) ---
        "PROBE_STRAIGHT[]": (
            "6-DOF test push executed with default parameters:\n"
            "  linear_velocity: {x: 0.0, y: 0.1, z: 0.0}\n"
            "  applied_force:   {x: 0.0, y: 0.0, z: 0.0}\n"
            "  orientation:     {roll: 0.0, pitch: 0.0, yaw: 0.0}\n"
            "\n"
            "Sensor feedback:\n"
            "  displacement_y:       0.015 m\n"
            "  velocity_y:           0.0 m/s\n"
            "  force_y:              85.0 N\n"
            "  z_displacement:       -0.020 m\n"
            "  structural_stress_y:  85.0 N/m^2"
        ),

        # --- PROBE_HARD_STRAIGHT: raw sensor data (yaw=0, high force) ---
        "PROBE_HARD_STRAIGHT[]": (
            "6-DOF test push executed with increased force:\n"
            "  linear_velocity: {x: 0.0, y: 0.1, z: 0.0}\n"
            "  applied_force:   {x: 0.0, y: 150.0, z: 0.0}\n"
            "  orientation:     {roll: 0.0, pitch: 0.0, yaw: 0.0}\n"
            "\n"
            "Sensor feedback:\n"
            "  displacement_y:       0.017 m\n"
            "  velocity_y:           0.0 m/s\n"
            "  force_y:              150.0 N\n"
            "  structural_stress_y:  148.2 N/m^2\n"
            "  material_strain:      0.94"
        ),
    },

    # ---- Stage 2: Demo Observation ----
    "demo_system_prompt": (
        "Here are some reference demonstrations showing different approaches "
        "to various physical problems."
    ),
    # NO labels — agent must identify principles from video/text alone
    "demo_labels": [],
    "demo_image_paths": [
        os.path.join(_DEMO_DIR, "demo1_bicycle_train_tracks.mp4"),
        os.path.join(_DEMO_DIR, "demo2_toothbrush_keyboard.mp4"),
        os.path.join(_DEMO_DIR, "demo3_sponge_window.mp4"),
        os.path.join(_DEMO_DIR, "demo4_vacuum_carpet.mp4"),
        os.path.join(_DEMO_DIR, "demo5_towel_table.mp4"),
    ],
    # Text fallback when demo videos are not available
    "demo_text_descriptions": [
        # Demo 1: bicycle crossing train tracks — structural match (yaw rotation)
        (
            "A cyclist approaches a set of train tracks that cross the "
            "road diagonally. The tracks have deep parallel grooves "
            "running at an angle to the road. The cyclist turns the "
            "handlebars to cross the tracks at a steep diagonal angle "
            "rather than going straight across. The wheels roll smoothly "
            "over the grooves without catching or slipping in."
        ),
        # Demo 2: toothbrush cleaning keyboard crevices — attractive trap
        (
            "A person holds a small toothbrush and scrubs between the "
            "keys of a computer keyboard. They push the bristles into "
            "each narrow gap one by one, moving along each row. Dust "
            "and crumbs are dislodged from the crevices. The brush "
            "fits neatly into each slot."
        ),
        # Demo 3: wet sponge wiping flat glass window — material trap
        (
            "A person wets a soft sponge and presses it flat against "
            "a glass window. They push the sponge forward in a straight "
            "line from top to bottom. The sponge glides smoothly across "
            "the flat, uninterrupted glass surface, leaving a clean "
            "streak behind."
        ),
        # Demo 4: vacuum cleaning flat carpet — suction trap
        (
            "A person pushes a vacuum cleaner forward across a flat "
            "carpet in straight, parallel lines. The suction picks up "
            "loose dirt and debris from the soft carpet surface. The "
            "vacuum head glides smoothly over the uniform surface "
            "without catching on anything."
        ),
        # Demo 5: towel wiping restaurant table — intuitive trap
        (
            "A person takes a damp towel and wipes a flat restaurant "
            "table in broad, straight strokes. The towel conforms to "
            "the smooth surface and slides forward easily. Crumbs and "
            "spills are swept off the edge of the table."
        ),
    ],

    # ---- Analysis & Parameter Definition (WITH demos) ----
    # Replaces "Tool Selection" — the scraper is given, agent defines parameters.
    "tool_selection_prompt": (
        "You have scraper_801. Now analyze the demonstrations in context of "
        "the raw sensor data (Y-axis resistance, Z-axis drop) from your "
        "exploration, and define the exact 6-DOF physical parameters required "
        "to clean the grill in a single push.\n\n"
        "CRITICAL: Execution is ONE-SHOT. You will have exactly ONE attempt "
        "to push the scraper. There are no retries — if your parameters are "
        "wrong, the task fails immediately. You must get the parameters right "
        "from your analysis of the demos and sensor data BEFORE execution.\n\n"
        "Provide:\n"
        "(1) Which demo you referenced and the abstract physical principle "
        "extracted\n"
        "(2) How the sensor data from PROBE_STRAIGHT and PROBE_HARD_STRAIGHT "
        "confirms the problem\n"
        "(3) The physical reasoning that maps the demo principle to specific "
        "6-DOF parameters\n"
        "(4) Your final action:\n"
        "    You MUST output the NEW_ACTION in this exact format, "
        "enclosing the JSON parameter dictionary in SINGLE QUOTES ('):\n\n"
        "    NEW_ACTION[PUSH_FORWARD, scraper_801, charcoal_grill_806]: "
        "'" + _6DOF_TEMPLATE + "'\n\n"
        "    All values default to 0.0. Modify only the parameters you need.\n"
        "    linear_velocity: movement speed along each axis (m/s)\n"
        "    applied_force: contact force along each axis (N)\n"
        "    orientation_euler_angles: tool rotation in degrees "
        "(roll/pitch/yaw)\n\n"
        "    You must rely on abstracting the demo principle, "
        "not directly overcoming force.\n\n"
        "IMPORTANT: At the very end of your response, provide your final "
        "action on a new line:\n"
        "NEW_ACTION[PUSH_FORWARD, scraper_801, charcoal_grill_806]: "
        "'{ ... your 6-DOF parameters ... }'"
    ),

    # ---- Analysis & Parameter Definition (NO demos available) ----
    "tool_selection_prompt_no_demo": (
        "You have scraper_801. Based on the raw sensor data from your "
        "exploration (Y-axis resistance, Z-axis drop, material strain), "
        "define the exact 6-DOF physical parameters required to clean "
        "the grill in a single push.\n\n"
        "CRITICAL: Execution is ONE-SHOT. You will have exactly ONE attempt "
        "to push the scraper. There are no retries — if your parameters are "
        "wrong, the task fails immediately. You must get the parameters right "
        "from your physical reasoning BEFORE execution.\n\n"
        "Provide:\n"
        "(1) What physical principle guides your parameter selection "
        "(based on the sensor data pattern)\n"
        "(2) How the sensor data from PROBE_STRAIGHT and PROBE_HARD_STRAIGHT "
        "confirms the problem\n"
        "(3) Your physical reasoning for choosing specific parameter values\n"
        "(4) Your final action:\n"
        "    You MUST output the NEW_ACTION in this exact format, "
        "enclosing the JSON parameter dictionary in SINGLE QUOTES ('):\n\n"
        "    NEW_ACTION[PUSH_FORWARD, scraper_801, charcoal_grill_806]: "
        "'" + _6DOF_TEMPLATE + "'\n\n"
        "    All values default to 0.0. Modify only the parameters you need.\n"
        "    linear_velocity: movement speed along each axis (m/s)\n"
        "    applied_force: contact force along each axis (N)\n"
        "    orientation_euler_angles: tool rotation in degrees "
        "(roll/pitch/yaw)\n\n"
        "    Base your parameter choice on physical reasoning from "
        "sensor data.\n\n"
        "IMPORTANT: At the very end of your response, provide your final "
        "action on a new line:\n"
        "NEW_ACTION[PUSH_FORWARD, scraper_801, charcoal_grill_806]: "
        "'{ ... your 6-DOF parameters ... }'"
    ),

    # ---- Stage 3: NEW_ACTION handlers (for physical grounding) ----
    #
    # Evaluation:
    #   - Primary metric: yaw in [20, 49] = SUCCESS (parameter adaptation)
    #   - Wrong parameter = FAILURE
    #   - Only scraper handler exists (single tool task)
    #
    "new_action_handlers": {
        # --- scraper: dynamic evaluation via param_checker ---
        ("scraper", "grill", "push"): {
            "param_checker": _check_push_params,
        },
    },

    # ---- Metacognitive Probes ----
    "probes": {
        "stage1": (
            "Based on the raw sensor data from your exploration, what is the "
            "exact physical nature of the resistance encountered? "
            "Why would directly increasing the Y-axis force fail to solve it?"
        ),
        "stage2": (
            "For each demo, analyze how the physical solution shown could "
            "translate to defining 6-DOF parameters for the scraper push. "
            "Specifically, which demo suggests adjusting a parameter in a "
            "completely different dimension than the axis of resistance?"
        ),
        "stage3": (
            "Did your chosen parameters resolve the resistance observed in "
            "the exploration phase? Explain the physical mechanics of why "
            "changing the orientation (if you did) bypassed the collision."
        ),
    },
}
