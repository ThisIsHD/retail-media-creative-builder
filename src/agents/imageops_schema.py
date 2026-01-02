from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ImageFormat = Literal["1080x1080", "1080x1920", "1200x628"]

# -----------------------------
# Image Assets
# -----------------------------

class ImageAsset(BaseModel):
    asset_id: str
    kind: Literal["packshot", "logo", "background", "generated", "unknown"] = "unknown"
    uri: Optional[str] = None
    mime: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

# -----------------------------
# Image Transform Operations
# -----------------------------

class ImageOpStep(BaseModel):
    """A single image transformation operation."""
    op: Literal[
        "remove_bg",
        "crop_rotate",
        "resize",
        "contrast_wcag",
        "compose_layers",
    ]
    params: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

class ImageOpsPlan(BaseModel):
    """A deterministic plan of image operations we intend to apply.
    This is NOT generation — just planned transforms (and can be executed later)."""
    steps: List[ImageOpStep] = Field(default_factory=list)
    input_packshot_uri: Optional[str] = None
    output_formats: List[str] = Field(default_factory=lambda: ["1080x1080"])
    provider: Optional[str] = None  # e.g. gemini image model or any future engine

# -----------------------------
# Render Instructions
# -----------------------------

class RenderInstruction(BaseModel):
    """
    What the renderer (Pillow/Node canvas/etc.) should do.
    Deterministic, testable, and auditable.
    Converts layout spec → pixel-perfect rendering instructions.
    """
    format: ImageFormat
    background: Dict[str, Any] = Field(default_factory=dict)
    layers: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

# -----------------------------
# ImageOps Result
# -----------------------------

class ImageOpsResult(BaseModel):
    """What the ImageOps agent returns to the master graph.
    
    Combines both:
    - transform_plan: How to prep source images (remove_bg, resize, etc.)
    - render_plan: How to compose final creative (layer positions, styles, etc.)
    """
    transform_plan: ImageOpsPlan
    render_plan: RenderInstruction
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)  # keep aligned with your existing Artifact dicts
    debug: Dict[str, Any] = Field(default_factory=dict)
