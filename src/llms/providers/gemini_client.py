# src/llms/providers/gemini_client.py
from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional, Tuple

from google import genai


class GeminiImageClient:
    """
    Vertex AI Gemini image generation wrapper (NanoBanana / image preview model).
    Uses API key auth (VERTEX_API_KEY) and Vertex mode.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("VERTEX_API_KEY")
        if not self.api_key:
            raise ValueError("Missing VERTEX_API_KEY in environment.")

        self.project_id = project_id or os.environ.get("PROJECT_ID")
        self.location = location or os.environ.get("VERTEX_LOCATION", "us-central1")

        # Vertex mode
        self.client = genai.Client(
            api_key=self.api_key,
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )

    def generate_image(
        self,
        *,
        prompt: str,
        model: str = "gemini-3.0-generate-002",
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Returns: (image_bytes, mime_type, meta)
        Tries to parse inline image bytes from response parts.

        NOTE: Response structures can vary by model/preview.
        This parser is defensive.
        """
        resp = self.client.models.generate_content(
            model=model,
            contents=prompt,
        )

        # Defensive parsing across common genai response shapes
        # We scan all candidates -> all parts for inline_data / bytes
        candidates = getattr(resp, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data:
                    mime = getattr(inline_data, "mime_type", None) or "image/png"
                    data = getattr(inline_data, "data", None)

                    # data may be bytes or base64 str
                    if isinstance(data, (bytes, bytearray)):
                        return bytes(data), mime, {"model": model}
                    if isinstance(data, str):
                        try:
                            return base64.b64decode(data), mime, {"model": model}
                        except Exception:
                            pass

                # Some previews return `data` directly on the part
                data = getattr(part, "data", None)
                if isinstance(data, (bytes, bytearray)):
                    mime = getattr(part, "mime_type", None) or "image/png"
                    return bytes(data), mime, {"model": model}

        # If we reach here, no image bytes were found
        raise RuntimeError("Gemini response did not include inline image bytes. Check model/response format.")
