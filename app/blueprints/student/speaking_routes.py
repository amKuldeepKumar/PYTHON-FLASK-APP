from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from ...rbac import require_role
from ...services.speaking.analytics_service import SpeakingAnalyticsService
from ...services.speaking.motivation_service import MotivationService
from ...services.speaking.prompt_service import PromptService
from ...services.speaking.speaking_session_service import SpeakingSessionService
from ...services.speaking.ai_enhancement_service import SpeakingAIEnhancementService
from ...services.student_ai_intelligence import StudentAIIntelligenceService
from ...models.lms import Course, Enrollment
from ...models.speaking_session import SpeakingSession
from ...models.speaking_topic import SpeakingTopic
from ...models.interview_turn import InterviewTurn
from ...services.interview import InterviewService

SPEAKING_POWERED_TRACKS = {'speaking', 'spoken', 'topic', 'interview'}


def _course_track_key(course: Course | None) -> str:
    return (getattr(course, 'track_type', '') or '').strip().lower()


def _is_speaking_powered_course(course: Course | None) -> bool:
    track = _course_track_key(course)
    return track in SPEAKING_POWERED_TRACKS or track.replace('spoken', 'speaking') in SPEAKING_POWERED_TRACKS


def _is_interview_course(course: Course | None) -> bool:
    track = _course_track_key(course)
    if track == 'interview':
        return True
    try:
        for level in (getattr(course, 'levels', []) or []):
            for lesson in (getattr(level, 'lessons', []) or []):
                if ((getattr(lesson, 'lesson_type', '') or '').strip().lower()) == 'interview':
                    return True
    except Exception:
        pass
    title = (getattr(course, 'title', '') or '').strip().lower()
    return 'interview' in title and track in {'', 'speaking'}


def _owner_admin_id() -> int | None:
    return getattr(current_user, "created_by_id", None)


def _student_enrolled_course(course_id: int) -> Course | None:
    enrollment = (
        Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id, status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .first()
    )
    return enrollment.course if enrollment and enrollment.course else None


def _student_course_enrollment(course_id: int) -> Enrollment | None:
    return (
        Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id, status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .first()
    )


def _topic_level_allowed(enrollment: Enrollment | None, level_number: int | None) -> bool:
    if not enrollment:
        return False
    return enrollment.has_level_access(level_number)

def _session_home_endpoint(session_row: SpeakingSession | None):
    if session_row and getattr(session_row, 'course_id', None):
        course = getattr(getattr(session_row, 'topic', None), 'course', None)
        if _is_interview_course(course):
            return 'student.course_interview_home', {'course_id': session_row.course_id}
        return 'student.course_speaking_home', {'course_id': session_row.course_id}
    return 'student.speaking_home', {}


def _session_route_payload(session_row: SpeakingSession):
    course = getattr(getattr(session_row, 'topic', None), 'course', None)
    is_interview = _is_interview_course(course)
    if getattr(session_row, 'course_id', None):
        return {
            'home_endpoint': 'student.course_interview_home' if is_interview else 'student.course_speaking_home',
            'home_kwargs': {'course_id': session_row.course_id},
            'history_endpoint': 'student.course_interview_history' if is_interview else 'student.course_speaking_history',
            'history_kwargs': {'course_id': session_row.course_id},
            'start_endpoint': 'student.course_interview_start' if is_interview else 'student.course_speaking_start',
            'start_kwargs': {'course_id': session_row.course_id},
            'retry_endpoint': 'student.course_interview_retry' if is_interview else 'student.course_speaking_retry',
            'retry_kwargs': {'course_id': session_row.course_id, 'session_id': session_row.id},
            'submit_endpoint': 'student.course_interview_submit' if is_interview else 'student.course_speaking_submit',
            'submit_kwargs': {'course_id': session_row.course_id, 'session_id': session_row.id},
        }
    return {
        'home_endpoint': 'student.speaking_home',
        'home_kwargs': {},
        'history_endpoint': 'student.speaking_history',
        'history_kwargs': {},
        'start_endpoint': 'student.speaking_start',
        'start_kwargs': {},
        'retry_endpoint': 'student.speaking_retry',
        'retry_kwargs': {'session_id': session_row.id},
        'submit_endpoint': 'student.speaking_submit',
        'submit_kwargs': {'session_id': session_row.id},
    }


