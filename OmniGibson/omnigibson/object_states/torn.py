import torch as th

from omnigibson.object_states.object_state_base import AbsoluteObjectState, BooleanStateMixin


class Torn(AbsoluteObjectState, BooleanStateMixin):
    """
    A simple boolean state indicating whether an object has been torn.

    This state is purely symbolic — it has no physics-based trigger and must
    be set explicitly via ``obj.states[Torn].set_value(True)`` or through
    a BDDL ``:init`` condition.
    """

    def __init__(self, obj):
        super(Torn, self).__init__(obj)
        self.value = False

    def _get_value(self):
        return self.value

    def _set_value(self, new_value):
        self.value = bool(new_value)
        return True

    @staticmethod
    def get_texture_change_params():
        # Slight yellow-brown tint to visually indicate tearing damage
        albedo_add = 0.0
        diffuse_tint = th.tensor([1.0, 0.9, 0.7])
        return albedo_add, diffuse_tint

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
