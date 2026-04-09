"""Prompt construction and LLM response parsing for OmniGibson tasks."""

import re
from typing import Dict, List, Optional, Tuple

from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
    SymbolicSemanticActionPrimitiveSet,
)
from omnigibson.action_primitives.eib_semantic_action_primitives import (
    EIBSemanticActionPrimitiveSet,
)

# DONE, ABSTAIN, ASK are special meta-actions handled in parse_llm_response()

# ---------- Starter (physics-based) primitives: 9 actions (commented out) ----------
# _STARTER_PRIMITIVES = {
#     "GRASP": StarterSemanticActionPrimitiveSet.GRASP,
#     "PLACE_ON_TOP": StarterSemanticActionPrimitiveSet.PLACE_ON_TOP,
#     "PLACE_INSIDE": StarterSemanticActionPrimitiveSet.PLACE_INSIDE,
#     "OPEN": StarterSemanticActionPrimitiveSet.OPEN,
#     "CLOSE": StarterSemanticActionPrimitiveSet.CLOSE,
#     "NAVIGATE_TO": StarterSemanticActionPrimitiveSet.NAVIGATE_TO,
#     "RELEASE": StarterSemanticActionPrimitiveSet.RELEASE,
#     "TOGGLE_ON": StarterSemanticActionPrimitiveSet.TOGGLE_ON,
#     "TOGGLE_OFF": StarterSemanticActionPrimitiveSet.TOGGLE_OFF,
# }

# ---------- Symbolic (teleport-based) primitives ----------
_SYMBOLIC_PRIMITIVES = {
    "GRASP": SymbolicSemanticActionPrimitiveSet.GRASP,
    "PLACE_ON_TOP": SymbolicSemanticActionPrimitiveSet.PLACE_ON_TOP,
    "PLACE_INSIDE": SymbolicSemanticActionPrimitiveSet.PLACE_INSIDE,
    "OPEN": SymbolicSemanticActionPrimitiveSet.OPEN,
    "CLOSE": SymbolicSemanticActionPrimitiveSet.CLOSE,
    "NAVIGATE_TO": SymbolicSemanticActionPrimitiveSet.NAVIGATE_TO,
    "RELEASE": SymbolicSemanticActionPrimitiveSet.RELEASE,
    "TOGGLE_ON": SymbolicSemanticActionPrimitiveSet.TOGGLE_ON,
    "TOGGLE_OFF": SymbolicSemanticActionPrimitiveSet.TOGGLE_OFF,
    "SOAK_UNDER": SymbolicSemanticActionPrimitiveSet.SOAK_UNDER,
    "SOAK_INSIDE": SymbolicSemanticActionPrimitiveSet.SOAK_INSIDE,
    "WIPE": SymbolicSemanticActionPrimitiveSet.WIPE,
    "CUT": SymbolicSemanticActionPrimitiveSet.CUT,
    "PLACE_NEAR_HEATING_ELEMENT": SymbolicSemanticActionPrimitiveSet.PLACE_NEAR_HEATING_ELEMENT,
    "CLIMB_ON": SymbolicSemanticActionPrimitiveSet.CLIMB_ON,
    "CLIMB_DOWN": SymbolicSemanticActionPrimitiveSet.CLIMB_DOWN,
    "PUSH": SymbolicSemanticActionPrimitiveSet.PUSH,
    "PULL": SymbolicSemanticActionPrimitiveSet.PULL,
    "FILL_WITH": SymbolicSemanticActionPrimitiveSet.FILL_WITH,
    "POUR_INTO": SymbolicSemanticActionPrimitiveSet.POUR_INTO,
    "WAIT_FOR_COOKED": SymbolicSemanticActionPrimitiveSet.WAIT_FOR_COOKED,
    "WAIT_FOR_WASHED": SymbolicSemanticActionPrimitiveSet.WAIT_FOR_WASHED,
    "WAIT": SymbolicSemanticActionPrimitiveSet.WAIT,
    "SPREAD": SymbolicSemanticActionPrimitiveSet.SPREAD,
    "WAIT_FOR_FROZEN": SymbolicSemanticActionPrimitiveSet.WAIT_FOR_FROZEN,
    "DRAW": SymbolicSemanticActionPrimitiveSet.DRAW,
    "PIERCE": SymbolicSemanticActionPrimitiveSet.PIERCE,
    "HAMMER": SymbolicSemanticActionPrimitiveSet.HAMMER,
    "PLACE_AGAINST": SymbolicSemanticActionPrimitiveSet.PLACE_AGAINST,
    "PLACE_NEXT_TO": SymbolicSemanticActionPrimitiveSet.PLACE_NEXT_TO,
    "SWEEP": SymbolicSemanticActionPrimitiveSet.SWEEP,
    "TEAR": SymbolicSemanticActionPrimitiveSet.TEAR,
}

