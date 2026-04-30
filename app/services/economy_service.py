from __future__ import annotations

from datetime import date, datetime, timedelta
import re

from sqlalchemy import func

from ..extensions import db
from ..models.economy import (
    BossLevel,
    BossLevelAttempt,
    CourseChatMessage,
    CourseChatModerationEvent,
    CourseCoinRedemption,
    LeaderboardRewardClaim,
    LeaderboardRewardPolicy,
    StudentWallet,
    WalletLedgerEntry,
)
from ..models.lms import Course, CourseProgress, Enrollment
from ..models.reward_policy import RewardPolicy
from ..models.student_daily_activity import StudentDailyActivity
from ..models.user import Role, User
from .student_activity_service import StudentActivityService


class EconomyService:
    REWARD_RULES = {
        "basic": {
            "label": "Basic",
            "speaking_base": 8,
            "speaking_relevance_bonus": 2,
            "speaking_progress_bonus": 2,
            "speaking_good_bonus": 4,
            "speaking_strong_bonus": 6,
            "speaking_full_length_bonus": 2,
            "speaking_first_try_bonus": 2,
            "lesson_base": 20,
            "lesson_accuracy_mid_bonus": 3,
            "lesson_accuracy_high_bonus": 6,
            "boss_suggested_reward": 40,
        },
        "intermediate": {
            "label": "Intermediate",
            "speaking_base": 12,
            "speaking_relevance_bonus": 3,
            "speaking_progress_bonus": 3,
            "speaking_good_bonus": 5,
            "speaking_strong_bonus": 8,
            "speaking_full_length_bonus": 3,
            "speaking_first_try_bonus": 2,
            "lesson_base": 30,
            "lesson_accuracy_mid_bonus": 4,
            "lesson_accuracy_high_bonus": 8,
            "boss_suggested_reward": 60,
        },
        "advanced": {
            "label": "Advanced",
            "speaking_base": 16,
            "speaking_relevance_bonus": 4,
            "speaking_progress_bonus": 4,
            "speaking_good_bonus": 7,
            "speaking_strong_bonus": 10,
            "speaking_full_length_bonus": 4,
            "speaking_first_try_bonus": 3,
            "lesson_base": 45,
            "lesson_accuracy_mid_bonus": 5,
            "lesson_accuracy_high_bonus": 10,
            "boss_suggested_reward": 90,
        },
    }

    STREAK_MILESTONES = {
        3: 5,
        7: 10,
        14: 20,
        30: 40,
    }
    CHAT_BLOCKLIST = {
        "abuse": {
            "abuse", "idiot", "stupid", "loser", "bastard", "moron", "dumb", "shut up", "hate you",
        },
        "drugs": {
            "cocaine", "heroin", "weed", "marijuana", "drug deal", "meth", "opium", "lsd", "ecstasy",
        },
        "weapons": {
            "gun", "pistol", "rifle", "bomb", "grenade", "knife attack", "weapon", "ammo", "bullet",
        },
        "illegal": {
            "steal", "rob", "hack", "fraud", "scam", "forgery", "counterfeit", "smuggle", "kill", "murder",
        },
    }
    COURSE_OVERRIDE_FIELD_MAP = {
        "speaking_base": "speaking_base_override",
        "speaking_relevance_bonus": "speaking_relevance_bonus_override",
        "speaking_progress_bonus": "speaking_progress_bonus_override",
        "speaking_good_bonus": "speaking_good_bonus_override",
        "speaking_strong_bonus": "speaking_strong_bonus_override",
        "speaking_full_length_bonus": "speaking_full_length_bonus_override",
        "speaking_first_try_bonus": "speaking_first_try_bonus_override",
        "lesson_base": "lesson_base_override",
        "lesson_accuracy_mid_bonus": "lesson_accuracy_mid_bonus_override",
        "lesson_accuracy_high_bonus": "lesson_accuracy_high_bonus_override",
        "boss_suggested_reward": "boss_reward_override",
    }

    @staticmethod
    def ensure_reward_policies() -> list[RewardPolicy]:
        rows: list[RewardPolicy] = []
        for band, defaults in EconomyService.REWARD_RULES.items():
            row = RewardPolicy.query.filter_by(difficulty_band=band).first()
            if row is None:
                row = RewardPolicy(
                    difficulty_band=band,
                    label=defaults["label"],
                    speaking_base=defaults["speaking_base"],
                    speaking_relevance_bonus=defaults["speaking_relevance_bonus"],
                    speaking_progress_bonus=defaults["speaking_progress_bonus"],
                    speaking_good_bonus=defaults["speaking_good_bonus"],
                    speaking_strong_bonus=defaults["speaking_strong_bonus"],
                    speaking_full_length_bonus=defaults["speaking_full_length_bonus"],
                    speaking_first_try_bonus=defaults["speaking_first_try_bonus"],
                    lesson_base=defaults["lesson_base"],
                    lesson_accuracy_mid_bonus=defaults["lesson_accuracy_mid_bonus"],
                    lesson_accuracy_high_bonus=defaults["lesson_accuracy_high_bonus"],
                    boss_suggested_reward=defaults["boss_suggested_reward"],
                    is_active=True,
                )
                db.session.add(row)
                db.session.flush()
            rows.append(row)
        return rows

    @staticmethod
    def normalize_difficulty_band(value: str | None) -> str:
        raw = (value or "").strip().lower()
        if raw in {"advanced", "hard", "expert", "elite"}:
            return "advanced"
        if raw in {"intermediate", "medium", "mid"}:
            return "intermediate"
        return "basic"

    @staticmethod
    def difficulty_rules(value: str | None) -> dict:
        band = EconomyService.normalize_difficulty_band(value)
        row = RewardPolicy.query.filter_by(difficulty_band=band).first()
        if row is None:
            EconomyService.ensure_reward_policies()
            row = RewardPolicy.query.filter_by(difficulty_band=band).first()
        if row is None:
            return dict(EconomyService.REWARD_RULES[band])
        return {
            "label": row.label,
            "speaking_base": int(row.speaking_base or 0),
            "speaking_relevance_bonus": int(row.speaking_relevance_bonus or 0),
            "speaking_progress_bonus": int(row.speaking_progress_bonus or 0),
            "speaking_good_bonus": int(row.speaking_good_bonus or 0),
            "speaking_strong_bonus": int(row.speaking_strong_bonus or 0),
            "speaking_full_length_bonus": int(row.speaking_full_length_bonus or 0),
            "speaking_first_try_bonus": int(row.speaking_first_try_bonus or 0),
            "lesson_base": int(row.lesson_base or 0),
            "lesson_accuracy_mid_bonus": int(row.lesson_accuracy_mid_bonus or 0),
            "lesson_accuracy_high_bonus": int(row.lesson_accuracy_high_bonus or 0),
            "boss_suggested_reward": int(row.boss_suggested_reward or 0),
        }

    @staticmethod
    def course_difficulty_band(course: Course | None) -> str:
        return EconomyService.normalize_difficulty_band(getattr(course, "difficulty", None) if course else None)

    @staticmethod
    def course_reward_rules(course: Course | None) -> dict:
        band = EconomyService.course_difficulty_band(course)
        rules = dict(EconomyService.difficulty_rules(band))
        for rules_key, course_attr in EconomyService.COURSE_OVERRIDE_FIELD_MAP.items():
            override_value = getattr(course, course_attr, None) if course else None
            if override_value is not None:
                rules[rules_key] = int(override_value or 0)
        return rules

    @staticmethod
    def ensure_leaderboard_reward_policy() -> LeaderboardRewardPolicy:
        policy = LeaderboardRewardPolicy.query.order_by(LeaderboardRewardPolicy.id.asc()).first()
        if policy is None:
            policy = LeaderboardRewardPolicy(
                weekly_first_coins=30,
                weekly_second_coins=20,
                weekly_third_coins=10,
                monthly_first_coins=60,
                monthly_second_coins=40,
                monthly_third_coins=20,
            )
            db.session.add(policy)
            db.session.flush()
        return policy

    @staticmethod
    def leaderboard_period_meta(period: str) -> dict:
        today = date.today()
        key = (period or "weekly").strip().lower()
        if key == "monthly":
            start_date = date(today.year, today.month, 1)
            return {
                "period": "monthly",
                "start_date": start_date,
                "period_key": start_date.strftime("%Y-%m"),
                "label": today.strftime("%B %Y"),
            }
        start_date = today - timedelta(days=today.weekday())
        return {
            "period": "weekly",
            "start_date": start_date,
            "period_key": start_date.isoformat(),
            "label": f"Week of {start_date.strftime('%d %b %Y')}",
        }

    @staticmethod
    def leaderboard_reward_amount(period: str, rank: int) -> int:
        policy = EconomyService.ensure_leaderboard_reward_policy()
        period_key = (period or "weekly").strip().lower()
        if period_key not in {"weekly", "monthly"}:
            period_key = "weekly"
        if int(rank or 0) == 1:
            return int(getattr(policy, f"{period_key}_first_coins", 0) or 0)
        if int(rank or 0) == 2:
            return int(getattr(policy, f"{period_key}_second_coins", 0) or 0)
        if int(rank or 0) == 3:
            return int(getattr(policy, f"{period_key}_third_coins", 0) or 0)
        return 0

    @staticmethod
    def speaking_session_reward_plan(session) -> dict:
        course = getattr(session, "course", None) or getattr(getattr(session, "topic", None), "course", None)
        band = EconomyService.course_difficulty_band(course)
        rules = EconomyService.course_reward_rules(course)

        score = float(getattr(session, "evaluation_score", 0) or 0)
        relevance = bool(getattr(session, "is_relevant", False))
        duration_seconds = int(getattr(session, "duration_seconds", 0) or 0)
        estimated_seconds = int(getattr(getattr(session, "prompt", None), "estimated_seconds", 0) or 0)
        submit_count = int(getattr(session, "submit_count", 0) or 0)

        coins = int(rules["speaking_base"])
        notes = [f"{rules['label']} speaking completion"]

        if relevance:
            coins += int(rules["speaking_relevance_bonus"])
            notes.append("On-topic bonus")

        if score >= 8:
            coins += int(rules["speaking_strong_bonus"])
            notes.append("Strong score bonus")
        elif score >= 6:
            coins += int(rules["speaking_good_bonus"])
            notes.append("Good score bonus")
        elif score >= 4:
            coins += int(rules["speaking_progress_bonus"])
            notes.append("Progress bonus")

        if estimated_seconds and duration_seconds >= max(10, int(estimated_seconds * 0.8)):
            coins += int(rules["speaking_full_length_bonus"])
            notes.append("Full-length answer bonus")

        if submit_count <= 1:
            coins += int(rules["speaking_first_try_bonus"])
            notes.append("First-try bonus")

        return {
            "difficulty_band": band,
            "difficulty_label": rules["label"],
            "coins_awarded": int(coins),
            "notes": notes,
        }

    @staticmethod
    def lesson_completion_reward_plan(course: Course | None, *, accuracy_score: float | int | None) -> dict:
        band = EconomyService.course_difficulty_band(course)
        rules = EconomyService.course_reward_rules(course)
        accuracy = float(accuracy_score or 0.0)
        coins = int(rules["lesson_base"])
        notes = [f"{rules['label']} lesson completion"]

        if accuracy >= 80:
            coins += int(rules["lesson_accuracy_high_bonus"])
            notes.append("High-accuracy bonus")
        elif accuracy >= 60:
            coins += int(rules["lesson_accuracy_mid_bonus"])
            notes.append("Accuracy bonus")

        return {
            "difficulty_band": band,
            "difficulty_label": rules["label"],
            "coins_awarded": int(coins),
            "notes": notes,
        }

    @staticmethod
    def reward_guide() -> list[dict]:
        EconomyService.ensure_reward_policies()
        rows: list[dict] = []
        for band in ("basic", "intermediate", "advanced"):
            rules = EconomyService.difficulty_rules(band)
            speaking_max = (
                int(rules["speaking_base"])
                + int(rules["speaking_relevance_bonus"])
                + int(rules["speaking_strong_bonus"])
                + int(rules["speaking_full_length_bonus"])
                + int(rules["speaking_first_try_bonus"])
            )
            lesson_mid = int(rules["lesson_base"]) + int(rules["lesson_accuracy_mid_bonus"])
            lesson_high = int(rules["lesson_base"]) + int(rules["lesson_accuracy_high_bonus"])
            rows.append(
                {
                    "band": band,
                    "label": rules["label"],
                    "speaking_min": int(rules["speaking_base"]),
                    "speaking_max": speaking_max,
                    "lesson_base": int(rules["lesson_base"]),
                    "lesson_mid": lesson_mid,
                    "lesson_high": lesson_high,
                    "boss_reward": int(rules["boss_suggested_reward"]),
                }
            )
        return rows

    @staticmethod
    def course_reward_overview(course: Course | None) -> dict:
        band = EconomyService.course_difficulty_band(course)
        rules = EconomyService.course_reward_rules(course)
        return {
            "band": band,
            "label": rules["label"],
            "speaking_min": int(rules["speaking_base"]),
            "speaking_max": int(rules["speaking_base"]) + int(rules["speaking_relevance_bonus"]) + int(rules["speaking_strong_bonus"]) + int(rules["speaking_full_length_bonus"]) + int(rules["speaking_first_try_bonus"]),
            "lesson_base": int(rules["lesson_base"]),
            "lesson_mid": int(rules["lesson_base"]) + int(rules["lesson_accuracy_mid_bonus"]),
            "lesson_high": int(rules["lesson_base"]) + int(rules["lesson_accuracy_high_bonus"]),
            "boss_reward": int(rules["boss_suggested_reward"]),
            "is_custom": bool(course and any(getattr(course, attr, None) is not None for attr in EconomyService.COURSE_OVERRIDE_FIELD_MAP.values())),
        }

    @staticmethod
    def leaderboard_reward_guide() -> list[dict]:
        EconomyService.ensure_leaderboard_reward_policy()
        rows: list[dict] = []
        for period in ("weekly", "monthly"):
            meta = EconomyService.leaderboard_period_meta(period)
            rows.append(
                {
                    "period": period,
                    "label": "Weekly" if period == "weekly" else "Monthly",
                    "period_name": meta["label"],
                    "first": EconomyService.leaderboard_reward_amount(period, 1),
                    "second": EconomyService.leaderboard_reward_amount(period, 2),
                    "third": EconomyService.leaderboard_reward_amount(period, 3),
                }
            )
        return rows

    @staticmethod
    def leaderboard_bonus_status(student_id: int) -> list[dict]:
        statuses: list[dict] = []
        for period in ("weekly", "monthly"):
            meta = EconomyService.leaderboard_period_meta(period)
            rank_row = next(
                (row for row in EconomyService.leaderboard(period, limit=3) if int(row["student_id"]) == int(student_id)),
                None,
            )
            rank = int(rank_row["rank"]) if rank_row else 0
            coins = EconomyService.leaderboard_reward_amount(period, rank)
            claim = (
                LeaderboardRewardClaim.query
                .filter_by(student_id=student_id, period_type=period, period_key=meta["period_key"])
                .first()
            )
            statuses.append(
                {
                    "period": period,
                    "label": "Weekly" if period == "weekly" else "Monthly",
                    "period_name": meta["label"],
                    "period_key": meta["period_key"],
                    "rank": rank,
                    "coins": coins,
                    "eligible": rank in {1, 2, 3} and coins > 0,
                    "claimed": claim is not None,
                    "claim": claim,
                }
            )
        return statuses

    @staticmethod
    def streak_milestone_guide() -> list[dict]:
        return [
            {"days": days, "coins": coins}
            for days, coins in EconomyService.STREAK_MILESTONES.items()
        ]

    @staticmethod
    def award_streak_milestone_if_eligible(student_id: int, current_streak: int) -> WalletLedgerEntry | None:
        coins = int(EconomyService.STREAK_MILESTONES.get(int(current_streak or 0), 0) or 0)
        if coins <= 0:
            return None
        return EconomyService.award_coins(
            student_id,
            coins,
            reference_type="streak_milestone",
            reference_id=current_streak,
            title=f"Streak milestone: {current_streak} days",
            description=f"Consistency reward for reaching a {current_streak}-day streak.",
            created_by="system",
            idempotency_key=f"streak-milestone:{student_id}:{current_streak}",
            activity_date=date.today(),
        )

    @staticmethod
    def ensure_wallet(student_id: int) -> StudentWallet:
        wallet = StudentWallet.query.filter_by(student_id=student_id).first()
        if wallet:
            return wallet

        student = db.session.get(User, student_id)
        seed_balance = int(getattr(student, "coin_balance", 0) or 0)
        wallet = StudentWallet(
            student_id=student_id,
            coin_balance=seed_balance,
            last_reconciled_at=datetime.utcnow(),
        )
        db.session.add(wallet)
        db.session.flush()
        return wallet

    @staticmethod
    def wallet_summary(student_id: int, *, ledger_limit: int = 20) -> dict:
        wallet = EconomyService.ensure_wallet(student_id)
        ledger = (
            WalletLedgerEntry.query
            .filter_by(student_id=student_id)
            .order_by(WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc())
            .limit(ledger_limit)
            .all()
        )
        current_streak = StudentActivityService.active_streak(student_id)
        earned_total = sum(max(0, int(row.amount or 0)) for row in ledger if row.txn_type == "earn")
        spent_total = abs(sum(min(0, int(row.amount or 0)) for row in ledger if row.txn_type == "spend"))
        return {
            "wallet": wallet,
            "ledger": ledger,
            "current_streak": current_streak,
            "earned_total": earned_total,
            "spent_total": spent_total,
        }

    @staticmethod
    def _sync_user_coin_balance(student_id: int, balance: int, *, earned_delta: int = 0) -> None:
        student = db.session.get(User, student_id)
        if not student:
            return
        student.coin_balance = int(balance or 0)
        if earned_delta > 0:
            student.lifetime_coins = int(student.lifetime_coins or 0) + int(earned_delta)

    @staticmethod
    def _apply_ledger_entry(
        student_id: int,
        *,
        txn_type: str,
        amount: int,
        reference_type: str,
        reference_id: str | int | None,
        title: str,
        description: str | None = None,
        created_by: str = "system",
        idempotency_key: str | None = None,
        activity_date: date | None = None,
    ) -> WalletLedgerEntry:
        if amount == 0:
            raise ValueError("Amount must be non-zero.")

        if idempotency_key:
            existing = WalletLedgerEntry.query.filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return existing

        wallet = EconomyService.ensure_wallet(student_id)
        before = int(wallet.coin_balance or 0)
        after = before + int(amount)
        if after < 0:
            raise ValueError("Not enough coins in wallet.")

        entry = WalletLedgerEntry(
            wallet_id=wallet.id,
            student_id=student_id,
            txn_type=(txn_type or "adjustment").strip().lower(),
            amount=int(amount),
            balance_before=before,
            balance_after=after,
            reference_type=(reference_type or "system").strip().lower(),
            reference_id=str(reference_id) if reference_id is not None else None,
            title=(title or "Wallet update").strip() or "Wallet update",
            description=(description or "").strip() or None,
            created_by=(created_by or "system").strip().lower() or "system",
            idempotency_key=(idempotency_key or "").strip() or None,
        )
        db.session.add(entry)

        wallet.coin_balance = after
        wallet.last_reconciled_at = datetime.utcnow()
        EconomyService._sync_user_coin_balance(student_id, after, earned_delta=max(0, int(amount)))

        if amount > 0:
            day_row = StudentActivityService.get_or_create(student_id, activity_date or date.today())
            day_row.coins_earned = int(day_row.coins_earned or 0) + int(amount)

        db.session.flush()
        return entry

    @staticmethod
    def award_coins(
        student_id: int,
        amount: int,
        *,
        reference_type: str,
        reference_id: str | int | None,
        title: str,
        description: str | None = None,
        created_by: str = "system",
        idempotency_key: str | None = None,
        activity_date: date | None = None,
    ) -> WalletLedgerEntry:
        return EconomyService._apply_ledger_entry(
            student_id,
            txn_type="earn",
            amount=max(0, int(amount or 0)),
            reference_type=reference_type,
            reference_id=reference_id,
            title=title,
            description=description,
            created_by=created_by,
            idempotency_key=idempotency_key,
            activity_date=activity_date,
        )

    @staticmethod
    def spend_coins(
        student_id: int,
        amount: int,
        *,
        reference_type: str,
        reference_id: str | int | None,
        title: str,
        description: str | None = None,
        created_by: str = "system",
        idempotency_key: str | None = None,
    ) -> WalletLedgerEntry:
        return EconomyService._apply_ledger_entry(
            student_id,
            txn_type="spend",
            amount=-abs(int(amount or 0)),
            reference_type=reference_type,
            reference_id=reference_id,
            title=title,
            description=description,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def redeem_course(student_id: int, course_id: int) -> CourseCoinRedemption:
        course = Course.query.get(course_id)
        if not course:
            raise ValueError("Course not found.")
        if not bool(getattr(course, "allow_coin_redemption", False)):
            raise ValueError("This course is not available for coin redemption.")

        coin_price = max(0, int(getattr(course, "coin_price", 0) or 0))
        if coin_price <= 0:
            raise ValueError("This course does not have a valid coin price.")

        existing_redemption = CourseCoinRedemption.query.filter_by(student_id=student_id, course_id=course_id).first()
        if existing_redemption:
            raise ValueError("You already redeemed this course with coins.")

        enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course_id, status="active").first()
        if enrollment and enrollment.has_full_access():
            raise ValueError("You already have access to this course.")

        ledger_entry = EconomyService.spend_coins(
            student_id,
            coin_price,
            reference_type="course_redemption",
            reference_id=course_id,
            title=f"Course unlock: {course.title}",
            description=f"Redeemed {coin_price} coins for full access.",
            created_by="system",
            idempotency_key=f"course-redeem:{student_id}:{course_id}",
        )
        enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
        if enrollment:
            enrollment.status = "active"
            enrollment.enrolled_by_id = None
            enrollment.access_scope = "full_course"
            enrollment.purchased_levels_json = None
        else:
            enrollment = Enrollment(
                student_id=student_id,
                course_id=course_id,
                enrolled_by_id=None,
                access_scope="full_course",
                status="active",
            )
            db.session.add(enrollment)
        redemption = CourseCoinRedemption(
            student_id=student_id,
            course_id=course_id,
            ledger_entry_id=ledger_entry.id,
            coins_spent=coin_price,
            status="completed",
        )
        db.session.add(redemption)
        db.session.flush()
        return redemption

    @staticmethod
    def claim_leaderboard_bonus(student_id: int, period: str) -> LeaderboardRewardClaim:
        meta = EconomyService.leaderboard_period_meta(period)
        rank_row = next(
            (row for row in EconomyService.leaderboard(meta["period"], limit=3) if int(row["student_id"]) == int(student_id)),
            None,
        )
        if not rank_row:
            raise ValueError("You are not in the top 3 for this leaderboard right now.")

        rank = int(rank_row["rank"] or 0)
        coins = EconomyService.leaderboard_reward_amount(meta["period"], rank)
        if rank not in {1, 2, 3} or coins <= 0:
            raise ValueError("No leaderboard bonus is configured for this rank.")

        existing = (
            LeaderboardRewardClaim.query
            .filter_by(student_id=student_id, period_type=meta["period"], period_key=meta["period_key"])
            .first()
        )
        if existing:
            raise ValueError("This leaderboard bonus has already been claimed.")

        ledger_entry = EconomyService.award_coins(
            student_id,
            coins,
            reference_type="leaderboard_bonus",
            reference_id=f"{meta['period']}:{meta['period_key']}",
            title=f"{meta['period'].title()} leaderboard rank #{rank}",
            description=f"Top-{rank} leaderboard bonus for {meta['label']}.",
            created_by="system",
            idempotency_key=f"leaderboard-bonus:{student_id}:{meta['period']}:{meta['period_key']}",
            activity_date=date.today(),
        )
        claim = LeaderboardRewardClaim(
            student_id=student_id,
            period_type=meta["period"],
            period_key=meta["period_key"],
            rank_position=rank,
            coins_awarded=coins,
            ledger_entry_id=ledger_entry.id,
        )
        db.session.add(claim)
        db.session.flush()
        return claim

    @staticmethod
    def student_course_progress(student_id: int, course_id: int) -> CourseProgress | None:
        return CourseProgress.query.filter_by(student_id=student_id, course_id=course_id).first()

    @staticmethod
    def boss_status_for_student(student_id: int, boss_level: BossLevel) -> dict:
        progress = EconomyService.student_course_progress(student_id, boss_level.course_id)
        attempt = BossLevelAttempt.query.filter_by(
            boss_level_id=boss_level.id,
            student_id=student_id,
        ).first()
        completion = int(getattr(progress, "completion_percent", 0) or 0)
        accuracy = int(round(float(getattr(progress, "average_accuracy", 0.0) or 0.0)))
        eligible = completion >= int(boss_level.unlock_completion_percent or 0) and accuracy >= int(boss_level.min_accuracy or 0)
        return {
            "progress": progress,
            "attempt": attempt,
            "completion": completion,
            "accuracy": accuracy,
            "eligible": eligible,
        }

    @staticmethod
    def submit_boss_level(student_id: int, boss_level_id: int, response_text: str) -> BossLevelAttempt:
        boss_level = BossLevel.query.get(boss_level_id)
        if not boss_level or not boss_level.is_active:
            raise ValueError("Boss level not found.")

        existing = BossLevelAttempt.query.filter_by(
            boss_level_id=boss_level_id,
            student_id=student_id,
        ).first()
        if existing:
            raise ValueError("You already cleared this boss level.")

        status = EconomyService.boss_status_for_student(student_id, boss_level)
        if not status["eligible"]:
            raise ValueError("Boss level is still locked for your progress.")

        clean_response = (response_text or "").strip()
        if len(clean_response) < 40:
            raise ValueError("Please write a more complete boss-level answer before submitting.")

        attempt = BossLevelAttempt(
            boss_level_id=boss_level.id,
            student_id=student_id,
            response_text=clean_response,
            status="completed",
            coins_awarded=int(boss_level.reward_coins or 0),
            completed_at=datetime.utcnow(),
        )
        db.session.add(attempt)
        db.session.flush()

        EconomyService.award_coins(
            student_id,
            int(boss_level.reward_coins or 0),
            reference_type="boss_level",
            reference_id=attempt.id,
            title=f"Boss level clear: {boss_level.title}",
            description=f"Boss level reward for {boss_level.course.title}.",
            created_by="system",
            idempotency_key=f"boss-level:{student_id}:{boss_level.id}",
        )
        db.session.flush()
        return attempt

    @staticmethod
    def leaderboard(period: str, *, limit: int = 10) -> list[dict]:
        meta = EconomyService.leaderboard_period_meta(period)
        key = meta["period"]
        start_date = meta["start_date"]

        rows = (
            db.session.query(
                StudentDailyActivity.student_id,
                func.sum(StudentDailyActivity.coins_earned).label("coins_earned"),
                func.sum(StudentDailyActivity.questions_attempted).label("questions_attempted"),
            )
            .join(User, User.id == StudentDailyActivity.student_id)
            .filter(StudentDailyActivity.activity_date >= start_date)
            .filter(User.role == Role.STUDENT.value, User.show_on_leaderboard.is_(True))
            .group_by(StudentDailyActivity.student_id)
            .order_by(
                func.sum(StudentDailyActivity.coins_earned).desc(),
                func.sum(StudentDailyActivity.questions_attempted).desc(),
                StudentDailyActivity.student_id.asc(),
            )
            .limit(limit)
            .all()
        )

        leaderboard_rows: list[dict] = []
        rank = 1
        for row in rows:
            user = User.query.get(int(row.student_id))
            if not user:
                continue
            leaderboard_rows.append(
                {
                    "rank": rank,
                    "student_id": user.id,
                    "display_name": EconomyService.public_display_name(user),
                    "username": user.username,
                    "avatar_url": getattr(user, "avatar_url", None),
                    "coins_earned": int(row.coins_earned or 0),
                    "questions_attempted": int(row.questions_attempted or 0),
                    "rank_bonus_coins": EconomyService.leaderboard_reward_amount(key, rank),
                }
            )
            rank += 1

        return leaderboard_rows

    @staticmethod
    def public_display_name(user: User) -> str:
        first_name = (getattr(user, "first_name", "") or "").strip()
        last_name = (getattr(user, "last_name", "") or "").strip()
        if first_name and last_name:
            return f"{first_name} {last_name[:1].upper()}."
        if first_name:
            return first_name
        return (getattr(user, "username", "") or f"Student {getattr(user, 'id', '')}").strip()

    @staticmethod
    def _normalize_chat_body(body: str) -> str:
        clean = (body or "").strip()
        return re.sub(r"\s+", " ", clean)

    @staticmethod
    def _moderation_flags(body: str) -> list[str]:
        haystack = EconomyService._normalize_chat_body(body).lower()
        if not haystack:
            return []

        flags: list[str] = []
        for category, keywords in EconomyService.CHAT_BLOCKLIST.items():
            if any(keyword in haystack for keyword in keywords):
                flags.append(category)

        if re.search(r"(https?://|www\.|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", haystack, re.IGNORECASE):
            flags.append("external_contact")
        if re.search(r"\b\d{10,}\b", haystack):
            flags.append("personal_contact")
        return list(dict.fromkeys(flags))

    @staticmethod
    def _enforce_chat_safety(body: str) -> str:
        clean_body = EconomyService._normalize_chat_body(body)
        if len(clean_body) < 2:
            raise ValueError("Message is too short.")
        if len(clean_body) > 600:
            raise ValueError("Message is too long.")

        flags = EconomyService._moderation_flags(clean_body)
        if flags:
            labels = ", ".join(flag.replace("_", " ") for flag in flags)
            raise ValueError(f"Message blocked by student safety rules: {labels}.")
        return clean_body

    @staticmethod
    def log_chat_moderation_event(student_id: int, course_id: int, body: str, flags: list[str]) -> CourseChatModerationEvent:
        event = CourseChatModerationEvent(
            course_id=course_id,
            sender_student_id=student_id,
            attempted_body=EconomyService._normalize_chat_body(body),
            flagged_categories=",".join(flags),
            status="blocked",
        )
        db.session.add(event)
        db.session.flush()
        return event

    @staticmethod
    def moderation_queue(limit: int = 200) -> list[CourseChatModerationEvent]:
        return (
            CourseChatModerationEvent.query
            .order_by(CourseChatModerationEvent.created_at.desc(), CourseChatModerationEvent.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_moderation_event(event_id: int, status: str, reviewer_id: int, notes: str | None = None) -> CourseChatModerationEvent:
        event = db.session.get(CourseChatModerationEvent, event_id)
        if event is None:
            raise ValueError("Moderation event was not found.")
        clean_status = (status or "").strip().lower()
        if clean_status not in {"reviewed", "dismissed"}:
            raise ValueError("Unsupported moderation status.")
        event.status = clean_status
        event.reviewed_by_id = reviewer_id
        event.reviewed_at = datetime.utcnow()
        event.moderator_notes = (notes or "").strip() or None
        db.session.flush()
        return event

    @staticmethod
    def recent_messages(course_id: int, *, limit: int = 100) -> list[CourseChatMessage]:
        rows = (
            CourseChatMessage.query
            .filter_by(course_id=course_id, status="active")
            .order_by(CourseChatMessage.created_at.desc(), CourseChatMessage.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))

    @staticmethod
    def student_chat_courses(student_id: int) -> list[Course]:
        enrollments = (
            Enrollment.query
            .join(Course, Course.id == Enrollment.course_id)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.status == "active",
                Course.community_enabled.is_(True),
            )
            .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
            .all()
        )
        return [row.course for row in enrollments if row.course]

    @staticmethod
    def chat_payload(student_id: int, course_id: int | None = None, *, limit: int = 25) -> dict:
        courses = EconomyService.student_chat_courses(student_id)
        active_course = next((course for course in courses if course.id == course_id), None)
        if active_course is None and courses:
            active_course = courses[0]

        messages = EconomyService.recent_messages(active_course.id, limit=limit) if active_course else []
        return {
            "courses": [
                {
                    "id": course.id,
                    "title": course.title,
                    "track": (course.track_type or "course").title(),
                }
                for course in courses
            ],
            "active_course_id": active_course.id if active_course else None,
            "active_course_title": active_course.title if active_course else None,
            "messages": [
                {
                    "id": message.id,
                    "sender_name": EconomyService.public_display_name(message.sender) if message.sender else f"Student {message.sender_student_id}",
                    "body": message.body,
                    "created_at": message.created_at.strftime("%d %b %Y %I:%M %p"),
                    "is_self": message.sender_student_id == student_id,
                }
                for message in messages
            ],
            "moderation_notice": "Student chat blocks abuse, drugs, weapons, illegal activity, and off-platform contact sharing.",
        }

    @staticmethod
    def post_course_message(student_id: int, course_id: int, body: str) -> CourseChatMessage:
        enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course_id, status="active").first()
        if not enrollment:
            raise ValueError("You can chat only inside courses you are enrolled in.")

        course = Course.query.get(course_id)
        if not course or not bool(getattr(course, "community_enabled", True)):
            raise ValueError("Community chat is not enabled for this course.")

        clean_body = EconomyService._normalize_chat_body(body)
        flags = EconomyService._moderation_flags(clean_body)
        if flags:
            EconomyService.log_chat_moderation_event(student_id, course_id, clean_body, flags)
            db.session.commit()
            labels = ", ".join(flag.replace("_", " ") for flag in flags)
            raise ValueError(f"Message blocked by student safety rules: {labels}.")
        clean_body = EconomyService._enforce_chat_safety(clean_body)

        message = CourseChatMessage(
            course_id=course_id,
            sender_student_id=student_id,
            body=clean_body,
            status="active",
        )
        db.session.add(message)
        db.session.flush()
        return message
