from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple


def _now_ms() -> int:
    return int(time.time() * 1000)

from src.agents.layout_schema import (
    LayoutOutput,
    LayoutSpec,
    SafeZones,
    ZoneSpec,
    RectN,
    BaseLayer,
    ImageLayer,
    TextLayer,
    TextStyle,
    ValueTileLayer,
    ValueTileSpec,
)

# -----------------------------
# Platform presets
# -----------------------------

PLATFORM_PRESETS: Dict[str, Dict[str, Any]] = {
    "instagram_feed": {
        "format": "1080x1080",
        "width": 1080,
        "height": 1080,
        "safe_zones": SafeZones(top=0.06, bottom=0.10, left=0.05, right=0.05),
    },
    "instagram_story": {
        "format": "1080x1920",
        "width": 1080,
        "height": 1920,
        "safe_zones": SafeZones(top=0.08, bottom=0.12, left=0.06, right=0.06),
    },
    "facebook_feed": {
        "format": "1200x628",
        "width": 1200,
        "height": 628,
        "safe_zones": SafeZones(top=0.08, bottom=0.12, left=0.06, right=0.06),
    },
    "facebook_story": {
        "format": "1080x1920",
        "width": 1080,
        "height": 1920,
        "safe_zones": SafeZones(top=0.08, bottom=0.12, left=0.06, right=0.06),
    },
}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _inside_safe(rect: RectN, safe: SafeZones) -> bool:
    # rect is center-based
    left = rect.x - rect.w / 2
    right = rect.x + rect.w / 2
    top = rect.y - rect.h / 2
    bottom = rect.y + rect.h / 2
    return (
        left >= safe.left
        and right <= (1.0 - safe.right)
        and top >= safe.top
        and bottom <= (1.0 - safe.bottom)
    )


def _safe_rect(safe: SafeZones) -> RectN:
    cx = (safe.left + (1.0 - safe.right)) / 2
    cy = (safe.top + (1.0 - safe.bottom)) / 2
    w = (1.0 - safe.left - safe.right)
    h = (1.0 - safe.top - safe.bottom)
    return RectN(x=cx, y=cy, w=w, h=h)


def _extract_style_hints(prompt: str) -> Dict[str, str]:
    """Lightweight intent extraction (deterministic)."""
    p = (prompt or "").lower()
    style = {}

    if any(k in p for k in ["minimal", "clean", "simple"]):
        style["layout_style"] = "clean"
    if any(k in p for k in ["bold", "strong", "loud"]):
        style["layout_style"] = "bold"
    if any(k in p for k in ["premium", "luxury", "elegant"]):
        style["layout_style"] = "premium"

    if "packshot" in p and any(k in p for k in ["big", "larger", "focus"]):
        style["packshot_priority"] = "high"

    if any(k in p for k in ["logo", "brand"]) and any(k in p for k in ["keep", "fixed", "don't move", "do not move"]):
        style["lock_logo"] = "true"

    return style


def _default_background(layout_style: str) -> Dict[str, str]:
    # keep it deterministic and safe for compliance
    if layout_style == "premium":
        return {"style": "solid", "value": "#F7F5F0"}
    if layout_style == "bold":
        return {"style": "solid", "value": "#EEF3FF"}
    return {"style": "solid", "value": "#FFFFFF"}


def _make_zones(platform: str, safe: SafeZones) -> List[ZoneSpec]:
    """Deterministic zones used downstream (image ops + compliance)."""
    s = _safe_rect(safe)

    # top = logo + headline, middle = packshot, bottom = cta/value
    top_zone = RectN(x=s.x, y=_clamp01(s.y - s.h * 0.32), w=s.w, h=s.h * 0.26)
    mid_zone = RectN(x=s.x, y=s.y, w=s.w, h=s.h * 0.44)
    bot_zone = RectN(x=s.x, y=_clamp01(s.y + s.h * 0.34), w=s.w, h=s.h * 0.26)

    return [
        ZoneSpec(name="title_zone", rect=top_zone, notes=["headline/subhead live here"]),
        ZoneSpec(name="packshot_zone", rect=mid_zone, notes=["packshot is primary visual"]),
        ZoneSpec(name="cta_zone", rect=bot_zone, notes=["CTA/value tile lives here"]),
    ]


def _rect_in_zone(zone: RectN, *, w: float, h: float, x_bias: float = 0.0, y_bias: float = 0.0) -> RectN:
    """Place a smaller rect inside a zone, with optional bias.
    Bias: -0.5 left/up, +0.5 right/down-ish."""
    cx = zone.x + x_bias * (zone.w * 0.20)
    cy = zone.y + y_bias * (zone.h * 0.20)
    return RectN(x=_clamp01(cx), y=_clamp01(cy), w=_clamp01(w), h=_clamp01(h))