def _course_mode_endpoints(course: Course) -> dict[str, str]:
    is_interview = _is_interview_course(course)
    return {
        'home': 'student.course_interview_home' if is_interview else 'student.course_speaking_home',
        'start': 'student.course_interview_start' if is_interview else 'student.course_speaking_start',
        'history': 'student.course_interview_history' if is_interview else 'student.course_speaking_history',
        'session': 'student.course_interview_session' if is_interview else 'student.course_speaking_session',
        'submit': 'student.course_interview_submit' if is_interview else 'student.course_speaking_submit',
        'result': 'student.course_interview_result' if is_interview else 'student.course_speaking_result',
        'retry': 'student.course_interview_retry' if is_interview else 'student.course_speaking_retry',
    }


def _redirect_course_mode(course: Course, target: str, **kwargs):
    return redirect(url_for(_course_mode_endpoints(course)[target], course_id=course.id, **kwargs))


def _course_speaking_context(course_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash("You are not enrolled in this course.", "warning")
        return None, redirect(url_for("student.my_courses"))
    if not _is_speaking_powered_course(course):
        flash('This course is not configured as a speaking-powered track.', 'warning')
        return None, redirect(url_for('student.course_detail', course_id=course.id))
    return course, None


def _render_course_interview_home(course: Course):
    from ...models.interview_profile import InterviewProfile

    latest_profile = (
        InterviewProfile.query
        .filter_by(student_id=current_user.id, course_id=course.id, is_active=True)
        .order_by(InterviewProfile.updated_at.desc())
        .first()
    )
    return render_template(
        'student/interview/index.html',
        course=course,
        recent_sessions=InterviewService.recent_sessions(current_user.id, course.id, limit=8),
        latest_profile=latest_profile,
    )


def _render_course_speaking_home(course: Course):
    enrollment = _student_course_enrollment(course.id)
    topics = [
        topic for topic in (getattr(course, "speaking_topics", []) or [])
        if bool(getattr(topic, "is_active", False))
        and bool(getattr(topic, "is_published", False))
        and int(getattr(topic, 'active_prompt_count', 0) or 0) > 0
    ]
    topics = [
        topic for topic in topics
        if _topic_level_allowed(enrollment, getattr(topic, "course_level_number", None))
    ]
    active_prompt_count = sum(topic.active_prompt_count for topic in topics)
    recent_sessions = SpeakingSessionService.recent_sessions_for_student(current_user.id, limit=5, course_id=course.id)
    motivation_stats = MotivationService.speaking_dashboard_stats(current_user.id)
    return render_template(
        "student/speaking_home.html",
        topics=topics,
        active_prompt_count=active_prompt_count,
        recent_sessions=recent_sessions,
        motivation_stats=motivation_stats,
        course=course,
        is_interview_mode=False,
        intelligence_track=StudentAIIntelligenceService.for_track(current_user.id, "speaking"),
    )


def _start_standard_speaking_flow(*, course: Course | None = None):
    owner_admin_id = _owner_admin_id()
    topic_id = request.values.get("topic_id", type=int)

    if course is not None:
        topic = SpeakingTopic.query.filter_by(id=topic_id, course_id=course.id).first() if topic_id else None
        home_redirect = lambda: _redirect_course_mode(course, 'home')
        session_redirect = lambda session_id: _redirect_course_mode(course, 'session', session_id=session_id)
        prompt_course_id = course.id

        if topic_id and not topic:
            flash("This speaking topic does not belong to the selected course.", "warning")
            return home_redirect()
    else:
        topic = SpeakingTopic.query.filter_by(id=topic_id).first() if topic_id else None
        home_redirect = lambda: redirect(url_for("student.speaking_home"))
        session_redirect = lambda session_id: redirect(url_for("student.speaking_session", session_id=session_id))
        prompt_course_id = None

        if topic_id and (not topic or not bool(getattr(topic, "is_active", False)) or not bool(getattr(topic, "is_published", False))):
            flash("This topic is not active right now.", "warning")
            return home_redirect()

    if topic is not None:
        enrollment = _student_course_enrollment(getattr(topic, "course_id", None)) if getattr(topic, "course_id", None) else None
        if course is not None and not _topic_level_allowed(_student_course_enrollment(course.id), getattr(topic, "course_level_number", None)):
            flash("This speaking level is locked in your plan.", "warning")
            return redirect(url_for("student.course_checkout", course_id=course.id, purchase_scope="single_level", level=getattr(topic, "course_level_number", 1) or 1))
        if course is None and enrollment and not _topic_level_allowed(enrollment, getattr(topic, "course_level_number", None)):
            flash("This speaking level is locked in your plan.", "warning")
            return redirect(url_for("student.course_checkout", course_id=topic.course_id, purchase_scope="single_level", level=getattr(topic, "course_level_number", 1) or 1))
        if int(getattr(topic, 'active_prompt_count', 0) or 0) <= 0:
            flash("This speaking topic has no active prompts yet." if course is not None else "This topic has no active prompts yet.", "warning")
            return home_redirect()

    resumable = SpeakingSessionService.get_resumable_session(current_user.id, topic_id=topic_id, course_id=prompt_course_id or getattr(topic, 'course_id', None))
    if resumable:
        flash("Resuming your latest speaking session.", "info")
        return session_redirect(resumable.id)

    prompt = SpeakingSessionService.select_prompt(
        owner_admin_id=owner_admin_id,
        topic_id=topic_id,
        student_id=current_user.id,
        course_id=prompt_course_id,
    )
    if not prompt:
        if course is not None:
            flash("This speaking topic has no active prompts yet." if topic is not None else "This course has no speaking topic available yet.", "warning")
        else:
            flash("This topic is not ready yet.", "warning")
        return home_redirect()

    if prompt.topic and getattr(prompt.topic, "course_id", None):
        enrollment = _student_course_enrollment(prompt.topic.course_id)
        if not _topic_level_allowed(enrollment, getattr(prompt.topic, "course_level_number", None)):
            flash("This speaking level is locked in your plan.", "warning")
            return redirect(url_for("student.course_checkout", course_id=prompt.topic.course_id, purchase_scope="single_level", level=getattr(prompt.topic, "course_level_number", 1) or 1))

    session_row = SpeakingSessionService.start_session(
        student_id=current_user.id,
        owner_admin_id=owner_admin_id,
        prompt=prompt,
    )
    return session_redirect(session_row.id)


def _render_standard_speaking_session_page(session_row: SpeakingSession, *, course: Course | None = None):
    attempts = SpeakingSessionService.attempts_for_session(session_row)
    route_payload = _session_route_payload(session_row)
    return render_template(
        "student/speaking_session.html",
        speaking_session=session_row,
        attempts=attempts,
        course=course,
        route_payload=route_payload,
        is_interview_mode=_is_interview_course(course),
    )


def _submit_standard_speaking_session(
    session_row: SpeakingSession,
    *,
    session_endpoint: str,
    result_endpoint: str,
    course: Course | None = None,
):
    transcript_text = (request.form.get("transcript_text") or "").strip()
    duration_seconds = request.form.get("duration_seconds", type=int) or 0
    audio_file = request.files.get("audio_file")
    browser_stt_used = (request.form.get("browser_stt_used") or "0").strip() == "1"

    session_kwargs = {"session_id": session_row.id}
    result_kwargs = {"session_id": session_row.id}
    if course is not None:
        session_kwargs["course_id"] = course.id
        result_kwargs["course_id"] = course.id

    if not transcript_text and not (audio_file and getattr(audio_file, "filename", "")):
        flash("Please speak, type a transcript, or attach an audio file before submitting.", "warning")
        return redirect(url_for(session_endpoint, **session_kwargs))

    try:
        result = SpeakingSessionService.submit_session(
            session_row,
            transcript_text=transcript_text,
            duration_seconds=duration_seconds,
            audio_file=audio_file,
            submitted_from='browser_stt' if browser_stt_used else 'web',
            browser_stt_used=browser_stt_used,
        )
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for(session_endpoint, **session_kwargs))

    flash("Speaking session submitted successfully.", "success")
    result_kwargs["session_id"] = result["session"].id
    return redirect(url_for(result_endpoint, **result_kwargs))


