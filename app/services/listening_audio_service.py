from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from hashlib import sha1
from pathlib import Path
import json
import shutil
import subprocess
import sys

from flask import current_app, url_for

from ..models.lms import Course, Lesson


@dataclass
class ListeningPlaybackConfig:
    replay_limit: int
    allowed_speeds: list[float]
    caption_default: str
    caption_locked: bool


class ListeningAudioService:
    """Simple backend-linked listening audio generation with filesystem caching.

    Uses `espeak` when available to create a wav file under static/uploads/listening.
    Falls back to no file when synthesis fails so the UI can still show the script.
    """

    @staticmethod
    def _uploads_dir() -> Path:
        root = Path(current_app.root_path).parent
        target = root / 'app' / 'static' / 'uploads' / 'listening'
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def script_text(lesson: Lesson) -> str:
        return (lesson.explanation_tts_text or lesson.explanation_text or '').strip()

    @staticmethod
    def _safe_voice_name(course: Optional[Course]) -> str:
        language = (getattr(course, 'language_code', '') or 'en').lower()
        if language.startswith('en'):
            return 'en'
        return 'en'

    @staticmethod
    def build_config(course: Optional[Course], lesson: Optional[Lesson] = None) -> ListeningPlaybackConfig:
        difficulty = ((getattr(course, 'difficulty', '') or '') if course else '').strip().lower()
        level_hint = ''
        if lesson and lesson.level and lesson.level.title:
            level_hint = lesson.level.title.strip().lower()
        if difficulty in {'basic', 'beginner', 'a1', 'a2'} or 'basic' in level_hint:
            return ListeningPlaybackConfig(replay_limit=3, allowed_speeds=[0.9, 1.0], caption_default='on', caption_locked=False)
        if difficulty in {'advanced', 'expert', 'c1', 'c2'} or 'advanced' in level_hint:
            return ListeningPlaybackConfig(replay_limit=2, allowed_speeds=[0.9, 1.0, 1.1], caption_default='off', caption_locked=False)
        return ListeningPlaybackConfig(replay_limit=2, allowed_speeds=[0.9, 1.0, 1.1], caption_default='off', caption_locked=False)

    @classmethod
    def _cache_key(cls, course: Optional[Course], lesson: Lesson) -> str:
        payload = {
            'lesson_id': lesson.id,
            'course_id': getattr(course, 'id', None),
            'voice': cls._safe_voice_name(course),
            'text': cls.script_text(lesson),
        }
        return sha1(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()[:16]

    @classmethod
    def cached_path(cls, course: Optional[Course], lesson: Lesson) -> Path:
        return cls._uploads_dir() / f'lesson_{lesson.id}_{cls._cache_key(course, lesson)}.wav'

    @classmethod
    def cached_exists(cls, course: Optional[Course], lesson: Lesson) -> bool:
        path = cls.cached_path(course, lesson)
        return path.exists() and path.stat().st_size > 64

    @classmethod
    def _synth_with_espeak(cls, course: Optional[Course], script: str, target: Path) -> bool:
        if not shutil.which('espeak'):
            return False
        cmd = [
            'espeak',
            '-v', cls._safe_voice_name(course),
            '-s', '145',
            '-w', str(target),
            script,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=False, timeout=45)
        return target.exists() and target.stat().st_size > 64

    @classmethod
    def _synth_with_windows_sapi(cls, script: str, target: Path) -> bool:
        if not sys.platform.startswith('win'):
            return False
        powershell = (
            shutil.which('powershell')
            or shutil.which('powershell.exe')
            or shutil.which('pwsh')
            or shutil.which('pwsh.exe')
        )
        if not powershell:
            return False
        safe_script = script.replace('`', '``').replace('"', '`"')
        safe_target = str(target).replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Speech;\n"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;\n"
            "$synth.Rate = 0;\n"
            "$synth.Volume = 100;\n"
            f"$synth.SetOutputToWaveFile('{safe_target}');\n"
            f'$synth.Speak("{safe_script}");\n'
            "$synth.Dispose();"
        )
        subprocess.run(
            [powershell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return target.exists() and target.stat().st_size > 64

    @classmethod
    def ensure_audio(cls, course: Optional[Course], lesson: Lesson) -> Optional[Path]:
        script = cls.script_text(lesson)
        if not script:
            return None
        target = cls.cached_path(course, lesson)
        if target.exists() and target.stat().st_size > 64:
            return target
        for stale in cls._uploads_dir().glob(f'lesson_{lesson.id}_*.wav'):
            if stale != target:
                try:
                    stale.unlink()
                except OSError:
                    pass
        synthesizers = [
            lambda: cls._synth_with_espeak(course, script, target),
            lambda: cls._synth_with_windows_sapi(script, target),
        ]
        for synth in synthesizers:
            try:
                if synth():
                    return target
            except Exception:
                continue
        try:
            if target.exists():
                target.unlink()
        except OSError:
            pass
        return None

    @classmethod
    def audio_url(cls, course: Optional[Course], lesson: Lesson) -> Optional[str]:
        path = cls.ensure_audio(course, lesson)
        if not path:
            return None
        filename = path.name
        return url_for('static', filename=f'uploads/listening/{filename}')
