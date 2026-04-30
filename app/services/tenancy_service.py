from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import or_

from ..extensions import db
from ..models.lms import Enrollment, QuestionAttempt
from ..models.user import Role, User


TENANT_STAFF_ROLES = [
    Role.ADMIN.value,
    Role.SUB_ADMIN.value,
    Role.SEO.value,
    Role.SUPPORT.value,
    Role.ACCOUNTS.value,
    Role.TEACHER.value,
]


def organization_scope_id(user: User) -> int | None:
    if user.is_superadmin:
        return None
    if user.is_admin:
        return user.id
    if user.is_sub_admin:
        return user.organization_id or user.admin_id
    return user.organization_id or user.admin_id


def tenant_students_for(user: User):
    query = User.query.filter_by(role=Role.STUDENT.value)
    if user.is_superadmin:
        return query.order_by(User.created_at.desc()).all()
    if user.role_code == Role.TEACHER.value:
        return query.filter_by(teacher_id=user.id).order_by(User.created_at.desc()).all()
    if user.is_sub_admin:
        scope_id = organization_scope_id(user)
        return query.filter(
            or_(
                User.managed_by_user_id == user.id,
                User.admin_id == user.id,
                User.organization_id == scope_id,
            )
        ).order_by(User.created_at.desc()).all()
    if user.is_admin or user.role_code in {Role.SEO.value, Role.SUPPORT.value, Role.ACCOUNTS.value}:
        scope_id = organization_scope_id(user) or user.id
        return query.filter(
            or_(
                User.organization_id == scope_id,
                User.admin_id == scope_id,
            )
        ).order_by(User.created_at.desc()).all()
    return []


def tenant_staff_for(admin_user: User):
    query = User.query.filter(User.role.in_(TENANT_STAFF_ROLES))
    if admin_user.is_superadmin:
        return query.order_by(User.created_at.desc()).all()
    scope_id = organization_scope_id(admin_user) or admin_user.id
    if admin_user.is_sub_admin:
        return query.filter(
            or_(
                User.id == admin_user.id,
                User.admin_id == admin_user.id,
                User.organization_id == scope_id,
            )
        ).order_by(User.created_at.desc()).all()
    return query.filter(
        or_(
            User.id == scope_id,
            User.admin_id == scope_id,
            User.organization_id == scope_id,
        )
    ).order_by(User.created_at.desc()).all()


def student_support_chain(student: User) -> dict:
    principal = student.organization or (User.query.get(student.admin_id) if student.admin_id else None)
    teacher = User.query.get(student.teacher_id) if getattr(student, "teacher_id", None) else None
    org_name = getattr(student, "organization_name", None) or (getattr(principal, "organization_name", None) if principal else None) or (principal.full_name if principal else None)
    return {
        "organization_name": org_name or "Independent Learner",
        "principal_name": principal.full_name if principal else "Fluencify Support Team",
        "teacher_name": teacher.full_name if teacher else "Not assigned yet",
        "is_independent": principal is None,
    }


def monthly_registration_chart(users: list[User], months: int = 6) -> dict:
    now = datetime.utcnow()
    labels = []
    counts = []
    for offset in range(months - 1, -1, -1):
        month = ((now.month - offset - 1) % 12) + 1
        year = now.year + ((now.month - offset - 1) // 12)
        labels.append(datetime(year, month, 1).strftime('%b'))
        counts.append(sum(1 for u in users if u.created_at and u.created_at.year == year and u.created_at.month == month))
    return {"labels": labels, "counts": counts}


def superadmin_chart_payload() -> dict:
    students = User.query.filter_by(role=Role.STUDENT.value).all()
    staff = User.query.filter(User.role.in_(TENANT_STAFF_ROLES)).all()
    student_chart = monthly_registration_chart(students)
    staff_chart = monthly_registration_chart(staff)
    role_counts = Counter(u.role_code for u in User.query.all())
    return {
        "labels": student_chart["labels"],
        "students": student_chart["counts"],
        "staff": staff_chart["counts"],
        "role_labels": list(role_counts.keys()),
        "role_values": list(role_counts.values()),
    }


def admin_dashboard_payload(admin_user: User) -> dict:
    students = tenant_students_for(admin_user)
    staff = tenant_staff_for(admin_user)
    student_ids = [s.id for s in students]
    teacher_ids = [s.id for s in staff if s.role_code == Role.TEACHER.value]
    enrollments = 0
    avg_accuracy = 0
    if student_ids:
        enrollments = Enrollment.query.filter(Enrollment.student_id.in_(student_ids)).count()
        accuracy_rows = db.session.query(QuestionAttempt.accuracy_score).filter(QuestionAttempt.student_id.in_(student_ids), QuestionAttempt.accuracy_score.isnot(None)).all()
        values = [row[0] for row in accuracy_rows if row[0] is not None]
        avg_accuracy = int(round(sum(values) / len(values))) if values else 0
    chart = monthly_registration_chart(students)
    return {
        "metrics": {
            "student_count": len(students),
            "staff_count": len(staff),
            "teacher_count": len(teacher_ids),
            "live_students": sum(1 for s in students if s.is_active),
            "monthly_revenue": 0,
            "active_courses": len({e.course_id for e in Enrollment.query.filter(Enrollment.student_id.in_(student_ids)).all()}) if student_ids else 0,
            "enrollments_count": enrollments,
            "avg_accuracy": avg_accuracy,
        },
        "chart_data": {
            "labels": chart["labels"],
            "students": chart["counts"],
        },
        "students": students,
        "staff": staff,
    }


def _user_in_scope(candidate: User | None, scope_admin_id: int | None) -> bool:
    if not candidate:
        return False
    if scope_admin_id is None:
        return True
    return int(candidate.id) == int(scope_admin_id) or int(candidate.admin_id or 0) == int(scope_admin_id) or int(candidate.organization_id or 0) == int(scope_admin_id)


def validate_student_linkage(organization_id: int | None, teacher_id: int | None, *, scope_admin_id: int | None = None) -> tuple[bool, str | None, User | None]:
    organization_id = int(organization_id or 0)
    teacher_id = int(teacher_id or 0)

    teacher = User.query.get(teacher_id) if teacher_id else None
    if teacher and teacher.role_code != Role.TEACHER.value:
        return False, "Selected teacher is invalid.", None

    if scope_admin_id is not None:
        if organization_id and organization_id != int(scope_admin_id):
            return False, "Selected institute is outside your scope.", None
        if teacher and not _user_in_scope(teacher, scope_admin_id):
            return False, "Selected teacher is outside your scope.", None

    if organization_id and teacher and int(teacher.organization_id or 0) != organization_id:
        return False, "Selected teacher does not belong to the chosen institute.", teacher

    return True, None, teacher


def apply_student_ownership(student: User, organization_id: int | None, teacher_id: int | None, *, managed_by_user_id: int | None = None) -> None:
    organization_id = int(organization_id or 0)
    teacher_id = int(teacher_id or 0)
    student.organization_id = organization_id or None
    student.teacher_id = teacher_id or None
    student.managed_by_user_id = managed_by_user_id or None
    if student.organization_id:
        owner = User.query.get(student.organization_id)
        student.admin_id = student.organization_id
        student.organization_name = (owner.organization_name if owner else None) or (owner.full_name if owner else None)
    else:
        student.admin_id = None
        student.organization_name = None
