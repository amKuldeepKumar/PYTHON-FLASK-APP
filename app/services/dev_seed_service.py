from __future__ import annotations

from datetime import datetime

from flask import current_app
from sqlalchemy import or_

from ..extensions import db
from ..models.rbac import RoleModel
from ..models.user import Role as UserRole, User
from ..models.user_preferences import UserPreferences
from .rbac_service import seed_default_rbac


DEFAULT_LOCAL_USERS = [
    {
        "role": UserRole.SUPERADMIN.value,
        "username": "superadmin",
        "email": "superadmin@fluencify.local",
        "password": "Admin@123",
        "first_name": "Super",
        "last_name": "Admin",
    },
    {
        "role": UserRole.ADMIN.value,
        "username": "admin",
        "email": "admin@fluencify.local",
        "password": "Admin@123",
        "first_name": "Platform",
        "last_name": "Admin",
    },
    {
        "role": UserRole.STUDENT.value,
        "username": "student",
        "email": "student@fluencify.local",
        "password": "Student@123",
        "first_name": "Demo",
        "last_name": "Student",
        "phone": "9999999999",
        "country": "India",
        "target_exam": "English Foundation",
        "current_level": "Beginner",
        "study_goal": "Speak simple English confidently every day.",
    },
]


def _is_local_dev_environment() -> bool:
    return bool(
        current_app.config.get("ENV_NAME") == "development"
        or current_app.debug
    )


def local_dev_login_accounts() -> list[dict]:
    if not _is_local_dev_environment():
        return []
    return [
        {
            "role": item["role"],
            "username": item["username"],
            "email": item["email"],
            "password": item["password"],
        }
        for item in DEFAULT_LOCAL_USERS
    ]


def ensure_local_dev_users() -> list[dict]:
    if not _is_local_dev_environment():
        return []

    seed_default_rbac()
    role_map = {row.code: row for row in RoleModel.query.all()}
    created_accounts: list[dict] = []

    for item in DEFAULT_LOCAL_USERS:
        role_code = item["role"]
        user = (
            User.query.filter(
                or_(
                    User.username == item["username"],
                    User.email == item["email"],
                )
            )
            .order_by(User.id.asc())
            .first()
        )

        if user is None:
            user = User(username=item["username"], email=item["email"])
            db.session.add(user)

        user.username = item["username"]
        user.email = item["email"]
        user.role = role_code
        user.role_id = getattr(role_map.get(role_code), "id", None)
        user.is_active = True
        user.first_name = item.get("first_name")
        user.last_name = item.get("last_name")
        user.phone = item.get("phone")
        user.country = item.get("country")
        user.target_exam = item.get("target_exam")
        user.current_level = item.get("current_level")
        user.study_goal = item.get("study_goal")
        if role_code == UserRole.STUDENT.value and user.profile_completed_at is None:
            user.profile_completed_at = datetime.utcnow()
        user.set_password(item["password"])
        db.session.flush()

        prefs = UserPreferences.query.filter_by(user_id=user.id).first()
        if prefs is None:
            prefs = UserPreferences(
                user_id=user.id,
                ui_language_code="en",
                learning_language_code="en",
                accent="en-IN",
                use_native_language_support=(role_code == UserRole.STUDENT.value),
            )
            db.session.add(prefs)
        else:
            prefs.ui_language_code = prefs.ui_language_code or "en"
            prefs.learning_language_code = prefs.learning_language_code or "en"
            prefs.accent = prefs.accent or "en-IN"

        created_accounts.append(
            {
                "role": role_code,
                "username": user.username,
                "email": user.email,
                "password": item["password"],
            }
        )

    db.session.commit()
    current_app.logger.warning(
        "Local dev accounts were auto-created because the database had no users: %s",
        ", ".join(account["username"] for account in created_accounts),
    )
    return created_accounts
