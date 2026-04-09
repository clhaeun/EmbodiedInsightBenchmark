"""CATS task configurations.

Each task module exports a TASK_CONFIG dict consumed by CATSPlanner.
"""

from omnigibson.llm_agent.cats_tasks.retrieve_egg_from_gap import TASK_CONFIG as retrieve_egg_from_gap
from omnigibson.llm_agent.cats_tasks.micro_glass_shard_pickup import TASK_CONFIG as micro_glass_shard_pickup
from omnigibson.llm_agent.cats_tasks.slatted_grill_cleaning import TASK_CONFIG as slatted_grill_cleaning
from omnigibson.llm_agent.cats_tasks.container_opening_push_turn import TASK_CONFIG as container_opening_push_turn
from omnigibson.llm_agent.cats_tasks.tilt_to_release_bench import TASK_CONFIG as tilt_to_release_bench
from omnigibson.llm_agent.cats_tasks.rotate_knob_drawer import TASK_CONFIG as rotate_knob_drawer
from omnigibson.llm_agent.cats_tasks.tilt_and_turn_window import TASK_CONFIG as tilt_and_turn_window

CATS_TASK_REGISTRY = {
    "retrieve_egg_from_gap": retrieve_egg_from_gap,
    "micro_glass_shard_pickup": micro_glass_shard_pickup,
    "slatted_grill_cleaning": slatted_grill_cleaning,
    "container_opening_push_turn": container_opening_push_turn,
    "tilt_to_release_bench": tilt_to_release_bench,
    "rotate_knob_drawer": rotate_knob_drawer,
    "tilt_and_turn_window": tilt_and_turn_window,
}
