from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------
# Core Types
# -----------------------------

Platform = Literal[
    "instagram_feed",      # 1080x1080
    "instagram_story",     # 1080x1920
    "facebook_feed",       # 1200x628 (common)
    "facebook_story",      # 1080x1920 (common)
    "custom",
]

CanvasFormat = Literal[
    "1080x1080",
    "1080x1920",
    "1200x628",
    "custom",
]

LayerType = Literal[
    "background",
    "packshot",
    "logo",
    "headline",
    "subhead",
    "cta",
    "value_tile",
    "badge",
    "legal",
]

Anchor = Literal[
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

FitMode = Literal["contain", "cover", "stretch"]

TextAlign = Literal["left", "center", "right"]

# -----------------------------
# Geometry / Zones
# -----------------------------

class RectN(BaseModel):
    """Normalized rect in 0..1 coordinate space relative to the canvas.
    (x,y) is center by default (because it composes better), not top-left."""
    model_config = ConfigDict(extra="forbid")
    
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., ge=0.0, le=1.0)
    h: float = Field(..., ge=0.0, le=1.0)

class SafeZones(BaseModel):
    """Margins from each edge (normalized 0..1).
    Everything "critical" (logo, headline, CTA, price/value tile) should be inside."""
    model_config = ConfigDict(extra="forbid")
    
    top: float = Field(default=0.06, ge=0.0, le=0.5)
    bottom: float = Field(default=0.10, ge=0.0, le=0.5)
    left: float = Field(default=0.05, ge=0.0, le=0.5)
    right: float = Field(default=0.05, ge=0.0, le=0.5)

class ZoneSpec(BaseModel):
    """Named zones help layout and compliance reason in a deterministic way.
    Example zones: "title_zone", "cta_zone", "packshot_zone"."""
    model_config = ConfigDict(extra="forbid")
    
    name: str
    rect: RectN
    notes: List[str] = Field(default_factory=list)

# -----------------------------
# Layer Specs
# -----------------------------

class BaseLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    id: str
    type: LayerType
    z: int = Field(default=10, ge=0, le=100)
    anchor: Anchor = "center"
    rect: RectN
    rotation_deg: float = Field(default=0.0, ge=-30.0, le=30.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    locked: bool = False                 # when user says "keep logo fixed"
    critical: bool = True                # must be inside safe zones
    meta: Dict[str, str] = Field(default_factory=dict)

class ImageLayer(BaseLayer):
    model_config = ConfigDict(extra="forbid")
    
    fit: FitMode = "contain"
    asset_ref: Optional[str] = None      # e.g. "packshot", "brand_logo", "bg_1"

class TextStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    font_family: str = "Inter"
    font_weight: int = Field(default=700, ge=100, le=900)
    align: TextAlign = "center"
    color: str = "#111111"               # hex
    stroke_color: Optional[str] = None   # optional outline for contrast
    stroke_width_px: int = Field(default=0, ge=0, le=12)
    max_lines: int = Field(default=2, ge=1, le=6)
    letter_spacing: float = Field(default=0.0, ge=-2.0, le=10.0)

class TextLayer(BaseLayer):
    model_config = ConfigDict(extra="forbid")
    
    text: str
    style: TextStyle = Field(default_factory=TextStyle)

class ValueTileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    kind: Literal["price", "promo", "award", "info"] = "promo"
    bg_color: str = "#FFD54F"
    text_color: str = "#111111"
    corner_radius_px: int = Field(default=18, ge=0, le=80)
    border_px: int = Field(default=0, ge=0, le=20)

class ValueTileLayer(TextLayer):
    model_config = ConfigDict(extra="forbid")
    
    tile: ValueTileSpec = Field(default_factory=ValueTileSpec)

# -----------------------------
# Layout Spec
# -----------------------------

class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    platform: Platform
    format: CanvasFormat
    width: int
    height: int
    safe_zones: SafeZones = Field(default_factory=SafeZones)
    zones: List[ZoneSpec] = Field(default_factory=list)
    background: Dict[str, str] = Field(default_factory=dict)  # e.g. {"style":"solid","value":"#F7F7FB"}
    layers: List[BaseLayer] = Field(default_factory=list)
    
    # Useful for stateful edits: keep intent across re-prompts
    intent: Dict[str, str] = Field(default_factory=dict)      # e.g. {"layout_style":"clean","packshot_priority":"high"}
    notes: List[str] = Field(default_factory=list)

class LayoutOutput(BaseModel):
    """What the Layout Planner Agent produces."""
    model_config = ConfigDict(extra="forbid")
    
    decision: Literal["OK", "WARN"] = "OK"
    warnings: List[str] = Field(default_factory=list)
    spec: LayoutSpec
