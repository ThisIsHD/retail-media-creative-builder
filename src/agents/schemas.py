from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


Decision = Literal["PASS", "WARN", "HARD_FAIL"]


class CopyFinding(BaseModel):
    category: Literal["PRICE", "SUSTAINABILITY", "CHARITY", "GUARANTEE", "COMPETITOR", "OTHER"]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    text_span: str
    reason: str
    suggestion: Optional[str] = None


class CopyOutput(BaseModel):
    decision: Decision = "PASS"
    headline: str
    subhead: Optional[str] = None
    cta: Optional[str] = None
    caption: str
    disclaimers: List[str] = Field(default_factory=list)
    findings: List[CopyFinding] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
