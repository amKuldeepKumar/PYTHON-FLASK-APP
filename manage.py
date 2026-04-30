"""
Phase Coverage:
- Phase 1: CLI commands for dev productivity, DB reset (dev-only), and SuperAdmin creation.
Future:
- Phase 2+: Seed roles/permissions matrix (RBAC), create default Admin, create demo content.
- Phase 4+: Add audit log commands and security diagnostics.
"""

import click
from flask.cli import with_appcontext

from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.models.rbac import RoleModel, Permission, RolePermission
from app.models.audit import AuditLog

app = create_app()


@app.cli.command("db-reset")
@with_appcontext
def db_reset():
    """
    Phase 1 (DEV ONLY):
    - Drop all tables and recreate them.
    - Useful during early development.

    Future:
    - Phase 2+: prefer migrations + seeds, avoid dropping DB in staging/prod.
    """
    db.drop_all()
    db.create_all()
    click.echo("Database reset complete.")


@app.cli.command("create-superadmin")
@click.option("--email", prompt=True)
@click.option("--username", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_superadmin(email: str, username: str, password: str):
    """
    Phase 1:
    - Creates the first SuperAdmin user.

    Future:
    - Phase 2+: also seed Role/Permission tables (if using permission matrix),
      and create initial system settings (theme defaults, provider registry placeholders).
    """
    if User.query.filter((User.email == email) | (User.username == username)).first():
        click.echo("User already exists with that email/username.")
        return

    # Ensure RBAC seed exists so superadmin has an RBAC role row.
    _seed_rbac_if_missing()

    rm = RoleModel.query.filter_by(code=Role.SUPERADMIN.value).first()
    u = User(
        email=email.strip().lower(),
        username=username.strip(),
        role=Role.SUPERADMIN.value,
        role_id=rm.id if rm else None,
        admin_id=None,
    )
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    click.echo("SuperAdmin created successfully.")


def _seed_rbac_if_missing() -> None:
    """Idempotent seed for roles/permissions used in Phase 2."""

    # Roles
    roles = [
        (Role.SUPERADMIN.value, "SuperAdmin", "system"),
        (Role.ADMIN.value, "Admin", "tenant"),
        (Role.SEO.value, "SEO", "tenant"),
        (Role.ACCOUNTS.value, "Accounts", "tenant"),
        (Role.SUPPORT.value, "Support", "tenant"),
        (Role.STUDENT.value, "Student", "tenant"),
    ]
    for code, name, scope in roles:
        if not RoleModel.query.filter_by(code=code).first():
            db.session.add(RoleModel(code=code, name=name, scope=scope))

    # Permissions (minimal set for Phase 2 skeleton)
    perms = [
        ("rbac.roles.manage", "Manage roles", "System"),
        ("rbac.permissions.manage", "Manage permissions", "System"),
        ("audit.view", "View audit logs", "System"),
        ("admin.students.view", "View students", "Admin"),
        ("admin.courses.view", "View courses", "Admin"),
        ("admin.support.view", "View support", "Admin"),
    ]
    for code, name, group in perms:
        if not Permission.query.filter_by(code=code).first():
            db.session.add(Permission(code=code, name=name, group=group))

    db.session.commit()

    # Role-Permission mapping
    def grant(role_code: str, perm_code: str):
        r = RoleModel.query.filter_by(code=role_code).first()
        p = Permission.query.filter_by(code=perm_code).first()
        if not r or not p:
            return
        exists = RolePermission.query.filter_by(role_id=r.id, permission_id=p.id).first()
        if not exists:
            db.session.add(RolePermission(role_id=r.id, permission_id=p.id))

    # SuperAdmin gets system perms (and has_perm already allows all).
    for perm_code, *_ in perms:
        grant(Role.SUPERADMIN.value, perm_code)

    # Admin gets admin module perms
    for perm_code in ["admin.students.view", "admin.courses.view", "admin.support.view"]:
        grant(Role.ADMIN.value, perm_code)

    db.session.commit()


@app.cli.command("seed-rbac")
@with_appcontext
def seed_rbac():
    """Phase 2: Seed default roles, permissions and mappings."""
    _seed_rbac_if_missing()
    click.echo("RBAC seed complete.")