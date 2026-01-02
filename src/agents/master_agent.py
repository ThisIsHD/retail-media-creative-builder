from __future__ import annotations

from typing import Any, Dict, List


def run_master_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Master agent:
    - Normalizes user input + ui_context
    - Initializes pipeline routing defaults
    - Adds simple intent + required assets hints (deterministic)
    """
    pipeline = state.get("pipeline", {}) or {}
    routing = pipeline.get("routing", {}) or {}
    pipeline.setdefault("graph_version", "v1")
    pipeline.setdefault("tool_loops", 0)
    pipeline.setdefault("timings_ms", {})
    pipeline.setdefault("agents_run", [])
    pipeline["routing"] = routing

    # Ensure core state fields exist
    user_text = (state.get("user_text") or state.get("input", {}).get("text") or state.get("text") or "").strip()
    ui_context = state.get("ui_context") or state.get("input", {}).get("ui_context") or {}

    selected_formats: List[str] = ui_context.get("selected_formats") or ["1080x1080"]
    state["ui_context"] = {**ui_context, "selected_formats": selected_formats}

    # Minimal intent extraction
    wants_packshot = ("packshot" in user_text.lower()) or any(
        (a.get("role") == "packshot") for a in (state.get("attachments") or [])
    )

    # Store master outputs
    outputs = state.get("outputs", {}) or {}
    outputs.setdefault("master", {})
    outputs["master"] = {
        "intent": "premium",
        "selected_formats": selected_formats,
        "required_assets": ["logo"] + (["packshot"] if wants_packshot else []),
        "notes": [
            "Master agent is deterministic (Phase 4G).",
            "Copy + layout agents will refine details next.",
        ],
    }
    state["outputs"] = outputs

    # Routing defaults (don’t claim PASS/OK here unless truly known)
    routing.setdefault("copy_result", "UNKNOWN")
    routing.setdefault("layout_result", "UNKNOWN")
    routing.setdefault("compliance_result", "UNKNOWN")

    # Track agent run
    if "master" not in pipeline["agents_run"]:
        pipeline["agents_run"].append("master")

    state["pipeline"] = pipeline
    return state
