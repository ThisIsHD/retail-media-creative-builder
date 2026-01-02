from __future__ import annotations

from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()  # Load .env file

from src.app.settings import load_settings
from src.app.logging import setup_logging
from src.db.mongo import connect_mongo, ensure_indexes
from src.db.repositories import SessionRepo, TurnRepo
from src.session.session_manager import SessionManager
from src.graph.build_graph import build_graph


def run_turn(
    *,
    session_id: Optional[str],
    user_text: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    ui_context: Optional[Dict[str, Any]] = None,
    title_if_new: str = "New Session",
    session_config_if_new: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Minimal callable entrypoint:
    - if session_id is None -> create new session
    - hydrate state from Mongo
    - run LangGraph
    - persist the turn to Mongo
    - return {session_id, turn_id, compliance_result, outputs_summary}
    """
    setup_logging()
    s = load_settings()

    handles = connect_mongo(s.mongo_uri, s.mongo_db)
    ensure_indexes(handles)

    session_repo = SessionRepo(handles["sessions"])
    turn_repo = TurnRepo(handles["turns"])
    sm = SessionManager(session_repo, turn_repo)

    if not session_id:
        session_id = sm.create_session(title=title_if_new, session_config=session_config_if_new or {})

    state_obj = sm.hydrate_state(
        session_id=session_id,
        user_text=user_text,
        attachments=attachments or [],
        ui_context=ui_context or {},
    )

    # Convert Pydantic state -> dict for graph execution
    state_dict = state_obj.model_dump()

    graph = build_graph().compile()
    final_state = graph.invoke(state_dict)

    # Reconstruct Pydantic object from final_state dict
    from src.agents.state import CreativeBuilderState
    state_obj = CreativeBuilderState(**final_state)

    turn_id = sm.persist_turn(state_obj)

    return {
        "session_id": session_id,
        "turn_id": turn_id,
        "turn_index": state_obj.turn_index,
        "compliance_result": state_obj.compliance_result,
        "summary": (state_obj.outputs.summary or {}).get("message"),
        "artifacts": [a.model_dump() for a in state_obj.outputs.artifacts],
    }
