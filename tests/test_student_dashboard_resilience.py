from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import text

from app.extensions import db
from app.models.student_daily_activity import StudentDailyActivity
from app.services.student_activity_service import StudentActivityService
from tests.test_student_nursery_flow import _build_student_course, _login


def test_student_dashboard_recovers_when_activity_table_is_missing(client, app_ctx):
    student, _course, _lesson, _question = _build_student_course(include_image=True)
    db.session.execute(text("DROP TABLE student_daily_activity"))
    db.session.commit()
    _login(client, student.id)

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Student workspace" in html
    assert "Practice Calendar" in html


def test_calendar_marks_only_login_days_as_present(app_ctx):
    student, _course, _lesson, _question = _build_student_course(include_image=True)
    question_only_day = date(2026, 4, 1)
    present_day = date(2026, 4, 2)
    db.session.add_all([
        StudentDailyActivity(
            student_id=student.id,
            activity_date=question_only_day,
            questions_attempted=8,
            questions_correct=6,
        ),
        StudentDailyActivity(
            student_id=student.id,
            activity_date=present_day,
            login_count=1,
            last_login_at=datetime(2026, 4, 2, 9, 30),
            questions_attempted=10,
            questions_correct=8,
        ),
    ])
    db.session.commit()

    payload = StudentActivityService.build_month_grid(student.id, 2026, 4)
    cells = {cell["date"]: cell for week in payload["weeks"] for cell in week}

    assert payload["active_days"] == 1
    assert cells["2026-04-01"]["was_present"] is False
    assert cells["2026-04-01"]["is_absent"] is True
    assert "You were not present on this date." in cells["2026-04-01"]["tooltip"]
    assert cells["2026-04-02"]["was_present"] is True
    assert cells["2026-04-02"]["questions"] == 10
    assert cells["2026-04-02"]["accuracy"] == 80
    assert "Improvement: Baseline" in cells["2026-04-02"]["tooltip"]


def test_student_dashboard_renders_attendance_calendar_states(client, app_ctx):
    student, _course, _lesson, _question = _build_student_course(include_image=True)
    today = date.today()
    db.session.add(StudentDailyActivity(
        student_id=student.id,
        activity_date=today,
        login_count=1,
        last_login_at=datetime.utcnow(),
        questions_attempted=4,
        questions_correct=3,
    ))
    db.session.commit()
    _login(client, student.id)

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "is-present" in html
    assert "is-absent" in html
    assert "bi-exclamation-triangle-fill day-caution" in html
    assert "You were not present on this date." in html
