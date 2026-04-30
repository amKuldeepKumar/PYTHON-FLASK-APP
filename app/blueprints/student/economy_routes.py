from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from ...extensions import db
from ...models.economy import BossLevel
from ...models.lms import Course, Enrollment
from ...rbac import require_role
from ...services.economy_service import EconomyService
from ...services.student_activity_service import StudentActivityService


def _student_enrollments():
    return (
        Enrollment.query
        .filter_by(student_id=current_user.id, status="active")
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .all()
    )


def _student_redeemable_courses():
    enrolled_ids = {row.course_id for row in _student_enrollments()}
    return (
        Course.query
        .filter(
            Course.is_published.is_(True),
            Course.status != "archived",
            Course.allow_coin_redemption.is_(True),
            Course.coin_price.isnot(None),
        )
        .order_by(Course.coin_price.asc(), Course.title.asc())
        .all(),
        enrolled_ids,
    )


def _student_boss_rows():
    course_ids = [row.course_id for row in _student_enrollments()]
    if not course_ids:
        return []

    boss_levels = (
        BossLevel.query
        .filter(BossLevel.course_id.in_(course_ids), BossLevel.is_active.is_(True))
        .order_by(BossLevel.sort_order.asc(), BossLevel.id.asc())
        .all()
    )
    rows = []
    for boss in boss_levels:
        status = EconomyService.boss_status_for_student(current_user.id, boss)
        rows.append(
            {
                "boss": boss,
                "status": status,
            }
        )
    return rows


@bp.get("/wallet")
@login_required
@require_role("STUDENT")
def wallet():
    summary = EconomyService.wallet_summary(current_user.id)
    db.session.commit()
    redeemable_courses, enrolled_ids = _student_redeemable_courses()
    return render_template(
        "student/wallet.html",
        wallet_summary=summary,
        redeemable_courses=redeemable_courses,
        enrolled_ids=enrolled_ids,
    )


@bp.post("/wallet/redeem-course/<int:course_id>")
@login_required
@require_role("STUDENT")
def redeem_course_with_coins(course_id: int):
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    try:
        EconomyService.redeem_course(current_user.id, course_id)
        db.session.commit()
        flash("Course unlocked with coins.", "success")
        return redirect(url_for("student.course_welcome", course_id=course_id))
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("student.wallet"))


@bp.get("/rewards")
@login_required
@require_role("STUDENT")
def rewards():
    summary = EconomyService.wallet_summary(current_user.id, ledger_limit=8)
    db.session.commit()
    weekly_leaders = EconomyService.leaderboard("weekly", limit=10)
    monthly_leaders = EconomyService.leaderboard("monthly", limit=10)
    redeemable_courses, enrolled_ids = _student_redeemable_courses()
    return render_template(
        "student/rewards.html",
        wallet_summary=summary,
        streak=StudentActivityService.active_streak(current_user.id),
        weekly_leaders=weekly_leaders,
        monthly_leaders=monthly_leaders,
        boss_rows=_student_boss_rows(),
        redeemable_courses=redeemable_courses[:6],
        enrolled_ids=enrolled_ids,
        reward_guide=EconomyService.reward_guide(),
        streak_milestones=EconomyService.streak_milestone_guide(),
        leaderboard_bonus_status=EconomyService.leaderboard_bonus_status(current_user.id),
        leaderboard_reward_guide=EconomyService.leaderboard_reward_guide(),
    )


@bp.post("/rewards/leaderboard-bonus/<string:period>")
@login_required
@require_role("STUDENT")
def claim_leaderboard_bonus(period: str):
    try:
        EconomyService.claim_leaderboard_bonus(current_user.id, period)
        db.session.commit()
        flash("Leaderboard bonus coins added to your wallet.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("student.rewards"))


@bp.post("/boss-levels/<int:boss_level_id>/submit")
@login_required
@require_role("STUDENT")
def submit_boss_level(boss_level_id: int):
    response_text = (request.form.get("response_text") or "").strip()
    try:
        EconomyService.submit_boss_level(current_user.id, boss_level_id, response_text)
        db.session.commit()
        flash("Boss level cleared and coins added to your wallet.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("student.rewards"))


@bp.get("/leaderboard")
@login_required
@require_role("STUDENT")
def leaderboard():
    return render_template(
        "student/leaderboard.html",
        weekly_leaders=EconomyService.leaderboard("weekly", limit=25),
        monthly_leaders=EconomyService.leaderboard("monthly", limit=25),
    )


@bp.get("/chat")
@login_required
@require_role("STUDENT")
def chat():
    enrollments = _student_enrollments()
    active_course_id = request.args.get("course_id", type=int)
    active_course = None
    if enrollments:
        active_course = next((row.course for row in enrollments if row.course_id == active_course_id), None)
        if active_course is None:
            active_course = enrollments[0].course

    messages = EconomyService.recent_messages(active_course.id, limit=100) if active_course else []
    return render_template(
        "student/chat.html",
        enrollments=enrollments,
        active_course=active_course,
        messages=messages,
    )


@bp.post("/chat/message")
@login_required
@require_role("STUDENT")
def chat_post_message():
    course_id = request.form.get("course_id", type=int)
    body = (request.form.get("body") or "").strip()
    try:
        EconomyService.post_course_message(current_user.id, course_id, body)
        db.session.commit()
        flash("Message sent.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("student.chat", course_id=course_id))


@bp.get("/chat/widget")
@login_required
@require_role("STUDENT")
def chat_widget():
    course_id = request.args.get("course_id", type=int)
    return jsonify({"ok": True, **EconomyService.chat_payload(current_user.id, course_id, limit=30)})


@bp.post("/chat/widget/message")
@login_required
@require_role("STUDENT")
def chat_widget_post_message():
    course_id = request.form.get("course_id", type=int)
    body = (request.form.get("body") or "").strip()
    try:
        message = EconomyService.post_course_message(current_user.id, course_id, body)
        db.session.commit()
        return jsonify(
            {
                "ok": True,
                "message": {
                    "id": message.id,
                    "sender_name": EconomyService.public_display_name(current_user),
                    "body": message.body,
                    "created_at": message.created_at.strftime("%d %b %Y %I:%M %p"),
                    "is_self": True,
                },
            }
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(exc)}), 400
