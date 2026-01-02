from __future__ import annotations

from typing import Any, Dict


def remove_bg(*, packshot_uri: str) -> Dict[str, Any]:
    """
    Deterministic stub. Later you can plug:
    - Vertex/Gemini image editing
    - rembg / U2Net
    - Segment Anything (SAM)
    """
    return {
        "op": "remove_bg",
        "params": {"packshot_uri": packshot_uri, "mode": "stub"},
        "notes": "Background removal planned (stub).",
    }
