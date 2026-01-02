from __future__ import annotations

from typing import Any, Dict, List

from src.schemas.compliance_schema import ComplianceIssue, ComplianceResult
from src.core.clock import utc_now
from src.tools.compliance.checks import Issue, issues_to_dict, resolve_status
from src.tools.compliance.copy_claims import detect_copy_issues
from src.tools.compliance.tesco_rules import (
    check_value_tile_rules,
    check_social_safe_zones,
    check_font_sizes,
    check_cta_tag_overlaps,
    check_packshot_spacing,
)


def _rect_inside_safe(rect: Dict[str, float], safe: Dict[str, float]) -> bool:
    """Check if center-based rect is inside safe zones.
    rect: {x, y, w, h} where x,y is center (0..1)
    safe: {top, bottom, left, right} margins (0..1)
    """
    # Convert center-based rect to edges
    left = rect["x"] - rect["w"] / 2
    right = rect["x"] + rect["w"] / 2
    top = rect["y"] - rect["h"] / 2
    bottom = rect["y"] + rect["h"] / 2
    
    # Check if inside safe zone
    return (
        left >= safe.get("left", 0.0)
        and right <= (1.0 - safe.get("right", 0.0))
        and top >= safe.get("top", 0.0)
        and bottom <= (1.0 - safe.get("bottom", 0.0))
    )


