"""Phase 2: RBAC models.

RoleModel: role codes (SUPERADMIN/ADMIN/SEO/ACCOUNTS/SUPPORT/STUDENT)
Permission: fine-grained permission codes (cms.pages.edit, courses.manage, etc.)
RolePermission: many-to-many mapping.
"""

from datetime import datetime
from ..extensions import db


class RoleModel(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)

    # system roles are for SuperAdmin-only features
    scope = db.Column(db.String(20), nullable=False, default="tenant")  # system|tenant

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)

    # optional grouping for UI management (CMS, Commerce, Users, System, etc.)
    group = db.Column(db.String(60), nullable=False, default="General")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), primary_key=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
