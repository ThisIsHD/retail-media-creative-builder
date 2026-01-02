from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

from src.core.utils import ensure_list


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_next_suggestions(outputs: Dict[str, Any]) -> List[str]:
    """
    Deterministic suggestions based on warnings/issues.
    """
    suggestions: List[str] = []

    compliance = outputs.get("compliance", {}) or {}
    issues = ensure_list(compliance.get("issues", []))

    # If warnings exist, suggest addressing them
    warn_codes = {i.get("code") for i in issues if i.get("severity") == "WARN"}
    if "SAFE_ZONES_MISSING" in warn_codes:
        suggestions.append("Add safe-zone padding to avoid UI overlap (top/bottom/left/right).")
    if "FONT_MIN_NOT_SET" in warn_codes:
        suggestions.append("Set a minimum font size rule for readability (e.g., >= 24px on 1080).")

    # If we have only 1 creative direction, suggest variants
    copy_out = outputs.get("copy_out", {}) or {}
    if copy_out.get("headline"):
        suggestions.append("Generate 1–2 alternative headline variants (same intent, different phrasing).")

    # If background is solid, suggest premium background options
    layout = outputs.get("layout", {}) or {}
    bg = (layout.get("spec", {}) or {}).get("background", {}) or {}
    if bg.get("style") in (None, "solid"):
        suggestions.append("Try 2 premium backgrounds (gradient + subtle texture) while keeping contrast compliant.")

    # Deduplicate + cap
    deduped = []
    seen = set()
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped[:4]


def run_summarizer_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 4F: Summarizer agent
    - Produces user-facing summary.message and next_suggestions
    - Updates rolling session memory.summary (short) + constraints (if present)
    """
    outputs = state.get("outputs", {}) or {}

    compliance_result = state.get("compliance_result") or outputs.get("compliance", {}).get("status", "UNKNOWN")

    artifacts = ensure_list(outputs.get("artifacts", []))
    formats = [a.get("format") for a in artifacts if a.get("format")]
    formats_str = ", ".join(formats) if formats else "N/A"

    # Build deterministic message
    if compliance_result == "PASS":
        msg = f"Generated export-ready creative assets ({formats_str}) and passed compliance."
    elif compliance_result == "WARN":
        msg = f"Generated creative assets ({formats_str}) with compliance warnings to review."
    elif compliance_result == "HARD_FAIL":
        msg = "Compliance hard-fail: assets need fixes before export."
    else:
        msg = f"Run completed with compliance={compliance_result}."

    next_suggestions = _pick_next_suggestions(outputs)

    outputs.setdefault("summary", {})
    outputs["summary"].update(
        {
            "message": msg,
            "next_suggestions": next_suggestions,
            "summarized_at": _utcnow_iso(),
        }
    )

    # Update rolling memory (short + safe)
    memory = state.get("memory", {}) or {}
    prev_summary = (memory.get("summary") or "").strip()

    # Keep it short: last summary only (or you can append)
    memory["summary"] = msg
    memory.setdefault("constraints", {})
    memory["last_updated_turn"] = int(state.get("turn_index") or 0)

    state["memory"] = memory
    state["outputs"] = outputs

    # Pipeline bookkeeping
    pipeline = state.get("pipeline", {}) or {}
    routing = pipeline.get("routing", {}) or {}
    routing["summarizer"] = "OK"
    pipeline["routing"] = routing
    state["pipeline"] = pipeline

    return state
