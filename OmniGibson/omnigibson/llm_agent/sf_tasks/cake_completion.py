"""SF Task: Cake Completion During Power Outage

Level 3.3 — Extrapolation-Required Prospection
Measures: Scenario Flexibility (SF)

Multi-strategy design with 4 independent "bonus tracks":
  Track A: Cream quality (liquid / dirty-whipped / clean-whipped)
  Track B: Chocolate quality (pieces / melted via kettle water bath)
  Track C: Presentation (platter from cabinet)
  Track D: Extra baking (power restore + oven reheat)

Hidden variables (12):
  V1:  cake doneness (80%)
  V2:  oven rapid cooling when opened (-18°C/step)
  V3:  fridge rapid warming when opened (+2°C/step) — extrapolation from V2
  V4:  power restore timing (step 8 = 24 min)
  V5:  hot cake + cream = melt (cake>50°C)
  V6:  oven preheat time (3 steps = 9 min)
  V7:  kettle cooling (75°C, -3°C/step → unusable at step 8)
  V8:  whisk is dirty (needs washing for clean cream)
  V9:  sink pump needs power (wash whisk only after power restore)
  V10: chocolate melt path (kettle → bowl → melt = 25pts vs pieces = 10pts)
  V11: platter in cabinet (+10 presentation pts)
  V12: kettle timing pressure (pour before step 8 or lose melt option)

Competitive strategies (all 80-90 points):
  S1 (90pts): Clean cream + Melted chocolate — V3,V5,V7,V8,V9,V12
  S2 (85pts): Clean cream + Choco pieces + Platter — V3,V5,V8,V9,V11
  S4 (80pts): Dirty cream + Melted chocolate — V3,V5,V7,V12
  S3 (75pts): Power bake + Melted choco + Liquid cream — V4,V6,V7,V12

Time system: 3 minutes per step, 20 steps total = 60 minutes.
"""

