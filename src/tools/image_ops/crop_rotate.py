from __future__ import annotations

from typing import Any, Dict, Optional


def crop_rotate(
    *,
    crop: Optional[Dict[str, int]] = None,
    rotate_deg: float = 0.0,
) -> Dict[str, Any]:
    """
    crop example: {"x": 0, "y": 0, "w": 800, "h": 800}
    """
    return {
        "op": "crop_rotate",
        "params": {"crop": crop, "rotate_deg": rotate_deg, "mode": "stub"},
        "notes": "Crop/rotate planned (stub).",
    }
