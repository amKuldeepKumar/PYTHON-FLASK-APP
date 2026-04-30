from __future__ import annotations

from app.extensions import db
from app.models.user import Role, User
from tests.test_student_nursery_flow import _login


def test_student_chat_widget_renders_even_without_course_rooms(client, app_ctx):
    student = User(
        email="widget-student@example.com",
        username="widget-student",
        role=Role.STUDENT.value,
        password_hash="hashed",
        is_active=True,
    )
    db.session.add(student)
    db.session.commit()
    _login(client, student.id)

    response = client.get("/student/chat")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="studentChatWidget"' in html
    assert 'class="student-chat-widget"' in html
    assert "No unlocked course room yet" in html
    assert "Course enrollment is required before sending messages." in html
