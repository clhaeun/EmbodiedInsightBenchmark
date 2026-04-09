"""OpenAI LLM backend via official openai SDK (API key auth).

Requires:
  - pip install openai
  - Environment variable: OPENAI_API_KEY
"""

import base64
import os
import time
from typing import Dict, List, Optional

from openai import OpenAI

from omnigibson.llm_agent.llm.base_llm import BaseLLM, Prompt

# Per-model defaults
# use_mct: True = must use max_completion_tokens instead of max_tokens
_MODEL_CONFIG = {
    "default": {"temperature": 0, "max_tokens": 16384},
    "models": {
        "gpt-4o":        {"temperature": 0, "max_tokens": 16384},
        "gpt-4o-mini":   {"temperature": 0, "max_tokens": 16384},
        "gpt-4.1":       {"temperature": 0, "max_tokens": 32768},
        "gpt-4.1-mini":  {"temperature": 0, "max_tokens": 32768},
        "gpt-4.1-nano":  {"temperature": 0, "max_tokens": 32768},
        "gpt-5":         {"temperature": 0, "max_tokens": 65536, "use_mct": True},
        "gpt-5-mini":    {"temperature": 0, "max_tokens": 65536, "use_mct": True},
        "gpt-5-nano":    {"temperature": 0, "max_tokens": 32768, "use_mct": True},
        "gpt-5.4":       {"temperature": 0, "max_tokens": 65536, "use_mct": True},
        "gpt-5.4-mini":  {"temperature": 0, "max_tokens": 65536, "use_mct": True},
        "gpt-5.4-nano":  {"temperature": 0, "max_tokens": 32768, "use_mct": True},
        "o1":            {"temperature": None, "max_tokens": 65536, "use_mct": True},
        "o3":            {"temperature": None, "max_tokens": 65536, "use_mct": True},
        "o3-mini":       {"temperature": None, "max_tokens": 65536, "use_mct": True},
        "o4-mini":       {"temperature": None, "max_tokens": 65536, "use_mct": True},
    },
}


class OpenAIChat(BaseLLM):
    def __init__(self, config: dict):
        super().__init__(config)
        self.message_history: List[Dict] = []
        self.keep_history = config.get("keep_message_history", False)
        self.system_message = config.get("system_message", "You are a helpful assistant.")
        self.verbose = config.get("verbose", False)

        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        # Clear stale Azure env vars so OpenAI SDK doesn't pick them up
        for var in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "AZURE_API_KEY", "AZURE_API_BASE"):
            os.environ.pop(var, None)

        self.client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")

    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: Prompt,
        stop: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        params = dict(self.generation_params)
        if stop is None:
            stop = params.pop("stop", None)
        else:
            params.pop("stop", None)

        model_name = params.pop("model", "gpt-4o")

        # Block models that don't support chat completions API
        if model_name not in _MODEL_CONFIG["models"]:
            raise ValueError(
                f"Model '{model_name}' is not supported. "
                f"Available: {sorted(_MODEL_CONFIG['models'].keys())}"
            )

        # Per-model config
        defaults = _MODEL_CONFIG["default"]
        model_cfg = _MODEL_CONFIG["models"][model_name]
        temperature = model_cfg.get("temperature", defaults["temperature"])
        max_tok = max_tokens or model_cfg.get("max_tokens", defaults["max_tokens"])

        # Build messages
        messages = self.message_history.copy()
        if not messages:
            messages.append({"role": "system", "content": self.system_message})

        if isinstance(prompt, str):
            messages.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list):
            for item in prompt:
                if len(item) >= 3 and item[2]:
                    role, text, image_path = item[0], item[1], item[2]
                    content_parts = [{"type": "text", "text": text}]
                    content_parts.append(self._make_image_part(image_path))
                    messages.append({"role": role, "content": content_parts})
                else:
                    role, text = item[0], item[1]
                    messages.append({"role": role, "content": text})

        # Build kwargs — GPT-5+ and o-series require max_completion_tokens
        use_mct = model_cfg.get("use_mct", False)
        tok_key = "max_completion_tokens" if use_mct else "max_tokens"
        kwargs: dict = {"model": model_name, "messages": messages, tok_key: max_tok}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if stop is not None:
            kwargs["stop"] = stop

        # Call with retry
        text = ""
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(**kwargs)
                text = response.choices[0].message.content or ""
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"[OpenAIChat] Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)

        if self.verbose:
            print(f"[OpenAIChat] Response: {text[:200]}...")

        if self.keep_history:
            self.message_history = messages.copy()
            self.message_history.append({"role": "assistant", "content": text})

        if stop and text:
            text = text.split(stop)[0]

        return text

    # ------------------------------------------------------------------
    @staticmethod
    def _make_image_part(image_path: str) -> dict:
        """Encode a local image file as an OpenAI vision image_url part."""
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(image_path)[1].lstrip(".").lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
        }

    # ------------------------------------------------------------------
    def reset(self):
        self.message_history = []
