from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from . import bp
from ...extensions import db
from ...models.economy import BossLevel, CourseChatMessage, CourseCoinRedemption, StudentWallet, WalletLedgerEntry
from ...models.lms import Course
from ...models.user import Role, User
from ...rbac import require_role
from ...services.economy_service import EconomyService


def _economy_metrics() -> dict:
    total_issued = (
        db.session.query(db.func.coalesce(db.func.sum(WalletLedgerEntry.amount), 0))
        .filter(WalletLedgerEntry.txn_type == "earn")
        .scalar()
    )
    total_spent = (
        db.session.query(db.func.coalesce(db.func.sum(db.func.abs(WalletLedgerEntry.amount)), 0))
        .filter(WalletLedgerEntry.txn_type == "spend")
        .scalar()
    )
    return {
        "active_wallets": StudentWallet.query.filter_by(wallet_status="active").count(),
        "total_wallets": StudentWallet.query.count(),
        "total_issued": int(total_issued or 0),
        "total_spent": int(total_spent or 0),
        "redemptions": CourseCoinRedemption.query.count(),
        "messages": CourseChatMessage.query.filter_by(status="active").count(),
    }


@bp.get("/economy")
@login_required
@require_role("SUPERADMIN")
def economy_dashboard():
    EconomyService.ensure_reward_policies()
    courses = (
        Course.query
        .filter(Course.status != "archived")
        .order_by(Course.created_at.desc(), Course.id.desc())
        .all()
    )
    boss_levels = (
        BossLevel.query
        .order_by(BossLevel.created_at.desc(), BossLevel.id.desc())
        .all()
    )
    redemptions = (
        CourseCoinRedemption.query
        .order_by(CourseCoinRedemption.created_at.desc(), CourseCoinRedemption.id.desc())
        .limit(20)
        .all()
    )
    leaderboard_students = (
        User.query
        .filter(User.role == Role.STUDENT.value)
        .order_by(User.first_name.asc(), User.username.asc(), User.id.asc())
        .limit(100)
        .all()
    )
    course_reward_map = {course.id: EconomyService.course_reward_overview(course) for course in courses}
    return render_template(
        "superadmin/economy.html",
        metrics=_economy_metrics(),
        courses=courses,
        boss_levels=boss_levels,
        redemptions=redemptions,
        weekly_leaders=EconomyService.leaderboard("weekly", limit=10),
        monthly_leaders=EconomyService.leaderboard("monthly", limit=10),
        leaderboard_students=leaderboard_students,
        reward_guide=EconomyService.reward_guide(),
        streak_milestones=EconomyService.streak_milestone_guide(),
        reward_policies=EconomyService.ensure_reward_policies(),
        course_reward_map=course_reward_map,
        leaderboard_reward_policy=EconomyService.ensure_leaderboard_reward_policy(),
        leaderboard_reward_guide=EconomyService.leaderboard_reward_guide(),
    )


