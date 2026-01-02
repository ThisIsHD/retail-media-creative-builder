from __future__ import annotations
from typing import Any, List


def ensure_list(obj: Any) -> List[Any]:
    """Ensure object is a list. If None, return empty list. If already list, return as-is."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return [obj]
