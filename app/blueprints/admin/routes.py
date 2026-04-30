from __future__ import annotations

from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from .lms_forms import (
    ChapterForm,
    CourseForm,
    DeleteForm,
    LessonForm,
    ModuleForm,
    LevelForm,
    QuestionForm,
    QuestionUploadForm,
    SubsectionForm,
)
from ..superadmin.forms import PageForm, AdminCreateForm, AdminEditForm, AdminPasswordForm, StudentEditForm
from ...extensions import db
from ...models.lms import Chapter, Course, Enrollment, Lesson, Level, Module, Question, Subsection, ContentVersion
from ...models.page import Page
from ...models.user import Role, User
from ...rbac import require_perm, require_role
from ...services.cms_service import ensure_page_content
from ...services.lms_client import get_student_latest_course
from ...services.lms_service import LMSService
from ...services.language_service import language_choices
from ...services.tenancy_service import admin_dashboard_payload, student_support_chain, tenant_students_for, organization_scope_id, tenant_staff_for, validate_student_linkage, apply_student_ownership

try:
    from ...audit import audit
except Exception:
    def audit(*args, **kwargs):
        return None


def _apply_language_choices(*forms):
    choices = language_choices(enabled_only=True, include_codes=True)
    for form in forms:
        if not form:
            continue
        if hasattr(form, "lang_code"):
            form.lang_code.choices = choices
        if hasattr(form, "language_code"):
            form.language_code.choices = choices


def _can_manage_pages() -> bool:
    role_code = (getattr(current_user, "role_code", None) or getattr(current_user, "role", "") or "").strip().upper()
    if role_code not in {"ADMIN", "SEO"}:
        return False

    has_perm = getattr(current_user, "has_perm", None)
    if not callable(has_perm):
        return True

    accepted_codes = {
        "cms.pages.view",
        "cms.pages.edit",
        "cms.pages.publish",
        "cms.pages.seo",
        "pages.view",
        "pages.edit",
        "pages.publish",
        "pages.seo",
    }

    try:
        return any(has_perm(code) for code in accepted_codes)
    except Exception:
        return True


def _build_admin_course_tree(course: Course) -> list[dict]:
    return LMSService.course_tree(course)

def _current_scope_admin_id() -> int:
    return current_user.id if current_user.is_admin else (current_user.organization_id or current_user.admin_id or current_user.id)


def _scope_admin_choices():
    if current_user.is_admin:
        admins = [current_user]
    else:
        owner = User.query.get(_current_scope_admin_id())
        admins = [owner] if owner else []
    return [(0, "Standalone admin / direct owner")] + [(a.id, (a.organization_name or a.full_name)) for a in admins if a]


def _scope_teacher_choices():
    rows = User.query.filter_by(role=Role.TEACHER.value, organization_id=_current_scope_admin_id()).order_by(User.first_name.asc().nullslast(), User.created_at.desc()).all()
    return [(0, "Not assigned yet")] + [(r.id, r.full_name) for r in rows]


def _scope_manager_choices():
    rows = User.query.filter(User.role.in_([Role.SUB_ADMIN.value]), User.organization_id == _current_scope_admin_id()).order_by(User.first_name.asc().nullslast(), User.created_at.desc()).all()
    choices = [(0, "Auto / none"), (current_user.id, current_user.full_name)]
    seen = {0, current_user.id}
    for row in rows:
        if row.id not in seen:
            choices.append((row.id, row.full_name))
            seen.add(row.id)
    return choices


def _apply_scope_management_choices(form):
    if hasattr(form, "parent_admin_id"):
        form.parent_admin_id.choices = _scope_admin_choices()
    if hasattr(form, "organization_id"):
        form.organization_id.choices = [(0, "Independent learner")] + [(c[0], c[1]) for c in _scope_admin_choices() if c[0] != 0]
    if hasattr(form, "teacher_id"):
        form.teacher_id.choices = _scope_teacher_choices()
    if hasattr(form, "managed_by_user_id"):
        form.managed_by_user_id.choices = _scope_manager_choices()


