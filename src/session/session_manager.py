from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.core.ids import new_session_id, new_turn_id
from src.db.repositories import SessionRepo, TurnRepo
from src.agents.state import (
    CreativeBuilderState,
    AttachmentRef,
    SessionMemory,
)
from src.session.turn_builder import build_turn_doc
from src.app.errors import SessionNotFoundError, TurnPersistenceError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionManager:
    def __init__(self, session_repo: SessionRepo, turn_repo: TurnRepo):
        self.session_repo = session_repo
        self.turn_repo = turn_repo

    # ---------- Sessions ----------
    def create_session(self, title: str = "New Session", session_config: Optional[Dict[str, Any]] = None) -> str:
        session_id = new_session_id()
        self.session_repo.create_session(session_id=session_id, title=title, session_config=session_config or {})
        return session_id

    def load_session(self, session_id: str) -> Dict[str, Any]:
        doc = self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return doc

    # ---------- Turns ----------
    def next_turn_index(self, session_id: str) -> int:
        last = self.turn_repo.get_last_turn(session_id)
        if not last:
            return 1
        return int(last.get("turn_index", 0)) + 1

    def hydrate_state(
        self,
        session_id: str,
        user_text: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        ui_context: Optional[Dict[str, Any]] = None,
    ) -> CreativeBuilderState:
        """
        Create a new state for this turn by combining:
        - session doc (config + memory)
        - recent turns if needed (optional later)
        - new user input for this turn
        """
        session_doc = self.load_session(session_id)
        turn_index = self.next_turn_index(session_id)
        turn_id = new_turn_id()

        # Memory
        mem_doc = session_doc.get("memory", {}) or {}
        memory = SessionMemory(
            summary=mem_doc.get("summary", "") or "",
            constraints=mem_doc.get("constraints", {}) or {},
            last_updated_turn=int(mem_doc.get("last_updated_turn", 0) or 0),
        )

        # Attachments
        atts = []
        for a in (attachments or []):
            atts.append(AttachmentRef(**a))

        # Config
        session_config = session_doc.get("session_config", {}) or {}

        state = CreativeBuilderState(
            session_id=session_id,
            turn_id=turn_id,
            turn_index=turn_index,
            created_at=_utcnow(),
            user_text=user_text,
            attachments=atts,
            ui_context=ui_context or {},
            session_config=session_config,
            memory=memory,
            max_tool_loops=int(session_config.get("max_tool_loops", 6)),
            max_turns=int(session_config.get("max_turns", 200)),
        )

        return state

    def persist_turn(self, state: CreativeBuilderState) -> str:
        """
        Persist the turn doc and update session pointers/counters.
        """
        try:
            doc = build_turn_doc(state)
            turn_id = self.turn_repo.insert_turn(doc)

            # Update session pointers/counters
            session_doc = self.load_session(state.session_id)
            current_count = int((session_doc.get("counters", {}) or {}).get("turn_count", 0))
            new_count = max(current_count, state.turn_index)

            self.session_repo.touch(
                state.session_id,
                last_turn_id=turn_id,
                turn_count=new_count
            )
            return turn_id
        except Exception as e:
            raise TurnPersistenceError(str(e)) from e
