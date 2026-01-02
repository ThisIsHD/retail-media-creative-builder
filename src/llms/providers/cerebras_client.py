from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from cerebras.cloud.sdk import Cerebras


class CerebrasLLM:
    """
    Wrapper around Cerebras Cloud SDK.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("CEREBRAS_API_KEY")
        self.client = Cerebras(api_key=self.api_key)

    def chat(
        self,
        *,
        model: str = "llama3.1-8b",
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        max_completion_tokens: int = 8192,
        top_p: float = 1.0,
        stream: bool = False,
    ) -> str:
        """
        Non-streaming chat completion.
        """
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            top_p=top_p,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    def chat_stream(
        self,
        *,
        model: str = "llama3.1-8b",
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        max_completion_tokens: int = 8192,
        top_p: float = 1.0,
    ):
        """
        Streaming chat completion - returns generator.
        """
        stream = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            top_p=top_p,
            stream=True,
        )
        for chunk in stream:
            yield chunk.choices[0].delta.content or ""

