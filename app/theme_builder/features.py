from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ThemeOption:
    key: str
    label: str
    value: str


@dataclass(frozen=True)
class ThemeField:
    key: str
    label: str
    field_type: str
    default: Any = None
    help_text: str = ""
    phase: str = "live"
    options: tuple[ThemeOption, ...] = field(default_factory=tuple)
    required: bool = False


@dataclass(frozen=True)
class ThemeFeatureGroup:
    key: str
    label: str
    description: str
    phase: str
    fields: tuple[ThemeField, ...]


BACKGROUND_MODE_OPTIONS = (
    ThemeOption("solid", "Solid Color", "solid"),
    ThemeOption("gradient", "Gradient", "gradient"),
    ThemeOption("fluid", "Fluid Animated Gradient", "fluid"),
    ThemeOption("image", "Image Background", "image"),
    ThemeOption("parallax", "Parallax Background", "parallax"),
)

ICON_STYLE_OPTIONS = (
    ThemeOption("bootstrap", "Bootstrap Icons", "bootstrap"),
    ThemeOption("futuristic-outline", "Futuristic Outline", "futuristic-outline"),
    ThemeOption("futuristic-filled", "Futuristic Filled", "futuristic-filled"),
    ThemeOption("neon", "Neon Icon Style", "neon"),
)

BUTTON_SHAPE_OPTIONS = (
    ThemeOption("rounded", "Rounded", "rounded"),
    ThemeOption("pill", "Pill", "pill"),
    ThemeOption("sharp", "Sharp", "sharp"),
    ThemeOption("glass", "Glass", "glass"),
)

HOVER_STYLE_OPTIONS = (
    ThemeOption("subtle", "Subtle Hover", "subtle"),
    ThemeOption("lift", "Lift on Hover", "lift"),
    ThemeOption("glow", "Glow Hover", "glow"),
    ThemeOption("slide", "Slide Highlight", "slide"),
)

GLASS_LEVEL_OPTIONS = (
    ThemeOption("off", "Off", "off"),
    ThemeOption("low", "Low", "low"),
    ThemeOption("medium", "Medium", "medium"),
    ThemeOption("high", "High", "high"),
)

MOTION_LEVEL_OPTIONS = (
    ThemeOption("reduced", "Reduced Motion", "reduced"),
    ThemeOption("normal", "Normal Motion", "normal"),
    ThemeOption("high", "High Motion", "high"),
)