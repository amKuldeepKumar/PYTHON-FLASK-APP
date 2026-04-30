from __future__ import annotations

from typing import Iterable

from ..extensions import db
from ..models.rbac import Permission, RoleModel, RolePermission
from ..models.user import User, Role as UserRole

DEFAULT_ROLES = [
    ("SUPERADMIN", "Super Admin", "system"),
    ("ADMIN", "Admin", "tenant"),
    ("SUB_ADMIN", "Sub Admin", "tenant"),
    ("SEO", "SEO Manager", "tenant"),
    ("ACCOUNTS", "Accounts", "tenant"),
    ("SUPPORT", "Support", "tenant"),
    ("TEACHER", "Teacher", "tenant"),
    ("STUDENT", "Student", "tenant"),
    ("PARENT", "Parent", "tenant"),
]

DEFAULT_PERMISSIONS = [
    ("superadmin.dashboard.view", "View superadmin dashboard", "System"),
    ("admin.dashboard.view", "View admin dashboard", "Admin"),
    ("admin.students.view", "View students", "Admin"),
    ("admin.courses.view", "View courses", "Admin"),
    ("admin.support.view", "View support", "Admin"),
    ("student.dashboard.view", "View student dashboard", "Student"),
    ("content.pages.manage", "Manage front pages", "Content"),
    ("seo.settings.manage", "Manage SEO settings", "Content"),
    ("theme.manage", "Manage theme builder", "Content"),
    ("security.settings.manage", "Manage security settings", "Security"),
    ("notifications.view", "View notifications", "System"),
    ("rbac.roles.manage", "Manage roles", "RBAC"),
    ("rbac.permissions.manage", "Manage permissions", "RBAC"),
    ("rbac.admin_permissions.manage", "Manage admin custom permissions", "RBAC"),
    ("superadmin.admins.manage", "Manage admins", "System"),
    ("reports.view", "View platform reports", "Reports"),
    ("courses.publish", "Publish and unpublish courses", "Academy"),
    ("courses.structure.manage", "Manage course structure", "Academy"),
    ("questions.manage", "Manage lesson questions", "Academy"),
]

ROLE_PERMISSION_MAP = {
    "SUPERADMIN": [code for code, _, _ in DEFAULT_PERMISSIONS],
    "ADMIN": [
        "admin.dashboard.view",
        "admin.students.view",
        "admin.courses.view",
        "admin.support.view",
        "courses.publish",
        "courses.structure.manage",
        "questions.manage",
        "notifications.view",
    ],
    "SUB_ADMIN": [
        "admin.dashboard.view",
        "admin.students.view",
        "admin.support.view",
        "notifications.view",
    ],
    "SEO": [
        "admin.dashboard.view",
        "content.pages.manage",
        "seo.settings.manage",
        "theme.manage",
        "notifications.view",
    ],
    "ACCOUNTS": ["admin.dashboard.view", "notifications.view", "reports.view"],
    "SUPPORT": ["admin.dashboard.view", "admin.support.view", "admin.students.view", "notifications.view"],
    "TEACHER": ["admin.dashboard.view", "admin.students.view", "student.dashboard.view"],
    "STUDENT": ["student.dashboard.view"],
    "PARENT": ["student.dashboard.view"],
}

ROLE_BY_USER_ROLE = {
    UserRole.SUPERADMIN.value: "SUPERADMIN",
    UserRole.ADMIN.value: "ADMIN",
    UserRole.SUB_ADMIN.value: "SUB_ADMIN",
    UserRole.SEO.value: "SEO",
    UserRole.ACCOUNTS.value: "ACCOUNTS",
    UserRole.SUPPORT.value: "SUPPORT",
    UserRole.TEACHER.value: "TEACHER",
    UserRole.STUDENT.value: "STUDENT",
    UserRole.PARENT.value: "PARENT",
}


def _get_or_create_role(code: str, name: str, scope: str) -> RoleModel:
    role = RoleModel.query.filter_by(code=code).first()
    if role is None:
        role = RoleModel(code=code, name=name, scope=scope)
        db.session.add(role)
        db.session.flush()
    else:
        role.name = name
        role.scope = scope
    return role


def _get_or_create_permission(code: str, name: str, group: str) -> Permission:
    permission = Permission.query.filter_by(code=code).first()
    if permission is None:
        permission = Permission(code=code, name=name, group=group)
        db.session.add(permission)
        db.session.flush()
    else:
        permission.name = name
        permission.group = group
    return permission


def _grant_permissions(role: RoleModel, perm_codes: Iterable[str], perm_by_code: dict[str, Permission]) -> None:
    existing_perm_ids = {
        row.permission_id for row in RolePermission.query.filter_by(role_id=role.id).all()
    }
    for code in perm_codes:
        permission = perm_by_code.get(code)
        if permission and permission.id not in existing_perm_ids:
            db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))


def seed_default_rbac() -> None:
    roles = [_get_or_create_role(*data) for data in DEFAULT_ROLES]
    permissions = [_get_or_create_permission(*data) for data in DEFAULT_PERMISSIONS]
    db.session.flush()

    perm_by_code = {permission.code: permission for permission in permissions}
    role_by_code = {role.code: role for role in roles}

    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        role = role_by_code.get(role_code)
        if role:
            _grant_permissions(role, permission_codes, perm_by_code)

    db.session.flush()

    for user in User.query.all():
        mapped_code = ROLE_BY_USER_ROLE.get((user.role or "").strip().upper())
        if mapped_code and user.role_id is None:
            role = role_by_code.get(mapped_code)
            if role:
                user.role_id = role.id

    db.session.commit()
