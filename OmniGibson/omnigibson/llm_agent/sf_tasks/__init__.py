"""SF (Scenario Flexibility) task configurations.

Each task module exports an SF_TASK_CONFIG dict consumed by SFPlanner.
"""

from omnigibson.llm_agent.sf_tasks.cake_completion import SF_TASK_CONFIG as cake_completion

SF_TASK_REGISTRY = {
    "cake_completion": cake_completion,
}
