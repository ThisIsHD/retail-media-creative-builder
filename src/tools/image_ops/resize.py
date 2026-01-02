from __future__ import annotations

from typing import Any, Dict


def resize(*, target: str) -> Dict[str, Any]:
    """
    target like: "1080x1080", "1080x1920", "1200x628"
    """
    return {
        "op": "resize",
        "params": {"target": target, "mode": "stub"},
        "notes": f"Resize planned to {target} (stub).",
    }
