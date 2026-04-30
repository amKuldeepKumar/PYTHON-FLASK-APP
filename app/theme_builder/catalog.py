from __future__ import annotations

from .features import (
    ThemeFeatureGroup,
    ThemeField,
    BACKGROUND_MODE_OPTIONS,
    ICON_STYLE_OPTIONS,
    BUTTON_SHAPE_OPTIONS,
    HOVER_STYLE_OPTIONS,
    GLASS_LEVEL_OPTIONS,
    MOTION_LEVEL_OPTIONS,
)


def get_feature_groups() -> list[ThemeFeatureGroup]:
    return [
        ThemeFeatureGroup(
            key="core",
            label="Core Theme",
            description="Base identity, palette, and surface styling.",
            phase="live",
            fields=(
                ThemeField("name", "Theme Name", "text", required=True, help_text="Friendly theme preset name."),
                ThemeField("primary", "Primary Color", "color", default="#0d6efd"),
                ThemeField("bg", "Background Color", "color", default="#06111f"),
                ThemeField("surface", "Surface Color", "color", default="#0b1a2c"),
                ThemeField("surface_2", "Surface 2", "color", default="#0f2238"),
                ThemeField("text", "Text Color", "text", default="rgba(255,255,255,.92)"),
                ThemeField("muted", "Muted Text", "text", default="rgba(255,255,255,.62)"),
                ThemeField("border", "Border", "text", default="rgba(255,255,255,.08)"),
                ThemeField("radius", "Radius", "text", default="16px"),
                ThemeField("shadow", "Shadow", "text", default="0 12px 30px rgba(0,0,0,.45)"),
                ThemeField("font_family", "Body Font Family", "text", default="Segoe UI, Arial, Helvetica, sans-serif"),
                ThemeField("heading_font_family", "Heading Font Family", "text", default="Bahnschrift, Segoe UI, Arial, Helvetica, sans-serif"),
                ThemeField("accent_font_family", "Accent Font Family", "text", default="Consolas, Cascadia Mono, SFMono-Regular, Menlo, monospace"),
            ),
        ),
        ThemeFeatureGroup(
            key="background_engine",
            label="Background Engine",
            description="Controls solid, gradient, fluid, image, and parallax background modes.",
            phase="phase_11",
            fields=(
                ThemeField(
                    "background_mode",
                    "Background Mode",
                    "select",
                    default="solid",
                    options=BACKGROUND_MODE_OPTIONS,
                    help_text="Choose how the page background is rendered.",
                    phase="phase_11",
                ),
                ThemeField("background_image_url", "Background Image URL", "text", default="", phase="phase_11"),
                ThemeField("gradient_start", "Gradient Start", "color", default="#06111f", phase="phase_11"),
                ThemeField("gradient_end", "Gradient End", "color", default="#0f2238", phase="phase_11"),
                ThemeField("fluid_color_1", "Fluid Color 1", "color", default="#00b7ff", phase="phase_11"),
                ThemeField("fluid_color_2", "Fluid Color 2", "color", default="#7c3aed", phase="phase_11"),
                ThemeField("fluid_color_3", "Fluid Color 3", "color", default="#00f5d4", phase="phase_11"),
                ThemeField("parallax_enabled", "Enable Parallax", "boolean", default=False, phase="phase_11"),
                ThemeField("fluid_enabled", "Enable Fluid Background", "boolean", default=False, phase="phase_11"),
                ThemeField("noise_overlay_enabled", "Noise Overlay", "boolean", default=False, phase="phase_11"),
            ),
        ),
        ThemeFeatureGroup(
            key="effects_engine",
            label="Effects Engine",
            description="Glow, glass blur, hover style, and animation tuning.",
            phase="phase_11",
            fields=(
                ThemeField(
                    "glass_level",
                    "Glass Effect",
                    "select",
                    default="off",
                    options=GLASS_LEVEL_OPTIONS,
                    phase="phase_11",
                ),
                ThemeField("glow_intensity", "Glow Intensity", "range", default=0, phase="phase_11"),
                ThemeField("blur_strength", "Blur Strength", "range", default=0, phase="phase_11"),
                ThemeField(
                    "hover_style",
                    "Hover Style",
                    "select",
                    default="subtle",
                    options=HOVER_STYLE_OPTIONS,
                    phase="phase_11",
                ),
                ThemeField(
                    "motion_level",
                    "Motion Level",
                    "select",
                    default="normal",
                    options=MOTION_LEVEL_OPTIONS,
                    phase="phase_11",
                ),
            ),
        ),
        ThemeFeatureGroup(
            key="icons",
            label="Icon System",
            description="Professional and futuristic icon pack control.",
            phase="phase_11",
            fields=(
                ThemeField("icon_style", "Icon Style", "select", default="bootstrap", options=ICON_STYLE_OPTIONS, phase="phase_11"),
                ThemeField("icon_glow", "Icon Glow", "boolean", default=False, phase="phase_11"),
                ThemeField("heading_text", "Heading Text Color", "text", default="rgba(255,255,255,.92)", phase="phase_11"),
                ThemeField("workspace_kicker_text", "Workspace Kicker Color", "text", default="rgba(255,255,255,.62)", phase="phase_11"),
                ThemeField("workspace_kicker_size", "Workspace Kicker Size", "text", default=".75rem", phase="phase_11"),
                ThemeField("workspace_kicker_weight", "Workspace Kicker Weight", "text", default="700", phase="phase_11"),
                ThemeField("page_title_size", "Page Title Size", "text", default="2rem", phase="phase_11"),
                ThemeField("page_title_weight", "Page Title Weight", "text", default="800", phase="phase_11"),
                ThemeField("page_title_transform", "Page Title Transform", "text", default="none", phase="phase_11"),
                ThemeField("page_title_spacing", "Page Title Letter Spacing", "text", default="0", phase="phase_11"),
            ),
        ),
        ThemeFeatureGroup(
            key="components",
            label="Components",
            description="Buttons, cards, inputs, tables, badges, and UI blocks.",
            phase="phase_11",
            fields=(
                ThemeField(
                    "button_shape",
                    "Button Shape",
                    "select",
                    default="rounded",
                    options=BUTTON_SHAPE_OPTIONS,
                    phase="phase_11",
                ),
                ThemeField("button_radius", "Button Radius", "text", default="12px", phase="phase_11"),
                ThemeField("card_style", "Card Style", "text", default="glass-dark", phase="phase_11"),
                ThemeField("table_style", "Table Style", "text", default="dark-modern", phase="phase_11"),
                ThemeField("badge_bg", "Badge Background", "text", default="rgba(255,255,255,.08)", phase="phase_11"),
                ThemeField("badge_text", "Badge Text", "text", default="#ffffff", phase="phase_11"),
                ThemeField("badge_border", "Badge Border", "text", default="rgba(255,255,255,.12)", phase="phase_11"),
                ThemeField("input_bg", "Input Background", "text", default="rgba(255,255,255,.04)"),
                ThemeField("input_border", "Input Border", "text", default="rgba(255,255,255,.10)"),
            ),
        ),
        ThemeFeatureGroup(
            key="advanced",
            label="Advanced",
            description="Custom CSS and future extension points.",
            phase="live",
            fields=(
                ThemeField("css_overrides", "CSS Overrides", "textarea", default="", help_text="Optional custom CSS."),
            ),
        ),
    ]


def get_theme_builder_catalog() -> dict:
    groups = get_feature_groups()
    return {
        "version": "2.0",
        "label": "Theme Builder 2.0",
        "description": "Preset-driven futuristic theme builder for Fluencify.",
        "groups": groups,
    }
