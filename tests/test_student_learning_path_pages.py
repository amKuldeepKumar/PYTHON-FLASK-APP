from __future__ import annotations

from tests.test_student_nursery_flow import _build_student_course, _login


def test_student_placement_test_page_renders_without_prior_result(client, app_ctx):
    student, _course, _lesson, _question = _build_student_course(include_image=True)
    _login(client, student.id)

    response = client.get("/student/placement-test")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Placement Test" in html
    assert "Check your level and get a course path that fits you" in html


def test_student_learning_path_page_renders_without_prior_result(client, app_ctx):
    student, _course, _lesson, _question = _build_student_course(include_image=True)
    _login(client, student.id)

    response = client.get("/student/learning-path")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "My Learning Path" in html
    assert "Take the placement test first" in html