def _render_standard_speaking_result_page(session_row: SpeakingSession, *, course: Course | None = None):
    attempts = SpeakingSessionService.attempts_for_session(session_row)
    motivation_stats = MotivationService.speaking_dashboard_stats(current_user.id)
    session_metrics = _speaking_metrics_payload(session_row.transcript_text, session_row.duration_seconds)
    attempt_metrics = {
        attempt.id: _speaking_metrics_payload(attempt.transcript_text, attempt.duration_seconds)
        for attempt in attempts
    }
    route_payload = _session_route_payload(session_row)
    evaluation_payload = _evaluation_payload(session_row)
    attempt_payloads = {attempt.id: _evaluation_payload(attempt) for attempt in attempts}
    return render_template(
        "student/speaking_result.html",
        speaking_session=session_row,
        attempts=attempts,
        motivation_stats=motivation_stats,
        session_metrics=session_metrics,
        attempt_metrics=attempt_metrics,
        evaluation_payload=evaluation_payload,
        attempt_payloads=attempt_payloads,
        course=course,
        route_payload=route_payload,
        is_interview_mode=_is_interview_course(course),
    )


def _retry_standard_speaking_session(
    session_row: SpeakingSession,
    *,
    result_endpoint: str,
    session_endpoint: str,
    success_message: str,
    course: Course | None = None,
):
    result_kwargs = {"session_id": session_row.id}
    session_kwargs = {"session_id": session_row.id}
    if course is not None:
        result_kwargs["course_id"] = course.id
        session_kwargs["course_id"] = course.id

    try:
        SpeakingSessionService.reopen_for_retry(session_row)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for(result_endpoint, **result_kwargs))

    flash(success_message, "success")
    return redirect(url_for(session_endpoint, **session_kwargs))


