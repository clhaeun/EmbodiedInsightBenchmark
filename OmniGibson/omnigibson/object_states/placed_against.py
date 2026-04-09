import torch as th

from omnigibson.object_states.object_state_base import RelativeObjectState, BooleanStateMixin


class PlacedAgainst(RelativeObjectState, BooleanStateMixin):
    """
    A boolean state indicating whether an object is placed upright against
    another object or surface (e.g., cardboard stood against a wall).

    This state is purely symbolic -- it has no physics-based trigger and must
    be set explicitly via the PLACE_AGAINST action primitive.

    Unlike NextTo (which implies side-by-side on the same surface),
    PlacedAgainst implies the object is leaning/standing against a vertical
    surface.

    Tracks constrained_sides for future directional constraint support.
    Currently only the count is used (>= 3 means fully constrained).
    """

    def __init__(self, obj):
        super(PlacedAgainst, self).__init__(obj)
        self._values = {}  # other_obj -> bool
        # Track which sides are constrained by heavy objects.
        # Keys: direction strings ("left", "right", "front", etc.)
        # Values: the constraining object
        # Currently we only check len() >= 3; direction keys are reserved
        # for future use.
        self.constrained_sides = {}

    def _get_value(self, other):
        return self._values.get(other, False)

    def _set_value(self, other, new_value):
        self._values[other] = bool(new_value)
        return True

    def add_constraint(self, heavy_obj, direction=None):
        """Register a heavy object as constraining this object.

        Args:
            heavy_obj: The heavy object providing constraint.
            direction: Optional direction string ("left", "right", "front").
                       If None, an auto-generated key is used.
        """
        if direction is None:
            direction = f"side_{len(self.constrained_sides)}"
        self.constrained_sides[direction] = heavy_obj

    @property
    def constraint_count(self):
        return len(self.constrained_sides)

    @property
    def is_fully_constrained(self):
        return self.constraint_count >= 3

    @property
    def state_size(self):
        # We only serialize the boolean values, not constraint tracking
        return 0

    def _dump_state(self):
        return dict()

    def _load_state(self, state):
        pass

    def serialize(self, state):
        return th.tensor([], dtype=th.float32)

    def deserialize(self, state):
        return dict(), 0
