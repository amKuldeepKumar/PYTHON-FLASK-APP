from __future__ import annotations

import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, login_manager


class Role(str, enum.Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    SUB_ADMIN = "SUB_ADMIN"
    SEO = "SEO"
    ACCOUNTS = "ACCOUNTS"
    SUPPORT = "SUPPORT"
    EDITOR = "EDITOR"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(30), nullable=False, default=Role.STUDENT.value, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    father_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    country = db.Column(db.String(80), nullable=True)
    state = db.Column(db.String(80), nullable=True)
    city = db.Column(db.String(80), nullable=True)
    address = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    gender = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)

    target_exam = db.Column(db.String(40), nullable=True)
    current_level = db.Column(db.String(40), nullable=True)
    target_score = db.Column(db.String(40), nullable=True)
    native_language = db.Column(db.String(40), nullable=True)

    bio = db.Column(db.Text, nullable=True)
    study_goal = db.Column(db.Text, nullable=True)
    preferred_study_time = db.Column(db.String(40), nullable=True)
    profile_completed_at = db.Column(db.DateTime, nullable=True)

    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    organization_name = db.Column(db.String(120), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    managed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    coin_balance = db.Column(db.Integer, nullable=False, default=0)
    lifetime_coins = db.Column(db.Integer, nullable=False, default=0)
    speaking_sessions_completed = db.Column(db.Integer, nullable=False, default=0)
    speaking_fast_submit_flags = db.Column(db.Integer, nullable=False, default=0)
    longest_learning_streak = db.Column(db.Integer, nullable=False, default=0)
    show_on_leaderboard = db.Column(db.Boolean, nullable=False, default=True, index=True)

    preferences = db.relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    login_events = db.relationship(
        "LoginEvent",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    daily_activity_rows = db.relationship(
        "StudentDailyActivity",
        back_populates="student",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    enrollments = db.relationship(
        "Enrollment",
        foreign_keys="Enrollment.student_id",
        back_populates="student",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    lesson_progress = db.relationship(
        "LessonProgress",
        back_populates="student",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    question_attempts = db.relationship(
        "QuestionAttempt",
        back_populates="student",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    course_progress_rows = db.relationship(
        "CourseProgress",
        back_populates="student",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    children = db.relationship(
        "User",
        backref=db.backref("parent_admin", remote_side=[id]),
        foreign_keys=[admin_id],
        lazy="dynamic",
    )
    organization = db.relationship(
        "User",
        foreign_keys=[organization_id],
        remote_side=[id],
        backref=db.backref("organization_members", lazy="dynamic"),
        lazy="joined",
    )
    assigned_teacher = db.relationship(
        "User",
        foreign_keys=[teacher_id],
        remote_side=[id],
        backref=db.backref("assigned_students", lazy="dynamic"),
        lazy="joined",
    )
    manager = db.relationship(
        "User",
        foreign_keys=[managed_by_user_id],
        remote_side=[id],
        backref=db.backref("managed_learners", lazy="dynamic"),
        lazy="joined",
    )

    rbac_role = db.relationship("RoleModel", foreign_keys=[role_id], lazy="joined")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def role_code(self) -> str:
        return (self.role or "").strip().upper()

    @property
    def is_superadmin(self) -> bool:
        return self.role_code == Role.SUPERADMIN.value

    @property
    def is_admin(self) -> bool:
        return self.role_code == Role.ADMIN.value

    @property
    def is_sub_admin(self) -> bool:
        return self.role_code == Role.SUB_ADMIN.value

    @property
    def is_student(self) -> bool:
        return self.role_code == Role.STUDENT.value

    @property
    def is_teacher(self) -> bool:
        return self.role_code == Role.TEACHER.value

    @property
    def is_parent(self) -> bool:
        return self.role_code == Role.PARENT.value

    @property
    def is_staff(self) -> bool:
        return self.role_code in {
            Role.SUPERADMIN.value,
            Role.ADMIN.value,
            Role.SUB_ADMIN.value,
            Role.SEO.value,
            Role.ACCOUNTS.value,
            Role.SUPPORT.value,
            Role.EDITOR.value,
            Role.TEACHER.value,
        }

    @property
    def full_name(self) -> str:
        full = f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip()
        return full or self.username

    def scope_admin_id(self) -> int | None:
        if self.is_superadmin:
            return None
        if self.is_admin:
            return self.id
        if self.organization_id:
            return self.organization_id
        if self.admin_id:
            return self.admin_id
        return None

    def effective_admin_id(self) -> int | None:
        return self.scope_admin_id()

    def tenant_owner_id(self) -> int | None:
        if self.is_superadmin:
            return None
        if self.is_admin:
            return self.id
        if self.organization_id:
            return self.organization_id
        if self.admin_id:
            return self.admin_id
        if self.managed_by_user_id:
            return self.managed_by_user_id
        return self.id if self.is_student or self.is_parent else None

    def learner_scope_label(self) -> str:
        return "Organization learner" if (self.organization_id or self.admin_id) else "Independent learner"

    def support_chain(self) -> dict:
        principal = self.organization or (db.session.get(User, self.admin_id) if self.admin_id else None)
        teacher = self.assigned_teacher
        return {
            "organization_name": self.organization_name or (principal.organization_name if principal else None) or (principal.full_name if principal else None),
            "principal_name": principal.full_name if principal else "Fluencify Support Team",
            "teacher_name": teacher.full_name if teacher else "Not assigned yet",
            "is_independent": principal is None,
        }

    def validate_tenancy(self) -> bool:
        if self.is_superadmin:
            return self.admin_id is None and self.organization_id is None
        if self.is_admin:
            return self.admin_id is None
        if self.is_sub_admin:
            return self.organization_id is not None or self.admin_id is not None
        if self.is_student or self.is_parent or self.is_teacher:
            return True
        return True

    def profile_completion_percent(self) -> int:
        pref = getattr(self, "preferences", None)
        fields = [
            self.first_name,
            self.last_name,
            self.father_name,
            self.phone,
            self.country,
            self.state,
            self.city,
            self.address,
            self.avatar_url,
            self.gender,
            self.date_of_birth,
            self.target_exam,
            self.current_level,
            self.target_score,
            self.native_language,
            self.bio,
            self.study_goal,
            self.preferred_study_time,
            getattr(pref, "ui_language_code", None),
            getattr(pref, "learning_language_code", None),
        ]
        total = len(fields)
        filled = sum(1 for value in fields if value not in (None, ""))
        return int(round((filled / total) * 100)) if total else 0

    def profile_next_steps(self) -> list[str]:
        pref = getattr(self, "preferences", None)
        steps: list[str] = []
        if not self.avatar_url:
            steps.append("Add your profile photo")
        if not (self.first_name and self.last_name):
            steps.append("Add your full name")
        if not self.father_name:
            steps.append("Add your father name for certificates")
        if not self.phone:
            steps.append("Add your phone number")
        if not self.address:
            steps.append("Add your full address")
        if not self.country:
            steps.append("Add your country")
        if not getattr(pref, "ui_language_code", None):
            steps.append("Choose your UI language")
        if not self.native_language:
            steps.append("Choose your native language")
        if not getattr(pref, "learning_language_code", None):
            steps.append("Choose your learning language")
        if not self.target_exam:
            steps.append("Choose your target exam")
        if not self.current_level:
            steps.append("Choose your current level")
        if not self.study_goal:
            steps.append("Write your study goal")
        return steps[:6]

    def needs_student_onboarding(self) -> bool:
        if not self.is_student:
            return False
        required = [
            self.first_name,
            self.phone,
            self.country,
            self.target_exam,
            self.current_level,
            self.study_goal,
        ]
        return any(not value for value in required)

    def latest_learning_summary(self) -> str:
        if self.profile_completion_percent() < 35:
            return "Complete your profile and begin your first guided practice session."
        if self.target_exam and self.current_level:
            return f"Your target is {self.target_exam} and your current level is {self.current_level}. Keep the momentum going."
        return "Keep practicing today and turn consistency into confident English."

    def performance_snapshot(self) -> dict:
        from .lms import QuestionAttempt

        attempts = self.question_attempts.order_by(QuestionAttempt.attempted_at.asc()).all()
        if not attempts:
            return {
                "attempt_count": 0,
                "accuracy_avg": 0,
                "grammar_avg": 0,
                "clarity_avg": 0,
                "confidence_avg": 0,
                "progress_trend": "No attempts yet",
            }

        def avg(attr: str) -> int:
            vals = [getattr(a, attr) for a in attempts if getattr(a, attr) is not None]
            if not vals:
                return 0
            return int(round(sum(vals) / len(vals)))

        first_half = attempts[: max(1, len(attempts) // 2)]
        second_half = attempts[max(1, len(attempts) // 2) :]

        def accuracy_of(rows):
            vals = [r.accuracy_score for r in rows if r.accuracy_score is not None]
            if not vals:
                return 0
            return sum(vals) / len(vals)

        trend = "Stable"
        if second_half and first_half:
            diff = accuracy_of(second_half) - accuracy_of(first_half)
            if diff >= 5:
                trend = "Improving"
            elif diff <= -5:
                trend = "Needs support"

        return {
            "attempt_count": len(attempts),
            "accuracy_avg": avg("accuracy_score"),
            "grammar_avg": avg("grammar_score"),
            "clarity_avg": avg("clarity_score"),
            "confidence_avg": avg("confidence_score"),
            "progress_trend": trend,
        }

    def has_perm(self, perm_code: str) -> bool:
        if self.is_superadmin:
            return True

        try:
            from .admin_permission_override import AdminPermissionOverride
            from .rbac import Permission, RoleModel, RolePermission

            perm = Permission.query.filter_by(code=perm_code).first()
            if perm is None:
                return False

            override = AdminPermissionOverride.query.filter_by(
                user_id=self.id,
                permission_id=perm.id,
            ).first()
            if override is not None:
                return bool(override.allowed)

            role_id = self.role_id
            if role_id is None:
                role_model = RoleModel.query.filter_by(code=self.role_code).first()
                role_id = role_model.id if role_model else None

            if role_id is None:
                return False

            return (
                db.session.query(RolePermission)
                .filter(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == perm.id,
                )
                .first()
                is not None
            )
        except Exception:
            return False


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None