def _overlap(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Returns overlap area (normalized units^2) for center-based rects."""
    # Convert center-based to edges
    ax1 = a["x"] - a["w"] / 2
    ax2 = a["x"] + a["w"] / 2
    ay1 = a["y"] - a["h"] / 2
    ay2 = a["y"] + a["h"] / 2
    
    bx1 = b["x"] - b["w"] / 2
    bx2 = b["x"] + b["w"] / 2
    by1 = b["y"] - b["h"] / 2
    by2 = b["y"] + b["h"] / 2

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    return (ix2 - ix1) * (iy2 - iy1)


def _area(rect: Dict[str, float]) -> float:
    return max(0.0, rect.get("w", 0.0)) * max(0.0, rect.get("h", 0.0))


def run_compliance_checks(layout_json: Dict[str, Any]) -> ComplianceResult:
    """
    Deterministic rules (hackathon-safe, explainable):
    - Critical layers must be inside safe-zone (HARD_FAIL)
    - No large overlaps between CTA/Text and packshot (WARN/HARD_FAIL based on overlap %)
    - Minimum font size for text layers (WARN)
    - Packshot must exist and be reasonably sized (WARN/HARD_FAIL)
    """
    issues: List[ComplianceIssue] = []
    notes: List[str] = []

    safe_zones = layout_json.get("safe_zones", {})
    layers = layout_json.get("layers", []) or []

    if not safe_zones:
        return ComplianceResult(
            status="HARD_FAIL",
            issues=[ComplianceIssue(
                code="SAFEZONE_MISSING",
                severity="HARD_FAIL",
                message="safe_zones missing from layout spec"
            )],
            score=0.0,
        )

    # Index by type for cross-layer checks
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for l in layers:
        by_type.setdefault(l.get("type", "unknown"), []).append(l)

    # 1) Safe-zone containment for critical layers
    for l in layers:
        if not l.get("critical", True):
            continue  # Skip non-critical layers
            
        rect = l.get("rect")
        if not rect:
            issues.append(
                ComplianceIssue(
                    code="RECT_MISSING",
                    severity="HARD_FAIL",
                    message="Layer rect missing.",
                    layer_id=l.get("id"),
                )
            )
            continue
            
        if not _rect_inside_safe(rect, safe_zones):
            issues.append(
                ComplianceIssue(
                    code="OUTSIDE_SAFEZONE",
                    severity="HARD_FAIL",
                    message=f"Critical layer '{l.get('type')}' extends outside safe zone.",
                    layer_id=l.get("id"),
                    fix_hint="Shrink/move the layer to fit inside safe_zones.",
                    meta={"rect": rect, "safe_zones": safe_zones},
                )
            )

    # 2) Font weight sanity (text layers)
    text_types = {"headline", "subhead", "cta", "legal", "badge"}
    for l in layers:
        if l.get("type") in text_types:
            style = l.get("style") or {}
            font_weight = style.get("font_weight", 700)
            
            # Check minimum font weight for readability
            min_weight = 400 if l.get("type") == "legal" else 600
            if font_weight < min_weight:
                issues.append(
                    ComplianceIssue(
                        code="FONT_TOO_LIGHT",
                        severity="WARN",
                        message=f"Font weight too light for {l.get('type')}.",
                        layer_id=l.get("id"),
                        fix_hint=f"Increase font_weight to >= {min_weight}.",
                        meta={"font_weight": font_weight, "min": min_weight},
                    )
                )

    # 3) Packshot existence + size
    packshots = by_type.get("packshot", [])
    if not packshots:
        issues.append(
            ComplianceIssue(
                code="PACKSHOT_MISSING",
                severity="HARD_FAIL",
                message="Packshot layer missing.",
                fix_hint="Add packshot layer (type='packshot') inside safe_zone.",
            )
        )
    else:
        # Choose largest packshot
        p = max(packshots, key=lambda x: _area(x.get("rect", {"w": 0, "h": 0})))
        prect = p.get("rect", {})
        pa = _area(prect)
        
        # Too small packshot reduces visual compliance
        if pa < 0.08:
            issues.append(
                ComplianceIssue(
                    code="PACKSHOT_TOO_SMALL",
                    severity="WARN",
                    message="Packshot area seems too small.",
                    layer_id=p.get("id"),
                    fix_hint="Increase packshot size or make it more prominent.",
                    meta={"packshot_area": pa},
                )
            )

    # 4) Overlap checks: packshot vs CTA/text
    if packshots:
        p = max(packshots, key=lambda x: _area(x.get("rect", {"w": 0, "h": 0})))
        prect = p.get("rect", {})
        
        for l in layers:
            if l.get("type") in {"cta", "headline", "subhead", "badge"}:
                rect = l.get("rect", {})
                ov = _overlap(prect, rect)
                if ov <= 0:
                    continue
                    
                frac = ov / max(_area(rect), 1e-9)
                
                # If text/cta is heavily overlapped by packshot, it's bad
                if frac > 0.35:
                    issues.append(
                        ComplianceIssue(
                            code="OVERLAP_TEXT_PACKSHOT",
                            severity="HARD_FAIL",
                            message=f"{l.get('type')} is heavily overlapped by packshot.",
                            layer_id=l.get("id"),
                            fix_hint="Move text/CTA away from packshot or reduce packshot size.",
                            meta={"overlap_frac": frac},
                        )
                    )
                elif frac > 0.15:
                    issues.append(
                        ComplianceIssue(
                            code="OVERLAP_TEXT_PACKSHOT",
                            severity="WARN",
                            message=f"{l.get('type')} overlaps with packshot.",
                            layer_id=l.get("id"),
                            fix_hint="Adjust placement to avoid overlap.",
                            meta={"overlap_frac": frac},
                        )
                    )

    # Determine status
    hard = any(i.severity == "HARD_FAIL" for i in issues)
    status = "HARD_FAIL" if hard else ("WARN" if issues else "PASS")

    # Simple score
    score = 1.0
    for i in issues:
        score -= 0.25 if i.severity == "HARD_FAIL" else 0.08
    score = max(0.0, min(1.0, score))

    notes.append("Deterministic compliance checks executed (safe-zone, font, packshot, overlap).")
    return ComplianceResult(status=status, issues=issues, score=score, notes=notes)


def run_compliance_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool-based compliance agent that uses actual compliance tools.
    Deterministic compliance checks:
    - Uses layout JSON
    - Uses copy text (if present)
    Returns PASS/WARN/HARD_FAIL + issues
    """
    created_at = utc_now()
    
    # Extract layout and copy from state
    outputs = state.get("outputs", {}) or {}
    layout_output = outputs.get("layout", {}) or {}
    layout_spec = layout_output.get("spec", {}) or {}  # Extract the actual spec
    copy_out = outputs.get("copy_out", {}) or {}
    copy_text = copy_out.get("headline", "") or copy_out.get("caption", "") or ""
    
    # Run all compliance checks using tools (pass layout_spec, not layout_output)
    issues: List[Issue] = []
    issues.extend(detect_copy_issues(copy_text))
    issues.extend(check_value_tile_rules(layout_spec))
    issues.extend(check_social_safe_zones(layout_spec))
    issues.extend(check_font_sizes(layout_spec))
    issues.extend(check_cta_tag_overlaps(layout_spec))
    issues.extend(check_packshot_spacing(layout_spec))
    
    # Resolve overall status
    status = resolve_status(issues)
    
    # Build payload
    payload = {
        "status": status,
        "issues": issues_to_dict(issues),
        "checked_at": created_at.isoformat(),
        "policy": "tesco_appendix_ab_stub_rules_v1",
    }
    
    return {
        "compliance": payload,
        "compliance_result": status,
        "updated_at": created_at,
    }
