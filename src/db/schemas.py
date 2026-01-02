from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional, List, Dict
from datetime import datetime

Status = Literal["active", "archived"]
TurnStatus = Literal["queued", "running", "completed", "failed"]
ComplianceResult = Literal["PASS", "WARN", "HARD_FAIL"]

class Attachment(BaseModel):
    attachment_id: str
    type: Literal["image", "text", "file"]
    role: Optional[str] = None
    source: Literal["upload", "url", "generated"] = "upload"
    mime: Optional[str] = None
    sha256: Optional[str] = None
    uri: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class Artifact(BaseModel):
    artifact_id: str
    type: Literal["image", "json", "text"]
    format: Optional[str] = None
    mime: Optional[str] = None
    uri: Optional[str] = None
    bytes: Optional[int] = None
    sha256: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class ComplianceCheck(BaseModel):
    id: str
    status: Literal["PASS", "WARN", "FAIL"]
    detail: Optional[str] = None

class TurnInput(BaseModel):
    text: str
    attachments: List[Attachment] = Field(default_factory=list)
    ui_context: Dict[str, Any] = Field(default_factory=dict)

class TurnOutputs(BaseModel):
    copy_text: Dict[str, Any] = Field(default_factory=dict)
    layout: Dict[str, Any] = Field(default_factory=dict)
    compliance: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[Artifact] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

class Tracing(BaseModel):
    langsmith: Dict[str, Any] = Field(default_factory=dict)
    provider_calls: List[Dict[str, Any]] = Field(default_factory=list)

class ChatTurn(BaseModel):
    id: str = Field(alias="_id")
    session_id: str
    turn_index: int
    created_at: datetime
    status: TurnStatus = "completed"
    input: TurnInput
    pipeline: Dict[str, Any] = Field(default_factory=dict)
    outputs: TurnOutputs = Field(default_factory=TurnOutputs)
    tracing: Tracing = Field(default_factory=Tracing)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

class SessionMemory(BaseModel):
    summary: str = ""
    constraints: Dict[str, Any] = Field(default_factory=dict)
    last_updated_turn: int = 0

class ChatSession(BaseModel):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    status: Status = "active"
    title: str = "New Session"
    session_config: Dict[str, Any] = Field(default_factory=dict)
    memory: SessionMemory = Field(default_factory=SessionMemory)
    counters: Dict[str, Any] = Field(default_factory=lambda: {"turn_count": 0})
    pointers: Dict[str, Any] = Field(default_factory=dict)
