# D:\fluencify\app\blueprints\theme\routes.py

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.audit import audit
from app.extensions import db
from app.models.theme import Theme
from app.rbac import require_perm, require_role

from . import bp

from app.theme_builder import (
    get_theme_builder_catalog,
    BUILTIN_PRESETS,
    theme_to_builder_payload,
    apply_builder_payload_to_theme,
    validate_builder_payload,
)


# ==========================================================
# Internal helpers
# ==========================================================

def _fallback_theme() -> Theme:
    return Theme(
        name="Fallback Theme",
        bg="#0b1220",
        surface="#0f1a2c",
        surface_2="#0c1628",
        border="rgba(255,255,255,.08)",
        text="rgba(255,255,255,.92)",
        muted="rgba(255,255,255,.62)",
        primary="#0d6efd",
        shadow="0 12px 30px rgba(0,0,0,.45)",
        radius="16px",
        input_bg="rgba(255,255,255,.04)",
        input_border="rgba(255,255,255,.10)",
        css_overrides="",
        is_active=True,
    )


def _recover_theme_schema() -> None:
    try:
        from app.schema_bootstrap import ensure_dev_sqlite_schema

        ensure_dev_sqlite_schema()
        db.session.remove()
    except Exception:
        pass


def _get_active_theme() -> Theme:
    """
    Return the current active theme.
    If none is active yet, make sure a default theme exists.
    """
    try:
        theme = Theme.query.filter_by(is_active=True).first()
        if not theme:
            theme = Theme.ensure_default()
        return theme
    except SQLAlchemyError:
        _recover_theme_schema()
        try:
            theme = Theme.query.filter_by(is_active=True).first()
            if not theme:
                theme = Theme.ensure_default()
            return theme
        except SQLAlchemyError:
            return _fallback_theme()


def _safe_audit(action: str, target: str = "", meta: str = "") -> None:
    """
    Audit wrapper that never breaks the request flow.
    """
    try:
        audit(action, target=target, meta=meta)
    except Exception:
        pass


# ==========================================================
# Public CSS endpoints
# ==========================================================

@bp.get("/tokens.css")
def tokens_css():
    """
    Dynamic CSS tokens generated from active theme values.
    """
    return Response(_get_active_theme().to_css_tokens(), mimetype="text/css")


@bp.get("/overrides.css")
def overrides_css():
    """
    Optional custom CSS overrides saved with the active theme.
    """
    try:
        return Response(_get_active_theme().css_overrides or "", mimetype="text/css")
    except Exception:
        return Response("", mimetype="text/css")


# ==========================================================
# Theme management pages
# ==========================================================

@bp.get("/manage")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def manage_themes():
    """
    Theme listing screen for SuperAdmin / SEO.
    """
    Theme.ensure_default()
    themes = Theme.query.order_by(Theme.is_active.desc(), Theme.name.asc()).all()
    return render_template("superadmin/themes.html", themes=themes)


@bp.post("/manage/create")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def create_theme():
    """
    Create a new theme shell with a unique name.
    """
    name = (request.form.get("name") or "").strip()

    if not name:
        flash("Theme name required.", "danger")
        return redirect(url_for("theme.manage_themes"))

    if Theme.query.filter_by(name=name).first():
        flash("Theme name already exists.", "warning")
        return redirect(url_for("theme.manage_themes"))

    theme = Theme(name=name)
    db.session.add(theme)
    db.session.commit()

    _safe_audit("theme_create", target=str(theme.id), meta=theme.name)
    flash("Theme created.", "success")
    return redirect(url_for("theme.manage_themes"))


@bp.get("/manage/<int:theme_id>/edit")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def edit_theme(theme_id: int):
    """
    Open theme builder edit page.
    """
    theme = Theme.query.get_or_404(theme_id)

    catalog = get_theme_builder_catalog()
    builder_payload = theme_to_builder_payload(theme)

    return render_template(
        "superadmin/theme_edit.html",
        theme=theme,
        catalog=catalog,
        builder=builder_payload,
        presets=BUILTIN_PRESETS,
    )


