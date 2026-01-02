from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from src.agents.state import CreativeBuilderState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_turn_doc(state: CreativeBuilderState) -> Dict[str, Any]:
    """
    Build a MongoDB turn document from the current state.
    One "Send" click = one document.
    """
    if not state.turn_id:
        raise ValueError("turn_id is required to build a turn doc")

    return {
        "_id": state.turn_id,
        "session_id": state.session_id,
        "turn_index": state.turn_index,
        "created_at": state.created_at or _utcnow(),
        "status": "completed" if not state.errors else "failed",
        "input": {
            "text": state.user_text,
            "attachments": [a.model_dump() for a in state.attachments],
            "ui_context": state.ui_context,
        },
        "pipeline": state.pipeline.model_dump(),
        "outputs": state.outputs.model_dump(),
        "tracing": state.tracing.model_dump(),
        "errors": state.errors,
    }
