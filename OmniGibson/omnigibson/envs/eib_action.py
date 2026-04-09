from omnigibson.action_primitives.action_primitive_set_base import (
    ActionPrimitiveError,
    ActionPrimitiveErrorGroup,
)

from omnigibson.envs.common.eib_matching import fuzzy_match
from omnigibson.action_primitives.eib_semantic_action_primitives import EIBSemanticActionPrimitiveSet


class ActionMixin:

    PRIMITIVE_MAP = {
        # 0-target
        "release":          EIBSemanticActionPrimitiveSet.RELEASE,
        # 1-target
        "navigate":         EIBSemanticActionPrimitiveSet.NAVIGATE_TO,
        "grasp":            EIBSemanticActionPrimitiveSet.GRASP,
        "open":             EIBSemanticActionPrimitiveSet.OPEN,
        "close":            EIBSemanticActionPrimitiveSet.CLOSE,
        "toggle_on":        EIBSemanticActionPrimitiveSet.TOGGLE_ON,
        "toggle_off":       EIBSemanticActionPrimitiveSet.TOGGLE_OFF,
        "wait":             EIBSemanticActionPrimitiveSet.WAIT,
        "wait_for_cooked":  EIBSemanticActionPrimitiveSet.WAIT_FOR_COOKED,
        "wait_for_washed":  EIBSemanticActionPrimitiveSet.WAIT_FOR_WASHED,
        # 2-target
        "place_on_top":     EIBSemanticActionPrimitiveSet.PLACE_ON_TOP,
        "place_inside":     EIBSemanticActionPrimitiveSet.PLACE_INSIDE,
        "wipe":             EIBSemanticActionPrimitiveSet.WIPE,
        "cut":              EIBSemanticActionPrimitiveSet.CUT,
        "soak_under":       EIBSemanticActionPrimitiveSet.SOAK_UNDER,
        "soak_inside":      EIBSemanticActionPrimitiveSet.SOAK_INSIDE,
        "fill_with":        EIBSemanticActionPrimitiveSet.FILL_WITH,
        "pour_into":        EIBSemanticActionPrimitiveSet.POUR_INTO,
        "spread":           EIBSemanticActionPrimitiveSet.SPREAD,
        "wait_for_frozen":  EIBSemanticActionPrimitiveSet.WAIT_FOR_FROZEN,
        "draw":             EIBSemanticActionPrimitiveSet.DRAW,
        "pierce":           EIBSemanticActionPrimitiveSet.PIERCE,
        "hammer":           EIBSemanticActionPrimitiveSet.HAMMER,
        "place_against":    EIBSemanticActionPrimitiveSet.PLACE_AGAINST,
        "place_next_to":    EIBSemanticActionPrimitiveSet.PLACE_NEXT_TO,
        "sweep":            EIBSemanticActionPrimitiveSet.SWEEP,
        "tear":             EIBSemanticActionPrimitiveSet.TEAR,
    }

    TERMINAL_ACTIONS = {"terminate", "abstain"}
    NO_TARGET_ACTIONS = {"release"}
    TWO_TARGET_ACTIONS = {
        "place_on_top", "place_inside",
        "wipe", "cut",
        "soak_under", "soak_inside",
        "fill_with", "pour_into",
        "spread", "wait_for_frozen",
        "draw",
        "pierce",
        "hammer",
    }

    def execute_action(self, action, target=None, target2=None):
        if action in self.TERMINAL_ACTIONS:
            return {"success": True, "terminal": action, "feedback": f"Agent called {action}."}

        return self._execute_primitive(action, target, target2)

    def _execute_primitive(self, primitive_type, target_name, target2_name=None):
        if primitive_type not in self.PRIMITIVE_MAP:
            return {"success": False, "terminal": None, "feedback": f"Unknown action '{primitive_type}'. Available: {list(self.PRIMITIVE_MAP.keys())}"}

        primitive_enum = self.PRIMITIVE_MAP[primitive_type]

        # 0-arg actions (e.g. release)
        if primitive_type in self.NO_TARGET_ACTIONS:
            return self._run_primitive(primitive_enum, primitive_type)

        # Resolve first target
        target_obj = self._object_registry.get(target_name)
        if target_obj is None:
            return {"success": False, "terminal": None, "feedback": self._not_found_msg(target_name)}

        # 2-arg actions
        if primitive_type in self.TWO_TARGET_ACTIONS:
            if target2_name is None:
                return {"success": False, "terminal": None, "feedback": f"Action '{primitive_type}' requires two targets. Provide target2."}
            target2_obj = self._object_registry.get(target2_name)
            if target2_obj is None:
                return {"success": False, "terminal": None, "feedback": self._not_found_msg(target2_name)}
            return self._run_primitive(primitive_enum, primitive_type, target_obj, target2_obj,
                                      label=f"{target_name}, {target2_name}")

        # 1-arg actions
        return self._run_primitive(primitive_enum, primitive_type, target_obj, label=target_name)

    def _run_primitive(self, primitive_enum, primitive_type, *args, label=""):
        try:
            ctrl_gen = self.primitives.apply_ref(primitive_enum, *args)
            for action in ctrl_gen:
                self.env.step(action)
            # Check for custom feedback set by the primitive (e.g. _draw)
            custom = getattr(self.primitives, '_custom_success_feedback', None)
            if custom:
                self.primitives._custom_success_feedback = None
                return {"success": True, "terminal": None, "feedback": custom}
            msg = f"Successfully executed {primitive_type}"
            if label:
                msg += f" on {label}"
            return {"success": True, "terminal": None, "feedback": f"{msg}."}
        except (ActionPrimitiveError, ActionPrimitiveErrorGroup, NotImplementedError) as e:
            feedback = str(e).split(". Additional info:")[0] + "."
            return {"success": False, "terminal": None, "feedback": feedback}

    def _not_found_msg(self, name):
        """Build 'not found' message with a close-match hint if possible."""
        match = fuzzy_match(name, self._object_registry.keys())
        if match:
            return f"Cannot find '{name}'. The correct name is '{match}'."
        return f"Cannot find '{name}'."