def _render_course_session_page(course: Course, session_id: int):
    if _is_interview_course(course):
        session_row = InterviewService.get_session(current_user.id, session_id)
        if not session_row or session_row.course_id != course.id:
            flash('Interview session not found.', 'warning')
            return _redirect_course_mode(course, 'home')
        current_turn = InterviewService.current_turn(session_row)
        return render_template('student/interview/live_room.html', course=course, interview_session=session_row, current_turn=current_turn)

    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row or session_row.course_id != course.id:
        flash("Speaking session not found.", "warning")
        return _redirect_course_mode(course, 'home')
    return _render_standard_speaking_session_page(session_row, course=course)


def _submit_course_session(course: Course, session_id: int):
    if _is_interview_course(course):
        session_row = InterviewService.get_session(current_user.id, session_id)
        if not session_row or session_row.course_id != course.id:
            flash('Interview session not found.', 'warning')
            return _redirect_course_mode(course, 'home')
        try:
            result = InterviewService.submit_turn(
                session_row,
                answer_text=(request.form.get('answer_text') or request.form.get('transcript_text') or '').strip(),
                duration_seconds=request.form.get('duration_seconds', type=int) or 0,
                pause_count=request.form.get('pause_count', type=int) or 0,
                long_pause_count=request.form.get('long_pause_count', type=int) or 0,
            )
        except ValueError as exc:
            flash(str(exc), 'warning')
            return _redirect_course_mode(course, 'session', session_id=session_id)
        if result.get('completed'):
            flash('Interview completed successfully.', 'success')
            return _redirect_course_mode(course, 'result', session_id=session_id)
        flash('Answer saved. Next AI question is ready.', 'success')
        return _redirect_course_mode(course, 'session', session_id=session_id)

    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row or session_row.course_id != course.id:
        flash("Speaking session not found.", "warning")
        return _redirect_course_mode(course, 'home')
    return _submit_standard_speaking_session(
        session_row,
        session_endpoint='student.course_speaking_session',
        result_endpoint='student.course_speaking_result',
        course=course,
    )


def _render_course_result_page(course: Course, session_id: int):
    if _is_interview_course(course):
        session_row = InterviewService.get_session(current_user.id, session_id)
        if not session_row or session_row.course_id != course.id:
            flash('Interview result not found.', 'warning')
            return _redirect_course_mode(course, 'home')
        feedback = InterviewService.get_or_create_feedback(session_row)
        turns = session_row.turns.order_by(InterviewTurn.turn_no.asc()).all()
        return render_template('student/interview/result.html', course=course, interview_session=session_row, feedback=feedback, turns=turns)

    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row or session_row.course_id != course.id:
        flash("Speaking result not found.", "warning")
        return _redirect_course_mode(course, 'home')
    return _render_standard_speaking_result_page(session_row, course=course)


