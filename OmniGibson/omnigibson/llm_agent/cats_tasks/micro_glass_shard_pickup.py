"""CATS Task 2.3-D: Micro Glass Shard Pickup.

Level: 2.3 (Insight-based selection)
Scene: house_single_floor (kitchen — tile floor with micro glass shards)
Instruction: Safely collect micro glass shards from the kitchen floor.
Correct tool: tool_A (internally potato — cut in half, starchy cross-section embeds shards)

Tool names are abstracted (tool_A … tool_E) to prevent LLM recall of
well-known household tips (e.g. "use a potato to pick up glass shards").

Critical Context Features (discovered via exploration):
  - Shards are extremely small and sharp — tactile pressure spikes reveal
  - Embedded in tile surface and grout lines
  - Cannot be displaced by wiping or sweeping — pre/post wipe data identical
  - tool_A skin is tough and dry — must be cut to expose soft interior

Demo structure (NO labels — agent must identify tools from video):
  Demo 1 (tool_A):    Museum restorer using clay putty on fossil debris  — structural match
  Demo 2 (tool_B):    Making lettuce wraps (ssam)                        — attractive trap
  Demo 3 (tool_C):    Car wash rotating brush cleaning                   — intuitive trap
  Demo 4 (tool_D):    Industrial dust collector                           — common-sense trap
  Demo 5 (sponge):    Potter wiping clay dust with wet sponge             — risk-transfer trap
  Demo 6 (tool_E):    Street sweeper clearing leaves                      — mechanical trap

Evaluation:
  - Tool Selection accuracy: selecting "tool_A" = correct (primary metric)
  - Execution success: requires CUT preprocessing to expose soft interior
  - Using whole tool_A without cutting → execution FAILURE (tool selection still correct)
"""

import os

# Base directory for demo assets (user provides actual videos/frames)
_DEMO_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "cats", "demos", "micro_glass_shard_pickup"
)