@bp.post("/economy/course/<int:course_id>/settings")
@login_required
@require_role("SUPERADMIN")
def economy_update_course(course_id: int):
    course = Course.query.get_or_404(course_id)
    try:
        course.allow_coin_redemption = request.form.get("allow_coin_redemption") == "1"
        course.difficulty = EconomyService.normalize_difficulty_band(request.form.get("difficulty"))
        coin_price = request.form.get("coin_price", type=int)
        course.coin_price = max(0, int(coin_price or 0)) or None
        course.community_enabled = request.form.get("community_enabled") == "1"
        db.session.commit()
        flash("Course economy settings updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("superadmin.economy_dashboard"))


@bp.post("/economy/course/<int:course_id>/reward-overrides")
@login_required
@require_role("SUPERADMIN")
def economy_update_course_reward_overrides(course_id: int):
    course = Course.query.get_or_404(course_id)

    def _optional_int(field_name: str):
        raw = (request.form.get(field_name) or "").strip()
        if raw == "":
            return None
        return max(0, int(raw))

    try:
        course.speaking_base_override = _optional_int("speaking_base_override")
        course.speaking_relevance_bonus_override = _optional_int("speaking_relevance_bonus_override")
        course.speaking_progress_bonus_override = _optional_int("speaking_progress_bonus_override")
        course.speaking_good_bonus_override = _optional_int("speaking_good_bonus_override")
        course.speaking_strong_bonus_override = _optional_int("speaking_strong_bonus_override")
        course.speaking_full_length_bonus_override = _optional_int("speaking_full_length_bonus_override")
        course.speaking_first_try_bonus_override = _optional_int("speaking_first_try_bonus_override")
        course.lesson_base_override = _optional_int("lesson_base_override")
        course.lesson_accuracy_mid_bonus_override = _optional_int("lesson_accuracy_mid_bonus_override")
        course.lesson_accuracy_high_bonus_override = _optional_int("lesson_accuracy_high_bonus_override")
        course.boss_reward_override = _optional_int("boss_reward_override")
        db.session.commit()
        flash(f"Course reward overrides updated for {course.title}.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("superadmin.economy_dashboard"))


@bp.post("/economy/boss-levels/create")
@login_required
@require_role("SUPERADMIN")
def economy_create_boss_level():
    try:
        boss_level = BossLevel(
            course_id=request.form.get("course_id", type=int),
            title=(request.form.get("title") or "").strip() or "Boss Level",
            description=(request.form.get("description") or "").strip() or None,
            prompt_text=(request.form.get("prompt_text") or "").strip() or None,
            reward_coins=max(1, int(request.form.get("reward_coins", type=int) or 50)),
            unlock_completion_percent=max(0, min(100, int(request.form.get("unlock_completion_percent", type=int) or 100))),
            min_accuracy=max(0, min(100, int(request.form.get("min_accuracy", type=int) or 60))),
            is_active=request.form.get("is_active") == "1",
            sort_order=max(0, int(request.form.get("sort_order", type=int) or 0)),
        )
        db.session.add(boss_level)
        db.session.commit()
        flash("Boss level created.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("superadmin.economy_dashboard"))


@bp.post("/economy/leaderboard/student/<int:student_id>")
@login_required
@require_role("SUPERADMIN")
def economy_update_leaderboard_student(student_id: int):
    student = User.query.get_or_404(student_id)
    if student.role != Role.STUDENT.value:
        flash("Only student accounts can be managed in the leaderboard.", "warning")
        return redirect(url_for("superadmin.economy_dashboard"))

    try:
        student.show_on_leaderboard = request.form.get("show_on_leaderboard") == "1"
        db.session.commit()
        flash("Leaderboard visibility updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("superadmin.economy_dashboard"))


@bp.post("/economy/reward-policy/<string:difficulty_band>")
@login_required
@require_role("SUPERADMIN")
def economy_update_reward_policy(difficulty_band: str):
    EconomyService.ensure_reward_policies()
    band = EconomyService.normalize_difficulty_band(difficulty_band)
    from ...models.reward_policy import RewardPolicy

    policy = RewardPolicy.query.filter_by(difficulty_band=band).first_or_404()
    try:
        policy.label = (request.form.get("label") or policy.label).strip() or policy.label
        policy.speaking_base = max(0, int(request.form.get("speaking_base", type=int) or 0))
        policy.speaking_relevance_bonus = max(0, int(request.form.get("speaking_relevance_bonus", type=int) or 0))
        policy.speaking_progress_bonus = max(0, int(request.form.get("speaking_progress_bonus", type=int) or 0))
        policy.speaking_good_bonus = max(0, int(request.form.get("speaking_good_bonus", type=int) or 0))
        policy.speaking_strong_bonus = max(0, int(request.form.get("speaking_strong_bonus", type=int) or 0))
        policy.speaking_full_length_bonus = max(0, int(request.form.get("speaking_full_length_bonus", type=int) or 0))
        policy.speaking_first_try_bonus = max(0, int(request.form.get("speaking_first_try_bonus", type=int) or 0))
        policy.lesson_base = max(0, int(request.form.get("lesson_base", type=int) or 0))
        policy.lesson_accuracy_mid_bonus = max(0, int(request.form.get("lesson_accuracy_mid_bonus", type=int) or 0))
        policy.lesson_accuracy_high_bonus = max(0, int(request.form.get("lesson_accuracy_high_bonus", type=int) or 0))
        policy.boss_suggested_reward = max(0, int(request.form.get("boss_suggested_reward", type=int) or 0))
        db.session.commit()
        flash(f"{policy.label} reward policy updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("superadmin.economy_dashboard"))


@bp.post("/economy/leaderboard-rewards")
@login_required
@require_role("SUPERADMIN")
def economy_update_leaderboard_rewards():
    policy = EconomyService.ensure_leaderboard_reward_policy()
    try:
        policy.weekly_first_coins = max(0, int(request.form.get("weekly_first_coins", type=int) or 0))
        policy.weekly_second_coins = max(0, int(request.form.get("weekly_second_coins", type=int) or 0))
        policy.weekly_third_coins = max(0, int(request.form.get("weekly_third_coins", type=int) or 0))
        policy.monthly_first_coins = max(0, int(request.form.get("monthly_first_coins", type=int) or 0))
        policy.monthly_second_coins = max(0, int(request.form.get("monthly_second_coins", type=int) or 0))
        policy.monthly_third_coins = max(0, int(request.form.get("monthly_third_coins", type=int) or 0))
        db.session.commit()
        flash("Leaderboard reward bonuses updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("superadmin.economy_dashboard"))