@bp.get("/dashboard")
@login_required
@require_role("ADMIN", "SUB_ADMIN", "SEO", "SUPPORT", "ACCOUNTS")
def dashboard():
    owner_admin_id = current_user.id if current_user.is_admin else (current_user.organization_id or current_user.admin_id or current_user.id)
    owned_courses = Course.query.filter_by(owner_admin_id=owner_admin_id).all()
    payload = admin_dashboard_payload(current_user)

    course_cards = []
    for course in owned_courses[:8]:
        course_cards.append({"course": course, **LMSService.course_metrics(course.id)})

    student_rows = []
    for student in payload["students"][:6]:
        support = student_support_chain(student)
        student_rows.append({
            "student": student,
            "support": support,
        })

    return render_template(
        "admin/dashboard.html",
        metrics=payload["metrics"],
        chart_data=payload["chart_data"],
        students_count=payload["metrics"]["student_count"],
        enrollments_count=payload["metrics"]["enrollments_count"],
        course_cards=course_cards,
        managed_students=student_rows,
    )


@bp.get("/questions/upload-template.csv")
@login_required
@require_role("ADMIN")
@require_perm("admin.courses.view")
def question_upload_template():
    return Response(
        LMSService.question_upload_template_csv(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="fluencify-question-upload-template.csv"'},
    )


@bp.route("/courses", methods=["GET", "POST"])
@login_required
@require_role("ADMIN")
@require_perm("admin.courses.view")
def courses():
    form = CourseForm()
    _apply_language_choices(form)

    if request.method == "POST":
        if form.validate_on_submit():
            try:
                course = LMSService.create_course(
                    title=form.title.data,
                    owner_admin_id=current_user.id,
                    created_by_id=current_user.id,
                    slug=form.slug.data,
                    description=form.description.data,
                    language_code=form.language_code.data,
                    track_type=form.track_type.data,
                    difficulty=form.difficulty.data,
                    currency_code=form.currency_code.data,
                    base_price=form.base_price.data,
                    sale_price=form.sale_price.data,
                    level_title=form.level_title.data,
                    lesson_title=form.lesson_title.data,
                    lesson_type=form.lesson_type.data,
                    explanation_text=form.explanation_text.data,
                    grammar_formula=form.grammar_formula.data,
                    badge_title=form.badge_title.data,
                    badge_subtitle=form.badge_subtitle.data,
                    badge_template=form.badge_template.data,
                    badge_animation=form.badge_animation.data,
                    is_published=form.is_published.data,
                    is_premium=form.is_premium.data,
                )
                audit("course_create", target=str(course.id), meta=course.slug)
                flash("Course created successfully.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))
            except ValueError as exc:
                flash(str(exc), "warning")
            except Exception as exc:
                flash(f"Unable to create course: {exc}", "danger")
        else:
            flash("Please correct the highlighted course form errors.", "warning")

    q = (request.args.get("q") or "").strip().lower()
    sort = (request.args.get("sort") or "latest").strip().lower()
    status = (request.args.get("status") or "").strip().lower()

    items = Course.query.filter_by(owner_admin_id=current_user.id).all()

    if q:
        items = [c for c in items if q in (c.title or "").lower() or q in (c.slug or "").lower()]
    if status:
        items = [c for c in items if (c.status or "").lower() == status]

    if sort == "title":
        items = sorted(items, key=lambda c: (c.title or "").lower())
    elif sort == "price_low":
        items = sorted(items, key=lambda c: float(c.current_price or 0))
    elif sort == "price_high":
        items = sorted(items, key=lambda c: float(c.current_price or 0), reverse=True)
    else:
        items = sorted(items, key=lambda c: c.created_at, reverse=True)

    course_cards = [{"course": c, **LMSService.course_metrics(c.id)} for c in items]

    return render_template(
        "admin/courses.html",
        form=form,
        course_cards=course_cards,
        current_query=q,
        current_sort=sort,
        current_status=status,
        panel_role="admin",
    )


@bp.route("/courses/<int:course_id>", methods=["GET", "POST"])
@login_required
@require_role("ADMIN")
@require_perm("admin.courses.view")
def course_detail(course_id: int):
    course = Course.query.filter_by(id=course_id, owner_admin_id=current_user.id).first_or_404()

    delete_form = DeleteForm()
    upload_form = QuestionUploadForm(prefix="upload")
    level_form = LevelForm(prefix="level")
    module_form = ModuleForm(prefix="module")
    lesson_form = LessonForm(prefix="lesson")
    chapter_form = ChapterForm(prefix="chapter")
    subsection_form = SubsectionForm(prefix="subsection")
    question_form = QuestionForm(prefix="question")
    _apply_language_choices(question_form)

    lessons = (
        Lesson.query.join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc())
        .all()
    )
    modules = (
        Module.query.join(Level, Level.id == Module.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Module.sort_order.asc())
        .all()
    )
    chapters = (
        Chapter.query.join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc())
        .all()
    )
    subsections = (
        Subsection.query.join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc(), Subsection.sort_order.asc())
        .all()
    )

    upload_form.lesson_id.choices = [(l.id, f"{l.level.title} / {l.title}") for l in lessons]
    lesson_form.level_id.choices = [(lvl.id, lvl.title) for lvl in course.levels]
    module_form.level_id.choices = [(lvl.id, lvl.title) for lvl in course.levels]
    lesson_form.module_id.choices = [(0, "No module (directly under level)")] + [(m.id, f"{m.level.title} / {m.title}") for m in modules]
    chapter_form.lesson_id.choices = [(l.id, f"{l.level.title} / {l.title}") for l in lessons]
    subsection_form.chapter_id.choices = [(c.id, f"{c.lesson.title} / {c.title}") for c in chapters]
    question_form.subsection_id.choices = [
        (s.id, f"{s.chapter.lesson.title} / {s.chapter.title} / {s.title}") for s in subsections
    ]

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            if action == "submit_review":
                LMSService.submit_course_for_review(course, current_user.id)
                flash("Course submitted for review.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action in {"publish", "unpublish", "disable", "archive", "restore"}:
                LMSService.set_course_status(course, action)
                flash("Course status updated.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "delete_course":
                LMSService.delete_course(course)
                flash("Course deleted.", "success")
                return redirect(url_for("admin.courses"))

            if action == "add_level" and level_form.validate_on_submit():
                LMSService.add_level(
                    course=course,
                    title=level_form.title.data,
                    description=level_form.description.data,
                    sort_order=level_form.sort_order.data,
                )
                flash("Level added.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "add_module" and module_form.validate_on_submit():
                level = next((lvl for lvl in course.levels if lvl.id == module_form.level_id.data), None)
                if not level:
                    raise ValueError("Selected level was not found.")
                LMSService.add_module(level=level, title=module_form.title.data, description=module_form.description.data, sort_order=module_form.sort_order.data)
                flash("Module added.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "add_lesson" and lesson_form.validate_on_submit():
                LMSService.add_lesson(
                    course=course,
                    level_id=lesson_form.level_id.data,
                    module_id=(lesson_form.module_id.data or None),
                    title=lesson_form.title.data,
                    slug=lesson_form.slug.data,
                    lesson_type=lesson_form.lesson_type.data,
                    explanation_text=lesson_form.explanation_text.data,
                    explanation_tts_text=lesson_form.explanation_tts_text.data,
                    estimated_minutes=lesson_form.estimated_minutes.data,
                    grammar_formula=lesson_form.grammar_formula.data,
                    is_published=lesson_form.is_published.data,
                )
                flash("Lesson created.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "add_chapter" and chapter_form.validate_on_submit():
                lesson = next((l for l in lessons if l.id == chapter_form.lesson_id.data), None)
                if not lesson:
                    raise ValueError("Selected lesson was not found.")
                LMSService.add_chapter(
                    lesson=lesson,
                    title=chapter_form.title.data,
                    description=chapter_form.description.data,
                    sort_order=chapter_form.sort_order.data,
                )
                flash("Chapter added.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "add_subsection" and subsection_form.validate_on_submit():
                chapter = next((c for c in chapters if c.id == subsection_form.chapter_id.data), None)
                if not chapter:
                    raise ValueError("Selected chapter was not found.")
                LMSService.add_subsection(
                    chapter=chapter,
                    title=subsection_form.title.data,
                    grammar_formula=subsection_form.grammar_formula.data,
                    grammar_tags=subsection_form.grammar_tags.data,
                    hint_seed=subsection_form.hint_seed.data,
                    sort_order=subsection_form.sort_order.data,
                )
                flash("Subsection added.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "upload_questions" and upload_form.validate_on_submit():
                lesson = next((l for l in lessons if l.id == upload_form.lesson_id.data), None)
                if not lesson:
                    raise ValueError("Selected lesson was not found.")
                parsed = LMSService.parse_question_upload(upload_form.upload.data)
                upload_issues = LMSService.validate_question_upload_rows(parsed)
                if upload_issues:
                    raise ValueError("Please fix the upload file first: " + " | ".join(upload_issues[:5]))
                count = LMSService.upload_questions_to_lesson(
                    lesson,
                    parsed,
                    auto_split_size=upload_form.auto_split_size.data or 10,
                )
                audit("question_upload", target=str(lesson.id), meta=f"count={count}")
                flash(f"{count} questions imported.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "add_question" and question_form.validate_on_submit():
                subsection = next((s for s in subsections if s.id == question_form.subsection_id.data), None)
                if not subsection:
                    raise ValueError("Selected subsection was not found.")
                LMSService.add_question(
                    subsection=subsection,
                    title=question_form.title.data,
                    prompt=question_form.prompt.data,
                    image_url=question_form.image_url.data,
                    prompt_type=question_form.prompt_type.data,
                    language_code=question_form.language_code.data,
                    hint_text=question_form.hint_text.data,
                    model_answer=question_form.model_answer.data,
                    evaluation_rubric=question_form.evaluation_rubric.data,
                    expected_keywords=question_form.expected_keywords.data,
                    is_active=question_form.is_active.data,
                )
                flash("Question added.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "delete_level":
                level_id = int(request.form.get("level_id") or 0)
                level = next((lvl for lvl in course.levels if lvl.id == level_id), None)
                if not level:
                    raise ValueError("Level not found.")
                LMSService.delete_level(level)
                flash("Level deleted.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "delete_lesson":
                lesson_id = int(request.form.get("lesson_id") or 0)
                lesson = next((l for l in lessons if l.id == lesson_id), None)
                if not lesson:
                    raise ValueError("Lesson not found.")
                LMSService.delete_lesson(lesson)
                flash("Lesson deleted.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "delete_chapter":
                chapter_id = int(request.form.get("chapter_id") or 0)
                chapter = next((c for c in chapters if c.id == chapter_id), None)
                if not chapter:
                    raise ValueError("Chapter not found.")
                LMSService.delete_chapter(chapter)
                flash("Chapter deleted.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "delete_subsection":
                subsection_id = int(request.form.get("subsection_id") or 0)
                subsection = next((s for s in subsections if s.id == subsection_id), None)
                if not subsection:
                    raise ValueError("Subsection not found.")
                LMSService.delete_subsection(subsection)
                flash("Subsection deleted.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))

            if action == "delete_question":
                question_id = int(request.form.get("question_id") or 0)
                question = (
                    Question.query.join(Subsection, Subsection.id == Question.subsection_id)
                    .join(Chapter, Chapter.id == Subsection.chapter_id)
                    .join(Lesson, Lesson.id == Chapter.lesson_id)
                    .join(Level, Level.id == Lesson.level_id)
                    .filter(Level.course_id == course.id, Question.id == question_id)
                    .first()
                )
                if not question:
                    raise ValueError("Question not found.")
                LMSService.delete_question(question)
                flash("Question deleted.", "success")
                return redirect(url_for("admin.course_detail", course_id=course.id))
        except Exception as exc:
            flash(str(exc), "warning")

    question_rows = (
        Question.query.join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(
            Level.sort_order.asc(),
            Lesson.sort_order.asc(),
            Chapter.sort_order.asc(),
            Subsection.sort_order.asc(),
            Question.sort_order.asc(),
        )
        .all()
    )

    enrollments = Enrollment.query.filter_by(course_id=course.id).order_by(Enrollment.enrolled_at.desc()).all()

    LMSService.ensure_default_batch(course, current_user.id)
    batches = LMSService.course_batches_for_admin(current_user.id, course)
    version_rows = ContentVersion.query.filter_by(entity_type="course", entity_id=course.id).order_by(ContentVersion.created_at.desc()).limit(10).all()

    return render_template(
        "admin/course_detail.html",
        course=course,
        lessons=lessons,
        modules=modules,
        chapters=chapters,
        subsections=subsections,
        question_rows=question_rows,
        enrollments=enrollments,
        upload_form=upload_form,
        level_form=level_form,
        module_form=module_form,
        lesson_form=lesson_form,
        chapter_form=chapter_form,
        subsection_form=subsection_form,
        question_form=question_form,
        delete_form=delete_form,
        metrics=LMSService.course_metrics(course.id),
        course_tree=_build_admin_course_tree(course),
        batches=batches,
        version_rows=version_rows,
        panel_role="admin",
    )



@bp.get("/students")
@login_required
@require_role("ADMIN")
@require_perm("admin.students.view")
def students():
    students = tenant_students_for(current_user)
    course_map = {s.id: get_student_latest_course(current_user.id, s.id) for s in students}
    progress_map = {s.id: LMSService.student_progress_report(s) for s in students}
    latest_login_map = {s.id: s.login_events.order_by(__import__("sqlalchemy").desc("created_at")).first() for s in students}
    support_map = {s.id: student_support_chain(s) for s in students}

    return render_template(
        "admin/students.html",
        students=students,
        course_map=course_map,
        progress_map=progress_map,
        latest_login_map=latest_login_map,
        support_map=support_map,
        panel_role="admin",
    )


@bp.route("/team", methods=["GET", "POST"])
@login_required
@require_role("ADMIN", "SUB_ADMIN")
def team():
    q = (request.args.get("q") or "").strip().lower()
    create_form = AdminCreateForm()
    _apply_scope_management_choices(create_form)
    create_form.role.choices = [(Role.SUB_ADMIN.value, "Sub Admin"), (Role.TEACHER.value, "Teacher")]

    if request.method == "POST" and create_form.validate_on_submit():
        if User.query.filter_by(username=create_form.username.data.strip()).first():
            flash("Username already exists.", "warning")
            return redirect(url_for("admin.team"))
        if User.query.filter_by(email=create_form.email.data.strip().lower()).first():
            flash("Email already exists.", "warning")
            return redirect(url_for("admin.team"))
        first, last = (create_form.full_name.data or "").strip().split(None, 1)[0], None
        parts = (create_form.full_name.data or "").strip().split(None, 1)
        first = parts[0] if parts else None
        last = parts[1] if len(parts) > 1 else None
        owner_id = _current_scope_admin_id()
        owner = User.query.get(owner_id)
        user = User(
            username=create_form.username.data.strip(),
            email=create_form.email.data.strip().lower(),
            first_name=first,
            last_name=last,
            role=create_form.role.data,
            is_active=bool(create_form.is_active.data),
            admin_id=owner_id,
            organization_id=owner_id,
            organization_name=(owner.organization_name if owner else None) or (owner.full_name if owner else None),
            managed_by_user_id=current_user.id,
        )
        user.set_password(create_form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Team member created.", "success")
        return redirect(url_for("admin.team"))

    staff = tenant_staff_for(current_user)
    staff = [row for row in staff if row.role_code in {Role.SUB_ADMIN.value, Role.TEACHER.value}]
    if q:
        staff = [row for row in staff if q in row.full_name.lower() or q in row.email.lower() or q in (row.organization_name or "").lower()]
    return render_template("admin/team.html", staff=staff, create_form=create_form, q=q)


@bp.route("/students/manage", methods=["GET", "POST"])
@login_required
@require_role("ADMIN", "SUB_ADMIN")
def manage_students():
    q = (request.args.get("q") or "").strip()
    teacher_id = int(request.args.get("teacher_id") or 0) if str(request.args.get("teacher_id") or "0").isdigit() else 0
    students = tenant_students_for(current_user)
    if teacher_id:
        students = [row for row in students if row.teacher_id == teacher_id]
    if q:
        low = q.lower()
        students = [row for row in students if low in row.full_name.lower() or low in row.email.lower() or low in (row.organization_name or "").lower()]

    edit_student = None
    edit_form = StudentEditForm()
    _apply_scope_management_choices(edit_form)
    if request.method == "POST":
        student_id = int(request.form.get("student_id") or 0)
        edit_student = next((row for row in tenant_students_for(current_user) if row.id == student_id), None)
        if not edit_student:
            flash("Student not found in your scope.", "warning")
            return redirect(url_for("admin.manage_students"))
        if edit_form.validate_on_submit():
            parts = (edit_form.full_name.data or "").strip().split(None, 1)
            edit_student.first_name = parts[0] if parts else None
            edit_student.last_name = parts[1] if len(parts) > 1 else None
            edit_student.username = edit_form.username.data.strip()
            edit_student.email = edit_form.email.data.strip().lower()
            edit_student.current_level = edit_form.current_level.data or None
            edit_student.target_exam = edit_form.target_exam.data or None
            selected_org_id = int(edit_form.organization_id.data or 0)
            selected_teacher_id = int(edit_form.teacher_id.data or 0)
            valid, error_message, _teacher = validate_student_linkage(
                selected_org_id,
                selected_teacher_id,
                scope_admin_id=_current_scope_admin_id(),
            )
            if not valid:
                flash(error_message or "Invalid institute/teacher mapping.", "warning")
            else:
                apply_student_ownership(
                    edit_student,
                    selected_org_id,
                    selected_teacher_id,
                    managed_by_user_id=(edit_form.managed_by_user_id.data or current_user.id),
                )
                edit_student.is_active = bool(edit_form.is_active.data)
                db.session.commit()
                flash("Student assignment updated.", "success")
                return redirect(url_for("admin.manage_students"))
        flash("Please correct the student form.", "warning")
    elif request.args.get("edit_id") and str(request.args.get("edit_id")).isdigit():
        edit_id = int(request.args.get("edit_id"))
        edit_student = next((row for row in tenant_students_for(current_user) if row.id == edit_id), None)
        if edit_student:
            edit_form.full_name.data = edit_student.full_name
            edit_form.username.data = edit_student.username
            edit_form.email.data = edit_student.email
            edit_form.current_level.data = edit_student.current_level or ""
            edit_form.target_exam.data = edit_student.target_exam or ""
            edit_form.organization_id.data = edit_student.organization_id or 0
            edit_form.teacher_id.data = edit_student.teacher_id or 0
            edit_form.managed_by_user_id.data = edit_student.managed_by_user_id or 0
            edit_form.is_active.data = edit_student.is_active

    course_map = {s.id: get_student_latest_course(_current_scope_admin_id(), s.id) for s in students}
    progress_map = {s.id: LMSService.student_progress_report(s) for s in students}
    latest_login_map = {s.id: s.login_events.order_by(__import__("sqlalchemy").desc("created_at")).first() for s in students}
    support_map = {s.id: student_support_chain(s) for s in students}
    return render_template("admin/students_manage.html", students=students, course_map=course_map, progress_map=progress_map, latest_login_map=latest_login_map, support_map=support_map, teacher_choices=_scope_teacher_choices(), selected_teacher_id=teacher_id, q=q, edit_student=edit_student, edit_form=edit_form, panel_role="admin")


@bp.get("/pages")
@login_required
@require_role("ADMIN", "SEO")
def pages_list():
    if not _can_manage_pages():
        flash("You do not have permission to manage pages.", "warning")
        return redirect(url_for("admin.dashboard"))

    pages = Page.query.order_by(Page.menu_order.asc(), Page.updated_at.desc()).all()
    return render_template("superadmin/pages_list.html", pages=pages, panel_role="admin")


@bp.route("/pages/create", methods=["GET", "POST"])
@login_required
@require_role("ADMIN", "SEO")
def pages_create():
    if not _can_manage_pages():
        flash("You do not have permission to create pages.", "warning")
        return redirect(url_for("admin.dashboard"))

    form = PageForm()
    _apply_language_choices(form)
    _apply_language_choices(form)

    if form.validate_on_submit():
        page = Page(
            title=form.title.data.strip(),
            slug=form.slug.data.strip().lower(),
            is_published=bool(form.is_published.data),
            is_in_menu=bool(form.is_in_menu.data),
            menu_order=int(form.menu_order.data or 0),
        )
        db.session.add(page)
        db.session.flush()

        content = ensure_page_content(page, form.lang_code.data)
        content.title = form.content_title.data or form.title.data
        content.subtitle = form.subtitle.data or ""
        content.body_html = form.body_html.data or ""
        content.hero_title = form.hero_title.data or form.title.data
        content.hero_subtitle = form.hero_subtitle.data or ""
        content.hero_cta_text = form.hero_cta_text.data or ""
        content.hero_cta_url = form.hero_cta_url.data or ""
        content.hero_image = form.hero_image.data or ""
        content.meta_title = form.meta_title.data or form.title.data
        content.meta_description = form.meta_description.data or ""
        content.canonical_url = form.canonical_url.data or ""
        content.og_title = form.og_title.data or form.title.data
        content.og_description = form.og_description.data or ""
        content.og_image = form.og_image.data or ""
        content.twitter_card = form.twitter_card.data or "summary_large_image"
        content.sections_json = form.sections_json.data or ""
        content.faq_json = form.faq_json.data or ""
        content.links_json = form.links_json.data or ""
        content.json_ld = form.json_ld.data or ""
        db.session.add(content)
        db.session.commit()

        flash("Page created successfully.", "success")
        return redirect(url_for("admin.pages_list"))

    return render_template(
        "superadmin/pages_edit.html",
        form=form,
        page=None,
        content=None,
        mode="create",
        panel_role="admin",
    )


@bp.route("/pages/<int:page_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("ADMIN", "SEO")
def pages_edit(page_id: int):
    if not _can_manage_pages():
        flash("You do not have permission to edit pages.", "warning")
        return redirect(url_for("admin.dashboard"))

    page = Page.query.get_or_404(page_id)
    lang_code = (request.args.get("lang") or "en").strip().lower()
    content = ensure_page_content(page, lang_code)

    form = PageForm()

    if request.method == "GET":
        form.title.data = page.title
        form.slug.data = page.slug
        form.is_published.data = page.is_published
        form.is_in_menu.data = page.is_in_menu
        form.menu_order.data = str(page.menu_order)
        form.lang_code.data = lang_code
        form.content_title.data = content.title or ""
        form.subtitle.data = content.subtitle or ""
        form.body_html.data = content.body_html or ""
        form.hero_title.data = content.hero_title or ""
        form.hero_subtitle.data = content.hero_subtitle or ""
        form.hero_cta_text.data = content.hero_cta_text or ""
        form.hero_cta_url.data = content.hero_cta_url or ""
        form.hero_image.data = content.hero_image or ""
        form.meta_title.data = content.meta_title or ""
        form.meta_description.data = content.meta_description or ""
        form.canonical_url.data = content.canonical_url or ""
        form.og_title.data = content.og_title or ""
        form.og_description.data = content.og_description or ""
        form.og_image.data = content.og_image or ""
        form.twitter_card.data = content.twitter_card or "summary_large_image"
        form.sections_json.data = content.sections_json or ""
        form.faq_json.data = content.faq_json or ""
        form.links_json.data = content.links_json or ""
        form.json_ld.data = content.json_ld or ""

    if form.validate_on_submit():
        page.title = form.title.data.strip()
        page.slug = form.slug.data.strip().lower()
        page.is_published = bool(form.is_published.data)
        page.is_in_menu = bool(form.is_in_menu.data)
        page.menu_order = int(form.menu_order.data or 0)

        content.lang_code = form.lang_code.data
        content.title = form.content_title.data or page.title
        content.subtitle = form.subtitle.data or ""
        content.body_html = form.body_html.data or ""
        content.hero_title = form.hero_title.data or page.title
        content.hero_subtitle = form.hero_subtitle.data or ""
        content.hero_cta_text = form.hero_cta_text.data or ""
        content.hero_cta_url = form.hero_cta_url.data or ""
        content.hero_image = form.hero_image.data or ""
        content.meta_title = form.meta_title.data or page.title
        content.meta_description = form.meta_description.data or ""
        content.canonical_url = form.canonical_url.data or ""
        content.og_title = form.og_title.data or page.title
        content.og_description = form.og_description.data or ""
        content.og_image = form.og_image.data or ""
        content.twitter_card = form.twitter_card.data or "summary_large_image"
        content.sections_json = form.sections_json.data or ""
        content.faq_json = form.faq_json.data or ""
        content.links_json = form.links_json.data or ""
        content.json_ld = form.json_ld.data or ""

        db.session.add(content)
        db.session.commit()
        flash("Page updated successfully.", "success")
        return redirect(url_for("admin.pages_edit", page_id=page.id, lang=form.lang_code.data))

    return render_template(
        "superadmin/pages_edit.html",
        form=form,
        page=page,
        content=content,
        mode="edit",
        panel_role="admin",
    )


@bp.post("/pages/<int:page_id>/publish")
@login_required
@require_role("ADMIN", "SEO")
def pages_publish(page_id: int):
    if not _can_manage_pages():
        flash("You do not have permission to publish pages.", "warning")
        return redirect(url_for("admin.dashboard"))

    page = Page.query.get_or_404(page_id)
    page.is_published = True
    db.session.commit()
    flash("Page published.", "success")
    return redirect(url_for("admin.pages_list"))


@bp.post("/pages/<int:page_id>/unpublish")
@login_required
@require_role("ADMIN", "SEO")
def pages_unpublish(page_id: int):
    if not _can_manage_pages():
        flash("You do not have permission to unpublish pages.", "warning")
        return redirect(url_for("admin.dashboard"))

    page = Page.query.get_or_404(page_id)
    page.is_published = False
    db.session.commit()
    flash("Page unpublished.", "success")
    return redirect(url_for("admin.pages_list"))


@bp.post("/pages/<int:page_id>/delete")
@login_required
@require_role("ADMIN")
def pages_delete(page_id: int):
    if not _can_manage_pages():
        flash("You do not have permission to delete pages.", "warning")
        return redirect(url_for("admin.dashboard"))

    page = Page.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    flash("Page deleted.", "success")
    return redirect(url_for("admin.pages_list"))


@bp.get("/support")
@login_required
@require_role("ADMIN", "SUPPORT")
def support():
    return render_template("admin/support.html")


@bp.get("/coming-soon/<feature>")
@login_required
@require_role("ADMIN", "SEO", "SUPPORT", "ACCOUNTS")
def coming_soon(feature: str):
    return render_template(
        "admin/coming_soon.html",
        feature_title=feature.replace("-", " ").title(),
        phase="Roadmap",
        message="This feature is planned for a later phase.",
    )
