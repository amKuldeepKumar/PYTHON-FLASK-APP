from __future__ import annotations

from flask import current_app
from sqlalchemy import text

from ..extensions import db


def ensure_runtime_schema() -> None:
    """Best-effort SQLite/dev schema sync for critical LMS tracking fields."""
    try:
        with current_app.app_context():
            engine = db.engine
            if not str(engine.url).startswith("sqlite"):
                return
            db.metadata.create_all(bind=engine)
            with engine.begin() as conn:
                table_names = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
                if "questions" in table_names:
                    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(questions)"))}
                    adds = {
                        "answer_patterns_text": "ALTER TABLE questions ADD COLUMN answer_patterns_text TEXT",
                        "answer_generation_status": "ALTER TABLE questions ADD COLUMN answer_generation_status VARCHAR(30) NOT NULL DEFAULT 'pending'",
                        "answer_generated_at": "ALTER TABLE questions ADD COLUMN answer_generated_at DATETIME",
                        "synonym_help_text": "ALTER TABLE questions ADD COLUMN synonym_help_text TEXT",
                        "translation_help_text": "ALTER TABLE questions ADD COLUMN translation_help_text TEXT",
                    }
                    for col, sql in adds.items():
                        if col not in cols:
                            conn.execute(text(sql))
                if "question_attempts" in table_names:
                    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(question_attempts)"))}
                    adds = {
                        "attempt_kind": "ALTER TABLE question_attempts ADD COLUMN attempt_kind VARCHAR(20) NOT NULL DEFAULT 'final'",
                        "retry_count": "ALTER TABLE question_attempts ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
                        "is_retry": "ALTER TABLE question_attempts ADD COLUMN is_retry BOOLEAN NOT NULL DEFAULT 0",
                        "hint_used": "ALTER TABLE question_attempts ADD COLUMN hint_used BOOLEAN NOT NULL DEFAULT 0",
                        "synonym_used": "ALTER TABLE question_attempts ADD COLUMN synonym_used BOOLEAN NOT NULL DEFAULT 0",
                        "translation_used": "ALTER TABLE question_attempts ADD COLUMN translation_used BOOLEAN NOT NULL DEFAULT 0",
                        "skipped": "ALTER TABLE question_attempts ADD COLUMN skipped BOOLEAN NOT NULL DEFAULT 0",
                        "returned_after_skip": "ALTER TABLE question_attempts ADD COLUMN returned_after_skip BOOLEAN NOT NULL DEFAULT 0",
                        "skip_reason": "ALTER TABLE question_attempts ADD COLUMN skip_reason VARCHAR(80)",
                        "support_tools_json": "ALTER TABLE question_attempts ADD COLUMN support_tools_json TEXT",
                        "support_tool_penalty_points": "ALTER TABLE question_attempts ADD COLUMN support_tool_penalty_points FLOAT NOT NULL DEFAULT 0",
                    }
                    for col, sql in adds.items():
                        if col not in cols:
                            conn.execute(text(sql))
                if "lesson_progress" in table_names:
                    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(lesson_progress)"))}
                    adds = {
                        "skipped_questions": "ALTER TABLE lesson_progress ADD COLUMN skipped_questions INTEGER NOT NULL DEFAULT 0",
                        "retry_questions": "ALTER TABLE lesson_progress ADD COLUMN retry_questions INTEGER NOT NULL DEFAULT 0",
                        "support_tool_usage_count": "ALTER TABLE lesson_progress ADD COLUMN support_tool_usage_count INTEGER NOT NULL DEFAULT 0",
                        "support_tool_penalty_points": "ALTER TABLE lesson_progress ADD COLUMN support_tool_penalty_points FLOAT NOT NULL DEFAULT 0",
                    }
                    for col, sql in adds.items():
                        if col not in cols:
                            conn.execute(text(sql))
                if "themes" in table_names:
                    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(themes)"))}
                    adds = {
                        "font_family": "ALTER TABLE themes ADD COLUMN font_family VARCHAR(255) NOT NULL DEFAULT 'Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif'",
                        "heading_font_family": "ALTER TABLE themes ADD COLUMN heading_font_family VARCHAR(255) NOT NULL DEFAULT 'Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif'",
                        "accent_font_family": "ALTER TABLE themes ADD COLUMN accent_font_family VARCHAR(255) NOT NULL DEFAULT 'JetBrains Mono, SFMono-Regular, Menlo, Monaco, Consolas, monospace'",
                    }
                    for col, sql in adds.items():
                        if col not in cols:
                            conn.execute(text(sql))
                if "user_preferences" in table_names:
                    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(user_preferences)"))}
                    adds = {
                        "auto_play_question": "ALTER TABLE user_preferences ADD COLUMN auto_play_question BOOLEAN NOT NULL DEFAULT 1",
                        "auto_start_listening": "ALTER TABLE user_preferences ADD COLUMN auto_start_listening BOOLEAN NOT NULL DEFAULT 1",
                        "question_beep_enabled": "ALTER TABLE user_preferences ADD COLUMN question_beep_enabled BOOLEAN NOT NULL DEFAULT 1",
                        "voice_gender": "ALTER TABLE user_preferences ADD COLUMN voice_gender VARCHAR(20) NOT NULL DEFAULT 'female'",
                        "voice_pitch": "ALTER TABLE user_preferences ADD COLUMN voice_pitch FLOAT NOT NULL DEFAULT 1.0",
                        "playback_speed": "ALTER TABLE user_preferences ADD COLUMN playback_speed FLOAT NOT NULL DEFAULT 1.0",
                    }
                    for col, sql in adds.items():
                        if col not in cols:
                            conn.execute(text(sql))
                if "api_call_logs" in table_names:
                    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(api_call_logs)"))}
                    adds = {
                        "provider_name": "ALTER TABLE api_call_logs ADD COLUMN provider_name VARCHAR(120)",
                        "input_tokens": "ALTER TABLE api_call_logs ADD COLUMN input_tokens INTEGER",
                        "output_tokens": "ALTER TABLE api_call_logs ADD COLUMN output_tokens INTEGER",
                        "total_tokens": "ALTER TABLE api_call_logs ADD COLUMN total_tokens INTEGER",
                        "estimated_cost": "ALTER TABLE api_call_logs ADD COLUMN estimated_cost NUMERIC(10,4)",
                    }
                    for col, sql in adds.items():
                        if col not in cols:
                            conn.execute(text(sql))
    except Exception as exc:
        current_app.logger.warning("Runtime schema sync skipped: %s", exc)
