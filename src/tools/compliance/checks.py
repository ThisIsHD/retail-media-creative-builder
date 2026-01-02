from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from dataclasses import dataclass


Severity = Literal["INFO", "WARN", "HARD_FAIL"]


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    field: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def issues_to_dict(issues: List[Issue]) -> List[Dict[str, Any]]:
    return [
        {
            "code": i.code,
            "severity": i.severity,
            "message": i.message,
            "field": i.field,
            "meta": i.meta or {},
        }
        for i in issues
    ]


def resolve_status(issues: List[Issue]) -> str:
    """
    PASS: no WARN/HARD_FAIL
    WARN: at least one WARN but no HARD_FAIL
    HARD_FAIL: at least one HARD_FAIL
    """
    has_fail = any(i.severity == "HARD_FAIL" for i in issues)
    if has_fail:
        return "HARD_FAIL"
    has_warn = any(i.severity == "WARN" for i in issues)
    if has_warn:
        return "WARN"
    return "PASS"
