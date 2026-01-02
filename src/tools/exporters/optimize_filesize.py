from __future__ import annotations
from typing import Any, Dict, Optional


def optimize_filesize_plan(
    *,
    current_bytes: int,
    target_bytes: int,
    mime: str = "image/jpeg",
    fmt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a plan to optimize file size (stub implementation).
    Returns a dict with optimization strategy.
    """
    reduction_needed = current_bytes - target_bytes
    reduction_pct = (reduction_needed / current_bytes) * 100 if current_bytes > 0 else 0
    
    strategy = []
    
    if mime == "image/jpeg":
        # JPEG: reduce quality
        if reduction_pct > 30:
            strategy.append("Reduce JPEG quality to 75")
        elif reduction_pct > 15:
            strategy.append("Reduce JPEG quality to 85")
        else:
            strategy.append("Reduce JPEG quality to 90")
    elif mime == "image/png":
        # PNG: convert to JPEG or optimize
        if reduction_pct > 40:
            strategy.append("Convert PNG to JPEG (quality 80)")
        else:
            strategy.append("Optimize PNG with pngquant")
    
    return {
        "current_bytes": current_bytes,
        "target_bytes": target_bytes,
        "reduction_needed": reduction_needed,
        "reduction_pct": round(reduction_pct, 2),
        "strategy": strategy,
        "mode": "stub",
    }
