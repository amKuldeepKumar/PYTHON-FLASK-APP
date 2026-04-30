from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class SpeakingStorageService:
    ALLOWED_EXTENSIONS = {"webm", "wav", "mp3", "ogg", "m4a", "mp4", "mpeg"}

    @classmethod
    def uploads_root(cls) -> Path:
        root = Path(current_app.root_path) / "static" / "uploads" / "speaking_audio"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def is_allowed_file(cls, filename: str | None) -> bool:
        if not filename or "." not in filename:
            return False
        extension = filename.rsplit(".", 1)[-1].lower().strip()
        return extension in cls.ALLOWED_EXTENSIONS

    @classmethod
    def save_audio(cls, audio_file: FileStorage | None) -> dict[str, Any]:
        if not audio_file or not getattr(audio_file, "filename", ""):
            return {
                "saved": False,
                "relative_path": None,
                "original_name": None,
                "mime_type": None,
                "file_size_bytes": 0,
            }

        original_name = secure_filename(audio_file.filename or "")
        if not cls.is_allowed_file(original_name):
            raise ValueError("Unsupported audio format. Please upload webm, wav, mp3, ogg, m4a, or mp4 audio.")

        extension = original_name.rsplit(".", 1)[-1].lower()
        stamp = datetime.utcnow().strftime("%Y/%m")
        folder = cls.uploads_root() / stamp
        folder.mkdir(parents=True, exist_ok=True)

        generated_name = f"speaking_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{extension}"
        absolute_path = folder / generated_name
        audio_file.save(absolute_path)

        file_size = absolute_path.stat().st_size if absolute_path.exists() else 0
        relative_path = f"uploads/speaking_audio/{stamp}/{generated_name}".replace(os.sep, "/")
        return {
            "saved": True,
            "relative_path": relative_path,
            "original_name": original_name,
            "mime_type": getattr(audio_file, "mimetype", None),
            "file_size_bytes": int(file_size or 0),
        }