# ---------- EIB primitives: 20 actions ----------
_EIB_PRIMITIVES = {
    "NAVIGATE_TO": EIBSemanticActionPrimitiveSet.NAVIGATE_TO,
    "GRASP": EIBSemanticActionPrimitiveSet.GRASP,
    "RELEASE": EIBSemanticActionPrimitiveSet.RELEASE,
    "PLACE_ON_TOP": EIBSemanticActionPrimitiveSet.PLACE_ON_TOP,
    "PLACE_INSIDE": EIBSemanticActionPrimitiveSet.PLACE_INSIDE,
    "OPEN": EIBSemanticActionPrimitiveSet.OPEN,
    "CLOSE": EIBSemanticActionPrimitiveSet.CLOSE,
    "TOGGLE_ON": EIBSemanticActionPrimitiveSet.TOGGLE_ON,
    "TOGGLE_OFF": EIBSemanticActionPrimitiveSet.TOGGLE_OFF,
    "SOAK_UNDER": EIBSemanticActionPrimitiveSet.SOAK_UNDER,
    "SOAK_INSIDE": EIBSemanticActionPrimitiveSet.SOAK_INSIDE,
    "WIPE": EIBSemanticActionPrimitiveSet.WIPE,
    "CUT": EIBSemanticActionPrimitiveSet.CUT,
    "FILL_WITH": EIBSemanticActionPrimitiveSet.FILL_WITH,
    "POUR_INTO": EIBSemanticActionPrimitiveSet.POUR_INTO,
    "SPREAD": EIBSemanticActionPrimitiveSet.SPREAD,
    "WAIT": EIBSemanticActionPrimitiveSet.WAIT,
    "WAIT_FOR_COOKED": EIBSemanticActionPrimitiveSet.WAIT_FOR_COOKED,
    "WAIT_FOR_WASHED": EIBSemanticActionPrimitiveSet.WAIT_FOR_WASHED,
    "WAIT_FOR_FROZEN": EIBSemanticActionPrimitiveSet.WAIT_FOR_FROZEN,
    "DRAW": EIBSemanticActionPrimitiveSet.DRAW,
    "PIERCE": EIBSemanticActionPrimitiveSet.PIERCE,
    "HAMMER": EIBSemanticActionPrimitiveSet.HAMMER,
    "PLACE_AGAINST": EIBSemanticActionPrimitiveSet.PLACE_AGAINST,
    "PLACE_NEXT_TO": EIBSemanticActionPrimitiveSet.PLACE_NEXT_TO,
    "SWEEP": EIBSemanticActionPrimitiveSet.SWEEP,
    "TEAR": EIBSemanticActionPrimitiveSet.TEAR,
}

ACTION_PRIMITIVES = dict(_EIB_PRIMITIVES)  # default; overridden by set_primitive_mode()

# How many object arguments each primitive expects
PRIMITIVE_ARG_COUNT = {
    "GRASP": 1,
    "PLACE_ON_TOP": 1,
    "PLACE_INSIDE": 1,
    "OPEN": 1,
    "CLOSE": 1,
    "NAVIGATE_TO": 1,
    "RELEASE": 0,
    "TOGGLE_ON": 1,
    "TOGGLE_OFF": 1,
    "SOAK_UNDER": 1,
    "SOAK_INSIDE": 1,
    "WIPE": 1,
    "CUT": 1,
    "PLACE_NEAR_HEATING_ELEMENT": 1,
    "CLIMB_ON": 1,
    "CLIMB_DOWN": 0,
    "PUSH": 1,
    "PULL": 1,
    "FILL_WITH": 1,
    "POUR_INTO": 1,
    "SPREAD": 2,
    "WAIT": 0,
    "WAIT_FOR_COOKED": 1,
    "WAIT_FOR_WASHED": 1,
    "WAIT_FOR_FROZEN": 1,
    "DRAW": 2,
    "PIERCE": 2,
    "HAMMER": 2,
    "PLACE_AGAINST": 1,
    "PLACE_NEXT_TO": 1,
    "SWEEP": 1,
    "TEAR": 1,
}

