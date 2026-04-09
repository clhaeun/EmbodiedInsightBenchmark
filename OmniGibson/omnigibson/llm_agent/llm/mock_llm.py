"""Mock LLM for testing the pipeline without API calls."""

from typing import List, Optional

from omnigibson.llm_agent.llm.base_llm import BaseLLM, Prompt


class MockLLM(BaseLLM):
    """Returns predefined responses in sequence. Useful for testing."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.responses: List[str] = config.get("responses", [
            "Thought: I need to look around first.\nAction: NAVIGATE_TO[table]",
        ])
        self._index = 0

    def generate(
        self,
        prompt: Prompt,
        stop: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        response = self.responses[self._index % len(self.responses)]
        self._index += 1
        return response

    def reset(self):
        self._index = 0
