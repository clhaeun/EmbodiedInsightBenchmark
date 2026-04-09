import torch as th

from omnigibson.object_states.object_state_base import AbsoluteObjectState, BooleanStateMixin


class High(AbsoluteObjectState, BooleanStateMixin):
    """
    A boolean state indicating whether a surface/container is too high
    for the robot to reach from the floor.

    When an object is on top of or inside a High surface, the robot must
    first CLIMB_ON something to reach it. This is enforced at the action
    primitive level (SymbolicSemanticActionPrimitives._grasp).

    Usage:
        shelf.states[High].set_value(True)
    """

    def __init__(self, obj):
        super(High, self).__init__(obj)
        self.value = False

    def _get_value(self):
        return self.value

    def _set_value(self, new_value):
        self.value = bool(new_value)
        return True

    @property
    def state_size(self):
        return 1

    def _dump_state(self):
        return dict(value=self.value)

    def _load_state(self, state):
        self.value = state["value"]

    def serialize(self, state):
        return th.tensor([float(state["value"])], dtype=th.float32)

    def deserialize(self, state):
        return dict(value=bool(state[0])), 1
