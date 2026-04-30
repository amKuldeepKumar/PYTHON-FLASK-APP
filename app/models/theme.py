"""
Fluencify Theme Engine
--------------------------------------
This file controls the dynamic theme system.

PHASE 7
Base theme engine + CSS token system

PHASE 10
Theme activation + theme duplication support

PHASE 11
Advanced theme builder
(background engine, glass engine, component styling)
"""

from __future__ import annotations

from datetime import datetime

from app.extensions import db


# ==========================================================
# PHASE 7
# Theme Database Model
# Stores theme configuration in database
# ==========================================================

class Theme(db.Model):
    __tablename__ = "themes"

    # ------------------------------------------------------
    # Core identifiers
    # ------------------------------------------------------

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # ------------------------------------------------------
    # Core color tokens
    # ------------------------------------------------------

    bg = db.Column(db.String(32), default="#0b1220")
    surface = db.Column(db.String(32), default="#0f1a2c")
    surface_2 = db.Column(db.String(32), default="#0c1628")

    border = db.Column(db.String(64), default="rgba(255,255,255,.08)")
    text = db.Column(db.String(64), default="rgba(255,255,255,.92)")
    muted = db.Column(db.String(64), default="rgba(255,255,255,.62)")

    primary = db.Column(db.String(32), default="#0d6efd")

    shadow = db.Column(db.String(128), default="0 12px 30px rgba(0,0,0,.45)")
    radius = db.Column(db.String(16), default="16px")

    input_bg = db.Column(db.String(64), default="rgba(255,255,255,.04)")
    input_border = db.Column(db.String(64), default="rgba(255,255,255,.10)")

    css_overrides = db.Column(db.Text, default="")

    # Typography engine
    font_family = db.Column(db.String(255), default="Segoe UI, Arial, Helvetica, sans-serif")
    heading_font_family = db.Column(db.String(255), default="Bahnschrift, Segoe UI, Arial, Helvetica, sans-serif")
    accent_font_family = db.Column(db.String(255), default="Consolas, Cascadia Mono, SFMono-Regular, Menlo, monospace")

    # ======================================================
    # PHASE 11
    # Background Engine
    # ======================================================

    background_mode = db.Column(db.String(24), default="solid")
    background_image_url = db.Column(db.String(512), default="")

    gradient_start = db.Column(db.String(32), default="#06111f")
    gradient_end = db.Column(db.String(32), default="#0f2238")

    parallax_enabled = db.Column(db.Boolean, default=False)
    fluid_enabled = db.Column(db.Boolean, default=False)
    noise_overlay_enabled = db.Column(db.Boolean, default=False)
    alphabet_background_enabled = db.Column(db.Boolean, default=False)
    alphabet_trails_enabled = db.Column(db.Boolean, default=True)
    alphabet_rotation_depth = db.Column(db.Integer, default=60)
    alphabet_speed = db.Column(db.Integer, default=100)
    alphabet_min_size = db.Column(db.Integer, default=18)
    alphabet_max_size = db.Column(db.Integer, default=66)
    alphabet_count = db.Column(db.Integer, default=64)
    alphabet_motion_mode = db.Column(db.String(24), default="float")
    alphabet_direction_x = db.Column(db.Integer, default=0)
    alphabet_direction_y = db.Column(db.Integer, default=100)
    alphabet_opacity = db.Column(db.Integer, default=82)
    alphabet_trail_length = db.Column(db.Integer, default=14)
    alphabet_tilt_x = db.Column(db.Integer, default=18)
    alphabet_tilt_y = db.Column(db.Integer, default=12)
    alphabet_tilt_z = db.Column(db.Integer, default=30)
    alphabet_outline_only = db.Column(db.Boolean, default=False)
    alphabet_outline_color = db.Column(db.String(64), default="#ffffff")
    header_sticky_enabled = db.Column(db.Boolean, default=False)
    header_transparent_enabled = db.Column(db.Boolean, default=False)

    # ======================================================
    # PHASE 11
    # Effects Engine
    # ======================================================

    glass_level = db.Column(db.String(24), default="off")
    glow_intensity = db.Column(db.Integer, default=0)
    blur_strength = db.Column(db.Integer, default=0)

    hover_style = db.Column(db.String(24), default="subtle")
    motion_level = db.Column(db.String(24), default="normal")

    # ======================================================
    # PHASE 11
    # Icon system
    # ======================================================

    icon_style = db.Column(db.String(32), default="bootstrap")
    icon_glow = db.Column(db.Boolean, default=False)

    heading_text = db.Column(db.String(64), default="rgba(255,255,255,.92)")
    workspace_kicker_text = db.Column(db.String(64), default="rgba(255,255,255,.62)")
    workspace_kicker_size = db.Column(db.String(16), default=".75rem")
    workspace_kicker_weight = db.Column(db.String(16), default="700")

    page_title_size = db.Column(db.String(16), default="2rem")
    page_title_weight = db.Column(db.String(16), default="800")
    page_title_transform = db.Column(db.String(16), default="none")
    page_title_spacing = db.Column(db.String(16), default="0")

    fluid_color_1 = db.Column(db.String(32), default="#00b7ff")
    fluid_color_2 = db.Column(db.String(32), default="#7c3aed")
    fluid_color_3 = db.Column(db.String(32), default="#00f5d4")

    badge_bg = db.Column(db.String(64), default="rgba(255,255,255,.08)")
    badge_text = db.Column(db.String(64), default="#ffffff")
    badge_border = db.Column(db.String(64), default="rgba(255,255,255,.12)")

    # ======================================================
    # PHASE 11
    # Component engine
    # ======================================================

    button_shape = db.Column(db.String(24), default="rounded")
    button_radius = db.Column(db.String(16), default="12px")

    card_style = db.Column(db.String(32), default="glass-dark")
    table_style = db.Column(db.String(32), default="dark-modern")

    # ======================================================
    # Theme activation
    # ======================================================

    is_active = db.Column(db.Boolean, default=False, index=True)

    # ======================================================
    # timestamps
    # ======================================================

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # ======================================================
    # PHASE 10
    # Ensure a default theme exists
    # ======================================================

    @classmethod
    def ensure_default(cls):

        active = cls.query.filter_by(is_active=True).first()
        if active:
            return active

        first = cls.query.order_by(cls.id.asc()).first()

        if first:
            first.is_active = True
            db.session.commit()
            return first

        theme = cls(
            name="AI Dark",
            is_active=True
        )

        db.session.add(theme)
        db.session.commit()

        return theme

    # ======================================================
    # Utility
    # safe css value loader
    # ======================================================

    def _css_value(self, field_name: str, default: str) -> str:

        value = getattr(self, field_name, None)

        if value is None:
            return default

        if isinstance(value, str) and not value.strip():
            return default

        return str(value)

    # ======================================================
    # PHASE 7
    # Convert theme database values to CSS variables
    # ======================================================

    def to_css_tokens(self) -> str:

        bg = self._css_value("bg", "#06111f")
        surface = self._css_value("surface", "#0b1a2c")
        surface_2 = self._css_value("surface_2", "#0f2238")

        border = self._css_value("border", "rgba(255,255,255,.08)")
        text = self._css_value("text", "rgba(255,255,255,.92)")
        muted = self._css_value("muted", "rgba(255,255,255,.62)")

        primary = self._css_value("primary", "#0d6efd")

        radius = self._css_value("radius", "16px")
        shadow = self._css_value("shadow", "0 12px 30px rgba(0,0,0,.45)")

        input_bg = self._css_value("input_bg", "rgba(255,255,255,.04)")
        input_border = self._css_value("input_border", "rgba(255,255,255,.10)")

        font_family = self._css_value("font_family", "Segoe UI, Arial, Helvetica, sans-serif")
        heading_font_family = self._css_value("heading_font_family", font_family)
        accent_font_family = self._css_value("accent_font_family", "Consolas, Cascadia Mono, SFMono-Regular, Menlo, monospace")

        background_mode = self._css_value("background_mode", "solid")
        background_image_url = self._css_value("background_image_url", "")

        gradient_start = self._css_value("gradient_start", bg)
        gradient_end = self._css_value("gradient_end", surface_2)

        heading_text = self._css_value("heading_text", text)
        workspace_kicker_text = self._css_value("workspace_kicker_text", muted)
        workspace_kicker_size = self._css_value("workspace_kicker_size", ".75rem")
        workspace_kicker_weight = self._css_value("workspace_kicker_weight", "700")

        page_title_size = self._css_value("page_title_size", "2rem")
        page_title_weight = self._css_value("page_title_weight", "800")
        page_title_transform = self._css_value("page_title_transform", "none")
        page_title_spacing = self._css_value("page_title_spacing", "0")

        fluid_color_1 = self._css_value("fluid_color_1", primary)
        fluid_color_2 = self._css_value("fluid_color_2", gradient_start)
        fluid_color_3 = self._css_value("fluid_color_3", gradient_end)

        badge_bg = self._css_value("badge_bg", "rgba(255,255,255,.08)")
        badge_text = self._css_value("badge_text", text)
        badge_border = self._css_value("badge_border", border)
        button_radius = self._css_value("button_radius", radius)

        alphabet_background_enabled = "1" if bool(getattr(self, "alphabet_background_enabled", False)) else "0"
        alphabet_trails_enabled = "1" if bool(getattr(self, "alphabet_trails_enabled", True)) else "0"
        alphabet_rotation_depth = self._css_value("alphabet_rotation_depth", "60")
        alphabet_speed = self._css_value("alphabet_speed", "100")
        alphabet_min_size = self._css_value("alphabet_min_size", "18")
        alphabet_max_size = self._css_value("alphabet_max_size", "66")
        alphabet_count = self._css_value("alphabet_count", "64")
        alphabet_motion_mode = self._css_value("alphabet_motion_mode", "float")
        alphabet_direction_x = self._css_value("alphabet_direction_x", "0")
        alphabet_direction_y = self._css_value("alphabet_direction_y", "100")
        alphabet_opacity = self._css_value("alphabet_opacity", "82")
        alphabet_trail_length = self._css_value("alphabet_trail_length", "14")
        alphabet_tilt_x = self._css_value("alphabet_tilt_x", "18")
        alphabet_tilt_y = self._css_value("alphabet_tilt_y", "12")
        alphabet_tilt_z = self._css_value("alphabet_tilt_z", "30")
        alphabet_outline_only = "1" if bool(getattr(self, "alphabet_outline_only", False)) else "0"
        alphabet_outline_color = self._css_value("alphabet_outline_color", "#ffffff")
        header_sticky_enabled = "1" if bool(getattr(self, "header_sticky_enabled", False)) else "0"
        header_transparent_enabled = "1" if bool(getattr(self, "header_transparent_enabled", False)) else "0"

        light_bg = "#f3f6fb"
        light_surface = "#ffffff"
        light_surface_2 = "#ffffff"
        light_border = "rgba(0,0,0,.10)"
        light_text = "rgba(0,0,0,.88)"
        light_muted = "rgba(0,0,0,.55)"
        light_shadow = "0 12px 30px rgba(15,23,42,.10)"
        light_input_bg = "rgba(0,0,0,.03)"
        light_input_border = "rgba(0,0,0,.14)"
        light_heading_text = light_text
        light_workspace_kicker_text = light_muted
        light_badge_bg = "rgba(13,110,253,.10)"
        light_badge_text = light_text
        light_badge_border = "rgba(13,110,253,.18)"

        if background_mode == "gradient":
            body_background = f"linear-gradient(135deg,{gradient_start},{gradient_end})"

        elif background_mode == "image" and background_image_url:
            body_background = f"url('{background_image_url}') center / cover no-repeat fixed"

        elif background_mode == "fluid":
            body_background = (
                f"radial-gradient(circle at top left,{fluid_color_1},transparent 25%),"
                f"radial-gradient(circle at top right,{fluid_color_2},transparent 25%),"
                f"radial-gradient(circle at bottom center,{fluid_color_3},transparent 30%),"
                f"{bg}"
            )

        else:
            body_background = bg

        light_body_background = light_bg

        return f"""
:root {{

--bg:{bg};
--surface:{surface};
--surface-2:{surface_2};

--border:{border};

--text:{text};
--muted:{muted};

--primary:{primary};

--radius:{radius};
--shadow:{shadow};

--input-bg:{input_bg};
--input-border:{input_border};

--font-family:{font_family};
--heading-font-family:{heading_font_family};
--accent-font-family:{accent_font_family};

--heading-text:{heading_text};
--workspace-kicker-text:{workspace_kicker_text};
--workspace-kicker-size:{workspace_kicker_size};
--workspace-kicker-weight:{workspace_kicker_weight};

--page-title-size:{page_title_size};
--page-title-weight:{page_title_weight};
--page-title-transform:{page_title_transform};
--page-title-spacing:{page_title_spacing};

--badge-bg:{badge_bg};
--badge-text:{badge_text};
--badge-border:{badge_border};

--fluid-color-1:{fluid_color_1};
--fluid-color-2:{fluid_color_2};
--fluid-color-3:{fluid_color_3};
--background-mode:{background_mode};
--gradient-start:{gradient_start};
--gradient-end:{gradient_end};
--body-background:{body_background};
--button-radius:{button_radius};
--alphabet-background-enabled:{alphabet_background_enabled};
--alphabet-trails-enabled:{alphabet_trails_enabled};
--alphabet-rotation-depth:{alphabet_rotation_depth};
--alphabet-speed:{alphabet_speed};
--alphabet-min-size:{alphabet_min_size};
--alphabet-max-size:{alphabet_max_size};
--alphabet-count:{alphabet_count};
--alphabet-motion-mode:{alphabet_motion_mode};
--alphabet-direction-x:{alphabet_direction_x};
--alphabet-direction-y:{alphabet_direction_y};
--alphabet-opacity:{alphabet_opacity};
--alphabet-trail-length:{alphabet_trail_length};
--alphabet-tilt-x:{alphabet_tilt_x};
--alphabet-tilt-y:{alphabet_tilt_y};
--alphabet-tilt-z:{alphabet_tilt_z};
--alphabet-outline-only:{alphabet_outline_only};
--alphabet-outline-color:{alphabet_outline_color};
--header-sticky-enabled:{header_sticky_enabled};
--header-transparent-enabled:{header_transparent_enabled};

}}

html[data-theme="dark"] {{
--bg:{bg};
--surface:{surface};
--surface-2:{surface_2};
--border:{border};
--text:{text};
--muted:{muted};
--primary:{primary};
--radius:{radius};
--shadow:{shadow};
--input-bg:{input_bg};
--input-border:{input_border};
--font-family:{font_family};
--heading-font-family:{heading_font_family};
--accent-font-family:{accent_font_family};
--heading-text:{heading_text};
--workspace-kicker-text:{workspace_kicker_text};
--workspace-kicker-size:{workspace_kicker_size};
--workspace-kicker-weight:{workspace_kicker_weight};
--page-title-size:{page_title_size};
--page-title-weight:{page_title_weight};
--page-title-transform:{page_title_transform};
--page-title-spacing:{page_title_spacing};
--badge-bg:{badge_bg};
--badge-text:{badge_text};
--badge-border:{badge_border};
--fluid-color-1:{fluid_color_1};
--fluid-color-2:{fluid_color_2};
--fluid-color-3:{fluid_color_3};
--background-mode:{background_mode};
--gradient-start:{gradient_start};
--gradient-end:{gradient_end};
--body-background:{body_background};
--button-radius:{button_radius};
--alphabet-background-enabled:{alphabet_background_enabled};
--alphabet-trails-enabled:{alphabet_trails_enabled};
--alphabet-rotation-depth:{alphabet_rotation_depth};
--alphabet-speed:{alphabet_speed};
--alphabet-min-size:{alphabet_min_size};
--alphabet-max-size:{alphabet_max_size};
--alphabet-count:{alphabet_count};
--alphabet-motion-mode:{alphabet_motion_mode};
--alphabet-direction-x:{alphabet_direction_x};
--alphabet-direction-y:{alphabet_direction_y};
--alphabet-opacity:{alphabet_opacity};
--alphabet-trail-length:{alphabet_trail_length};
--alphabet-tilt-x:{alphabet_tilt_x};
--alphabet-tilt-y:{alphabet_tilt_y};
--alphabet-tilt-z:{alphabet_tilt_z};
--alphabet-outline-only:{alphabet_outline_only};
--alphabet-outline-color:{alphabet_outline_color};
--header-sticky-enabled:{header_sticky_enabled};
--header-transparent-enabled:{header_transparent_enabled};
}}

html[data-theme="light"] {{
--bg:{light_bg};
--surface:{light_surface};
--surface-2:{light_surface_2};
--border:{light_border};
--text:{light_text};
--muted:{light_muted};
--primary:{primary};
--radius:{radius};
--shadow:{light_shadow};
--input-bg:{light_input_bg};
--input-border:{light_input_border};
--font-family:{font_family};
--heading-font-family:{heading_font_family};
--accent-font-family:{accent_font_family};
--heading-text:{light_heading_text};
--workspace-kicker-text:{light_workspace_kicker_text};
--workspace-kicker-size:{workspace_kicker_size};
--workspace-kicker-weight:{workspace_kicker_weight};
--page-title-size:{page_title_size};
--page-title-weight:{page_title_weight};
--page-title-transform:{page_title_transform};
--page-title-spacing:{page_title_spacing};
--badge-bg:{light_badge_bg};
--badge-text:{light_badge_text};
--badge-border:{light_badge_border};
--fluid-color-1:{fluid_color_1};
--fluid-color-2:{fluid_color_2};
--fluid-color-3:{fluid_color_3};
--background-mode:{background_mode};
--gradient-start:{gradient_start};
--gradient-end:{gradient_end};
--body-background:{light_body_background};
--button-radius:{button_radius};
--alphabet-background-enabled:{alphabet_background_enabled};
--alphabet-trails-enabled:{alphabet_trails_enabled};
--alphabet-rotation-depth:{alphabet_rotation_depth};
--alphabet-speed:{alphabet_speed};
--alphabet-min-size:{alphabet_min_size};
--alphabet-max-size:{alphabet_max_size};
--alphabet-count:{alphabet_count};
--alphabet-motion-mode:{alphabet_motion_mode};
--alphabet-direction-x:{alphabet_direction_x};
--alphabet-direction-y:{alphabet_direction_y};
--alphabet-opacity:{alphabet_opacity};
--alphabet-trail-length:{alphabet_trail_length};
--alphabet-tilt-x:{alphabet_tilt_x};
--alphabet-tilt-y:{alphabet_tilt_y};
--alphabet-tilt-z:{alphabet_tilt_z};
--alphabet-outline-only:{alphabet_outline_only};
--alphabet-outline-color:{alphabet_outline_color};
--header-sticky-enabled:{header_sticky_enabled};
--header-transparent-enabled:{header_transparent_enabled};
}}

html, body {{
color:var(--text) !important;
font-family: var(--font-family) !important;
}}

html[data-theme="dark"], html[data-theme="dark"] body {{
background:{body_background} !important;
}}

html[data-theme="light"], html[data-theme="light"] body {{
background:{light_body_background} !important;
}}

button, input, select, textarea, .btn, .badge, .chip, code, pre {{
font-family: var(--font-family) !important;
}}

h1, h2, h3, h4, h5, h6 {{
color: var(--heading-text) !important;
font-family: var(--heading-font-family) !important;
}}

.fw-semibold,
.fw-bold,
.card-title,
.section-title,
.page-title {{
color: var(--heading-text) !important;
}}

.topbar-kicker {{
color: var(--workspace-kicker-text) !important;
font-family: var(--accent-font-family) !important;
font-size: var(--workspace-kicker-size) !important;
font-weight: var(--workspace-kicker-weight) !important;
}}

.topbar-page-title {{
color: var(--heading-text) !important;
font-size: var(--page-title-size) !important;
font-weight: var(--page-title-weight) !important;
text-transform: var(--page-title-transform) !important;
letter-spacing: var(--page-title-spacing) !important;
line-height: 1.1;
}}

.text-muted,
.small.text-muted,
.form-text,
.text-secondary,
small.text-muted {{
color: var(--muted) !important;
opacity: 1 !important;
}}

.badge, .status-badge, .chip {{
background: var(--badge-bg) !important;
color: var(--badge-text) !important;
border: 1px solid var(--badge-border) !important;
}}

.card,
.modal-content,
.dropdown-menu,
.offcanvas {{
background:var(--surface) !important;
border:1px solid var(--border) !important;
border-radius:var(--radius);
}}

.form-control,
.form-select {{
background:var(--input-bg) !important;
color:var(--text) !important;
border-color:var(--input-border) !important;
}}

.form-label,
label {{
color: var(--heading-text) !important;
}}

.btn-primary {{
background:var(--primary) !important;
border-color:var(--primary) !important;
}}

.btn-outline-light {{
border-color: var(--border) !important;
color: var(--text) !important;
}}

.btn-outline-light:hover {{
background: var(--surface-2) !important;
color: var(--heading-text) !important;
}}

::selection {{
background-color:var(--primary);
color:#ffffff;
}}
""".strip()