def _retry_course_session(course: Course, session_id: int):
    if _is_interview_course(course):
        session_row = InterviewService.get_session(current_user.id, session_id)
        if not session_row or session_row.course_id != course.id:
            flash('Interview session not found.', 'warning')
            return _redirect_course_mode(course, 'home')
        profile = session_row.profile
        new_session = InterviewService.start_session(current_user.id, course.id, profile, retry_only_weak=True)
        flash('Weak-question retry interview started.', 'success')
        return _redirect_course_mode(course, 'session', session_id=new_session.id)

    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row or session_row.course_id != course.id:
        flash("Speaking session not found.", "warning")
        return _redirect_course_mode(course, 'home')
    return _retry_standard_speaking_session(
        session_row,
        result_endpoint='student.course_speaking_result',
        session_endpoint='student.course_speaking_session',
        success_message="Retry opened. You can resubmit the same prompt.",
        course=course,
    )


def _evaluation_payload(row) -> dict:

    return getattr(row, 'evaluation_payload', {}) or {}

def _speaking_metrics_payload(transcript: str | None, duration_seconds: int | None) -> dict:
    metrics = SpeakingAIEnhancementService.speaking_metrics(
        transcript=(transcript or ''),
        duration_seconds=duration_seconds or 0,
    )
    return {
        'words_per_minute': float(metrics.get('words_per_minute') or 0.0),
        'filler_count': int(metrics.get('filler_count') or 0),
        'filler_ratio_percent': round(float(metrics.get('filler_ratio') or 0.0) * 100, 1),
        'avg_sentence_length': float(metrics.get('avg_sentence_length') or 0.0),
        'pacing_band': (metrics.get('pacing_band') or 'unknown').replace('_', ' '),
    }



@bp.route("/speaking", methods=["GET"])
@login_required
@require_role("STUDENT")
def speaking_home():
    owner_admin_id = _owner_admin_id()
    topics = PromptService.list_student_visible_topics(owner_admin_id)
    topics = [topic for topic in topics if not topic.course_id]
    active_prompt_count = sum(topic.active_prompt_count for topic in topics)
    recent_sessions = SpeakingSessionService.recent_sessions_for_student(current_user.id, limit=5)
    motivation_stats = MotivationService.speaking_dashboard_stats(current_user.id)
    return render_template(
        "student/speaking_home.html",
        topics=topics,
        active_prompt_count=active_prompt_count,
        recent_sessions=recent_sessions,
        motivation_stats=motivation_stats,
        intelligence_track=StudentAIIntelligenceService.for_track(current_user.id, "speaking"),
    )


