from __future__ import annotations
from typing import Any, Dict, Literal

# Type alias for backward compatibility
Route = Literal["pass", "fail"]


def _get_max_tool_loops(state: Dict[str, Any]) -> int:
    """Get max tool loops from state or session config."""
    return int(
        state.get("max_tool_loops") 
        or state.get("session_config", {}).get("max_tool_loops") 
        or 6
    )


def _get_tool_loops(state: Dict[str, Any]) -> int:
    """Get current tool loop count."""
    pipeline = state.get("pipeline") or {}
    return int(pipeline.get("tool_loops") or state.get("tool_loops") or 0)


def _inc_tool_loops(state: Dict[str, Any]) -> None:
    """Increment tool loop counter."""
    pipeline = state.setdefault("pipeline", {})
    pipeline["tool_loops"] = int(pipeline.get("tool_loops") or 0) + 1


def _compliance_status(state: Dict[str, Any]) -> str:
    """Get compliance status from canonical location."""
    # Check top-level first (set by compliance_node)
    top_level = state.get("compliance_result")
    if top_level:
        return top_level.upper()
    
    # Fallback to outputs.compliance.status
    outputs = state.get("outputs") or {}
    compliance = outputs.get("compliance") or {}
    return (compliance.get("status") or "UNKNOWN").upper()


def _has_hard_fail_issue(state: Dict[str, Any]) -> bool:
    """Check if any compliance issue has HARD_FAIL severity."""
    outputs = state.get("outputs") or {}
    compliance = outputs.get("compliance") or {}
    issues = compliance.get("issues") or []
    
    for issue in issues:
        if (issue.get("severity") or "").upper() == "HARD_FAIL":
            return True
    return False


def _prefer_loop_target(state: Dict[str, Any]) -> str:
    """
    Decide which node to retry on failure.
    - If copy failed: redo copy first
    - If layout failed: redo layout
    - Else: redo imageops (common when visual constraints fail)
    """
    pipeline = state.get("pipeline") or {}
    routing = pipeline.get("routing") or {}
    
    copy_res = (routing.get("copy_result") or "").upper()
    layout_res = (routing.get("layout_result") or "").upper()
    
    if copy_res in {"FAIL", "HARD_FAIL"}:
        return "copy_validator"
    if layout_res in {"FAIL", "HARD_FAIL"}:
        return "layout_planner"
    
    # Default: retry imageops (most common failure point)
    return "imageops"


def route_after_compliance(state: Dict[str, Any]) -> str:
    """
    Central Phase 4G decision with smart retry:
    - PASS/WARN -> "exporter"
    - HARD_FAIL -> retry specific node ("copy_validator", "layout_planner", or "imageops")
    - Max loops reached -> "summarizer" (graceful degradation)
    
    Returns actual node name for direct routing.
    """
    status = _compliance_status(state)
    
    # Check if we have hard-fail issues (more granular than just status)
    has_hard_fail = _has_hard_fail_issue(state)
    
    # PASS or WARN without hard-fail issues -> proceed to export
    if status in {"PASS", "WARN"} and not has_hard_fail:
        return "exporter"
    
    # HARD_FAIL or hard-fail issues present -> check retry budget
    current_loops = _get_tool_loops(state)
    max_loops = _get_max_tool_loops(state)
    
    # If we've hit max retries, go to summarizer (graceful degradation)
    if current_loops >= max_loops:
        return "summarizer"
    
    # Increment loop counter and determine which node to retry
    _inc_tool_loops(state)
    
    # Smart retry: go back to the specific node that failed
    return _prefer_loop_target(state)


# Backward compatible version for simple graph (Phase 4)
def route_after_compliance_simple(state: Dict[str, Any]) -> Route:
    """
    Backward compatible version for current simple graph.
    Returns "pass" or "fail" which are mapped to nodes in build_graph.
    """
    status = _compliance_status(state)
    has_hard_fail = _has_hard_fail_issue(state)
    
    if status in {"PASS", "WARN"} and not has_hard_fail:
        return "pass"
    
    current_loops = _get_tool_loops(state)
    max_loops = _get_max_tool_loops(state)
    
    if current_loops >= max_loops:
        return "pass"  # Force pass to avoid infinite loop
    
    _inc_tool_loops(state)
    return "fail"


# Additional routers for future enhanced graph (Phase 5+)
def route_after_master(state: Dict[str, Any]) -> str:
    """
    After master: decide which branch to run.
    If you already have a full plan, go to imageops.
    Otherwise run copy/layout first.
    """
    pipeline = state.get("pipeline") or {}
    routing = pipeline.get("routing") or {}
    
    # If earlier phases already mark copy/layout as OK, skip to imageops
    copy_ok = (routing.get("copy_result") or "").upper() == "PASS"
    layout_ok = (routing.get("layout_result") or "").upper() == "OK"
    
    if copy_ok and layout_ok:
        return "imageops"
    
    return "copy_validator"


def route_after_copy(state: Dict[str, Any]) -> str:
    """Route after copy validator."""
    pipeline = state.get("pipeline") or {}
    routing = pipeline.get("routing") or {}
    copy_res = (routing.get("copy_result") or "").upper()
    
    # If copy passes, proceed to layout
    if copy_res == "PASS":
        return "layout_planner"
    
    # Copy failed - check retry budget (without prematurely burning a loop)
    current_loops = _get_tool_loops(state)
    max_loops = _get_max_tool_loops(state)

    if current_loops >= max_loops:
        return "summarizer"  # Give up gracefully
    
    _inc_tool_loops(state)
    return "copy_validator"  # Retry copy


def route_after_layout(state: Dict[str, Any]) -> str:
    """Route after layout planner."""
    pipeline = state.get("pipeline") or {}
    routing = pipeline.get("routing") or {}
    layout_res = (routing.get("layout_result") or "").upper()
    
    # If layout is OK, proceed to imageops
    if layout_res == "OK":
        return "imageops"
    
    # Layout failed - check retry budget (without prematurely burning a loop)
    current_loops = _get_tool_loops(state)
    max_loops = _get_max_tool_loops(state)

    if current_loops >= max_loops:
        return "summarizer"  # Give up gracefully
    
    _inc_tool_loops(state)
    return "layout_planner"  # Retry layout

