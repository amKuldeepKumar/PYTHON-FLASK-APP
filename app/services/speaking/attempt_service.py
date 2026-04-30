from __future__ import annotations

import json

import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ...extensions import db
from ...models.speaking_attempt import SpeakingAttempt
from ...models.speaking_session import SpeakingSession


class SpeakingAttemptService:
    ALLOWED_AUDIO_EXTENSIONS = {"webm", "wav", "mp3", "m4a", "ogg", "mp4"}

    @classmethod
    def _audio_folder(cls) -> Path:
        folder = Path(current_app.instance_path) / "uploads" / "speaking"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @classmethod
    def save_audio(cls, file_storage: FileStorage | None) -> dict:
        if file_storage is None or not getattr(file_storage, "filename", None):
            return {
                "audio_file_path": None,
                "audio_original_name": None,
                "audio_mime_type": None,
                "audio_file_size_bytes": 0,
            }

        original_name = secure_filename(file_storage.filename or "")
        suffix = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        if suffix and suffix not in cls.ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError("Unsupported audio file format.")

        stored_name = f"{uuid.uuid4().hex}_{original_name or 'audio.bin'}"
        target = cls._audio_folder() / stored_name
        file_storage.save(target)
        size_bytes = target.stat().st_size if target.exists() else 0

        return {
            "audio_file_path": str(target.relative_to(Path(current_app.instance_path)).as_posix()),
            "audio_original_name": original_name or None,
            "audio_mime_type": getattr(file_storage, "mimetype", None),
            "audio_file_size_bytes": size_bytes,
        }

    @staticmethod
    def create_attempt(
        *,
        session: SpeakingSession,
        transcript_text: str,
        duration_seconds: int,
        evaluation: dict,
        audio_meta: dict | None = None,
        transcript_source: str = "manual",
    ) -> SpeakingAttempt:
        audio_meta = audio_meta or {}

        attempt = SpeakingAttempt(
            owner_admin_id=session.owner_admin_id,
            session_id=session.id,
            student_id=session.student_id,
            topic_id=session.topic_id,
            prompt_id=session.prompt_id,
            attempt_number=int(session.submit_count or 0) + 1,
            duration_seconds=max(0, int(duration_seconds or 0)),
            audio_file_path=audio_meta.get("audio_file_path"),
            audio_original_name=audio_meta.get("audio_original_name"),
            audio_mime_type=audio_meta.get("audio_mime_type"),
            audio_file_size_bytes=int(audio_meta.get("audio_file_size_bytes") or 0),
            transcript_text=transcript_text,
            transcript_source=transcript_source or "manual",
            word_count=int(evaluation.get("word_count") or 0),
            char_count=int(evaluation.get("char_count") or 0),
            result_summary=evaluation.get("feedback_text"),
            score=evaluation.get("score"),
            relevance_score=evaluation.get("relevance_score"),
            is_relevant=bool(evaluation.get("is_relevant")),
            feedback_text=evaluation.get("feedback_text"),
            evaluation_json=json.dumps(evaluation, ensure_ascii=False),
            recommended_next_step=evaluation.get("recommended_next_step"),
            retry_recommended=bool(evaluation.get("should_retry")),
        )

        db.session.add(attempt)
        db.session.flush()
        return attempt


# Backward-compatible alias
AttemptService = SpeakingAttemptService