@bp.route("/courses/<int:course_id>/speaking", methods=["GET"])
@bp.route("/courses/<int:course_id>/interview", methods=["GET"], endpoint="course_interview_home")
@login_required
@require_role("STUDENT")
def course_speaking_home(course_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response
    if _is_interview_course(course):
        return _render_course_interview_home(course)
    return _render_course_speaking_home(course)


@bp.route("/courses/<int:course_id>/speaking/start", methods=["GET", "POST"])
@bp.route("/courses/<int:course_id>/interview/start", methods=["GET", "POST"], endpoint="course_interview_start")
@login_required
@require_role("STUDENT")
def course_speaking_start(course_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response

    if _is_interview_course(course):
        if request.method == 'GET' and not request.values.get('profile_id'):
            return render_template('student/interview/setup.html', course=course)
        profile_id = request.values.get('profile_id', type=int)
        profile = None
        try:
            if profile_id:
                from ...models.interview_profile import InterviewProfile
                profile = InterviewProfile.query.filter_by(id=profile_id, student_id=current_user.id, course_id=course.id).first()
            if profile is None:
                profile = InterviewService.create_profile_from_form(current_user.id, course.id, request.values)
            session = InterviewService.start_session(current_user.id, course.id, profile, retry_only_weak=(request.values.get('retry_only_weak') == '1'))
        except Exception as exc:
            flash(str(exc), 'warning')
            return _redirect_course_mode(course, 'home')
        flash('AI interview session started.', 'success')
        return _redirect_course_mode(course, 'session', session_id=session.id)
    return _start_standard_speaking_flow(course=course)


@bp.route("/courses/<int:course_id>/speaking/history", methods=["GET"])
@bp.route("/courses/<int:course_id>/interview/history", methods=["GET"], endpoint="course_interview_history")
@login_required
@require_role("STUDENT")
def course_speaking_history(course_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response
    if _is_interview_course(course):
        sessions = InterviewService.recent_sessions(current_user.id, course.id, limit=50)
        return render_template('student/interview/history.html', sessions=sessions, course=course)
    sessions = SpeakingSessionService.recent_sessions_for_student(current_user.id, limit=50, course_id=course.id)
    return render_template("student/speaking_history.html", sessions=sessions, course=course, is_interview_mode=False)


@bp.route("/courses/<int:course_id>/speaking/session/<int:session_id>", methods=["GET"])
@bp.route("/courses/<int:course_id>/interview/session/<int:session_id>", methods=["GET"], endpoint="course_interview_session")
@login_required
@require_role("STUDENT")
def course_speaking_session(course_id: int, session_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response
    return _render_course_session_page(course, session_id)


@bp.route("/courses/<int:course_id>/speaking/session/<int:session_id>/submit", methods=["POST"])
@bp.route("/courses/<int:course_id>/interview/session/<int:session_id>/submit", methods=["POST"], endpoint="course_interview_submit")
@login_required
@require_role("STUDENT")
def course_speaking_submit(course_id: int, session_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response
    return _submit_course_session(course, session_id)


@bp.route("/courses/<int:course_id>/speaking/session/<int:session_id>/result", methods=["GET"])
@bp.route("/courses/<int:course_id>/interview/session/<int:session_id>/result", methods=["GET"], endpoint="course_interview_result")
@login_required
@require_role("STUDENT")
def course_speaking_result(course_id: int, session_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response
    return _render_course_result_page(course, session_id)


@bp.route("/courses/<int:course_id>/speaking/session/<int:session_id>/retry", methods=["POST"])
@bp.route("/courses/<int:course_id>/interview/session/<int:session_id>/retry", methods=["POST"], endpoint="course_interview_retry")
@login_required
@require_role("STUDENT")
def course_speaking_retry(course_id: int, session_id: int):
    course, response = _course_speaking_context(course_id)
    if response is not None:
        return response
    return _retry_course_session(course, session_id)


@bp.route("/speaking/history", methods=["GET"])
@login_required
@require_role("STUDENT")
def speaking_history():
    sessions = SpeakingSessionService.recent_sessions_for_student(current_user.id, limit=50)
    return render_template("student/speaking_history.html", sessions=sessions)


@bp.route("/speaking/analytics", methods=["GET"])
@login_required
@require_role("STUDENT")
def speaking_analytics():
    report = SpeakingAnalyticsService.student_report(current_user)
    return render_template("student/speaking_analytics.html", report=report, analytics=report)


@bp.route("/speaking/start", methods=["GET", "POST"])
@login_required
@require_role("STUDENT")
def speaking_start():
    return _start_standard_speaking_flow()


@bp.route("/speaking/session/<int:session_id>", methods=["GET"])
@login_required
@require_role("STUDENT")
def speaking_session(session_id: int):
    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row:
        flash("Speaking session not found.", "warning")
        return redirect(url_for("student.speaking_home"))
    return _render_standard_speaking_session_page(session_row)


@bp.route("/speaking/session/<int:session_id>/submit", methods=["POST"])
@login_required
@require_role("STUDENT")
def speaking_submit(session_id: int):
    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row:
        flash("Speaking session not found.", "warning")
        return redirect(url_for("student.speaking_home"))
    return _submit_standard_speaking_session(
        session_row,
        session_endpoint='student.speaking_session',
        result_endpoint='student.speaking_result',
    )


@bp.route("/speaking/session/<int:session_id>/result", methods=["GET"])
@login_required
@require_role("STUDENT")
def speaking_result(session_id: int):
    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row:
        flash("Speaking result not found.", "warning")
        return redirect(url_for("student.speaking_home"))
    return _render_standard_speaking_result_page(session_row)


@bp.route("/speaking/session/<int:session_id>/retry", methods=["POST"])
@login_required
@require_role("STUDENT")
def speaking_retry(session_id: int):
    session_row = SpeakingSessionService.get_student_session(current_user.id, session_id)
    if not session_row:
        flash("Speaking session not found.", "warning")
        return redirect(url_for("student.speaking_home"))
    return _retry_standard_speaking_session(
        session_row,
        result_endpoint='student.speaking_result',
        session_endpoint='student.speaking_session',
        success_message="Retry opened for the same prompt.",
    )
