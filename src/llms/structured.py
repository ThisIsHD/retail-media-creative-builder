from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar("T")


def extract_json(text: str) -> Dict[str, Any]:
    """
    Best-effort JSON extraction:
    - Accepts raw JSON
    - Or JSON wrapped in markdown fences
    """
    if not text:
        return {}

    s = text.strip()

    # Strip markdown fences
    if s.startswith("```"):
        s = s.strip("`")
        # sometimes starts with ```json
        s = s.replace("json\n", "", 1)

    # Try parse directly
    try:
        return json.loads(s)
    except Exception:
        pass

    # Fallback: attempt to locate first { ... } block
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = s[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return {}

    return {}


def validate_with_pydantic(data: Dict[str, Any], model_cls: Type[T]) -> T:
    """
    Validate dict against a Pydantic model class (v2 compatible).
    """
    # Pydantic v2: model_validate
    return model_cls.model_validate(data)  # type: ignore[attr-defined]


def structured_output(
    raw_text: str,
    *,
    model_cls: Optional[Type[T]] = None,
) -> Any:
    """
    Convert LLM raw text -> dict, and optionally validate into Pydantic model.
    """
    data = extract_json(raw_text)
    if model_cls is None:
        return data
    return validate_with_pydantic(data, model_cls)
