from typing import List, Optional, Tuple, Union

# Each message is (role, content) where content is a string,
# or (role, content, image_path) to attach an image to that message.
Message = Union[Tuple[str, str], Tuple[str, str, Optional[str]]]
Prompt = Union[str, List[Message]]


class BaseLLM:
    """Abstract base class for all LLM backends."""

    def __init__(self, config: dict):
        self.config = config
        self.generation_params = config.get("generation_params", {})

    def generate(
        self,
        prompt: Prompt,
        stop: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: Input text or list of (role, content) message tuples.
            stop: Stop sequence to halt generation.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            Generated text string.
        """
        raise NotImplementedError

    def reset(self):
        """Reset any conversation history."""
        pass
