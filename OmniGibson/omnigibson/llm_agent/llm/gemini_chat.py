"""Google Gemini LLM backend via google-genai SDK (API key auth).

Requires:
  - pip install google-genai
  - Environment variable: GEMINI_API_KEY
"""

import base64
import os
import time
from typing import Dict, List, Optional

from google import genai
from google.genai import types

from omnigibson.llm_agent.llm.base_llm import BaseLLM, Prompt

# Per-model defaults
_MODEL_CONFIG = {
    "default": {"temperature": 0, "max_output_tokens": 8192},
    "models": {
        "gemini-2.5-pro":                {"temperature": 0, "max_output_tokens": 65535},
        "gemini-2.5-flash":              {"temperature": 0, "max_output_tokens": 65535},
        "gemini-2.5-flash-lite":         {"temperature": 0, "max_output_tokens": 65535},
        "gemini-3-flash-preview":        {"temperature": 0, "max_output_tokens": 65535},
        "gemini-3-pro-preview":          {"temperature": 0, "max_output_tokens": 65535},
        "gemini-3.1-pro-preview":        {"temperature": 0, "max_output_tokens": 65535},
        "gemini-3.1-flash-lite-preview": {"temperature": 0, "max_output_tokens": 65535},
    },
}


class GeminiChat(BaseLLM):
    def __init__(self, config: dict):
        super().__init__(config)
        self.message_history: list = []
        self.keep_history = config.get("keep_message_history", False)
        self.system_message = config.get("system_message", "You are a helpful assistant.")
        self.verbose = config.get("verbose", False)

        api_key = config.get("api_key") or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=api_key)

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

        model_name = params.pop("model", "gemini-2.0-flash")

        # Per-model config
        defaults = _MODEL_CONFIG["default"]
        model_cfg = _MODEL_CONFIG["models"].get(model_name, {})
        temperature = model_cfg.get("temperature", defaults["temperature"])
        max_tok = max_tokens or model_cfg.get("max_output_tokens", defaults["max_output_tokens"])

        # Build generation config
        gen_config = types.GenerateContentConfig(
            max_output_tokens=max_tok,
            temperature=temperature,
            stop_sequences=[stop] if isinstance(stop, str) and stop else stop or None,
        )

        # Extract system instruction and build contents
        system_instruction, contents = self._build_contents(prompt)
        if system_instruction:
            gen_config.system_instruction = system_instruction

        # Prepend history if kept
        if self.keep_history and self.message_history:
            contents = self.message_history + contents

        # Call with retry
        text = ""
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=gen_config,
                )
                text = response.text or ""
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"[GeminiChat] Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)

        if self.verbose:
            print(f"[GeminiChat] Response: {text[:200]}...")

        # Update history
        if self.keep_history:
            self.message_history = list(contents)
            self.message_history.append(
                types.Content(role="model", parts=[types.Part.from_text(text=text)])
            )

        if stop and text:
            text = text.split(stop)[0]

        return text

    # ------------------------------------------------------------------
    def _build_contents(self, prompt: Prompt):
        """Convert prompt to google-genai Content list.

        Returns (system_instruction, contents).
        """
        if isinstance(prompt, str):
            return None, [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

        system_instruction = None
        contents: list = []

        for item in prompt:
            role = item[0]
            text = item[1]
            image_path = item[2] if len(item) >= 3 and item[2] else None

            if role == "system":
                system_instruction = text
                continue

            gemini_role = "model" if role == "assistant" else "user"
            parts: list = [types.Part.from_text(text=text)]

            if image_path:
                if image_path.startswith("http://") or image_path.startswith("https://"):
                    # YouTube / web URL
                    parts.append(types.Part.from_uri(file_uri=image_path, mime_type="video/mp4"))
                elif os.path.exists(image_path):
                    with open(image_path, "rb") as f:
                        data = f.read()
                    ext = os.path.splitext(image_path)[1].lstrip(".").lower()
                    mime = {
                        "png": "image/png",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "mp4": "video/mp4",
                        "webm": "video/webm",
                    }.get(ext, "image/png")
                    parts.append(types.Part.from_bytes(data=data, mime_type=mime))

            contents.append(types.Content(role=gemini_role, parts=parts))

        return system_instruction, contents

    # ------------------------------------------------------------------
    def reset(self):
        self.message_history = []
