from omnigibson.llm_agent.llm.base_llm import BaseLLM


def create_llm(config: dict) -> BaseLLM:
    """Factory function to create an LLM backend from a config dict.

    Args:
        config: dict with keys:
            - type: one of "openai", "gemini", "local", "mock"
            - (other keys passed to the backend constructor)

    Returns:
        BaseLLM instance
    """
    llm_type = config.get("type", "openai")

    if llm_type == "openai":
        from omnigibson.llm_agent.llm.openai_chat import OpenAIChat
        return OpenAIChat(config)
    elif llm_type == "gemini":
        from omnigibson.llm_agent.llm.gemini_chat import GeminiChat
        return GeminiChat(config)
    elif llm_type == "local":
        from omnigibson.llm_agent.llm.local_llm import LocalLLM
        return LocalLLM(config)
    elif llm_type == "mock":
        from omnigibson.llm_agent.llm.mock_llm import MockLLM
        return MockLLM(config)
    else:
        raise ValueError(f"Unknown LLM type: {llm_type}. Choose from ['openai', 'gemini', 'local', 'mock']")
