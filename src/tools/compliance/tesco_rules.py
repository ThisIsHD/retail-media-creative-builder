from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.tools.compliance.checks import Issue


def _get(layout: Dict[str, Any], path: str, default=None):
    """
    Safe getter for nested dict paths like "safe_zones.packshot.min_padding"
    """
    cur = layout
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def check_value_tile_rules(layout: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    value_tile = _get(layout, "elements.value_tile", default=None)

    # If value tile exists, ensure it has required fields (stub rule)
    if value_tile:
        text = value_tile.get("text")
        if not text:
            issues.append(
                Issue(
                    code="VALUE_TILE_MISSING_TEXT",
                    severity="HARD_FAIL",
                    message="Value tile present but text missing.",
                    field="layout.elements.value_tile.text",
                )
            )
    return issues


def check_social_safe_zones(layout: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    safe = _get(layout, "safe_zones", default={}) or {}

    # Stub: require safe zones exist
    if not safe:
        issues.append(
            Issue(
                code="SAFE_ZONES_MISSING",
                severity="WARN",
                message="Safe zones not specified in layout. Risk of platform UI overlap.",
                field="layout.safe_zones",
            )
        )
    return issues


def check_font_sizes(layout: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    fonts = _get(layout, "typography", default={}) or {}

    min_font = fonts.get("min_font_px")
    if min_font is None:
        issues.append(
            Issue(
                code="FONT_MIN_NOT_SET",
                severity="WARN",
                message="Minimum font size not specified. Might violate readability rules.",
                field="layout.typography.min_font_px",
            )
        )
    else:
        if min_font < 12:
            issues.append(
                Issue(
                    code="FONT_TOO_SMALL",
                    severity="HARD_FAIL",
                    message="Minimum font size too small (<12px).",
                    field="layout.typography.min_font_px",
                    meta={"min_font_px": min_font},
                )
            )
    return issues


def check_cta_tag_overlaps(layout: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    # Stub overlap detection: require CTA and tag not share same anchor
    cta = _get(layout, "elements.cta", default=None)
    tag = _get(layout, "elements.tag", default=None)

    if cta and tag:
        cta_anchor = cta.get("anchor")
        tag_anchor = tag.get("anchor")
        if cta_anchor and tag_anchor and cta_anchor == tag_anchor:
            issues.append(
                Issue(
                    code="CTA_TAG_POTENTIAL_OVERLAP",
                    severity="WARN",
                    message="CTA and tag share the same anchor; potential overlap risk.",
                    field="layout.elements",
                    meta={"anchor": cta_anchor},
                )
            )
    return issues


def check_packshot_spacing(layout: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    packshot = _get(layout, "elements.packshot", default=None)
    if packshot:
        pad = packshot.get("min_padding_px")
        if pad is None:
            issues.append(
                Issue(
                    code="PACKSHOT_PADDING_MISSING",
                    severity="WARN",
                    message="Packshot min padding not set; may violate spacing rules.",
                    field="layout.elements.packshot.min_padding_px",
                )
            )
        elif pad < 8:
            issues.append(
                Issue(
                    code="PACKSHOT_PADDING_TOO_LOW",
                    severity="HARD_FAIL",
                    message="Packshot padding too low (<8px).",
                    field="layout.elements.packshot.min_padding_px",
                    meta={"min_padding_px": pad},
                )
            )
    return issues
