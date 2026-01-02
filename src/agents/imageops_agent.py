from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.agents.imageops_schema import (
    ImageOpsResult,
    ImageOpsPlan,
    ImageOpStep,
    RenderInstruction,
)
from src.tools.image_ops import remove_bg, crop_rotate, resize, contrast_wcag, compose_layers
from src.core.ids import new_artifact_id
from src.core.clock import utc_now


_FMT_TO_WH = {
    "1080x1080": (1080, 1080),
    "1080x1920": (1080, 1920),
    "1200x628": (1200, 628),
}


def _norm_to_px(rect: Dict[str, float], fmt: str) -> Dict[str, int]:
    """Convert normalized RectN (center-based) to pixel coordinates."""
    w, h = _FMT_TO_WH.get(fmt, (1080, 1080))
    
    # rect is center-based: {x, y, w, h} where x,y is center
    cx = rect.get("x", 0.5)
    cy = rect.get("y", 0.5)
    rw = rect.get("w", 0.1)
    rh = rect.get("h", 0.1)
    
    # Convert to pixel box (center-based)
    return {
        "cx": int(round(cx * w)),
        "cy": int(round(cy * h)),
        "w": int(round(rw * w)),
        "h": int(round(rh * h)),
    }


def build_transform_plan(
    *,
    layout_json: Dict[str, Any],
    assets: Dict[str, Any] | None = None,
) -> ImageOpsPlan:
    """
    Build a plan of image transformations needed for source assets.
    Uses actual tool functions from src/tools/image_ops/.
    This is deterministic and can be executed later by a real image processor.
    """
    assets = assets or {}
    fmt = layout_json.get("format", "1080x1080")
    layers = layout_json.get("layers", [])
    
    steps: List[ImageOpStep] = []
    
    # Find packshot layer to determine if we need background removal
    packshot_layers = [l for l in layers if l.get("type") == "packshot"]
    if packshot_layers:
        packshot = packshot_layers[0]
        packshot_uri = assets.get("packshot_uri") or packshot.get("asset_ref")
        
        if packshot_uri:
            # Step 1: Remove background from packshot using tool
            bg_result = remove_bg.remove_bg(packshot_uri=packshot_uri)
            steps.append(
                ImageOpStep(
                    op=bg_result["op"],
                    params=bg_result["params"],
                    notes=bg_result["notes"]
                )
            )
            
            # Step 2: Resize packshot to target dimensions using tool
            resize_result = resize.resize(target=fmt)
            steps.append(
                ImageOpStep(
                    op=resize_result["op"],
                    params=resize_result["params"],
                    notes=resize_result["notes"]
                )
            )
    
    # Step 3: Check WCAG contrast for text layers using tool
    text_layers = [l for l in layers if l.get("type") in {"headline", "subhead", "cta", "legal"}]
    if text_layers:
        # Extract background and foreground colors if available
        bg_color = layout_json.get("background", {}).get("value")
        fg_color = text_layers[0].get("style", {}).get("color") if text_layers else None
        
        contrast_result = contrast_wcag.contrast_wcag_fix(
            min_contrast_ratio=4.5,
            bg=bg_color,
            fg=fg_color
        )
        steps.append(
            ImageOpStep(
                op=contrast_result["op"],
                params=contrast_result["params"],
                notes=contrast_result["notes"]
            )
        )
    
    return ImageOpsPlan(
        steps=steps,
        input_packshot_uri=assets.get("packshot_uri"),
        output_formats=[fmt],
        provider="pillow",  # or "gemini-image" for future AI-based transforms
    )


def build_render_plan_from_layout(
    *,
    layout_json: Dict[str, Any],
    assets: Dict[str, Any] | None = None,
) -> RenderInstruction:
    """
    Converts LayoutSpec JSON → renderer-friendly instruction list (px boxes).
    No real image processing yet; deterministic conversion step.
    """
    assets = assets or {}

    fmt = layout_json.get("format", "1080x1080")
    bg = layout_json.get("background", {"style": "solid", "value": "#FFFFFF"})
    layers = layout_json.get("layers", [])

    render_layers: List[Dict[str, Any]] = []
    for layer in layers:
        rect = layer.get("rect", {})
        px_box = _norm_to_px(rect, fmt)

        render_layers.append(
            {
                "id": layer.get("id"),
                "type": layer.get("type"),
                "z": layer.get("z", 1),
                "anchor": layer.get("anchor", "center"),
                "box_px": px_box,
                "text": layer.get("text"),
                "style": layer.get("style"),
                "tile": layer.get("tile"),
                "asset_ref": layer.get("asset_ref"),
                "fit": layer.get("fit"),
                "opacity": layer.get("opacity", 1.0),
                "rotation_deg": layer.get("rotation_deg", 0.0),
                "locked": layer.get("locked", False),
                "critical": layer.get("critical", True),
                # keep raw layer too for audit
                "raw": layer,
            }
        )

    # stable sort by z for deterministic render order
    render_layers.sort(key=lambda x: int(x.get("z", 1)))

    plan = RenderInstruction(
        format=fmt,
        background=bg,
        layers=render_layers,
        notes=["Render plan built from layout_json (normalized→px)."],
    )
    return plan


def run_imageops_agent(
    *,
    session_id: str,
    turn_id: str,
    layout_json: Dict[str, Any],
    assets: Dict[str, Any] | None = None,
    provider_name: str = "gemini-3-pro-image-preview",
    output_formats: List[str] | None = None,
) -> ImageOpsResult:
    """
    Tool-based imageops agent: uses actual tool functions from src/tools/image_ops/.
    We produce:
      - transform_plan (what image ops we'd apply to source assets)
      - render_plan (what we'd render for final composition)
      - artifact stubs (what exporter will later turn into downloadable images)
    
    Supports multi-format output (e.g., both IG square and story).
    """
    assets = assets or {}
    output_formats = output_formats or [layout_json.get("format", "1080x1080")]
    
    # Build both plans
    transform_plan = build_transform_plan(layout_json=layout_json, assets=assets)
    render_plan = build_render_plan_from_layout(layout_json=layout_json, assets=assets)

    # Create artifact stubs for each output format
    artifacts = []
    timestamp = utc_now().isoformat()
    
    for fmt in output_formats:
        artifact_id = new_artifact_id()
        mime = "image/png" if assets.get("packshot_uri") else "image/jpeg"
        
        artifacts.append({
            "artifact_id": artifact_id,
            "type": "image",
            "format": fmt,
            "uri": f"gcs://stub-bucket/{session_id}/{turn_id}/{artifact_id}.{mime.split('/')[-1]}",
            "mime": mime,
            "bytes": 420000,
            "sha256": None,
            "created_at": timestamp,
            "meta": {
                "provider": provider_name,
                "stub": True,
                "render_plan_in_db": True,
                "transform_steps": len(transform_plan.steps),
                "packshot_optional": assets.get("packshot_uri") is None,
            },
        })

    return ImageOpsResult(
        transform_plan=transform_plan,
        render_plan=render_plan,
        artifacts=artifacts,
        debug={
            "layout_format": render_plan.format,
            "layer_count": len(render_plan.layers),
            "transform_step_count": len(transform_plan.steps),
            "output_formats": output_formats,
            "timestamp": timestamp,
        }
    )

