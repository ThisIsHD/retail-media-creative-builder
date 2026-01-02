from __future__ import annotations

from typing import Any, Dict, List, Optional


def compose_layers(
    *,
    layers: List[Dict[str, Any]],
    canvas: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    layers example:
      [{"type":"packshot","uri":"...","x":100,"y":200,"w":300,"h":300},
       {"type":"text","text":"...", "x":..}]
    """
    return {
        "op": "compose_layers",
        "params": {"layers": layers, "canvas": canvas, "mode": "stub"},
        "notes": "Layer composition planned (stub).",
    }
