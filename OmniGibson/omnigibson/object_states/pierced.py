import torch as th

from omnigibson.object_states.object_state_base import AbsoluteObjectState, BooleanStateMixin


class Pierced(AbsoluteObjectState, BooleanStateMixin):
    """
    A simple boolean state indicating whether an object has been pierced
    through another object (e.g., a nail pierced through cardboard).

    This state is purely symbolic -- it has no physics-based trigger and must
    be set explicitly via the PIERCE action primitive.
    """

    def __init__(self, obj):
        super(Pierced, self).__init__(obj)
        self.value = False
        # Track which object this was pierced through (for precondition checks)
        self.pierced_through = None

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