_TOOL_DESCRIPTIONS_STARTER = """\
- GRASP[object_name]: Grasp an object. Robot navigates to the object and picks it up. (Requires: hand empty)
- PLACE_ON_TOP[target_object]: Place the currently held object on top of another object. (Requires: holding an object)
- PLACE_INSIDE[target_object]: Place the currently held object inside another object. (Requires: holding an object)
- OPEN[object_name]: Open an object (e.g., cabinet, fridge). (Either hand state)
- CLOSE[object_name]: Close an object. (Either hand state)
- NAVIGATE_TO[object_name]: Navigate to a furniture, appliance, or wall (e.g., countertop, fridge, table, stove, cabinet, sink, wall). Only fixed objects are valid targets — you cannot navigate to movable objects like food or tools. To reach a small object, navigate to the furniture it is on. (Either hand state)
- RELEASE[]: Release the currently held object (it will fall to the ground). (Requires: holding an object)
- TOGGLE_ON[object_name]: Toggle an object on (e.g., stove, lamp). (Either hand state)
- TOGGLE_OFF[object_name]: Toggle an object off. (Either hand state)"""

_TOOL_DESCRIPTIONS_SYMBOLIC_EXTRA = """
- SOAK_UNDER[fluid_source]: Soak the currently held object under a fluid source (e.g., faucet). (Requires: holding an object)
- SOAK_INSIDE[container]: Soak the currently held object inside the fluid within a container. (Requires: holding an object)
- WIPE[object_name]: Wipe the given object with the currently held object. (Requires: holding an object)
- CUT[object_name]: Cut (slice or dice) the given object with the currently held object. (Requires: holding an object)
- PLACE_NEAR_HEATING_ELEMENT[appliance]: Place the currently held object near a heating element (e.g., stove, oven) to cook it. (Requires: holding an object)
- CLIMB_ON[object_name]: Climb on top of an object (e.g., chair, stool) to reach higher surfaces. You can carry held objects while climbing. (Either hand state)
- CLIMB_DOWN[]: Climb down from the object you are standing on, returning to the floor. You can carry held objects while climbing down. (Either hand state)
- PUSH[object_name]: Push an object away from the robot along the floor (e.g., push a chair to a new position). (Requires: hand empty)
- PULL[object_name]: Pull an object toward the robot along the floor. (Requires: hand empty)
- FILL_WITH[fluid_source]: Fill the currently held container with fluid from a source (e.g., faucet, dispenser). (Requires: holding a container)
- POUR_INTO[target_container]: Pour fluid from the currently held container into another container. (Requires: holding a container)
- SPREAD[fluid_container, target_object]: Spread fluid from a container (e.g., butter dish) onto a target object (e.g., toast). (Requires: holding the spreading tool, e.g., knife)
- WAIT[]: Wait briefly for state changes (e.g., temperature) to settle. (Either hand state)
- WAIT_FOR_COOKED[food_object]: Wait near a heating element until the food is fully cooked. (Either hand state)
- WAIT_FOR_WASHED[laundry_object]: Wait for a washing machine to finish washing. (Either hand state)
- WAIT_FOR_FROZEN[food_object]: Wait inside or near a refrigerator until the object is fully frozen. (Either hand state)
- DRAW[ink_system, target_paper]: Draw on the target paper with the held pen/pencil. (Requires: holding a pen/pencil)
- PIERCE[target_object, piercing_tool]: Pierce an object with a tool you are holding. (Requires: holding the piercing tool)
- HAMMER[target_nail, hammer]: Strike a nail with the hammer you are holding to drive it into a surface. (Requires: holding the hammer)
- PLACE_AGAINST[surface]: Place the currently held object upright against a vertical surface (e.g. wall). (Requires: holding an object)
- PLACE_NEXT_TO[target_object]: Place the currently held object next to another object. (Requires: holding an object)
- SWEEP[target]: Sweep breadcrumbs toward the target using the held broom. Use SWEEP[floor_landing] to gather crumbs from the floor, then SWEEP[dustpan] to sweep them into the dustpan. (Requires: holding a broom or brush)
- TEAR[target_paper]: Tear the held paper along a ruler to get a clean straight line. Place a ruler on a surface and weigh it down with a heavy object before tearing. (Requires: holding the paper)"""

