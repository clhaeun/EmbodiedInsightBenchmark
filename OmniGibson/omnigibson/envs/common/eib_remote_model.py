"""Azure OpenAI VLM wrapper with vision support — uses httpx to avoid SDK serialization issues."""

import base64
import json
import os

import httpx


class RemoteVLM:
    """Wrapper for Azure OpenAI vision-language models."""

    def __init__(self, model="gpt-4.1", temperature=0.0, max_tokens=1024):
        base_url = os.environ.get("OPENAI_BASE_URL", "https://wk-ma0.openai.azure.com")
        # Strip path suffix if present (e.g. /openai/v1/)
        self.endpoint = base_url.split("/openai/")[0] if "/openai/" in base_url else base_url.rstrip("/")
        self.api_key = os.environ["OPENAI_API_KEY"]
        self.api_version = "2024-08-01-preview"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def query(self, system_prompt, user_prompt, image_path=None):
        """Send a query to the VLM with optional image.

        Args:
            system_prompt: System message string.
            user_prompt: User message string.
            image_path: Optional path to a PNG image file.

        Returns:
            Raw response text from the model.
        """
        messages = [{"role": "system", "content": system_prompt}]

        if image_path:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            user_content = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"},
                },
                {"type": "text", "text": user_prompt},
            ]
        else:
            user_content = user_prompt

        messages.append({"role": "user", "content": user_content})

        url = (
            f"{self.endpoint}/openai/deployments/{self.model}"
            f"/chat/completions?api-version={self.api_version}"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }
        payload = {
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