TASK_CONFIG = {
    # ---- Basic info ----
    "task_name": "micro_glass_shard_pickup",
    "level": "2.3",
    "instruction": (
        "A glass cup broke on the kitchen floor. The large pieces have been "
        "cleared, but micro glass shards remain. Safely collect them.\n"
        "You have five candidate tools (tool_A through tool_E) on the countertop "
        "and a carving knife (carving_knife_707) for preparation."
    ),
    # Tool Selection accuracy: "tool_A" = correct (primary metric).
    # Execution success requires CUT preprocessing — evaluated separately.
    "correct_tool": "tool_A",

    # ---- One-Shot CA Tool Selection ----
    # Scene object names of CA tool candidates (must match scene template).
    # knife (carving_knife_707) is NOT a CA tool — freely usable for preprocessing.
    #
    # Display names are abstracted to prevent LLM recall.
    # Internal mapping (NOT shown to agent):
    #   tool_A = potato_701,  tool_B = lettuce_702,  tool_C = broccoli_703,
    #   tool_D = vacuum_704,  tool_E = broom_706
    "ca_tool_names": [
        # "sponge_705",  # TODO: re-enable when clay putty demo is ready
        "tool_C",
        "tool_D",
        "tool_B",
        "tool_A",
        "tool_E",
    ],
    # Mapping from abstracted names to scene object names
    "tool_name_mapping": {
        "tool_A": "potato_701",
        "tool_B": "lettuce_702",
        "tool_C": "broccoli_703",
        "tool_D": "vacuum_704",
        "tool_E": "broom_706",
        "carving_knife": "carving_knife_707",
        "knife": "carving_knife_707",
    },
    # Non-CA objects available in Stage 3 (e.g. preprocessing tools)
    "extra_object_names": [
        "carving_knife_707",
    ],

    # ---- Stage 1: Exploration — Navigation & Camera Tracking ----
    #
    # Scene layout (house_single_floor kitchen):
    #   countertop_kelzer_0:  pos=[6.030, -1.984, 0.870]
    #     Tools placed at Y~-1.90, Z=0.90, X=[6.50..7.30]
    #   spill_area (floor):   center ~[7.0, -3.0, 0.0]
    #     8 broken_glass objects scattered in ~50cm radius, scale 0.1
    #   Robot start:          pos=[5.21, -0.14, 0.0] (kitchen center, facing away from spill)
    #
    "exploration_direct_camera": {},
    "exploration_nav_targets": {
        "kitchen_floor, spill_area": "broken_glass_711",
        "countertop, scan":          "countertop_kelzer_0",
    },
    "exploration_nav_tracking": {
        "kitchen_floor, spill_area": "broken_glass_711",
        "countertop, scan":          "countertop_kelzer_0",
    },
    "exploration_look_targets": {},

    # ---- Stage 1: Exploration — Primitives Description ----
    "exploration_primitives_desc": (
        "NAVIGATE_TO[furniture, modifier]\n"
        "  Move to a fixed location to observe from a different angle. Returns camera image.\n"
        "  Valid: kitchen_floor, spill_area | countertop, scan\n\n"
        "TOUCH[surface, area]\n"
        "  Press fingertip sensor against a surface. Returns tactile sensor data.\n"
        "  Valid: floor, spill_area\n\n"
        "PUSH[object, target]\n"
        "  Wipe/sweep the surface and measure before/after. Returns force + tactile data.\n"
        "  Valid: hand, floor_surface\n\n"
        "PICK_UP[object]\n"
        "  Grasp and lift an object briefly. Returns grip and surface sensor data.\n"
        "  Valid: tool_A | tool_B | tool_C | tool_D | tool_E\n\n"
        "NAVIGATE_TO returns an image. TOUCH, PUSH, and PICK_UP return sensor data only."
    ),

    # ---- Stage 1: Exploration — Sensor Feedbacks ----
    # NAVIGATE_TO: visual (camera image + brief scene description)
    # TOUCH / PUSH / PICK_UP: raw sensor data (force, tactile array, physical properties)
    "exploration_feedbacks": {
        # --- NAVIGATE_TO: visual feedback (image + scene description) ---
        "NAVIGATE_TO[kitchen_floor, spill_area]":
            "You see a roughly 50cm area on the tile floor. "
            "The large pieces have been cleared. "
            "Under the light, faint glints are scattered across the tiles and grout lines.",
        "NAVIGATE_TO[countertop, scan]":
            "On the countertop you see five candidate tools and a knife:\n"
            "  tool_A — a dense, round, beige object with rough skin (≈fist-sized)\n"
            "  tool_B — a leafy green object with thin, flexible layers\n"
            "  tool_C — a green object with a thick stem and clustered florets\n"
            "  tool_D — a large mechanical device with a nozzle and power cord\n"
            "  tool_E — a long-handled object with dense bristles at one end\n"
            "  carving_knife_707 — a sharp kitchen knife (freely usable for preparation)",

        # --- TOUCH: tactile sensor data ---
        "TOUCH[floor, spill_area]": (
            "Fingertip tactile sensor (4x4 contact pressure array)\n"
            "Unit: kPa\n"
            "  [ 0.1,  0.0,  0.3,  0.0]\n"
            "  [ 0.0,  8.2,  0.0,  0.1]\n"
            "  [ 0.0,  0.0,  5.7,  0.0]\n"
            "  [ 0.2,  0.0,  0.0,  9.1]\n"
            "Normal force: 2.34 N\n"
            "Surface temperature: 22.3 C"
        ),

        # --- PUSH: before/after tactile comparison ---
        "PUSH[hand, floor_surface]": (
            "Wipe motion — lateral force 3.2 N, stroke 0.15 m\n"
            "\n"
            "Pre-wipe tactile (4x4, kPa):\n"
            "  [ 0.1,  0.0,  0.3,  0.0]\n"
            "  [ 0.0,  8.2,  0.0,  0.1]\n"
            "  [ 0.0,  0.0,  5.7,  0.0]\n"
            "  [ 0.2,  0.0,  0.0,  9.1]\n"
            "\n"
            "Post-wipe tactile (4x4, kPa):\n"
            "  [ 0.0,  0.0,  0.2,  0.0]\n"
            "  [ 0.0,  7.8,  0.0,  0.0]\n"
            "  [ 0.1,  0.0,  6.1,  0.0]\n"
            "  [ 0.0,  0.0,  0.0,  8.5]\n"
            "\n"
            "Particles displaced (lateral): 0\n"
            "\n"
            "Vertical pull test (per particle, N=3 samples):\n"
            "  extraction_force: [4.8, 6.2, 5.1] N\n"
            "  particle_depth_below_surface: [0.3, 0.6, 0.4] mm"
        ),

        # --- PICK_UP: object physical properties ---
        # "PICK_UP[sponge]": (  # TODO: re-enable when clay putty demo is ready
        #     "Object: sponge\n"
        #     "Mass: 0.04 kg\n"
        #     "Grip force required: 0.8 N\n"
        #     "Surface hardness (Shore A): 12\n"
        #     "Surface friction coefficient: 0.85\n"
        #     "Surface moisture: 0.05 (scale 0-1)\n"
        #     "Porosity: 0.82 (scale 0-1)"
        # ),
        "PICK_UP[tool_C]": (
            "Object: tool_C\n"
            "Mass: 0.31 kg\n"
            "Grip force required: 3.8 N\n"
            "Surface hardness (Shore A): 45\n"
            "Surface friction coefficient: 0.48\n"
            "Surface moisture: 0.15 (scale 0-1)\n"
            "Brittleness: florets crumble under 2.0 N shear"
        ),
        "PICK_UP[tool_A]": (
            "Object: tool_A\n"
            "Mass: 0.38 kg\n"
            "Grip force required: 4.2 N\n"
            "Surface hardness (Shore A): 78\n"
            "Surface friction coefficient: 0.62\n"
            "Surface moisture: 0.02 (scale 0-1)\n"
            "Interior (if cut): Shore A ~15, moisture 0.79, high adhesive compound content"
        ),
        "PICK_UP[tool_D]": (
            "Object: tool_D\n"
            "Mass: 3.2 kg\n"
            "Grip force required: 28.5 N\n"
            "Surface hardness (Shore A): 95\n"
            "Surface friction coefficient: 0.35\n"
            "Surface moisture: 0.00 (scale 0-1)\n"
            "Max suction force per particle: 0.3 N"
        ),
        "PICK_UP[tool_B]": (
            "Object: tool_B\n"
            "Mass: 0.22 kg\n"
            "Grip force required: 1.5 N\n"
            "Surface hardness (Shore A): 8\n"
            "Surface friction coefficient: 0.72\n"
            "Surface moisture: 0.88 (scale 0-1)\n"
            "Layer thickness: 0.4 mm — tears above 1.2 N point load"
        ),
        "PICK_UP[tool_E]": (
            "Object: tool_E\n"
            "Mass: 0.85 kg\n"
            "Grip force required: 6.2 N\n"
            "Surface hardness (Shore A): 90\n"
            "Surface friction coefficient: 0.40\n"
            "Surface moisture: 0.00 (scale 0-1)\n"
            "Bristle spacing: 1.2 mm — particles < 0.5 mm pass through"
        ),
    },

    # ---- Stage 2: Demo Observation ----
    "demo_system_prompt": (
        "Here are some reference demonstrations showing different approaches "
        "to various tasks."
    ),
    # NO labels — agent must identify tools and principles from video/text alone
    "demo_labels": [],
    "demo_image_paths": [
        os.path.join(_DEMO_DIR, "demo1_putty_restoration.mp4"),
        os.path.join(_DEMO_DIR, "demo2_lettuce_wrap.mp4"),
        os.path.join(_DEMO_DIR, "demo3_car_wash_brush.mp4"),
        os.path.join(_DEMO_DIR, "demo4_industrial_collector.mp4"),
        # os.path.join(_DEMO_DIR, "demo5_pottery_wipe.mp4"),  # TODO: re-enable with clay putty demo
        os.path.join(_DEMO_DIR, "demo6_street_sweeper.mp4"),
    ],
    # Text fallback when demo videos are not available
    "demo_text_descriptions": [
        # Demo 1: clay putty on fossil debris — structural match (soft adhesive surface)
        (
            "A museum restorer is cleaning tiny fossil fragments from "
            "a stone slab. They take a ball of soft, sticky putty and "
            "press it firmly onto the surface. When they peel the putty "
            "away, dozens of tiny fragments are embedded in the putty's "
            "soft surface. They repeat this pressing-and-peeling motion "
            "across the slab, and even fragments stuck in fine cracks "
            "are pulled out by the putty deforming into the gaps."
        ),
        # Demo 2: wrapping food in thin leaves — attractive trap
        (
            "A person prepares a meal by placing small pieces of food "
            "onto a thin, flexible green leaf. They fold the leaf "
            "around the food. The leaf is moist and pliable, wrapping "
            "tightly around the contents. They repeat this with "
            "several leaves, creating neat little parcels."
        ),
        # Demo 3: car wash rotating brush — intuitive trap
        (
            "An automated car wash station. Large rotating cylindrical "
            "brushes with dense clustered bristles spin rapidly against "
            "the car's surface. The bristles scrub away dirt and grime. "
            "Water sprays continuously as the brushes move along the "
            "car body."
        ),
        # Demo 4: industrial dust collector — common-sense trap
        (
            "A factory floor with fine metal shavings scattered around "
            "a lathe. A worker turns on an industrial dust collection "
            "unit with a wide nozzle. The machine generates strong "
            "suction, pulling loose shavings off the smooth concrete "
            "floor and into a collection bag."
        ),
        # Demo 5 (sponge): disabled — TODO re-enable with clay putty demo
        # Demo 6: street sweeper clearing leaves — mechanical trap
        (
            "A street sweeper vehicle drives slowly along a curb. Its "
            "large rotating brush sweeps fallen leaves and litter from "
            "the road surface into a collection chute. The stiff "
            "bristles push debris along the flat pavement. Small items "
            "that are flush with the ground are left behind."
        ),
    ],

    # ---- Tool Selection Step (with demos) ----
    "tool_selection_prompt": (
        "Now select the tool you will use for cleaning. "
        "Once you pick up a tool for cleaning, you cannot switch to another.\n\n"
        "Provide:\n"
        "(1) Which demo you referenced and why\n"
        "(2) Which tool you select (tool_A, tool_B, tool_C, tool_D, or tool_E)\n"
        "(3) What features of the current situation make this tool suitable\n"
        "(4) Your action plan — you may use the following base actions:\n"
        "    NAVIGATE_TO[object], GRASP[object], RELEASE[], "
        "PLACE_ON_TOP[object, surface], PUSH[object], PULL[object], "
        "OPEN[object], CUT[target_object, cutting_tool]\n\n"
        "    After cutting an object, it splits into two halves named "
        "half_<original_name>_0 and half_<original_name>_1.\n\n"
        "    carving_knife_707 is freely available for preparation.\n\n"
        "    If none of these base actions capture the required motion, "
        "you may define a new action:\n"
        "    NEW_ACTION[name, tool, target]: 'description of the physical motion'\n"
        "    This new action must be physically plausible."
    ),

    # ---- Tool Selection Step (no demos available) ----
    "tool_selection_prompt_no_demo": (
        "Now select the tool you will use for cleaning. "
        "Once you pick up a tool for cleaning, you cannot switch to another.\n\n"
        "Provide:\n"
        "(1) What physical principle guides your tool selection\n"
        "(2) Which tool you select (tool_A, tool_B, tool_C, tool_D, or tool_E)\n"
        "(3) What sensor data or physical properties make this tool suitable "
        "(reference specific values from your exploration)\n"
        "(4) Your action plan — you may use the following base actions:\n"
        "    NAVIGATE_TO[object], GRASP[object], RELEASE[], "
        "PLACE_ON_TOP[object, surface], PUSH[object], PULL[object], "
        "OPEN[object], CUT[target_object, cutting_tool]\n\n"
        "    After cutting an object, it splits into two halves named "
        "half_<original_name>_0 and half_<original_name>_1.\n\n"
        "    carving_knife_707 is freely available for preparation.\n\n"
        "    If none of these base actions capture the required motion, "
        "you may define a new action:\n"
        "    NEW_ACTION[name, tool, target]: 'description of the physical motion'\n"
        "    This new action must be physically plausible."
    ),

    # ---- Stage 3: NEW_ACTION handlers (for physical grounding) ----
    # Each handler: (tool_key, target_key, context_key) → outcome + aux_text
    # Matching is fuzzy substring — dict order matters (first match wins).
    #
    # Evaluation design:
    #   - Selecting "potato" in Tool Selection = CORRECT (primary metric)
    #   - Execution with half_potato (after CUT) = SUCCESS
    #   - Execution with whole potato (no CUT) = FAILURE (but tool selection is still correct)
    #
    # "half_tool_A" MUST precede "tool_A" for correct fuzzy matching.
    "new_action_handlers": {
        # half_tool_A (after CUT) → SUCCESS
        ("half_tool_A", "glass", "spill"): {
            "outcome": "SUCCESS",
            "state_changes": [
                # 1. Teleport all broken_glass objects to z=-10 (underground)
                # 2. og.sim.step()
            ],
            "aux_text": (
                "The soft, moist cross-section pressed firmly against the tiles. "
                "Micro glass shards embedded into the adhesive interior. "
                "The material deformed into grout line gaps, capturing wedged shards. "
                "The floor is now clean."
            ),
        },
        # whole tool_A (no CUT) → FAILURE at execution, but tool selection was correct
        ("tool_A", "glass", "spill"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The outer surface is too tough and dry (Shore A 78). "
                "The shards do not embed into the hard exterior. "
                "You need to cut tool_A to expose the soft interior."
            ),
        },
        # tool_B → FAILURE
        ("tool_B", "glass", "spill"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The thin layers are too fragile — sharp shards pierced through. "
                "The material tore apart on the floor. No shards picked up. "
                "Torn pieces now cover some shards, making them harder to locate."
            ),
        },
        # tool_C → FAILURE
        ("tool_C", "glass", "spill"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The florets crumbled on contact with the floor. "
                "Debris scattered across the spill area, "
                "mixing with glass shards. No shards picked up."
            ),
        },
        # tool_D → FAILURE
        ("tool_D", "glass", "spill"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "Grinding sounds from inside the device. "
                "Fine glass dust blown out from the exhaust. "
                "Micro shards damaged the internal filter. "
                "Shards wedged in grout lines remain — "
                "suction cannot dislodge embedded particles."
            ),
        },
        # sponge → FAILURE (risk transfer)
        # TODO: re-enable when clay putty demo is ready
        # ("sponge", "glass", "spill"): {
        #     "outcome": "FAILURE",
        #     "state_changes": [],
        #     "aux_text": (
        #         "Some surface shards picked up by the sponge, "
        #         "but grout line shards remain. "
        #         "Shards are now deeply embedded in sponge pores — "
        #         "the sponge itself has become a hazardous object. "
        #         "Risk transferred, not eliminated."
        #     ),
        # },
        # tool_E → FAILURE (scatters shards further)
        ("tool_E", "glass", "spill"): {
            "outcome": "FAILURE",
            "state_changes": [],
            "aux_text": (
                "The bristles scattered micro shards across a wider area. "
                "Shards are too small and flat to be caught between bristles. "
                "Grout line shards remain untouched. "
                "The contamination area has expanded."
            ),
        },
    },

    # ---- Stage 3: Menu-based symbolic execution ----
    # Pre-defined action primitives — LLM chooses from this menu.
    # All actions execute symbolically; state_changes update the scene for photos.
    #
    # tool_key: filters which actions are shown based on selected tool.
    #   "preprocessing" — always shown regardless of selected tool.
    #   "<tool_name>"   — shown only when that tool is selected.
    #
    # Feedback style: raw sensor observations, no prescriptive hints.
    # Agent must infer "why" from the data.
    "stage3_action_menu": {
        # --- Preprocessing (always available) ---
        "CUT[tool_A, carving_knife_707]": {
            "tool_key": "tool_A",
            "description": "Cut tool_A in half with the carving knife",
            "outcome": "SUCCESS",
            "feedback": (
                "Blade resistance: 12N. Clean separation.\n"
                "Two halves produced: half_tool_A_0, half_tool_A_1.\n"
                "Exposed cross-section properties:\n"
                "  Shore A: 15 (vs exterior: 78)\n"
                "  Moisture: 0.79 (vs exterior: 0.02)\n"
                "  Surface: adhesive gel matrix, slightly tacky"
            ),
            "sim_action": ("CUT", "potato_701", "carving_knife_707"),
            "unlocks": ["DAB[half_tool_A_0, spill_area]"],
        },

        # --- tool_A actions ---
        "DAB[tool_A, spill_area]": {
            "tool_key": "tool_A",
            "description": "Press tool_A (whole) onto the spill area",
            "outcome": "FAILURE",
            "feedback": (
                "Contact pressure: 6.8 kPa over 28 cm² area.\n"
                "Surface deformation: < 0.1 mm (insufficient).\n"
                "Post-contact tactile (4x4, kPa):\n"
                "  [ 0.0,  0.0,  0.3,  0.0]\n"
                "  [ 0.0,  7.9,  0.0,  0.1]\n"
                "  [ 0.0,  0.0,  5.8,  0.0]\n"
                "  [ 0.2,  0.0,  0.0,  8.8]\n"
                "Particles displaced: 0\n"
                "Particles adhered to tool surface: 0"
            ),
        },
        "DAB[half_tool_A_0, spill_area]": {
            "tool_key": "tool_A",
            "description": "Press the cut half (exposed interior) onto the spill area",
            "requires": "CUT[tool_A, carving_knife_707]",
            "outcome": "SUCCESS",
            "feedback": (
                "Contact pressure: 5.2 kPa over 35 cm² area.\n"
                "Surface deformation: 0.8 mm (gel matrix compressed).\n"
                "Post-contact tactile (4x4, kPa):\n"
                "  [ 0.0,  0.0,  0.0,  0.0]\n"
                "  [ 0.0,  0.0,  0.0,  0.0]\n"
                "  [ 0.0,  0.0,  0.0,  0.0]\n"
                "  [ 0.0,  0.0,  0.0,  0.0]\n"
                "Particles displaced: 0\n"
                "Particles adhered to tool surface: 47\n"
                "Grout line residual: 0\n"
                "Floor status: CLEAN"
            ),
            "state_changes": [
                {"type": "teleport_underground", "pattern": "broken_glass"},
            ],
            "task_success": True,
        },
        "PUSH[tool_A, spill_area]": {
            "tool_key": "tool_A",
            "description": "Roll/push tool_A across the spill area",
            "outcome": "FAILURE",
            "feedback": (
                "Lateral force applied: 4.1 N, stroke: 0.30 m.\n"
                "Contact type: rolling — intermittent surface contact.\n"
                "Surface deformation: < 0.05 mm per contact point.\n"
                "Grout line penetration: 0 mm.\n"
                "Particles displaced: 2\n"
                "Particles adhered to tool surface: 0"
            ),
        },

        # --- tool_D actions ---
        "SUCTION[tool_D, spill_area]": {
            "tool_key": "tool_D",
            "description": "Use tool_D to suck up shards from the spill area",
            "outcome": "FAILURE",
            "feedback": (
                "Suction applied: 0.3 N per particle (max).\n"
                "Particles on surface: extraction force 4.8-6.2 N (embedded).\n"
                "Particles extracted: 0\n"
                "Audible: high-pitch grinding (filter contact).\n"
                "Exhaust particulate count: elevated (glass dust recirculated).\n"
                "Grout line residual: 47 particles"
            ),
        },

        # --- Sponge actions ---
        # TODO: re-enable when clay putty demo is ready

        # --- tool_E actions ---
        "SWEEP[tool_E, spill_area]": {
            "tool_key": "tool_E",
            "description": "Sweep the spill area with tool_E",
            "outcome": "FAILURE",
            "feedback": (
                "Lateral force: 5.4 N, stroke: 0.45 m.\n"
                "Bristle contact width: 1.2 mm spacing.\n"
                "Particles swept into pile: 0 (particle size < bristle gap).\n"
                "Particles scattered beyond original area: 18.\n"
                "Grout line residual: 47 (untouched).\n"
                "Contamination radius expanded: 50 cm → 120 cm"
            ),
        },

        # --- tool_B actions ---
        "DAB[tool_B, spill_area]": {
            "tool_key": "tool_B",
            "description": "Press tool_B layers onto the spill area",
            "outcome": "FAILURE",
            "feedback": (
                "Contact pressure: 1.8 kPa over 50 cm² area.\n"
                "Layer thickness at contact: 0.4 mm.\n"
                "Structural failure: 6 puncture points detected.\n"
                "Layer integrity: TORN (shear force exceeded 1.2 N at 6 points).\n"
                "Particles adhered to layer: 2\n"
                "Particles fell through punctures: 4\n"
                "Debris now covers remaining particles"
            ),
        },

        # --- tool_C actions ---
        "DAB[tool_C, spill_area]": {
            "tool_key": "tool_C",
            "description": "Press tool_C florets onto the spill area",
            "outcome": "FAILURE",
            "feedback": (
                "Contact pressure: 4.5 kPa over 22 cm² area.\n"
                "Structural failure: florets crumbled at 2.0 N shear.\n"
                "Tool integrity: DESTROYED (fragmented into 12+ pieces).\n"
                "Particles adhered: 0\n"
                "Tool debris on floor: 12 fragments.\n"
                "Glass particles now mixed with organic debris"
            ),
        },
    },

    # ---- Metacognitive Probes ----
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
