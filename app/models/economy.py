from __future__ import annotations

from datetime import datetime

from ..extensions import db


class StudentWallet(db.Model):
    __tablename__ = "student_wallets"
    __table_args__ = (
        db.UniqueConstraint("student_id", name="uq_student_wallets_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    coin_balance = db.Column(db.Integer, nullable=False, default=0)
    wallet_status = db.Column(db.String(20), nullable=False, default="active", index=True)
    last_reconciled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship(
        "User",
        backref=db.backref("wallet", uselist=False, lazy="joined"),
        lazy="joined",
    )
    ledger_entries = db.relationship(
        "WalletLedgerEntry",
        back_populates="wallet",
        cascade="all, delete-orphan",
        order_by="WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc()",
    )


class WalletLedgerEntry(db.Model):
    __tablename__ = "wallet_ledger"
    __table_args__ = (
        db.UniqueConstraint("idempotency_key", name="uq_wallet_ledger_idempotency_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("student_wallets.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    txn_type = db.Column(db.String(20), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    balance_before = db.Column(db.Integer, nullable=False, default=0)
    balance_after = db.Column(db.Integer, nullable=False, default=0)
    reference_type = db.Column(db.String(40), nullable=False, default="system", index=True)
    reference_id = db.Column(db.String(64), nullable=True, index=True)
    title = db.Column(db.String(120), nullable=False, default="Wallet update")
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(20), nullable=False, default="system", index=True)
    idempotency_key = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    wallet = db.relationship("StudentWallet", back_populates="ledger_entries", lazy="joined")
    student = db.relationship("User", lazy="joined")


class CourseCoinRedemption(db.Model):
    __tablename__ = "course_coin_redemptions"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_course_coin_redemptions_student_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    ledger_entry_id = db.Column(db.Integer, db.ForeignKey("wallet_ledger.id"), nullable=True, index=True)
    coins_spent = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="completed", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("User", lazy="joined")
    course = db.relationship("Course", lazy="joined")
    ledger_entry = db.relationship("WalletLedgerEntry", lazy="joined")


class BossLevel(db.Model):
    __tablename__ = "boss_levels"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    prompt_text = db.Column(db.Text, nullable=True)
    reward_coins = db.Column(db.Integer, nullable=False, default=50)
    unlock_completion_percent = db.Column(db.Integer, nullable=False, default=100)
    min_accuracy = db.Column(db.Integer, nullable=False, default=60)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship(
        "Course",
        backref=db.backref(
            "boss_levels",
            lazy="select",
            order_by="BossLevel.sort_order.asc(), BossLevel.id.asc()",
        ),
        lazy="joined",
    )


class BossLevelAttempt(db.Model):
    __tablename__ = "boss_level_attempts"
    __table_args__ = (
        db.UniqueConstraint("boss_level_id", "student_id", name="uq_boss_level_attempts_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    boss_level_id = db.Column(db.Integer, db.ForeignKey("boss_levels.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    response_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="completed", index=True)
    coins_awarded = db.Column(db.Integer, nullable=False, default=0)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    boss_level = db.relationship("BossLevel", lazy="joined")
    student = db.relationship("User", lazy="joined")


class CourseChatMessage(db.Model):
    __tablename__ = "course_chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    sender_student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship("Course", lazy="joined")
    sender = db.relationship("User", lazy="joined")


class CourseChatModerationEvent(db.Model):
    __tablename__ = "course_chat_moderation_events"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    sender_student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    attempted_body = db.Column(db.Text, nullable=False)
    flagged_categories = db.Column(db.String(255), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="blocked", index=True)
    moderator_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    course = db.relationship("Course", lazy="joined")
    sender = db.relationship("User", foreign_keys=[sender_student_id], lazy="joined")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id], lazy="joined")


class LeaderboardRewardPolicy(db.Model):
    __tablename__ = "leaderboard_reward_policies"

    id = db.Column(db.Integer, primary_key=True)
    weekly_first_coins = db.Column(db.Integer, nullable=False, default=30)
    weekly_second_coins = db.Column(db.Integer, nullable=False, default=20)
    weekly_third_coins = db.Column(db.Integer, nullable=False, default=10)
    monthly_first_coins = db.Column(db.Integer, nullable=False, default=60)
    monthly_second_coins = db.Column(db.Integer, nullable=False, default=40)
    monthly_third_coins = db.Column(db.Integer, nullable=False, default=20)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LeaderboardRewardClaim(db.Model):
    __tablename__ = "leaderboard_reward_claims"
    __table_args__ = (
        db.UniqueConstraint("period_type", "period_key", "student_id", name="uq_leaderboard_reward_claim_period_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    period_type = db.Column(db.String(20), nullable=False, index=True)
    period_key = db.Column(db.String(40), nullable=False, index=True)
    rank_position = db.Column(db.Integer, nullable=False, default=0)
    coins_awarded = db.Column(db.Integer, nullable=False, default=0)
    ledger_entry_id = db.Column(db.Integer, db.ForeignKey("wallet_ledger.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("User", lazy="joined")
    ledger_entry = db.relationship("WalletLedgerEntry", lazy="joined")
