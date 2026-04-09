import torch as th

from omnigibson.object_states.object_state_base import AbsoluteObjectState, BooleanStateMixin


class Nailed(AbsoluteObjectState, BooleanStateMixin):
    """
    A simple boolean state indicating whether a nail has been driven into
    a surface (e.g., hammered into a wall through a fixture chain).

    This state is purely symbolic -- it has no physics-based trigger and must
    be set explicitly via the HAMMER action primitive when all preconditions
    are met (nail pierced through holder, holder placed against wall and
    constrained by heavy objects).
    """

    def __init__(self, obj):
        super(Nailed, self).__init__(obj)
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
