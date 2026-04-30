from __future__ import annotations

from flask import request
from flask_login import current_user

from .extensions import db, socketio
from .services.economy_service import EconomyService

if socketio is not None:
    from flask_socketio import emit, join_room, leave_room

    def _room(course_id: int) -> str:
        return EconomyService.course_room_name(course_id)

    @socketio.on("join_course_room")
    def join_course_room_event(data):
        if not getattr(current_user, "is_authenticated", False) or not getattr(current_user, "is_student", False):
            return {"ok": False, "message": "Authentication required."}
        try:
            course_id = int((data or {}).get("course_id") or 0)
            EconomyService.ensure_student_course_chat_access(current_user.id, course_id)
            join_room(_room(course_id))
            presence = EconomyService.upsert_presence(current_user.id, course_id, socket_id=request.sid, is_online=True)
            payload = EconomyService.chat_payload(current_user.id, course_id, limit=50)
            db.session.commit()
            emit("room_bootstrap", {"ok": True, **payload})
            emit("presence_update", {"course_id": course_id, **presence}, to=_room(course_id))
            return {"ok": True}
        except Exception as exc:
            db.session.rollback()
            return {"ok": False, "message": str(exc)}

    @socketio.on("leave_course_room")
    def leave_course_room_event(data):
        if not getattr(current_user, "is_authenticated", False):
            return
        course_id = int((data or {}).get("course_id") or 0)
        try:
            leave_room(_room(course_id))
            presence = EconomyService.mark_presence_offline(current_user.id, course_id, socket_id=request.sid) or {"online_count": 0, "members": []}
            db.session.commit()
            emit("presence_update", {"course_id": course_id, **presence}, to=_room(course_id))
        except Exception:
            db.session.rollback()

    @socketio.on("presence_ping")
    def presence_ping_event(data):
        if not getattr(current_user, "is_authenticated", False) or not getattr(current_user, "is_student", False):
            return
        try:
            course_id = int((data or {}).get("course_id") or 0)
            presence = EconomyService.upsert_presence(current_user.id, course_id, socket_id=request.sid, is_online=True)
            db.session.commit()
            emit("presence_update", {"course_id": course_id, **presence}, to=_room(course_id))
        except Exception:
            db.session.rollback()

    @socketio.on("send_course_message")
    def send_course_message_event(data):
        if not getattr(current_user, "is_authenticated", False) or not getattr(current_user, "is_student", False):
            return {"ok": False, "message": "Authentication required."}
        try:
            course_id = int((data or {}).get("course_id") or 0)
            body = ((data or {}).get("body") or "").strip()
            EconomyService.upsert_presence(current_user.id, course_id, socket_id=request.sid, is_online=True)
            message = EconomyService.post_course_message(current_user.id, course_id, body)
            serialized = EconomyService.serialize_chat_message(message, viewer_student_id=current_user.id)
            presence = EconomyService.room_presence(course_id)
            db.session.commit()
            emit("new_course_message", {"ok": True, "message": serialized}, to=_room(course_id))
            emit("presence_update", {"course_id": course_id, **presence}, to=_room(course_id))
            return {"ok": True}
        except Exception as exc:
            db.session.rollback()
            return {"ok": False, "message": str(exc)}

    @socketio.on("disconnect")
    def disconnect_event():
        if not getattr(current_user, "is_authenticated", False):
            return
        try:
            EconomyService.mark_presence_offline(current_user.id, socket_id=request.sid)
            db.session.commit()
        except Exception:
            db.session.rollback()
