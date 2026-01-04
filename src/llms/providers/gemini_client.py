# src/llms/providers/gemini_client.py
from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import types


class GeminiImageClient:
    """
    Gemini 3 Pro Image generation wrapper for Vertex AI.
    Uses Vertex AI with API key authentication (as per Gemini 3 Pro Image docs).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("VERTEX_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_CLOUD_API_KEY")
        self.project_id = project_id or os.getenv("PROJECT_ID")
        self.location = location or os.getenv("VERTEX_LOCATION", "us-central1")
        # Default to gemini-3-pro-image-preview as per documentation
        self.default_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")

        # Initialize client - per docs, can use vertexai=True with api_key
        if self.api_key and self.project_id:
            # Vertex AI with API key (as shown in sample code)
            self.client = genai.Client(
                vertexai=True,
                api_key=self.api_key,
            )
        elif self.api_key:
            # Gemini API directly (fallback)
            self.client = genai.Client(api_key=self.api_key)
        elif self.project_id:
            # Vertex AI with Application Default Credentials
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )
        else:
            raise RuntimeError(
                "Either VERTEX_API_KEY/GEMINI_API_KEY (for Vertex AI with API key) or PROJECT_ID (for Vertex AI with ADC) must be set"
            )

    def _format_to_aspect_ratio(self, fmt: str) -> str:
        """Convert format string to aspect ratio for image_config."""
        # Map common formats to aspect ratios
        fmt_map = {
            "1080x1080": "1:1",
            "1080x1920": "9:16",  # Story/vertical
            "1920x1080": "16:9",  # Landscape
            "1200x628": "16:9",   # Facebook feed
        }
        return fmt_map.get(fmt, "1:1")  # Default to square
    
    def _format_to_image_size(self, fmt: str) -> str:
        """Convert format to image size hint."""
        # For 1080px width/height, use 1K; for larger, use 2K
        if "1080" in fmt:
            return "1K"
        elif "1920" in fmt or "1200" in fmt:
            return "2K"
        return "1K"  # Default

    def generate_image(
        self,
        *,
        prompt: str,
        model: Optional[str] = None,
        format_hint: Optional[str] = None,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Generate image using Gemini 3 Pro Image model.
        Returns: (image_bytes, mime_type, meta)
        
        Uses proper GenerateContentConfig with response_modalities=["TEXT", "IMAGE"]
        and image_config as per Gemini 3 Pro Image documentation.
        """
        model = model or self.default_model
        
        # Determine aspect ratio and image size from format
        aspect_ratio = self._format_to_aspect_ratio(format_hint) if format_hint else "1:1"
        image_size = self._format_to_image_size(format_hint) if format_hint else "1K"
        
        # Build config as per documentation
        config = types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],  # Critical for image generation
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_NONE"
                ),
            ],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                output_mime_type="image/png",
            ),
        )
        
        # Pass prompt as string (SDK will convert to Content internally)
        resp = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
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
    
    def generate_image_bytes(
        self,
        *,
        prompt: str,
        format_hint: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Tuple[str, bytes]:
        """
        Convenience wrapper that returns (mime_type, image_bytes) for compatibility.
        format_hint is used to determine aspect ratio and image size.
        """
        img_bytes, mime, meta = self.generate_image(
            prompt=prompt, 
            model=model,
            format_hint=format_hint
        )
        return mime, img_bytes
