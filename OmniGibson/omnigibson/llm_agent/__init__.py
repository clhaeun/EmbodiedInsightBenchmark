def __getattr__(name):
    if name == "OmniGibsonLLMPlanner":
        from omnigibson.llm_agent.planner import OmniGibsonLLMPlanner
        return OmniGibsonLLMPlanner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