_ABSTAIN_DESCRIPTION = (
    "\n- ABSTAIN[reason]: Declare that this task is NOT achievable. "
    "Use this when you have sufficiently explored the environment and determined "
    "the task cannot be completed. Provide a brief reason."
)

_ASK_DESCRIPTION = (
    "\n- ASK[question]: Ask a clarifying question when the task instruction is ambiguous "
    "or missing critical information."
    "You will receive an response before your next action."
)


def set_primitive_mode(symbolic: bool = False):
    """Switch the global ACTION_PRIMITIVES.

    Args:
        symbolic: If True, use SymbolicSemanticActionPrimitiveSet (OG path).
                  If False, use EIBSemanticActionPrimitiveSet (EIB/allow-abstain path).
    """
    global ACTION_PRIMITIVES
    ACTION_PRIMITIVES.clear()
    ACTION_PRIMITIVES.update(_SYMBOLIC_PRIMITIVES if symbolic else _EIB_PRIMITIVES)


def get_tool_descriptions(
    allow_abstain: bool = False, allow_ask: bool = False, symbolic: bool = False,
) -> str:
    """Return tool descriptions, optionally including ABSTAIN and/or ASK."""
    desc = "Available actions:\n" + _TOOL_DESCRIPTIONS_STARTER
    if symbolic:
        desc += _TOOL_DESCRIPTIONS_SYMBOLIC_EXTRA
    if allow_abstain:
        desc += _ABSTAIN_DESCRIPTION
    if allow_ask:
        desc += _ASK_DESCRIPTION
    return desc + "\n"


_SINGLE_ARM_ROBOTS = {"Fetch", "Stretch"}
_DUAL_ARM_ROBOTS = {"Tiago", "R1", "R1Pro"}


# Task-specific object descriptions injected into the system prompt.
# These clarify objects whose visual appearance may mislead the LLM.
TASK_OBJECT_NOTES: dict[str, str] = {
    "hammer_nail": (
        "\nObject notes:\n"
        "- cardboard.n.01_1 is a flat, thin panel of cardboard.\n"
    ),
    "sweep_dustpan": (
        "\nEnvironment notes:\n"
        "- You are on the upper floor (2nd floor) of a house_double_floor, connected to a descending staircase.\n"
        "- floor_landing.n.01_1 is the floor area right at the top of the descending staircase (the entrance to the stairs).\n"
        "- stair_first_step.n.01_1 is the first step down on the descending staircase (one step lower than the floor level).\n"
        "\nDustpan physical constraints:\n"
        "- If you place the dustpan on the floor and sweep into it, the dustpan will slide away from the broom's force.\n"
        "- Even if you support the dustpan from behind (e.g. against a wall), the dustpan entrance lifts slightly off the ground, "
        "causing breadcrumbs to go under the dustpan instead of into it.\n"
        "- You must find a way to bypass these physical limitations.\n"
    ),
}


