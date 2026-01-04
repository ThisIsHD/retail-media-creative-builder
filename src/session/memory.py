from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MemoryConfig:
    """
    Keep memory deterministic + bounded.
    """
    max_messages: int = 20          # rolling window
    max_chars_total: int = 12_000   # hard cap for stored message text


class SessionMemoryStore:
    """
    Pure-Python memory helper that stores a bounded chat history + lightweight summary fields.
    This is meant to be persisted into Mongo inside the session document under `memory`.
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()

    def init_memory(self) -> Dict[str, Any]:
        return {
            "messages": [],               # list[{role, content, ts}]
            "summary": "",                # optional, can be filled later by summarizer agent
            "constraints": {},            # dict[str, Any] stable preferences, brand rules, etc. (matches state.py schema)
            "last_updated": _utcnow().isoformat(),
        }

    def append(
        self,
        memory: Dict[str, Any],
        *,
        role: str,
        content: str,
        ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        if memory is None:
            memory = self.init_memory()

        msgs: List[Dict[str, Any]] = list(memory.get("messages", []))
        msgs.append(
            {
                "role": role,
                "content": content,
                "ts": ts or _utcnow().isoformat(),
            }
        )

        msgs = self._trim_messages(msgs)
        memory["messages"] = msgs
        memory["last_updated"] = _utcnow().isoformat()

        # Enforce char cap (best-effort)
        memory = self._enforce_char_cap(memory)

        return memory

    def add_constraint(self, memory: Dict[str, Any], constraint_key: str, constraint_value: Any = True) -> Dict[str, Any]:
        """
        Add a constraint to memory. Constraints are stored as a dict to match state.py schema.
        """
        if memory is None:
            memory = self.init_memory()
        constraints = dict(memory.get("constraints", {}))
        if constraint_key:
            constraints[constraint_key] = constraint_value
        memory["constraints"] = constraints
        memory["last_updated"] = _utcnow().isoformat()
        return memory

    def get_context_messages(self, memory: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Return OpenAI-style messages list usable for Cerebras/OpenAI-compatible chat.
        """
        msgs = memory.get("messages", []) if memory else []
        out: List[Dict[str, str]] = []
        for m in msgs:
            role = m.get("role", "user")
            content = m.get("content", "")
            out.append({"role": role, "content": content})
        return out

    # -------------------------
    # internal trimming helpers
    # -------------------------
    def _trim_messages(self, msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(msgs) <= self.config.max_messages:
            return msgs
        return msgs[-self.config.max_messages :]

    def _enforce_char_cap(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        msgs: List[Dict[str, Any]] = list(memory.get("messages", []))
        total = sum(len((m.get("content") or "")) for m in msgs)
        if total <= self.config.max_chars_total:
            return memory

        # Drop oldest until under cap
        while msgs and total > self.config.max_chars_total:
            dropped = msgs.pop(0)
            total -= len(dropped.get("content") or "")

        memory["messages"] = msgs
        return memory