SF_TASK_CONFIG = {
    # ---- Basic Info ----
    "task_name": "cake_completion",
    "measurement_target": "Scenario Flexibility",
    "level": "3.3",
    "instruction": (
        "You were making a cake in the kitchen when the power went out. "
        "The cake is sitting on a casserole dish inside the oven. "
        "Guests arrive in 60 minutes. Complete the cake as best you can "
        "\u2014 the guests are expecting a decorated cake. "
        "To move the cake, grab the casserole dish it sits on."
    ),

    # ---- Robot Rules ----
    "robot_rules": (
        "Robot capabilities:\n"
        "- You can safely GRASP any object regardless of its temperature "
        "(no heat protection needed)\n"
        "- You can hold ONE object at a time \u2014 you must PLACE or RELEASE "
        "the current object before GRASPing another\n"
        "- To access objects inside a closed container (oven, fridge, cabinet), "
        "you must OPEN it first\n"
        "- The casserole dish and cake move as one unit \u2014 "
        "GRASP the casserole to move the cake\n"
        "- To interact with an object, NAVIGATE to it first"
    ),

    # ---- Time System ----
    # 3 minutes per step, 20 steps = 60 minutes total.
    # All rates are per 3-minute step.
    "time_system": {
        "step_duration_minutes": 3,
        "max_steps": 20,
        "room_temp": 23.0,
        "power_restore_step": 8,
        "oven_preheat_steps": 3,

        "oven_initial_temp": 180.0,
        "oven_cooling_closed": 7.0,
        "oven_cooling_opened": 18.0,

        "fridge_initial_temp": 5.0,
        "fridge_warming_closed": 1.0,
        "fridge_warming_opened": 2.0,

        "cake_initial_doneness": 80.0,
        "cake_cooking_threshold": 100.0,
        "cake_cooking_coeff": 0.02,
        "cake_temp_when_removed": 93.0,
        "cake_cooling_rate": 9.0,

        "cream_melt_threshold": 25.0,
        "cream_apply_max_cake_temp": 50.0,
        "cream_warming_outside": 0.5,

        # Kettle (hot water for chocolate melting)
        "kettle_initial_temp": 75.0,
        "kettle_cooling_rate": 3.0,
        "kettle_min_useful_temp": 45.0,

        # Bowl water bath
        "bowl_water_cooling_rate": 2.0,
        "chocolate_melt_threshold": 45.0,

        # Scoring — multi-track
        "scoring": {
            "doneness_90plus": 35,
            "doneness_80_90": 25,
            "doneness_70_80": 15,
            "cream_clean_whipped": 25,
            "cream_dirty_whipped": 15,
            "cream_liquid": 10,
            "chocolate_melted": 25,
            "chocolate_pieces": 10,
            "platter_presentation": 10,
            "completed_in_time": 15,
            "max_score": 110,
        },
    },

    # ---- Phase 0: Observation ----
    "exploration_primitives_desc": (
        "This is the OBSERVATION phase. You may look around and "
        "touch external surfaces to gather information.\n"
        "You may NOT open, grab, or manipulate any objects yet.\n\n"
        "Available actions:\n"
        "- NAVIGATE_TO[location]: Move to look at something\n"
        "  Valid locations: kitchen, oven, fridge, countertop, sink\n"
        "- TOUCH[surface]: Measure surface temperature/properties\n"
        "  Valid surfaces: oven_door, fridge_door, countertop, kettle, whisk, sink\n"
        "- LOOK_CLOSER[target]: Zoom in to observe details\n"
        "  Valid targets: oven, fridge, countertop, sink, top_cabinet\n"
        "- DONE_OBSERVING[]: Finish observation phase\n\n"
        "Respond in format:\n"
        "Thought: <reasoning>\n"
        "Action: <ACTION>[<args>]"
    ),
    "exploration_nav_targets": {
        "kitchen": "countertop_kelzer_0",
        "oven": "oven_ffitak_0",
        "fridge": "fridge_dszchb_0",
        "countertop": "countertop_kelzer_0",
        "sink": "countertop_kelzer_0",
    },
    "exploration_nav_tracking": {
        "oven": "oven_ffitak_0",
        "fridge": "fridge_dszchb_0",
        "countertop": "countertop_kelzer_0",
    },
    "exploration_look_targets": {
        "oven": "oven_ffitak_0",
        "fridge": "fridge_dszchb_0",
        "countertop": "countertop_kelzer_0",
        "sink": "countertop_kelzer_0",
        "top_cabinet": "countertop_kelzer_0",
    },
    "exploration_direct_camera": {},
    "look_closer_focal_length": 50.0,

    "exploration_feedbacks": {
        "NAVIGATE_TO[kitchen]": None,
        "NAVIGATE_TO[oven]": None,
        "NAVIGATE_TO[fridge]": None,
        "NAVIGATE_TO[countertop]": None,
        "NAVIGATE_TO[sink]": None,
        "TOUCH[oven_door]": (
            "Surface temperature: 172\u00b0C. "
            "Cooling rate (door closed): -2.0\u00b0C per 3 minutes. "
            "Power indicator LED: OFF."
        ),
        "TOUCH[fridge_door]": (
            "Surface temperature: 8\u00b0C. "
            "Warming rate (door closed): +0.3\u00b0C per 3 minutes. "
            "Compressor: silent. Power indicator: OFF."
        ),
        "TOUCH[countertop]": (
            "Surface temperature: 23\u00b0C (room temperature). "
            "Items on countertop: chocolate bar, mixing bowl, plate, dishtowel. "
            "A kettle sits near the back \u2014 faint steam is rising from its spout. "
            "Nearby: a sink area is visible to the left, "
            "and upper cabinets with glass doors are above."
        ),
        "TOUCH[kettle]": (
            "Surface is warm to the touch. "
            "Temperature: 75\u00b0C. Contains hot water. Cooling steadily."
        ),
        "TOUCH[whisk]": (
            "Whisk has dried food residue on the wires. "
            "Needs washing before clean use."
        ),
        "TOUCH[sink]": (
            "Faucet handle turned \u2014 no water comes out. "
            "No water pressure. The pump appears to be electric."
        ),
        "LOOK_CLOSER[oven]": None,
        "LOOK_CLOSER[fridge]": None,
        "LOOK_CLOSER[countertop]": (
            "Countertop items: a solid chocolate bar (unwrapped), "
            "an empty mixing bowl, a plain plate, and a dishtowel. "
            "A stainless steel kettle sits near the back with faint steam. "
            "To the left, the sink area has a dirty whisk resting on its edge. "
            "Above, glass-doored upper cabinets show something reflective inside."
        ),
        "LOOK_CLOSER[sink]": (
            "A whisk with dried food residue sits on the sink edge. "
            "The faucet handle is in the OFF position. "
            "A small label on the faucet reads: 'Electric pump assisted.'"
        ),
        "LOOK_CLOSER[top_cabinet]": (
            "Through the glass door of the upper cabinet, "
            "a decorative serving platter is visible inside."
        ),
    },

    # ---- SF Prediction 1: Initial Scenario Prediction ----
    "phase1_system_prompt": (
        "You are a robot agent in a kitchen during a power outage.\n"
        "Task: {instruction}\n\n"
        "{robot_rules}\n\n"
        "You have observed the environment but have NOT yet taken "
        "any action. Before acting, think about what could happen."
    ),
    "phase1_user_prompt": (
        "Based on your observations, analyze the situation:\n\n"
        "=== Part A: Variable Identification ===\n"
        "List ALL uncertain or hidden factors that could affect\n"
        "the outcome. For each:\n"
        "- VARIABLE: Name it\n"
        "- CURRENT KNOWLEDGE: What you know / don't know\n"
        "- POSSIBLE VALUES: What it could be\n"
        "- IMPACT: How it would affect the task\n"
        "- HOW TO DISCOVER: How you could confirm it\n\n"
        "=== Part B: Scenario Generation ===\n"
        "Now combine these variables into concrete scenarios.\n"
        "Consider what happens when multiple variables interact.\n"
        "For each scenario:\n"
        "- SCENARIO: Describe what happens\n"
        "- VARIABLES INVOLVED: Which variables from Part A\n"
        "- TRIGGER: What condition makes this happen\n"
        "- CONSEQUENCE: Impact on task completion\n"
        "- LIKELIHOOD: High / Medium / Low\n\n"
        "Generate as many plausible scenarios as you can.\n"
        "Focus especially on scenarios where variables COMBINE\n"
        "to create unexpected outcomes."
    ),

    # ---- Phase 2: Investigation (irreversible) ----
    "rollout_max_steps": 4,
    "rollout_allowed_actions": ["NAVIGATE_TO", "OPEN", "CLOSE", "TOUCH", "LOOK_CLOSER"],
    "rollout_system_prompt": (
        "You are a robot agent in a kitchen during a power outage.\n"
        "Task: {instruction}\n\n"
        "{robot_rules}\n\n"
        "This is the INVESTIGATION phase.\n"
        "You may now interact with the environment to verify "
        "your predictions and resolve uncertainties.\n\n"
        "IMPORTANT:\n"
        "- Actions in this phase PERMANENTLY change the environment "
        "and CANNOT be undone.\n"
        "- Each action takes 3 minutes.\n"
        "- Maximum 4 steps in this phase.\n"
        "- After this phase, you will create your final execution "
        "plans. You will NOT be able to adjust plans mid-execution.\n\n"
        "Available actions:\n"
        "- NAVIGATE_TO[location]: Move near an object\n"
        "  Valid: oven, fridge, countertop, sink\n"
        "- OPEN[object]: Open a container door\n"
        "  Valid: oven_ffitak_0, fridge_dszchb_0\n"
        "- CLOSE[object]: Close a container door\n"
        "  Valid: oven_ffitak_0, fridge_dszchb_0\n"
        "- TOUCH[surface]: Measure temperature/properties\n"
        "  Valid: oven_door, fridge_door, oven_interior, cake, cream, "
        "countertop, kettle, whisk, mixing_bowl, sink, top_cabinet\n"
        "- LOOK_CLOSER[target]: Zoom in to observe details\n"
        "  Valid: oven, fridge, countertop, sink, top_cabinet\n"
        "- DONE_INVESTIGATING[]: Finish investigation\n\n"
        "NOT allowed: GRASP, PLACE, WAIT, NEW_ACTION\n\n"
        "Respond in format:\n"
        "Thought: <reasoning>\n"
        "Action: <ACTION>[<args>]"
    ),

    # ---- SF Prediction 2: Extended Prediction (SF core measurement) ----
    "phase3_system_prompt": (
        "You are a robot agent in a kitchen during a power outage.\n"
        "Task: {instruction}\n\n"
        "{robot_rules}\n\n"
        "The investigation phase is complete.\n"
        "The environment has been changed by your actions and "
        "CANNOT be reset. Use what you learned to finalize "
        "your strategy."
    ),
    "phase3_user_prompt": (
        "=== Part A: Variable Updates ===\n"
        "For each variable from SF Prediction 1:\n"
        "- CONFIRMED / REVISED / STILL UNKNOWN\n"
        "- New information (if any)\n\n"
        "Are there NEW variables you didn't identify before?\n\n"
        "=== Part B: Scenario Updates ===\n"
        "For each scenario from SF Prediction 1:\n"
        "- CONFIRM / REVISE / DELETE \u2014 and why\n\n"
        "What NEW scenarios should be added based on\n"
        "what you learned? Think about:\n"
        "- Did any observation reveal effects that might\n"
        "  apply to OTHER parts of the environment?\n"
        "- Did any variable combination become more or\n"
        "  less likely?\n\n"
        "=== Part C: Execution Plans (exactly 5) ===\n"
        "Based on ALL your updated variables and scenarios,\n"
        "create 5 plans that maximize the chance of success.\n"
        "Each plan should address a DIFFERENT combination of\n"
        "scenarios from Part B.\n\n"
        "CRITICAL: Plans will be executed EXACTLY as written\n"
        "with NO opportunity to adjust mid-execution.\n\n"
        "Format:\n"
        "Plan [A/B/C/D/E]: [strategy name]\n"
        "  Addresses scenarios: [list which scenarios this plan handles]\n"
        "  Step 1: ACTION[args]\n"
        "  Step 2: ACTION[args]\n"
        "  ...\n"
        "  Expected outcome: [specific result]\n"
        "  Expected score: [points breakdown]\n"
        "  Key risk: [which scenarios would cause failure]\n\n"
        "Available actions for plans:\n"
        "- NAVIGATE_TO[location]\n"
        "- GRASP[object] (requires empty hands)\n"
        "- RELEASE[]\n"
        "- PLACE_ON_TOP[surface]\n"
        "- OPEN[container]\n"
        "- CLOSE[container]\n"
        "- TOUCH[surface]\n"
        "- WAIT[]\n\n"
        "Custom actions (use these exact formats):\n"
        "- NEW_ACTION[PREPARE_DECORATION, chocolate_bar_703, decoration]\n"
        "  Chops chocolate into pieces for decoration\n"
        "- NEW_ACTION[APPLY_CREAM, cream_carton_702, chocolate_cake_701]\n"
        "  Applies cream to cake (cream must be GRASPed from fridge first)\n"
        "- NEW_ACTION[APPLY_CHOCOLATE, chocolate_bar_703, chocolate_cake_701]\n"
        "  Applies chocolate decoration (PREPARE or MELT must be done first)\n"
        "- NEW_ACTION[TURN_ON_OVEN, oven_ffitak_0, 180]\n"
        "  Turns on oven to 180\u00b0C (requires power restored)\n"
        "- NEW_ACTION[WASH_WHISK, whisk_708, sink]\n"
        "  Washes dirty whisk (requires water \u2014 pump needs power)\n"
        "- NEW_ACTION[WHIP_CREAM, whisk_708, cream_carton_702]\n"
        "  Whips cream (quality depends on whisk cleanliness)\n"
        "- NEW_ACTION[POUR_HOT_WATER, kettle_706, mixing_bowl_707]\n"
        "  Pours hot water from kettle into bowl (kettle must be > 50\u00b0C)\n"
        "- NEW_ACTION[MELT_CHOCOLATE, chocolate_bar_703, mixing_bowl_707]\n"
        "  Melts chocolate in water bath (requires hot water in bowl)\n"
        "- NEW_ACTION[RETRIEVE_PLATTER, platter_709, top_cabinet]\n"
        "  Gets platter from cabinet for presentation\n"
        "- NEW_ACTION[USE_PLATTER, chocolate_cake_701, platter_709]\n"
        "  Places cake on platter for elegant presentation (+10 pts)\n\n"
        "{available_objects}\n\n"
        "Remember: Each step = 3 minutes. {remaining_info}\n\n"
        "RANKING: [A/B/C/D/E] > [A/B/C/D/E] > [A/B/C/D/E] > [A/B/C/D/E] > [A/B/C/D/E]"
    ),

    # ---- NEW_ACTION handlers ----
    "new_action_handlers": {
        # Cream track
        ("cream", "cake", "apply"): {
            "outcome": "DYNAMIC",
            "handler_fn": "apply_cream",
        },
        ("whisk", "sink", "wash"): {
            "outcome": "DYNAMIC",
            "handler_fn": "wash_whisk",
        },
        ("whisk", "cream", "whip"): {
            "outcome": "DYNAMIC",
            "handler_fn": "whip_cream",
        },
        # Chocolate track
        ("chocolate", "decoration", "prepare"): {
            "outcome": "DYNAMIC",
            "handler_fn": "prepare_decoration",
        },
        ("chocolate", "cake", "decorate"): {
            "outcome": "DYNAMIC",
            "handler_fn": "apply_chocolate",
        },
        ("kettle", "bowl", "pour"): {
            "outcome": "DYNAMIC",
            "handler_fn": "pour_hot_water",
        },
        ("chocolate", "bowl", "melt"): {
            "outcome": "DYNAMIC",
            "handler_fn": "melt_chocolate",
        },
        # Presentation track
        ("platter", "cabinet", "retrieve"): {
            "outcome": "DYNAMIC",
            "handler_fn": "retrieve_platter",
        },
        ("cake", "platter", "present"): {
            "outcome": "DYNAMIC",
            "handler_fn": "use_platter",
        },
        # Baking track
        ("oven", "180", "turn_on"): {
            "outcome": "DYNAMIC",
            "handler_fn": "turn_on_oven",
        },
    },

    # ---- Hidden Variables ----
    "hidden_variables": [
        {
            "id": "V1", "name": "cake_doneness",
            "discovery": "OPEN[oven] + TOUCH[cake]",
            "layer": 3,
            "description": "Cake is 80% done \u2014 edible, decoration is higher priority",
        },
        {
            "id": "V2", "name": "oven_rapid_cooling",
            "discovery": "investigation \u2014 OPEN[oven] then observe temp drop",
            "layer": 3,
            "description": "Opening oven causes -18\u00b0C/step rapid heat loss (vs -7 closed)",
        },
        {
            "id": "V3", "name": "fridge_rapid_warming",
            "discovery": "extrapolation from V2",
            "layer": "extrapolation",
            "description": "Opening fridge causes +2\u00b0C/step rapid warming (extrapolated)",
        },
        {
            "id": "V4", "name": "power_restore_timing",
            "discovery": "wait until step 8 (24 minutes)",
            "layer": 3,
            "description": "Power restores at step 8, enabling oven + water pump",
        },
        {
            "id": "V5", "name": "hot_cake_melts_cream",
            "discovery": "physical reasoning",
            "layer": "extrapolation",
            "description": "Applying cream to cake >50\u00b0C causes cream to melt",
        },
        {
            "id": "V6", "name": "oven_preheat_time",
            "discovery": "after power restore, attempt TURN_ON[oven]",
            "layer": 3,
            "description": "Oven needs 3 steps (9 min) to preheat after power restore",
        },
        {
            "id": "V7", "name": "kettle_cooling",
            "discovery": "TOUCH[kettle] at different times",
            "layer": 3,
            "description": "Kettle starts at 75\u00b0C, cools -3\u00b0C/step. Unusable for melting after step 8.",
        },
        {
            "id": "V8", "name": "whisk_dirty",
            "discovery": "TOUCH[whisk] or LOOK_CLOSER[sink]",
            "layer": 3,
            "description": "Whisk has residue. Dirty whisk gives dirty_whipped cream (15pts vs 25pts).",
        },
        {
            "id": "V9", "name": "water_requires_power",
            "discovery": "TOUCH[sink] or attempt WASH_WHISK before power restore",
            "layer": "extrapolation",
            "description": "Sink pump needs power. Washing whisk requires power at step 8+.",
        },
        {
            "id": "V10", "name": "chocolate_melt_path",
            "discovery": "observation of kettle + bowl + reasoning about water bath",
            "layer": "extrapolation",
            "description": "Kettle water \u2192 bowl \u2192 melt chocolate = 25pts vs pieces 10pts.",
        },
        {
            "id": "V11", "name": "platter_in_cabinet",
            "discovery": "LOOK_CLOSER[top_cabinet]",
            "layer": 3,
            "description": "Decorative platter in cabinet adds 10 presentation points.",
        },
        {
            "id": "V12", "name": "kettle_timing_pressure",
            "discovery": "extrapolation from kettle cooling rate",
            "layer": "extrapolation",
            "description": "Must pour kettle water before step 8 (75-3*8=51\u00b0C, barely above 50\u00b0C threshold).",
        },
    ],

    # ---- SF Metrics Weights ----
    "sf_metrics": {
        "scenario_coverage": {"weight": 0.25},
        "prediction_accuracy": {"weight": 0.25},
        "extrapolation_ratio": {"weight": 0.20},
        "cake_score_normalized": {"weight": 0.20},
        "balance_ratio": {"weight": 0.10},
    },

    # ---- Metacognitive Probes ----
    "probes": {
        "phase0": (
            "Based on your observations, what are the key physical variables "
            "in this environment? What can you estimate from sensor data, "
            "and what remains uncertain?"
        ),
        "phase2": (
            "What did you learn from the investigation that you couldn't learn "
            "from external observation alone? Were there any unexpected side effects?"
        ),
        "sf_prediction2": (
            "Did your plans account for all the scenarios you predicted? "
            "Which plan do you think will perform best and why?"
        ),
    },
}