def build_system_prompt(
    allow_abstain: bool = False, allow_ask: bool = False, symbolic: bool = False,
    robot_type: str = "", task_name: str = "",
) -> str:
    """Build the system prompt for the LLM.

    Args:
        allow_abstain: If True, include ABSTAIN as an available action.
        allow_ask: If True, include ASK as an available action.
        symbolic: If True, include symbolic-only actions (SOAK, WIPE, CUT, etc.).
        robot_type: Robot class name (e.g. "Fetch", "Tiago") for arm-count description.
    """
    discovery_mode = allow_abstain or allow_ask

    tool_desc = get_tool_descriptions(
        allow_abstain=allow_abstain, allow_ask=allow_ask, symbolic=symbolic,
    )

    extra_rules = ""
    # Deliberately omitted: let the LLM decide to ABSTAIN/ASK from the action
    # description alone, without extra hints in the rules section.
    # if allow_abstain:
    #     extra_rules += (
    #         "- If you have explored the environment and determined the task is impossible "
    #         "respond with: Action: ABSTAIN[reason]\n"
    #     )
    # if allow_ask:
    #     extra_rules += (
    #         "- If the task instruction is ambiguous or you need more information to proceed, "
    #         "respond with: Action: ASK[your question].\n"
    #     )

    if discovery_mode:
        state_description = (
            "At each step, you will receive:\n"
            "1. The task goal (what you need to achieve)\n"
            "2. The current state — you do NOT have full knowledge of the scene. "
            "You can only see objects that you have discovered by navigating close to them.\n"
            "3. Your progress (which goal conditions are satisfied/unsatisfied)\n\n"
            "Exploration rules:\n"
            "- You start with no knowledge of which objects are in the scene.\n"
            "- As you NAVIGATE_TO objects or areas, nearby objects will be automatically discovered.\n"
            "- Newly discovered objects will be highlighted in the state description.\n"
            "- You must explore the environment to find the objects needed for your task.\n"
            "- Use NAVIGATE_TO to move to objects you have already discovered, "
            "or explore by navigating to objects visible in the discovered list.\n\n"
        )
    else:
        state_description = (
            "At each step, you will receive:\n"
            "1. The task goal (what you need to achieve)\n"
            "2. The current state (objects and their relationships)\n"
            "3. Your progress (which goal conditions are satisfied/unsatisfied)\n\n"
        )

    # Robot description based on arm configuration
    if robot_type in _SINGLE_ARM_ROBOTS:
        robot_desc = (
            f"You are a one-arm robot agent controlling a {robot_type} mobile manipulator in a household environment. "
            f"You have a single arm, so you can only hold one object at a time. "
            f"You must PLACE or RELEASE one before GRASPing the other. "
            f"You solve tasks by executing a sequence of action primitives."
        )
    elif robot_type in _DUAL_ARM_ROBOTS:
        robot_desc = (
            f"You are a robot agent controlling a {robot_type} dual-arm mobile manipulator in a household environment. "
            f"You have two arms and can hold one object in each hand. "
            f"You solve tasks by executing a sequence of action primitives."
        )
    else:
        robot_desc = (
            "You are a robot agent controlling a mobile manipulator in a household environment. "
            "You solve tasks by executing a sequence of action primitives."
        )

    return (
        f"{robot_desc}\n\n"
        f"{state_description}"
        "You must respond in the following format:\n"
        "Thought: <your reasoning about what to do next>\n"
        "Action: <ACTION_NAME>[<argument>]\n\n"
        f"{tool_desc}\n"
        "Important rules:\n"
        "- You can only hold one object at a time. RELEASE or PLACE before grasping another.\n"
        "- Use exact object names from the state description.\n"
        "- Think step-by-step about the goal conditions that are not yet satisfied.\n"
        + (
            "- To reach objects on high surfaces, CLIMB_ON a nearby chair/stool first. "
            "You can carry objects while climbing up or down. "
            "You cannot NAVIGATE_TO while standing on an object — CLIMB_DOWN first.\n"
            if symbolic else ""
        )
        + f"{extra_rules}"
        "- When all goal conditions are satisfied, respond with: Action: DONE[]\n"
        + TASK_OBJECT_NOTES.get(task_name, "")
    )


