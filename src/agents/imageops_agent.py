from __future__ import annotations

import os
import uuid
import hashlib
from datetime import datetime, timezone
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
from src.llms.providers.gemini_client import GeminiImageClient

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

    # --- LIVE GENERATION (Gemini / Vertex) ---
    client = GeminiImageClient()

    artifacts = []
    # Build prompt from layout and copy information
    # Extract text from layout layers for better prompt
    layout_layers = layout_json.get("layers", [])
    text_parts = []
    for layer in layout_layers:
        if layer.get("type") in {"headline", "subhead", "cta"}:
            text = layer.get("text", "")
            if text:
                text_parts.append(text)
    
    # Build a descriptive prompt for image generation
    prompt_parts = ["Generate a premium retail media creative"]
    if text_parts:
        prompt_parts.append(f"with text: {', '.join(text_parts)}")
    if assets.get("packshot_uri"):
        prompt_parts.append("featuring a product packshot")
    prompt_parts.append("with professional layout, logo, headline, and CTA button.")
    
    prompt = " ".join(prompt_parts)

    for fmt in output_formats:
        # Generate image using Gemini with format hint for proper aspect ratio
        img_bytes, mime, meta = client.generate_image(
            prompt=prompt,
            model=provider_name,
            format_hint=fmt
        )

        # Write locally (exporter can upload later if needed)
        out_path = f"artifacts/{session_id}/{turn_id}/{fmt.replace('x','_')}.png"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(img_bytes)

        artifacts.append({
            "artifact_id": f"art_{uuid.uuid4().hex[:16]}",
            "type": "image",
            "format": fmt,
            "uri": f"file://{os.path.abspath(out_path)}",
            "mime": mime,
            "bytes": len(img_bytes),
            "sha256": hashlib.sha256(img_bytes).hexdigest(),
            "meta": {
                "provider": provider_name,
                "stub": False,
                "render_plan_in_db": True,
                "transform_steps": len(transform_plan.steps) if transform_plan else 0,
                "packshot_optional": False,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "turn_id": turn_id,
                "platform": layout_json.get("platform"),
            }
        })

    return ImageOpsResult(
        transform_plan=transform_plan,
        render_plan=render_plan,
        artifacts=artifacts,
        debug={"live": True, "provider": provider_name},
    )