def _derive_layout_for_platform(
    *,
    platform: str,
    user_prompt: str,
    prior_layout: Optional[Dict[str, Any]] = None,
) -> LayoutOutput:
    preset = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["instagram_feed"])
    safe = preset["safe_zones"]

    # Intent (stateful merge)
    intent = {}
    if prior_layout and isinstance(prior_layout, dict):
        # preserve intent across re-prompts
        intent.update(prior_layout.get("intent", {}) or {})
    intent.update(_extract_style_hints(user_prompt))

    layout_style = intent.get("layout_style", "clean")
    bg = _default_background(layout_style)
    zones = _make_zones(platform, safe)
    zmap = {z.name: z.rect for z in zones}

    # sizing heuristics by platform aspect ratio
    is_story = preset["height"] > preset["width"]
    packshot_priority = intent.get("packshot_priority", "normal")

    # Layer plan (deterministic)
    layers: List[BaseLayer] = []

    # Background
    layers.append(
        ImageLayer(
            id=_uid("bg"),
            type="background",
            z=0,
            anchor="center",
            rect=RectN(x=0.5, y=0.5, w=1.0, h=1.0),
            fit="cover",
            asset_ref="background",
            critical=False,
            meta={"note": "background fill"},
        )
    )

    # Packshot
    pack_w = 0.62 if is_story else 0.55
    pack_h = 0.48 if is_story else 0.52
    if packshot_priority == "high":
        pack_w = min(0.70, pack_w + 0.08)
        pack_h = min(0.62, pack_h + 0.08)

    pack_rect = _rect_in_zone(
        zmap["packshot_zone"],
        w=pack_w,
        h=pack_h,
        x_bias=0.18 if not is_story else 0.0,
        y_bias=0.05
    )
    layers.append(
        ImageLayer(
            id=_uid("packshot"),
            type="packshot",
            z=30,
            anchor="center",
            rect=pack_rect,
            fit="contain",
            asset_ref="packshot",
            critical=True,
            meta={"priority": packshot_priority},
        )
    )

    # Logo (top-left inside safe)
    logo_rect = _rect_in_zone(
        zmap["title_zone"],
        w=0.18 if is_story else 0.16,
        h=0.10 if is_story else 0.09,
        x_bias=-0.35,
        y_bias=-0.20
    )
    layers.append(
        ImageLayer(
            id=_uid("logo"),
            type="logo",
            z=40,
            anchor="top-left",
            rect=logo_rect,
            fit="contain",
            asset_ref="brand_logo",
            critical=True,
            locked=(intent.get("lock_logo") == "true"),
            meta={"note": "brand logo"},
        )
    )

    # Headline (top-center)
    headline_style = TextStyle(
        font_family="Inter",
        font_weight=800 if layout_style in ("bold", "premium") else 700,
        align="center",
        color="#111111",
        stroke_color="#FFFFFF" if layout_style == "bold" else None,
        stroke_width_px=2 if layout_style == "bold" else 0,
        max_lines=2,
    )
    headline_rect = _rect_in_zone(
        zmap["title_zone"],
        w=0.70,
        h=0.12 if is_story else 0.14,
        x_bias=0.10 if not is_story else 0.0,
        y_bias=0.12
    )
    layers.append(
        TextLayer(
            id=_uid("headline"),
            type="headline",
            z=50,
            anchor="top-center",
            rect=headline_rect,
            text="NEW LOOK\nSAME AWARD WINNING TASTE",
            style=headline_style,
            critical=True,
            meta={"note": "placeholder headline (to be refined by copy/summarizer)"},
        )
    )

    # CTA (bottom-right) — keep conservative and inside safe
    cta_style = TextStyle(
        font_family="Inter",
        font_weight=800,
        align="center",
        color="#111111",
        stroke_color=None,
        stroke_width_px=0,
        max_lines=2,
    )
    cta_rect = _rect_in_zone(
        zmap["cta_zone"],
        w=0.36 if is_story else 0.34,
        h=0.11 if is_story else 0.12,
        x_bias=0.30,
        y_bias=0.10
    )
    layers.append(
        TextLayer(
            id=_uid("cta"),
            type="cta",
            z=60,
            anchor="bottom-right",
            rect=cta_rect,
            text="Available in all major retailers",
            style=cta_style,
            critical=True,
            meta={"note": "CTA placeholder"},
        )
    )

    # Value tile (bottom-left) — optional but very common in retail
    tile_rect = _rect_in_zone(
        zmap["cta_zone"],
        w=0.30 if is_story else 0.28,
        h=0.14 if is_story else 0.16,
        x_bias=-0.32,
        y_bias=0.05
    )
    layers.append(
        ValueTileLayer(
            id=_uid("value"),
            type="value_tile",
            z=55,
            anchor="bottom-left",
            rect=tile_rect,
            text="WINNER\nAWARD",
            style=TextStyle(
                font_family="Inter",
                font_weight=900,
                align="center",
                color="#111111",
                max_lines=3,
            ),
            tile=ValueTileSpec(
                kind="award",
                bg_color="#FFD54F",
                text_color="#111111",
                corner_radius_px=20,
                border_px=0
            ),
            critical=True,
            meta={"note": "award/value tile placeholder"},
        )
    )

    # Safety check (pre-empt compliance headaches)
    warnings: List[str] = []
    for lyr in layers:
        if getattr(lyr, "critical", False) and not _inside_safe(lyr.rect, safe):
            warnings.append(f"Layer '{lyr.type}' is close to/over safe zone. Consider nudging inward.")

    spec = LayoutSpec(
        platform=platform,
        format=preset["format"],
        width=preset["width"],
        height=preset["height"],
        safe_zones=safe,
        zones=zones,
        background=bg,
        layers=layers,
        intent=intent,
        notes=["Deterministic layout v1.0 (safe-zone aware)."],
    )

    out = LayoutOutput(
        decision="WARN" if warnings else "OK",
        warnings=warnings,
        spec=spec,
    )

    # Validate strictly (raises if schema violated)
    LayoutOutput.model_validate(out.model_dump())
    return out