@bp.post("/manage/<int:theme_id>/edit")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def update_theme(theme_id: int):
    """
    Save theme builder values back into the Theme model.
    Handles booleans and integers safely before validation.
    """
    theme = Theme.query.get_or_404(theme_id)

    payload = request.form.to_dict()

    # ------------------------------------------------------
    # Checkbox / boolean fields
    # HTML checkboxes send "on"/"1" only when checked.
    # We convert them into real Python booleans here.
    # ------------------------------------------------------
    boolean_fields = {
        "parallax_enabled",
        "fluid_enabled",
        "noise_overlay_enabled",
        "alphabet_background_enabled",
        "alphabet_trails_enabled",
        "alphabet_outline_only",
        "header_sticky_enabled",
        "header_transparent_enabled",
        "icon_glow",
    }

    # ------------------------------------------------------
    # Integer / slider fields
    # Convert numeric strings into integers before save.
    # ------------------------------------------------------
    integer_fields = {
        "glow_intensity",
        "blur_strength",
        "alphabet_rotation_depth",
        "alphabet_speed",
        "alphabet_min_size",
        "alphabet_max_size",
        "alphabet_count",
        "alphabet_direction_x",
        "alphabet_direction_y",
        "alphabet_opacity",
        "alphabet_trail_length",
        "alphabet_tilt_x",
        "alphabet_tilt_y",
        "alphabet_tilt_z",
    }

    for field in boolean_fields:
        payload[field] = field in request.form

    for field in integer_fields:
        value = payload.get(field)
        payload[field] = int(value) if value not in (None, "") else 0

    # ------------------------------------------------------
    # Validate payload
    # ------------------------------------------------------
    errors = validate_builder_payload(payload)

    # ------------------------------------------------------
    # Enforce unique theme name
    # ------------------------------------------------------
    name = (payload.get("name") or "").strip()
    if name:
        duplicate = Theme.query.filter(Theme.name == name, Theme.id != theme.id).first()
        if duplicate:
            errors["name"] = "Another theme already uses that name."

    if errors:
        for err in errors.values():
            flash(err, "danger")
        return redirect(url_for("theme.edit_theme", theme_id=theme.id))

    # ------------------------------------------------------
    # Apply payload and save
    # ------------------------------------------------------
    apply_builder_payload_to_theme(theme, payload)
    db.session.commit()

    _safe_audit("theme_update", target=str(theme.id), meta=theme.name)
    flash("Theme updated successfully.", "success")
    return redirect(url_for("theme.manage_themes"))


@bp.post("/manage/<int:theme_id>/activate")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def activate_theme(theme_id: int):
    """
    Mark one theme as active and deactivate all others.
    """
    theme = Theme.query.get_or_404(theme_id)

    Theme.query.update({Theme.is_active: False})
    theme.is_active = True
    db.session.commit()

    _safe_audit("theme_activate", target=str(theme.id), meta=theme.name)
    flash("Theme activated.", "success")
    return redirect(url_for("theme.manage_themes"))


