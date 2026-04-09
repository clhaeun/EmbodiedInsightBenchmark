"""Local LLM backend using vLLM's OpenAI-compatible server.

Usage:
  1. Start vLLM server:
     python -m vllm.entrypoints.openai.api_server \
       --model ~/models/qwen2.5-14b-instruct --port 8000

  2. Configure:
     config = {
       "type": "local",
       "generation_params": {
         "model": "qwen2.5-14b-instruct",
         "api_base": "http://localhost:8000/v1",
         "api_key": "dummy",
         ...
       }
     }

This backend uses the OpenAI client to talk to a vLLM server,
so it works with any model served by vLLM.
"""

from typing import Dict, List, Optional

from openai import OpenAI

from omnigibson.llm_agent.llm.base_llm import BaseLLM, Prompt


class LocalLLM(BaseLLM):
    def __init__(self, config: dict):
        super().__init__(config)
        params = self.generation_params
        self.client = OpenAI(
            base_url=params.get("api_base", "http://localhost:8000/v1"),
            api_key=params.get("api_key", "dummy"),
        )
        self.model_name = params.get("model", "default")
        self.message_history: List[Dict] = []
        self.keep_history = config.get("keep_message_history", False)
        self.system_message = config.get("system_message", "You are a helpful assistant.")
        self.verbose = config.get("verbose", False)

    def generate(
        self,
        prompt: Prompt,
        stop: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        params = dict(self.generation_params)

        if stop is None:
            stop = params.get("stop")
        if max_tokens is None:
            max_tokens = params.get("max_tokens", 1024)

        messages = self.message_history.copy()
        if not messages:
            messages.append({"role": "system", "content": self.system_message})

        if isinstance(prompt, str):
            messages.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list):
            for item in prompt:
                if len(item) >= 3 and item[2]:
                    role, text, image_path = item[0], item[1], item[2]
                    # Local vLLM may not support vision; pass text only as fallback
                    messages.append({"role": role, "content": text})
                else:
                    role, text = item[0], item[1]
                    messages.append({"role": role, "content": text})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=params.get("temperature", 0),
            top_p=params.get("top_p", 1),
            stop=stop,
        )
        text = response.choices[0].message.content

        if self.keep_history:
            self.message_history = messages.copy()
            self.message_history.append({"role": "assistant", "content": text})

        if stop and text:
            text = text.split(stop)[0]

        if self.verbose:
            print(f"[LocalLLM] Response: {text[:200]}...")

        return text

    def reset(self):
        self.message_history = []
