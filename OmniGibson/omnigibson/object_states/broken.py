import torch as th

from omnigibson.object_states.object_state_base import AbsoluteObjectState, BooleanStateMixin


class Broken(AbsoluteObjectState, BooleanStateMixin):
    """
    A simple boolean state indicating whether an object is broken.

    Broken objects cannot be toggled on (enforced by ToggledOn._set_value).
    This state is purely symbolic — it has no physics-based trigger and must
    be set explicitly via ``obj.states[Broken].set_value(True)`` or through
    a BDDL ``:init`` condition.
    """

    def __init__(self, obj):
        super(Broken, self).__init__(obj)
        self.value = False

    def _get_value(self):
        return self.value

    def _set_value(self, new_value):
        self.value = bool(new_value)
        return True

    @staticmethod
    def get_texture_change_params():
        # Slight red tint to visually indicate damage
        albedo_add = 0.0
        diffuse_tint = th.tensor([1.0, 0.6, 0.6])
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