# -----------------------------
# Public Agent API
# -----------------------------

def run_layout_planner(state: Dict[str, Any]) -> Dict[str, Any]:
    """Layout Planner Agent:
    - Reads user prompt + prior layout (if any)
    - Produces strict LayoutOutput schema
    - Writes to state["outputs"]["layout"] and optionally memory
    """
    user_prompt = (state.get("user_text") or "").strip()

    # Platform selection: take from ui_context, else session_config, else default
    ui_context = state.get("ui_context", {}) or {}
    session_config = state.get("session_config", {}) or {}
    
    platform = (
        ui_context.get("platform")
        or session_config.get("platform")
        or "instagram_feed"
    )
    
    if platform not in PLATFORM_PRESETS:
        platform = "instagram_feed"

    prior_layout = None
    # If you store previous turn layout in memory, preserve it
    mem = state.get("memory") or {}
    if isinstance(mem, dict):
        prior_layout = mem.get("layout")

    # Track timing
    t0 = _now_ms()
    
    layout_out = _derive_layout_for_platform(
        platform=platform,
        user_prompt=user_prompt,
        prior_layout=prior_layout,
    )

    # Write outputs
    outputs = state.get("outputs", {}) or {}
    layout_dump = layout_out.model_dump()
    # Mirror for compliance engines that expect these at top-level
    if isinstance(layout_dump.get("spec"), dict):
        layout_dump["safe_zones"] = layout_dump["spec"].get("safe_zones")

        # Ensure typography exists so we don't WARN on min font
        typography = (layout_dump["spec"].get("typography") or {})
        typography.setdefault("min_font_px", 24)  # sensible default for 1080 canvas
        layout_dump["spec"]["typography"] = typography

        # also mirror at top-level if checks look for layout.typography.*
        layout_dump["typography"] = typography

    outputs["layout"] = layout_dump

    state["outputs"] = outputs

    # Preserve lightweight layout intent for re-prompts (stateful UX)
    memory = state.get("memory", {}) or {}
    memory["layout"] = {
        "platform": platform,
        "format": layout_out.spec.format,
        "intent": layout_out.spec.intent,
        # you may store the whole spec later, but keep memory lean:
        "last_layout_id": layout_out.spec.layers[0].id if layout_out.spec.layers else None,
    }
    state["memory"] = memory

    # Update pipeline routing and track agent run
    pipeline = state.get("pipeline", {}) or {}
    pipeline.setdefault("routing", {})
    pipeline.setdefault("agents_run", [])
    pipeline.setdefault("timings_ms", {})
    
    if "layout_planner" not in pipeline["agents_run"]:
        pipeline["agents_run"].append("layout_planner")
    pipeline["routing"]["layout_result"] = layout_out.decision
    pipeline["timings_ms"]["layout_planner"] = _now_ms() - t0
    
    state["pipeline"] = pipeline

    return state
