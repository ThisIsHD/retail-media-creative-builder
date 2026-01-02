from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ComplianceStatus = Literal["PASS", "WARN", "HARD_FAIL"]

class ComplianceIssue(BaseModel):
    code: str
    severity: Literal["WARN", "HARD_FAIL"]
    message: str
    layer_id: Optional[str] = None
    fix_hint: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class ComplianceResult(BaseModel):
    status: ComplianceStatus
    issues: List[ComplianceIssue] = Field(default_factory=list)
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: List[str] = Field(default_factory=list)
