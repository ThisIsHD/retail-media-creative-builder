from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime


ComplianceResult = Literal["PASS", "WARN", "HARD_FAIL", "UNKNOWN"]


class AttachmentRef(BaseModel):
    """
    Lightweight reference to an attachment already uploaded/stored.
    """
    attachment_id: str
    role: Optional[str] = None  # e.g. packshot, background
    uri: Optional[str] = None
    mime: Optional[str] = None
    sha256: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class CreativeArtifactRef(BaseModel):
    """
    Output artifact reference stored in GCS/S3/local.
    """
    artifact_id: str
    type: Literal["image", "json", "text"] = "image"
    format: Optional[str] = None  # 1080x1080 etc.
    uri: Optional[str] = None
    mime: Optional[str] = None
    bytes: Optional[int] = None
    sha256: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class SessionMemory(BaseModel):
    """
    Rolling memory and constraints summarised across turns.
    """
    summary: str = ""
    constraints: Dict[str, Any] = Field(default_factory=dict)
    last_updated_turn: int = 0


class AgentOutputs(BaseModel):
    """
    Outputs produced within a single run/turn of the graph.
    """
    copy_out: Dict[str, Any] = Field(default_factory=dict)
    layout: Dict[str, Any] = Field(default_factory=dict)
    compliance: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[CreativeArtifactRef] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class PipelineMeta(BaseModel):
    graph_version: str = "v1"
    agents_run: List[str] = Field(default_factory=list)
    tool_loops: int = 0
    timings_ms: Dict[str, int] = Field(default_factory=dict)
    routing: Dict[str, Any] = Field(default_factory=dict)


class TracingMeta(BaseModel):
    langsmith: Dict[str, Any] = Field(default_factory=dict)
    provider_calls: List[Dict[str, Any]] = Field(default_factory=list)


class CreativeBuilderState(BaseModel):
    """
    LangGraph-compatible state object.
    This is what gets hydrated from Mongo and then persisted back per turn.
    """

    # Core identifiers
    session_id: str
    turn_id: Optional[str] = None
    turn_index: int = 0

    # Timestamps
    created_at: Optional[datetime] = None

    # User input
    user_text: str = ""
    attachments: List[AttachmentRef] = Field(default_factory=list)
    ui_context: Dict[str, Any] = Field(default_factory=dict)

    # Session configuration (retailer/channel/formats etc.)
    session_config: Dict[str, Any] = Field(default_factory=dict)

    # Rolling session memory
    memory: SessionMemory = Field(default_factory=SessionMemory)

    # Outputs of current turn
    outputs: AgentOutputs = Field(default_factory=AgentOutputs)

    # Compliance status for routing
    compliance_result: ComplianceResult = "UNKNOWN"

    # Bookkeeping
    pipeline: PipelineMeta = Field(default_factory=PipelineMeta)
    tracing: TracingMeta = Field(default_factory=TracingMeta)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    # Optional guardrails
    max_tool_loops: int = 6
    max_turns: int = 200