def build_step_prompt(
    goal_text: str,
    state_text: str,
    progress_text: Optional[str],
    action_history: List[str],
    error_feedback: Optional[str] = None,
    steps_remaining: Optional[int] = None,
    exploration_status: Optional[Dict] = None,
    allow_abstain: bool = False,
) -> str:
    """Build the user prompt for a single planning step.

    Args:
        goal_text: Natural language description of the goal.
        state_text: Current environment state as text.
        progress_text: Which conditions are satisfied/unsatisfied. None to omit.
        action_history: List of previous actions taken.
        error_feedback: Error message from the last failed action, if any.
        steps_remaining: Number of action steps remaining, if applicable.
        exploration_status: Optional dict with 'total_discovered' and
            'steps_since_last_discovery' for discovery mode.

    Returns:
        Formatted prompt string.
    """
    parts = []

    parts.append(f"## Task Goal\n{goal_text}")
    parts.append(f"\n## Current State\n{state_text}")
    if progress_text is not None:
        parts.append(f"\n## Progress\n{progress_text}")

    if exploration_status is not None:
        total = exploration_status["total_discovered"]
        since = exploration_status["steps_since_last_discovery"]
        lines = [
            f"Total objects discovered: {total}",
            f"Steps since last new discovery: {since}",
        ]
        parts.append(f"\n## Exploration Status\n" + "\n".join(lines))

    if action_history:
        history_str = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(action_history))
        parts.append(f"\n## Action History ({len(action_history)} steps)\n{history_str}")

    if error_feedback:
        parts.append(f"\n## Error from Last Action\n{error_feedback}")

    if steps_remaining is not None and allow_abstain:
        parts.append(f"\nSteps remaining: {steps_remaining}")

    parts.append("\nWhat is your next action?")

    return "\n".join(parts)


def format_goal_text(natural_goal_conditions: List[str]) -> str:
    """Format BDDL natural language goal conditions into a readable string."""
    if not natural_goal_conditions:
        return "No goal conditions specified."
    return "\n".join(f"- {cond}" for cond in natural_goal_conditions)


def format_state_text(
    scene_objects: Dict,
    robot_holding: Optional[str] = None,
    object_states_info: Optional[Dict] = None,
    spatial_relations: Optional[Dict] = None,
    discovery_mode: bool = False,
    discovered_objects: Optional[set] = None,
    newly_discovered: Optional[set] = None,
) -> str:
    """Format environment state into text the LLM can reason about.

    Args:
        scene_objects: Dict mapping object names to objects (from task.object_scope or scene).
        robot_holding: Name of the object the robot is currently holding, if any.
        object_states_info: Optional dict mapping object names to their state descriptions.
        spatial_relations: Optional dict mapping object names to lists of spatial relation strings.
        discovery_mode: If True, only show discovered objects instead of all scene objects.
        discovered_objects: Set of object names the robot has discovered (used in discovery_mode).
        newly_discovered: Set of object names discovered this step (used in discovery_mode).

    Returns:
        Formatted state string.
    """
    lines = []

    if robot_holding:
        lines.append(f"Robot is holding: {robot_holding}")
    else:
        lines.append("Robot is not holding anything. (one-arm)")

    if discovery_mode:
        # Discovery mode: only show objects the robot has found
        if newly_discovered:
            lines.append(f"\nNewly discovered objects (just found):")
            for obj_name in sorted(newly_discovered):
                parts = []
                if object_states_info and obj_name in object_states_info:
                    parts.append(object_states_info[obj_name])
                if spatial_relations and obj_name in spatial_relations:
                    parts.extend(spatial_relations[obj_name])
                suffix = f" ({', '.join(parts)})" if parts else ""
                lines.append(f"  - {obj_name}{suffix}")

        visible = (discovered_objects or set()) - (newly_discovered or set())
        if visible:
            lines.append(f"\nPreviously discovered objects:")
            for obj_name in sorted(visible):
                parts = []
                if object_states_info and obj_name in object_states_info:
                    parts.append(object_states_info[obj_name])
                if spatial_relations and obj_name in spatial_relations:
                    parts.extend(spatial_relations[obj_name])
                suffix = f" ({', '.join(parts)})" if parts else ""
                lines.append(f"  - {obj_name}{suffix}")

        if not (discovered_objects or newly_discovered):
            lines.append("\nNo objects discovered yet. Navigate around the room to find objects.")
    else:
        lines.append("\nObjects in the scene:")
        for obj_name in sorted(scene_objects.keys()):
            parts = []
            if object_states_info and obj_name in object_states_info:
                parts.append(object_states_info[obj_name])
            if spatial_relations and obj_name in spatial_relations:
                parts.extend(spatial_relations[obj_name])
            suffix = f" ({', '.join(parts)})" if parts else ""
            lines.append(f"  - {obj_name}{suffix}")

    return "\n".join(lines)


