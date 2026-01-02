from __future__ import annotations
import secrets

def _tok(nbytes: int = 12) -> str:
    return secrets.token_urlsafe(nbytes)

def new_session_id() -> str:
    return f"sess_{_tok()}"

def new_turn_id() -> str:
    return f"turn_{_tok()}"

def new_attachment_id() -> str:
    return f"att_{_tok()}"

def new_artifact_id() -> str:
    return f"art_{_tok()}"

def new_id(nbytes: int = 12) -> str:
    """Generate a generic ID with specified byte length."""
    return _tok(nbytes)