@bp.post("/manage/<int:theme_id>/duplicate")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def duplicate_theme(theme_id: int):
    """
    Duplicate an existing theme, including advanced futuristic fields.
    """
    theme = Theme.query.get_or_404(theme_id)

    base_name = f"{theme.name} Copy"
    name = base_name
    counter = 2

    while Theme.query.filter_by(name=name).first():
        name = f"{base_name} {counter}"
        counter += 1

    clone = Theme(
        name=name,
        bg=theme.bg,
        surface=theme.surface,
        surface_2=theme.surface_2,
        border=theme.border,
        text=theme.text,
        muted=theme.muted,
        primary=theme.primary,
        shadow=theme.shadow,
        radius=theme.radius,
        input_bg=theme.input_bg,
        input_border=theme.input_border,
        css_overrides=theme.css_overrides,
        font_family=theme.font_family,
        heading_font_family=theme.heading_font_family,
        accent_font_family=theme.accent_font_family,
        background_mode=theme.background_mode,
        background_image_url=theme.background_image_url,
        gradient_start=theme.gradient_start,
        gradient_end=theme.gradient_end,
        parallax_enabled=theme.parallax_enabled,
        fluid_enabled=theme.fluid_enabled,
        noise_overlay_enabled=theme.noise_overlay_enabled,
        alphabet_background_enabled=theme.alphabet_background_enabled,
        alphabet_trails_enabled=getattr(theme, "alphabet_trails_enabled", True),
        alphabet_rotation_depth=getattr(theme, "alphabet_rotation_depth", 60),
        alphabet_speed=getattr(theme, "alphabet_speed", 100),
        alphabet_min_size=getattr(theme, "alphabet_min_size", 18),
        alphabet_max_size=getattr(theme, "alphabet_max_size", 66),
        alphabet_count=getattr(theme, "alphabet_count", 64),
        alphabet_motion_mode=getattr(theme, "alphabet_motion_mode", "float"),
        alphabet_direction_x=getattr(theme, "alphabet_direction_x", 0),
        alphabet_direction_y=getattr(theme, "alphabet_direction_y", 100),
        alphabet_opacity=getattr(theme, "alphabet_opacity", 82),
        alphabet_trail_length=getattr(theme, "alphabet_trail_length", 14),
        alphabet_tilt_x=getattr(theme, "alphabet_tilt_x", 18),
        alphabet_tilt_y=getattr(theme, "alphabet_tilt_y", 12),
        alphabet_tilt_z=getattr(theme, "alphabet_tilt_z", 30),
        alphabet_outline_only=getattr(theme, "alphabet_outline_only", False),
        alphabet_outline_color=getattr(theme, "alphabet_outline_color", "#ffffff"),
        glass_level=theme.glass_level,
        glow_intensity=theme.glow_intensity,
        blur_strength=theme.blur_strength,
        hover_style=theme.hover_style,
        motion_level=theme.motion_level,
        icon_style=theme.icon_style,
        icon_glow=theme.icon_glow,
        heading_text=theme.heading_text,
        workspace_kicker_text=theme.workspace_kicker_text,
        workspace_kicker_size=theme.workspace_kicker_size,
        workspace_kicker_weight=theme.workspace_kicker_weight,
        page_title_size=theme.page_title_size,
        page_title_weight=theme.page_title_weight,
        page_title_transform=theme.page_title_transform,
        page_title_spacing=theme.page_title_spacing,
        fluid_color_1=theme.fluid_color_1,
        fluid_color_2=theme.fluid_color_2,
        fluid_color_3=theme.fluid_color_3,
        badge_bg=theme.badge_bg,
        badge_text=theme.badge_text,
        badge_border=theme.badge_border,
        button_shape=theme.button_shape,
        button_radius=theme.button_radius,
        card_style=theme.card_style,
        table_style=theme.table_style,
        is_active=False,
    )

    db.session.add(clone)
    db.session.commit()

    _safe_audit("theme_duplicate", target=str(clone.id), meta=clone.name)
    flash("Theme duplicated.", "success")
    return redirect(url_for("theme.manage_themes"))


@bp.post("/manage/<int:theme_id>/delete")
@login_required
@require_role("SUPERADMIN", "SEO")
@require_perm("theme.manage")
def delete_theme(theme_id: int):
    """
    Delete a theme unless it is the currently active one.
    """
    theme = Theme.query.get_or_404(theme_id)

    if theme.is_active:
        flash("You cannot delete the active theme.", "warning")
        return redirect(url_for("theme.manage_themes"))

    db.session.delete(theme)
    db.session.commit()

    _safe_audit("theme_delete", target=str(theme_id), meta=theme.name)
    flash("Theme deleted.", "success")
    return redirect(url_for("theme.manage_themes"))