def format_progress_text(goal_status: dict) -> str:
    """Format goal evaluation results into text.

    Args:
        goal_status: Dict with 'satisfied' and 'unsatisfied' keys,
                     each mapping to a list of condition descriptions.
    """
    lines = []

    satisfied = goal_status.get("satisfied", [])
    unsatisfied = goal_status.get("unsatisfied", [])

    if satisfied:
        lines.append(f"Satisfied ({len(satisfied)}/{len(satisfied) + len(unsatisfied)}):")
        for cond in satisfied:
            lines.append(f"  [DONE] {cond}")

    if unsatisfied:
        lines.append(f"Unsatisfied ({len(unsatisfied)}/{len(satisfied) + len(unsatisfied)}):")
        for cond in unsatisfied:
            lines.append(f"  [TODO] {cond}")

    if not satisfied and not unsatisfied:
        lines.append("No goal conditions to track.")

    return "\n".join(lines)


def parse_llm_response(response: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Parse LLM response to extract thought and action.

    Expected format:
        Thought: <reasoning>
        Action: ACTION_NAME[argument]

    Returns:
        (thought, action_name, action_arg, error_message)
    """
    thought = None
    action_name = None
    action_arg = None
    error = None

    # Extract thought
    thought_match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\Z)", response, re.DOTALL)
    if thought_match:
        thought = thought_match.group(1).strip()

    # Extract action
    action_match = re.search(r"Action:\s*(\w+)\[([^\]]*)\]", response)
    if action_match:
        action_name = action_match.group(1).strip()
        action_arg = action_match.group(2).strip()
        if action_arg == "":
            action_arg = None
    else:
        # Try without brackets (e.g., "Action: DONE")
        action_match = re.search(r"Action:\s*(\w+)", response)
        if action_match:
            action_name = action_match.group(1).strip()
        else:
            error = "Could not parse action from response. Use format: Action: ACTION_NAME[argument]"
            return thought, None, None, error

    # Normalize action name to uppercase (LLMs may output "Abstain", "done", etc.)
    action_name = action_name.upper()

    # Validate action name — DONE, ABSTAIN, ASK are special (not in ACTION_PRIMITIVES)
    if action_name == "DONE":
        return thought, "DONE", None, None

    if action_name == "ABSTAIN":
        return thought, "ABSTAIN", action_arg, None

    if action_name == "ASK":
        return thought, "ASK", action_arg, None

    if action_name not in ACTION_PRIMITIVES:
        # Try fuzzy matching
        best_match = _find_closest_action(action_name)
        if best_match:
            error = f"Unknown action '{action_name}'. Did you mean '{best_match}'? Using '{best_match}'."
            action_name = best_match
        else:
            error = f"Unknown action '{action_name}'. Available actions: {list(ACTION_PRIMITIVES.keys())}"
            return thought, None, None, error

    # Validate argument count
    expected_args = PRIMITIVE_ARG_COUNT.get(action_name, 1)
    if expected_args > 0 and action_arg is None:
        error = f"Action '{action_name}' requires an object argument. Use: {action_name}[object_name]"
        return thought, None, None, error

    return thought, action_name, action_arg, error


def _find_closest_action(name: str) -> Optional[str]:
    """Find the closest matching action name (case-insensitive)."""
    name_upper = name.upper()
    for action in ACTION_PRIMITIVES:
        if action.upper() == name_upper:
            return action
    # Substring match
    for action in ACTION_PRIMITIVES:
        if name_upper in action.upper() or action.upper() in name_upper:
            return action
    return None


def resolve_object_name(
    name: str,
    object_scope: Dict,
) -> Optional[str]:
    """Resolve an object name from LLM output to an actual object in the scene.

    Tries exact match first, then partial/fuzzy match.

    Args:
        name: Object name from LLM output.
        object_scope: Dict mapping object names to objects.

    Returns:
        Resolved object name, or None if not found.
    """
    if name in object_scope:
        return name

    # Case-insensitive match
    name_lower = name.lower()
    for obj_name in object_scope:
        if obj_name.lower() == name_lower:
            return obj_name

    # Partial match: check if name is a substring
    matches = [obj for obj in object_scope if name_lower in obj.lower()]
    if len(matches) == 1:
        return matches[0]

    # Try matching without synset suffix (e.g., "bottle" matches "bottle.n.01_1")
    matches = [obj for obj in object_scope if name_lower in obj.lower().split(".")[0]]
    if len(matches) == 1:
        return matches[0]

    return None
