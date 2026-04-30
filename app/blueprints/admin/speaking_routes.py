from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from ...models.speaking_prompt import SpeakingPrompt
from ...models.speaking_topic import SpeakingTopic
from ...rbac import require_role
from ...services.speaking.prompt_service import PromptService
from ...services.speaking.analytics_service import SpeakingAnalyticsService
from typing import Optional


LEVEL_CHOICES = ("basic", "intermediate", "advanced")


def _owner_admin_id() -> Optional[int]:
    return current_user.scope_admin_id() or current_user.id


@bp.route("/speaking/topics", methods=["GET", "POST"])
@login_required
@require_role("ADMIN", "SUB_ADMIN")
def speaking_topics():
    owner_admin_id = _owner_admin_id()

    if request.method == "POST":
        try:
            PromptService.create_topic(
                owner_admin_id=owner_admin_id,
                code=request.form.get("code"),
                title=request.form.get("title"),
                description=request.form.get("description"),
                level=request.form.get("level") or "basic",
                display_order=request.form.get("display_order") or 0,
                is_active=bool(request.form.get("is_active")),
            )
            flash("Speaking topic created successfully.", "success")
            return redirect(url_for("admin.speaking_topics"))
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception as exc:
            flash(f"Unable to create speaking topic: {exc}", "danger")

    topics = PromptService.list_topics(owner_admin_id)
    return render_template(
        "admin/speaking_topics.html",
        topics=topics,
        level_choices=LEVEL_CHOICES,
    )


@bp.post("/speaking/topics/<int:topic_id>/toggle")
@login_required
@require_role("ADMIN", "SUB_ADMIN")
def speaking_topic_toggle(topic_id: int):
    owner_admin_id = _owner_admin_id()
    topic = SpeakingTopic.query.filter_by(id=topic_id, owner_admin_id=owner_admin_id).first_or_404()
    PromptService.toggle_topic(topic)
    flash("Speaking topic status updated.", "success")
    return redirect(url_for("admin.speaking_topics"))


@bp.route("/speaking/prompts", methods=["GET", "POST"])
@login_required
@require_role("ADMIN", "SUB_ADMIN")
def speaking_prompts():
    owner_admin_id = _owner_admin_id()
    topics = PromptService.list_topics(owner_admin_id)
    selected_topic_id = request.args.get("topic_id", type=int)

    if request.method == "POST":
        topic_id = request.form.get("topic_id", type=int)
        topic = SpeakingTopic.query.filter_by(id=topic_id, owner_admin_id=owner_admin_id).first()
        if not topic:
            flash("Please choose a valid topic.", "warning")
            return redirect(url_for("admin.speaking_prompts", topic_id=selected_topic_id or ""))

        try:
            PromptService.create_prompt(
                owner_admin_id=owner_admin_id,
                topic=topic,
                title=request.form.get("title"),
                prompt_text=request.form.get("prompt_text"),
                instruction_text=request.form.get("instruction_text"),
                difficulty=request.form.get("difficulty") or topic.level,
                estimated_seconds=request.form.get("estimated_seconds") or 60,
                display_order=request.form.get("display_order") or 0,
                is_active=bool(request.form.get("is_active")),
            )
            flash("Speaking prompt created successfully.", "success")
            return redirect(url_for("admin.speaking_prompts", topic_id=topic.id))
        except ValueError as exc:
            flash(str(exc), "warning")
        except Exception as exc:
            flash(f"Unable to create speaking prompt: {exc}", "danger")

    prompts = PromptService.list_prompts(owner_admin_id, topic_id=selected_topic_id)
    return render_template(
        "admin/speaking_prompts.html",
        prompts=prompts,
        topics=topics,
        selected_topic_id=selected_topic_id,
        level_choices=LEVEL_CHOICES,
    )


@bp.post("/speaking/prompts/<int:prompt_id>/toggle")
@login_required
@require_role("ADMIN", "SUB_ADMIN")
def speaking_prompt_toggle(prompt_id: int):
    owner_admin_id = _owner_admin_id()
    prompt = SpeakingPrompt.query.filter_by(id=prompt_id, owner_admin_id=owner_admin_id).first_or_404()
    PromptService.toggle_prompt(prompt)
    flash("Speaking prompt status updated.", "success")
    return redirect(url_for("admin.speaking_prompts", topic_id=prompt.topic_id))


@bp.get('/speaking/analytics')
@login_required
@require_role('ADMIN', 'SUB_ADMIN')
def speaking_analytics():
    selected_student_id = request.args.get('student_id', type=int)
    payload = SpeakingAnalyticsService.admin_scope_report(current_user, selected_student_id=selected_student_id)
    return render_template('admin/speaking_analytics.html', analytics=payload, selected_student_id=selected_student_id)
