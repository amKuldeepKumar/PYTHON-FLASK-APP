from __future__ import annotations

from flask import jsonify, request
from flask_login import current_user, login_required

from . import bp
from ...rbac import require_role
from ...services.interview import InterviewService


@bp.post('/interview/session/<int:session_id>/pause-check')
@login_required
@require_role('STUDENT')
def interview_pause_check(session_id: int):
    session = InterviewService.get_session(current_user.id, session_id)
    if not session:
        return jsonify({'ok': False, 'message': 'Interview session not found.'}), 404

    silence_seconds = request.form.get('silence_seconds', type=int) or 0
    pause_level = 0

    if silence_seconds >= 15:
        pause_level = 3
    elif silence_seconds >= 9:
        pause_level = 2
    elif silence_seconds >= 5:
        pause_level = 1

    return jsonify({
        'ok': True,
        'pause_level': pause_level,
        'nudge_text': InterviewService.pause_message(pause_level),
    })
