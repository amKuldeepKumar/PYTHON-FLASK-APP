from __future__ import annotations

from sqlalchemy import inspect, text

from .extensions import db


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _sqlite_column_is_not_null(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return bool(col.get("nullable") is False)
    return False


def ensure_dev_sqlite_schema() -> None:
    engine = db.engine
    if not str(engine.url).startswith("sqlite"):
        return

    inspector = inspect(engine)
    db.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    with engine.begin() as conn:

        if not _table_exists(inspector, "speaking_providers"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS speaking_providers (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    provider_kind VARCHAR(30) NOT NULL,
                    provider_type VARCHAR(40) NOT NULL DEFAULT 'mock',
                    api_key TEXT,
                    api_base_url VARCHAR(255),
                    model_name VARCHAR(120),
                    config_json TEXT,
                    official_website VARCHAR(255),
                    usage_scope VARCHAR(60),
                    pricing_note VARCHAR(255),
                    notes TEXT,
                    fallback_provider_id INTEGER,
                    is_enabled BOOLEAN NOT NULL DEFAULT 0,
                    is_default BOOLEAN NOT NULL DEFAULT 0,
                    supports_test BOOLEAN NOT NULL DEFAULT 1,
                    last_test_status VARCHAR(20),
                    last_test_message VARCHAR(255),
                    last_tested_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if _table_exists(inspector, "themes"):
            cols = _column_names(inspector, "themes")
            theme_adds = {
                "font_family": "ALTER TABLE themes ADD COLUMN font_family VARCHAR(255) NOT NULL DEFAULT 'Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif'",
                "heading_font_family": "ALTER TABLE themes ADD COLUMN heading_font_family VARCHAR(255) NOT NULL DEFAULT 'Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif'",
                "accent_font_family": "ALTER TABLE themes ADD COLUMN accent_font_family VARCHAR(255) NOT NULL DEFAULT 'JetBrains Mono, SFMono-Regular, Menlo, Monaco, Consolas, monospace'",
                "alphabet_min_size": "ALTER TABLE themes ADD COLUMN alphabet_min_size INTEGER NOT NULL DEFAULT 18",
                "alphabet_max_size": "ALTER TABLE themes ADD COLUMN alphabet_max_size INTEGER NOT NULL DEFAULT 66",
                "alphabet_count": "ALTER TABLE themes ADD COLUMN alphabet_count INTEGER NOT NULL DEFAULT 64",
                "alphabet_motion_mode": "ALTER TABLE themes ADD COLUMN alphabet_motion_mode VARCHAR(24) NOT NULL DEFAULT 'float'",
                "alphabet_direction_x": "ALTER TABLE themes ADD COLUMN alphabet_direction_x INTEGER NOT NULL DEFAULT 0",
                "alphabet_direction_y": "ALTER TABLE themes ADD COLUMN alphabet_direction_y INTEGER NOT NULL DEFAULT 100",
                "alphabet_opacity": "ALTER TABLE themes ADD COLUMN alphabet_opacity INTEGER NOT NULL DEFAULT 82",
                "alphabet_trail_length": "ALTER TABLE themes ADD COLUMN alphabet_trail_length INTEGER NOT NULL DEFAULT 14",
                "alphabet_tilt_x": "ALTER TABLE themes ADD COLUMN alphabet_tilt_x INTEGER NOT NULL DEFAULT 18",
                "alphabet_tilt_y": "ALTER TABLE themes ADD COLUMN alphabet_tilt_y INTEGER NOT NULL DEFAULT 12",
                "alphabet_tilt_z": "ALTER TABLE themes ADD COLUMN alphabet_tilt_z INTEGER NOT NULL DEFAULT 30",
                "alphabet_outline_only": "ALTER TABLE themes ADD COLUMN alphabet_outline_only BOOLEAN NOT NULL DEFAULT 0",
                "alphabet_outline_color": "ALTER TABLE themes ADD COLUMN alphabet_outline_color VARCHAR(64) NOT NULL DEFAULT '#ffffff'",
                "header_sticky_enabled": "ALTER TABLE themes ADD COLUMN header_sticky_enabled BOOLEAN NOT NULL DEFAULT 0",
                "header_transparent_enabled": "ALTER TABLE themes ADD COLUMN header_transparent_enabled BOOLEAN NOT NULL DEFAULT 0",
            }
            for col, sql in theme_adds.items():
                if col not in cols:
                    conn.execute(text(sql))
            inspector = inspect(engine)

        if _table_exists(inspector, "seo_settings"):
            cols = _column_names(inspector, "seo_settings")
            seo_adds = {
                "favicon_url": "ALTER TABLE seo_settings ADD COLUMN favicon_url VARCHAR(500) NOT NULL DEFAULT ''",
                "site_logo_url": "ALTER TABLE seo_settings ADD COLUMN site_logo_url VARCHAR(500) NOT NULL DEFAULT ''",
                "footer_logo_url": "ALTER TABLE seo_settings ADD COLUMN footer_logo_url VARCHAR(500) NOT NULL DEFAULT ''",
                "custom_json_ld": "ALTER TABLE seo_settings ADD COLUMN custom_json_ld TEXT",
                "robots_enabled": "ALTER TABLE seo_settings ADD COLUMN robots_enabled BOOLEAN NOT NULL DEFAULT 1",
                "sitemap_include_pages": "ALTER TABLE seo_settings ADD COLUMN sitemap_include_pages BOOLEAN NOT NULL DEFAULT 1",
                "sitemap_include_public_reading": "ALTER TABLE seo_settings ADD COLUMN sitemap_include_public_reading BOOLEAN NOT NULL DEFAULT 1",
                "sitemap_include_courses": "ALTER TABLE seo_settings ADD COLUMN sitemap_include_courses BOOLEAN NOT NULL DEFAULT 1",
                "htaccess_enabled": "ALTER TABLE seo_settings ADD COLUMN htaccess_enabled BOOLEAN NOT NULL DEFAULT 0",
                "htaccess_force_https": "ALTER TABLE seo_settings ADD COLUMN htaccess_force_https BOOLEAN NOT NULL DEFAULT 1",
                "htaccess_force_www": "ALTER TABLE seo_settings ADD COLUMN htaccess_force_www BOOLEAN NOT NULL DEFAULT 0",
                "htaccess_enable_compression": "ALTER TABLE seo_settings ADD COLUMN htaccess_enable_compression BOOLEAN NOT NULL DEFAULT 1",
                "htaccess_enable_browser_cache": "ALTER TABLE seo_settings ADD COLUMN htaccess_enable_browser_cache BOOLEAN NOT NULL DEFAULT 1",
                "htaccess_custom_rules": "ALTER TABLE seo_settings ADD COLUMN htaccess_custom_rules TEXT",
                "header_announcement_enabled": "ALTER TABLE seo_settings ADD COLUMN header_announcement_enabled BOOLEAN NOT NULL DEFAULT 0",
                "header_announcement_text": "ALTER TABLE seo_settings ADD COLUMN header_announcement_text VARCHAR(255) NOT NULL DEFAULT ''",
                "header_cta_text": "ALTER TABLE seo_settings ADD COLUMN header_cta_text VARCHAR(120) NOT NULL DEFAULT 'Get Started'",
                "header_cta_url": "ALTER TABLE seo_settings ADD COLUMN header_cta_url VARCHAR(255) NOT NULL DEFAULT '/auth/register'",
                "header_links_json": "ALTER TABLE seo_settings ADD COLUMN header_links_json TEXT NOT NULL DEFAULT '[]'",
                "footer_columns": "ALTER TABLE seo_settings ADD COLUMN footer_columns INTEGER NOT NULL DEFAULT 4",
                "footer_widgets_json": "ALTER TABLE seo_settings ADD COLUMN footer_widgets_json TEXT NOT NULL DEFAULT '[]'",
                "footer_copyright": "ALTER TABLE seo_settings ADD COLUMN footer_copyright VARCHAR(255) NOT NULL DEFAULT '© 2026 Fluencify AI'",
                "whatsapp_enabled": "ALTER TABLE seo_settings ADD COLUMN whatsapp_enabled BOOLEAN NOT NULL DEFAULT 0",
                "whatsapp_show_on_public": "ALTER TABLE seo_settings ADD COLUMN whatsapp_show_on_public BOOLEAN NOT NULL DEFAULT 1",
                "whatsapp_click_tracking_enabled": "ALTER TABLE seo_settings ADD COLUMN whatsapp_click_tracking_enabled BOOLEAN NOT NULL DEFAULT 1",
                "whatsapp_number": "ALTER TABLE seo_settings ADD COLUMN whatsapp_number VARCHAR(32) NOT NULL DEFAULT ''",
                "whatsapp_button_text": "ALTER TABLE seo_settings ADD COLUMN whatsapp_button_text VARCHAR(80) NOT NULL DEFAULT 'Need Help? WhatsApp'",
                "whatsapp_help_text": "ALTER TABLE seo_settings ADD COLUMN whatsapp_help_text VARCHAR(180) NOT NULL DEFAULT 'Ask us about courses, fees, or placement test help.'",
                "whatsapp_default_category": "ALTER TABLE seo_settings ADD COLUMN whatsapp_default_category VARCHAR(120) NOT NULL DEFAULT 'Course inquiry'",
                "whatsapp_message": "ALTER TABLE seo_settings ADD COLUMN whatsapp_message VARCHAR(500) NOT NULL DEFAULT 'Hi! I need help with Fluencify courses.'",
            }
            for col, sql in seo_adds.items():
                if col not in cols:
                    conn.execute(text(sql))
            inspector = inspect(engine)

        if _table_exists(inspector, "speaking_sessions"):
            cols = _column_names(inspector, "speaking_sessions")
            if "evaluation_json" not in cols:
                conn.execute(text("ALTER TABLE speaking_sessions ADD COLUMN evaluation_json TEXT"))
            inspector = inspect(engine)

        if _table_exists(inspector, "enrollments"):
            cols = _column_names(inspector, "enrollments")
            if "welcome_seen_at" not in cols:
                conn.execute(text("ALTER TABLE enrollments ADD COLUMN welcome_seen_at DATETIME"))
            inspector = inspect(engine)

        if _table_exists(inspector, "courses"):
            cols = _column_names(inspector, "courses")
            if "welcome_intro_script" not in cols:
                conn.execute(text("ALTER TABLE courses ADD COLUMN welcome_intro_script TEXT"))
            if "learning_outcomes_script" not in cols:
                conn.execute(text("ALTER TABLE courses ADD COLUMN learning_outcomes_script TEXT"))
            inspector = inspect(engine)


        if not _table_exists(inspector, "student_placement_results"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS student_placement_results (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    version VARCHAR(32) NOT NULL DEFAULT 'phase-b-v1',
                    target_language VARCHAR(32) NOT NULL DEFAULT 'english',
                    goal VARCHAR(64),
                    focus_skill VARCHAR(32),
                    comfort_level VARCHAR(32),
                    overall_score INTEGER NOT NULL DEFAULT 0,
                    grammar_score INTEGER NOT NULL DEFAULT 0,
                    vocabulary_score INTEGER NOT NULL DEFAULT 0,
                    reading_score INTEGER NOT NULL DEFAULT 0,
                    writing_score INTEGER NOT NULL DEFAULT 0,
                    speaking_score INTEGER NOT NULL DEFAULT 0,
                    listening_score INTEGER NOT NULL DEFAULT 0,
                    confidence_score INTEGER NOT NULL DEFAULT 0,
                    mcq_score INTEGER NOT NULL DEFAULT 0,
                    mcq_total INTEGER NOT NULL DEFAULT 0,
                    level VARCHAR(32) NOT NULL DEFAULT 'basic',
                    recommended_level VARCHAR(32) NOT NULL DEFAULT 'basic',
                    recommended_tracks_json TEXT,
                    recommended_titles_json TEXT,
                    recommended_keywords_json TEXT,
                    strengths_json TEXT,
                    weak_areas_json TEXT,
                    next_steps_json TEXT,
                    learning_path_json TEXT,
                    answers_json TEXT,
                    profile_answers_json TEXT,
                    skill_scores_json TEXT,
                    summary TEXT,
                    fit_summary TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)
        if not _table_exists(inspector, "whatsapp_inquiry_logs"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS whatsapp_inquiry_logs (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    source_path VARCHAR(500) NOT NULL DEFAULT '',
                    referer VARCHAR(500) NOT NULL DEFAULT '',
                    ip_address VARCHAR(80) NOT NULL DEFAULT '',
                    user_agent VARCHAR(500) NOT NULL DEFAULT '',
                    category VARCHAR(120) NOT NULL DEFAULT 'Course inquiry',
                    number_snapshot VARCHAR(40) NOT NULL DEFAULT '',
                    message_snapshot TEXT,
                    status VARCHAR(30) NOT NULL DEFAULT 'clicked',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "course_chat_moderation_events"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS course_chat_moderation_events (
                    id INTEGER PRIMARY KEY,
                    course_id INTEGER NOT NULL,
                    sender_student_id INTEGER NOT NULL,
                    attempted_body TEXT NOT NULL,
                    flagged_categories VARCHAR(255) NOT NULL DEFAULT '',
                    status VARCHAR(20) NOT NULL DEFAULT 'blocked',
                    moderator_notes TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at DATETIME,
                    reviewed_by_id INTEGER
                )
            """))
            inspector = inspect(engine)

        if _table_exists(inspector, "speaking_topics"):
            cols = _column_names(inspector, "speaking_topics")
            topic_adds = {
                "topic_kind": "ALTER TABLE speaking_topics ADD COLUMN topic_kind VARCHAR(30) NOT NULL DEFAULT 'general'",
                "interview_category": "ALTER TABLE speaking_topics ADD COLUMN interview_category VARCHAR(60)",
                "role_family": "ALTER TABLE speaking_topics ADD COLUMN role_family VARCHAR(80)",
                "role_name": "ALTER TABLE speaking_topics ADD COLUMN role_name VARCHAR(120)",
                "answer_framework": "ALTER TABLE speaking_topics ADD COLUMN answer_framework TEXT",
                "sample_answer": "ALTER TABLE speaking_topics ADD COLUMN sample_answer TEXT",
            }
            for col, sql in topic_adds.items():
                if col not in cols:
                    conn.execute(text(sql))
            inspector = inspect(engine)

        if _table_exists(inspector, "speaking_prompts"):
            cols = _column_names(inspector, "speaking_prompts")
            prompt_adds = {
                "prompt_kind": "ALTER TABLE speaking_prompts ADD COLUMN prompt_kind VARCHAR(30) NOT NULL DEFAULT 'general'",
                "interview_question_type": "ALTER TABLE speaking_prompts ADD COLUMN interview_question_type VARCHAR(60)",
                "answer_tips_text": "ALTER TABLE speaking_prompts ADD COLUMN answer_tips_text TEXT",
                "sample_answer_text": "ALTER TABLE speaking_prompts ADD COLUMN sample_answer_text TEXT",
                "followup_prompt_text": "ALTER TABLE speaking_prompts ADD COLUMN followup_prompt_text TEXT",
                "target_keywords_text": "ALTER TABLE speaking_prompts ADD COLUMN target_keywords_text TEXT",
            }
            for col, sql in prompt_adds.items():
                if col not in cols:
                    conn.execute(text(sql))
            inspector = inspect(engine)

        if _table_exists(inspector, "speaking_attempts"):
            cols = _column_names(inspector, "speaking_attempts")
            if "evaluation_json" not in cols:
                conn.execute(text("ALTER TABLE speaking_attempts ADD COLUMN evaluation_json TEXT"))
            inspector = inspect(engine)

        if not _table_exists(inspector, "translation_providers"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS translation_providers (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(80) NOT NULL DEFAULT 'Primary Translation Provider',
                    provider_type VARCHAR(40) NOT NULL DEFAULT 'mock',
                    api_key TEXT,
                    api_base_url VARCHAR(255),
                    model_name VARCHAR(120),
                    is_enabled BOOLEAN NOT NULL DEFAULT 0,
                    supports_live_credit_check BOOLEAN NOT NULL DEFAULT 0,
                    source_language_code VARCHAR(16) NOT NULL DEFAULT 'en',
                    credits_remaining FLOAT,
                    credit_unit VARCHAR(30) NOT NULL DEFAULT 'credits',
                    per_request_cost FLOAT NOT NULL DEFAULT 1.0,
                    last_credit_sync_at DATETIME,
                    last_error VARCHAR(255),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "reading_providers"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reading_providers (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    provider_kind VARCHAR(30) NOT NULL,
                    provider_type VARCHAR(40) NOT NULL DEFAULT 'mock',
                    api_key TEXT,
                    api_base_url VARCHAR(255),
                    model_name VARCHAR(120),
                    config_json TEXT,
                    official_website VARCHAR(255),
                    usage_scope VARCHAR(60),
                    pricing_note VARCHAR(255),
                    notes TEXT,
                    fallback_provider_id INTEGER,
                    is_enabled BOOLEAN NOT NULL DEFAULT 0,
                    is_default BOOLEAN NOT NULL DEFAULT 0,
                    supports_test BOOLEAN NOT NULL DEFAULT 1,
                    last_test_status VARCHAR(20),
                    last_test_message VARCHAR(255),
                    last_tested_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "reading_prompt_configs"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reading_prompt_configs (
                    id INTEGER PRIMARY KEY,
                    task_type VARCHAR(30) NOT NULL UNIQUE,
                    title VARCHAR(120) NOT NULL,
                    prompt_text TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_published BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)



        if not _table_exists(inspector, "ai_request_logs"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_request_logs (
                    id INTEGER PRIMARY KEY,
                    request_id VARCHAR(64) NOT NULL,
                    actor_user_id INTEGER,
                    course_id INTEGER,
                    lesson_id INTEGER,
                    task_key VARCHAR(64) NOT NULL,
                    provider_source VARCHAR(32),
                    provider_id INTEGER,
                    provider_name VARCHAR(120),
                    provider_type VARCHAR(64),
                    model_name VARCHAR(120),
                    prompt_hash VARCHAR(64),
                    response_hash VARCHAR(64),
                    redacted_prompt TEXT,
                    redacted_response TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    latency_ms INTEGER,
                    estimated_cost NUMERIC(12,6),
                    cache_hit BOOLEAN NOT NULL DEFAULT 0,
                    fallback_used BOOLEAN NOT NULL DEFAULT 0,
                    circuit_state VARCHAR(20),
                    status VARCHAR(20) NOT NULL DEFAULT 'success',
                    error_code VARCHAR(80),
                    error_message VARCHAR(255),
                    consent_snapshot BOOLEAN NOT NULL DEFAULT 0,
                    exportable_for_ml BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "ai_usage_counters"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_usage_counters (
                    id INTEGER PRIMARY KEY,
                    actor_user_id INTEGER NOT NULL,
                    usage_date DATE NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    translation_count INTEGER NOT NULL DEFAULT 0,
                    speech_seconds INTEGER NOT NULL DEFAULT 0,
                    tts_characters INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_usage_counters_user_day_idx ON ai_usage_counters(actor_user_id, usage_date)"))
            inspector = inspect(engine)

        if not _table_exists(inspector, "ai_rule_configs"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_rule_configs (
                    id INTEGER PRIMARY KEY,
                    track_key VARCHAR(30) NOT NULL UNIQUE,
                    is_enabled BOOLEAN NOT NULL DEFAULT 1,
                    rule_text TEXT NOT NULL DEFAULT '',
                    guardrails_text TEXT,
                    scoring_notes TEXT,
                    output_format TEXT,
                    strictness INTEGER NOT NULL DEFAULT 3,
                    min_length INTEGER NOT NULL DEFAULT 0,
                    require_explanations BOOLEAN NOT NULL DEFAULT 1,
                    off_topic_block BOOLEAN NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    updated_by_user_id INTEGER,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "reading_topics"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reading_topics (
                    id INTEGER PRIMARY KEY,
                    code VARCHAR(80) NOT NULL UNIQUE,
                    title VARCHAR(160) NOT NULL,
                    category VARCHAR(120),
                    level VARCHAR(30) NOT NULL DEFAULT 'basic',
                    description TEXT,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_published BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "reading_passages"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reading_passages (
                    id INTEGER PRIMARY KEY,
                    topic_id INTEGER NOT NULL,
                    topic_title_snapshot VARCHAR(160) NOT NULL,
                    level VARCHAR(30) NOT NULL DEFAULT 'basic',
                    length_mode VARCHAR(20) NOT NULL DEFAULT 'medium',
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    prompt_snapshot TEXT,
                    generation_notes TEXT,
                    generation_source VARCHAR(40) NOT NULL DEFAULT 'dynamic_api',
                    provider_id INTEGER,
                    provider_name_snapshot VARCHAR(160),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_published BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "reading_questions"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reading_questions (
                    id INTEGER PRIMARY KEY,
                    passage_id INTEGER NOT NULL,
                    topic_id INTEGER NOT NULL,
                    question_type VARCHAR(30) NOT NULL,
                    level VARCHAR(30) NOT NULL DEFAULT 'basic',
                    language_code VARCHAR(16) NOT NULL DEFAULT 'en',
                    display_order INTEGER NOT NULL DEFAULT 0,
                    prompt_snapshot TEXT,
                    question_text TEXT NOT NULL,
                    options_json TEXT,
                    correct_answer TEXT,
                    explanation TEXT,
                    source_sentence TEXT,
                    provider_id INTEGER,
                    provider_name_snapshot VARCHAR(160),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_published BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "reading_session_logs"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reading_session_logs (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    course_id INTEGER,
                    passage_id INTEGER NOT NULL,
                    topic_id INTEGER,
                    accuracy FLOAT NOT NULL DEFAULT 0,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    incorrect_count INTEGER NOT NULL DEFAULT 0,
                    total_questions INTEGER NOT NULL DEFAULT 0,
                    errors_count INTEGER NOT NULL DEFAULT 0,
                    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
                    reading_speed_wpm FLOAT NOT NULL DEFAULT 0,
                    progress_percent INTEGER NOT NULL DEFAULT 100,
                    answers_json TEXT,
                    checked_rows_json TEXT,
                    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)


        if not _table_exists(inspector, "writing_topics"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS writing_topics (
                    id INTEGER PRIMARY KEY,
                    code VARCHAR(80) NOT NULL UNIQUE,
                    title VARCHAR(160) NOT NULL,
                    category VARCHAR(120),
                    level VARCHAR(30) NOT NULL DEFAULT 'basic',
                    description TEXT,
                    course_id INTEGER,
                    course_level_number INTEGER,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_published BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "writing_tasks"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS writing_tasks (
                    id INTEGER PRIMARY KEY,
                    topic_id INTEGER NOT NULL,
                    topic_title_snapshot VARCHAR(160) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    instructions TEXT NOT NULL,
                    task_type VARCHAR(30) NOT NULL DEFAULT 'essay',
                    level VARCHAR(30) NOT NULL DEFAULT 'basic',
                    min_words INTEGER NOT NULL DEFAULT 80,
                    max_words INTEGER,
                    language_code VARCHAR(16) NOT NULL DEFAULT 'en',
                    course_id INTEGER,
                    course_level_number INTEGER,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_published BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if not _table_exists(inspector, "writing_submissions"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS writing_submissions (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    course_id INTEGER,
                    topic_id INTEGER,
                    task_id INTEGER,
                    submission_text TEXT NOT NULL,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    char_count INTEGER NOT NULL DEFAULT 0,
                    paragraph_count INTEGER NOT NULL DEFAULT 0,
                    sentence_count INTEGER NOT NULL DEFAULT 0,
                    score FLOAT,
                    feedback_text TEXT,
                    evaluation_summary TEXT,
                    evaluation_payload TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
                    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        # rebuild writing_submissions if old sqlite table still has task_id as NOT NULL
        inspector = inspect(engine)
        if _table_exists(inspector, "writing_submissions") and _sqlite_column_is_not_null(inspector, "writing_submissions", "task_id"):
            conn.execute(text("ALTER TABLE writing_submissions RENAME TO writing_submissions_old"))

            conn.execute(text("""
                CREATE TABLE writing_submissions (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    course_id INTEGER,
                    topic_id INTEGER,
                    task_id INTEGER,
                    submission_text TEXT NOT NULL,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    char_count INTEGER NOT NULL DEFAULT 0,
                    paragraph_count INTEGER NOT NULL DEFAULT 0,
                    sentence_count INTEGER NOT NULL DEFAULT 0,
                    score FLOAT,
                    feedback_text TEXT,
                    evaluation_summary TEXT,
                    evaluation_payload TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
                    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                INSERT INTO writing_submissions (
                    id, student_id, course_id, topic_id, task_id, submission_text,
                    word_count, char_count, paragraph_count, sentence_count,
                    score, feedback_text, evaluation_summary, evaluation_payload, status,
                    submitted_at, created_at, updated_at
                )
                SELECT
                    id, student_id, course_id, topic_id, task_id, submission_text,
                    word_count, char_count, paragraph_count, sentence_count,
                    score, feedback_text, evaluation_summary, NULL, status,
                    submitted_at, created_at, updated_at
                FROM writing_submissions_old
            """))

            conn.execute(text("DROP TABLE writing_submissions_old"))
            inspector = inspect(engine)

        for table_name, adds in {
            "courses": {
                "version_number": "ALTER TABLE courses ADD COLUMN version_number INTEGER NOT NULL DEFAULT 1",
                "workflow_status": "ALTER TABLE courses ADD COLUMN workflow_status VARCHAR(30) NOT NULL DEFAULT 'draft'",
                "submitted_for_review_at": "ALTER TABLE courses ADD COLUMN submitted_for_review_at DATETIME",
                "reviewed_at": "ALTER TABLE courses ADD COLUMN reviewed_at DATETIME",
                "published_at": "ALTER TABLE courses ADD COLUMN published_at DATETIME",
                "max_level": "ALTER TABLE courses ADD COLUMN max_level INTEGER NOT NULL DEFAULT 1",
                "access_type": "ALTER TABLE courses ADD COLUMN access_type VARCHAR(20) NOT NULL DEFAULT 'free'",
                "allow_level_purchase": "ALTER TABLE courses ADD COLUMN allow_level_purchase BOOLEAN NOT NULL DEFAULT 0",
                "level_access_type": "ALTER TABLE courses ADD COLUMN level_access_type VARCHAR(20) NOT NULL DEFAULT 'free'",
                "level_price": "ALTER TABLE courses ADD COLUMN level_price NUMERIC(10, 2) NOT NULL DEFAULT 0",
                "level_sale_price": "ALTER TABLE courses ADD COLUMN level_sale_price NUMERIC(10, 2)",
                "allow_coin_redemption": "ALTER TABLE courses ADD COLUMN allow_coin_redemption BOOLEAN NOT NULL DEFAULT 0",
                "coin_price": "ALTER TABLE courses ADD COLUMN coin_price INTEGER",
                "community_enabled": "ALTER TABLE courses ADD COLUMN community_enabled BOOLEAN NOT NULL DEFAULT 1",
                "speaking_base_override": "ALTER TABLE courses ADD COLUMN speaking_base_override INTEGER",
                "speaking_relevance_bonus_override": "ALTER TABLE courses ADD COLUMN speaking_relevance_bonus_override INTEGER",
                "speaking_progress_bonus_override": "ALTER TABLE courses ADD COLUMN speaking_progress_bonus_override INTEGER",
                "speaking_good_bonus_override": "ALTER TABLE courses ADD COLUMN speaking_good_bonus_override INTEGER",
                "speaking_strong_bonus_override": "ALTER TABLE courses ADD COLUMN speaking_strong_bonus_override INTEGER",
                "speaking_full_length_bonus_override": "ALTER TABLE courses ADD COLUMN speaking_full_length_bonus_override INTEGER",
                "speaking_first_try_bonus_override": "ALTER TABLE courses ADD COLUMN speaking_first_try_bonus_override INTEGER",
                "lesson_base_override": "ALTER TABLE courses ADD COLUMN lesson_base_override INTEGER",
                "lesson_accuracy_mid_bonus_override": "ALTER TABLE courses ADD COLUMN lesson_accuracy_mid_bonus_override INTEGER",
                "lesson_accuracy_high_bonus_override": "ALTER TABLE courses ADD COLUMN lesson_accuracy_high_bonus_override INTEGER",
                "boss_reward_override": "ALTER TABLE courses ADD COLUMN boss_reward_override INTEGER",
            },
            "lessons": {
                "module_id": "ALTER TABLE lessons ADD COLUMN module_id INTEGER",
                "workflow_status": "ALTER TABLE lessons ADD COLUMN workflow_status VARCHAR(30) NOT NULL DEFAULT 'draft'",
            },
            "questions": {
                "image_url": "ALTER TABLE questions ADD COLUMN image_url VARCHAR(255)",
                "answer_patterns_text": "ALTER TABLE questions ADD COLUMN answer_patterns_text TEXT",
                "answer_generation_status": "ALTER TABLE questions ADD COLUMN answer_generation_status VARCHAR(30) NOT NULL DEFAULT 'pending'",
                "answer_generated_at": "ALTER TABLE questions ADD COLUMN answer_generated_at DATETIME",
                "synonym_help_text": "ALTER TABLE questions ADD COLUMN synonym_help_text TEXT",
                "translation_help_text": "ALTER TABLE questions ADD COLUMN translation_help_text TEXT",
                "version_number": "ALTER TABLE questions ADD COLUMN version_number INTEGER NOT NULL DEFAULT 1",
            },
            "question_attempts": {
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
                "ml_consent_granted": "ALTER TABLE question_attempts ADD COLUMN ml_consent_granted BOOLEAN NOT NULL DEFAULT 0",
            },
            "enrollments": {
                "access_scope": "ALTER TABLE enrollments ADD COLUMN access_scope VARCHAR(20) NOT NULL DEFAULT 'full_course'",
                "purchased_levels_json": "ALTER TABLE enrollments ADD COLUMN purchased_levels_json TEXT",
            },
            "payments": {
                "purchase_scope": "ALTER TABLE payments ADD COLUMN purchase_scope VARCHAR(20) NOT NULL DEFAULT 'full_course'",
                "level_number": "ALTER TABLE payments ADD COLUMN level_number INTEGER",
            },
            "speaking_topics": {
                "course_level_number": "ALTER TABLE speaking_topics ADD COLUMN course_level_number INTEGER",
                "language_code": "ALTER TABLE speaking_topics ADD COLUMN language_code VARCHAR(16) NOT NULL DEFAULT 'en'",
                "course_id": "ALTER TABLE speaking_topics ADD COLUMN course_id INTEGER",
            },
            "reading_topics": {
                "course_id": "ALTER TABLE reading_topics ADD COLUMN course_id INTEGER",
                "course_level_number": "ALTER TABLE reading_topics ADD COLUMN course_level_number INTEGER",
                "description": "ALTER TABLE reading_topics ADD COLUMN description TEXT",
                "display_order": "ALTER TABLE reading_topics ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0",
            },
            "reading_passages": {
                "course_level_number": "ALTER TABLE reading_passages ADD COLUMN course_level_number INTEGER",
                "is_published": "ALTER TABLE reading_passages ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT 0",
                "course_id": "ALTER TABLE reading_passages ADD COLUMN course_id INTEGER",
                "prompt_snapshot": "ALTER TABLE reading_passages ADD COLUMN prompt_snapshot TEXT",
                "generation_notes": "ALTER TABLE reading_passages ADD COLUMN generation_notes TEXT",
                "generation_source": "ALTER TABLE reading_passages ADD COLUMN generation_source VARCHAR(40) NOT NULL DEFAULT 'dynamic_api'",
                "provider_id": "ALTER TABLE reading_passages ADD COLUMN provider_id INTEGER",
                "provider_name_snapshot": "ALTER TABLE reading_passages ADD COLUMN provider_name_snapshot VARCHAR(160)",
                "status": "ALTER TABLE reading_passages ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'",
                "review_notes": "ALTER TABLE reading_passages ADD COLUMN review_notes TEXT",
                "reviewed_at": "ALTER TABLE reading_passages ADD COLUMN reviewed_at DATETIME",
                "reviewed_by_id": "ALTER TABLE reading_passages ADD COLUMN reviewed_by_id INTEGER",
                "confidence_score": "ALTER TABLE reading_passages ADD COLUMN confidence_score FLOAT",
                "auto_flag_reason": "ALTER TABLE reading_passages ADD COLUMN auto_flag_reason VARCHAR(255)",
                "is_active": "ALTER TABLE reading_passages ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
            },
            "lesson_progress": {
                "skipped_questions": "ALTER TABLE lesson_progress ADD COLUMN skipped_questions INTEGER NOT NULL DEFAULT 0",
                "retry_questions": "ALTER TABLE lesson_progress ADD COLUMN retry_questions INTEGER NOT NULL DEFAULT 0",
                "support_tool_usage_count": "ALTER TABLE lesson_progress ADD COLUMN support_tool_usage_count INTEGER NOT NULL DEFAULT 0",
                "support_tool_penalty_points": "ALTER TABLE lesson_progress ADD COLUMN support_tool_penalty_points FLOAT NOT NULL DEFAULT 0",
            },
            "audit_logs": {
                "prev_hash": "ALTER TABLE audit_logs ADD COLUMN prev_hash VARCHAR(64)",
                "event_hash": "ALTER TABLE audit_logs ADD COLUMN event_hash VARCHAR(64)",
            },
            "users": {
                "organization_name": "ALTER TABLE users ADD COLUMN organization_name VARCHAR(120)",
                "organization_id": "ALTER TABLE users ADD COLUMN organization_id INTEGER",
                "teacher_id": "ALTER TABLE users ADD COLUMN teacher_id INTEGER",
                "managed_by_user_id": "ALTER TABLE users ADD COLUMN managed_by_user_id INTEGER",
                "father_name": "ALTER TABLE users ADD COLUMN father_name VARCHAR(120)",
                "address": "ALTER TABLE users ADD COLUMN address TEXT",
                "coin_balance": "ALTER TABLE users ADD COLUMN coin_balance INTEGER NOT NULL DEFAULT 0",
                "lifetime_coins": "ALTER TABLE users ADD COLUMN lifetime_coins INTEGER NOT NULL DEFAULT 0",
                "speaking_sessions_completed": "ALTER TABLE users ADD COLUMN speaking_sessions_completed INTEGER NOT NULL DEFAULT 0",
                "speaking_fast_submit_flags": "ALTER TABLE users ADD COLUMN speaking_fast_submit_flags INTEGER NOT NULL DEFAULT 0",
                "longest_learning_streak": "ALTER TABLE users ADD COLUMN longest_learning_streak INTEGER NOT NULL DEFAULT 0",
                "show_on_leaderboard": "ALTER TABLE users ADD COLUMN show_on_leaderboard BOOLEAN NOT NULL DEFAULT 1",
            },
            "user_preferences": {
                "auto_play_question": "ALTER TABLE user_preferences ADD COLUMN auto_play_question BOOLEAN NOT NULL DEFAULT 1",
                "auto_start_listening": "ALTER TABLE user_preferences ADD COLUMN auto_start_listening BOOLEAN NOT NULL DEFAULT 1",
                "question_beep_enabled": "ALTER TABLE user_preferences ADD COLUMN question_beep_enabled BOOLEAN NOT NULL DEFAULT 1",
                "voice_gender": "ALTER TABLE user_preferences ADD COLUMN voice_gender VARCHAR(20) NOT NULL DEFAULT 'female'",
                "voice_pitch": "ALTER TABLE user_preferences ADD COLUMN voice_pitch FLOAT NOT NULL DEFAULT 1.0",
                "playback_speed": "ALTER TABLE user_preferences ADD COLUMN playback_speed FLOAT NOT NULL DEFAULT 1.0",
                "allow_ml_training": "ALTER TABLE user_preferences ADD COLUMN allow_ml_training BOOLEAN NOT NULL DEFAULT 0",
                "translation_support_language_code": "ALTER TABLE user_preferences ADD COLUMN translation_support_language_code VARCHAR(20) NOT NULL DEFAULT 'en'",
                "use_native_language_support": "ALTER TABLE user_preferences ADD COLUMN use_native_language_support BOOLEAN NOT NULL DEFAULT 1",
            },
            "user_sessions": {
                "country": "ALTER TABLE user_sessions ADD COLUMN country VARCHAR(80)",
                "city": "ALTER TABLE user_sessions ADD COLUMN city VARCHAR(80)",
            },
            "translation_providers": {
                "credits_remaining": "ALTER TABLE translation_providers ADD COLUMN credits_remaining FLOAT",
                "credit_unit": "ALTER TABLE translation_providers ADD COLUMN credit_unit VARCHAR(30) NOT NULL DEFAULT 'credits'",
                "per_request_cost": "ALTER TABLE translation_providers ADD COLUMN per_request_cost FLOAT NOT NULL DEFAULT 1.0",
                "supports_live_credit_check": "ALTER TABLE translation_providers ADD COLUMN supports_live_credit_check BOOLEAN NOT NULL DEFAULT 0",
                "last_credit_sync_at": "ALTER TABLE translation_providers ADD COLUMN last_credit_sync_at DATETIME",
                "last_error": "ALTER TABLE translation_providers ADD COLUMN last_error VARCHAR(255)",
                "source_language_code": "ALTER TABLE translation_providers ADD COLUMN source_language_code VARCHAR(16) NOT NULL DEFAULT 'en'",
            },
            "reading_providers": {
                "official_website": "ALTER TABLE reading_providers ADD COLUMN official_website VARCHAR(255)",
                "usage_scope": "ALTER TABLE reading_providers ADD COLUMN usage_scope VARCHAR(60)",
                "pricing_note": "ALTER TABLE reading_providers ADD COLUMN pricing_note VARCHAR(255)",
                "notes": "ALTER TABLE reading_providers ADD COLUMN notes TEXT",
                "fallback_provider_id": "ALTER TABLE reading_providers ADD COLUMN fallback_provider_id INTEGER",
            },
            "reading_questions": {
                "prompt_snapshot": "ALTER TABLE reading_questions ADD COLUMN prompt_snapshot TEXT",
                "options_json": "ALTER TABLE reading_questions ADD COLUMN options_json TEXT",
                "correct_answer": "ALTER TABLE reading_questions ADD COLUMN correct_answer TEXT",
                "explanation": "ALTER TABLE reading_questions ADD COLUMN explanation TEXT",
                "source_sentence": "ALTER TABLE reading_questions ADD COLUMN source_sentence TEXT",
                "provider_id": "ALTER TABLE reading_questions ADD COLUMN provider_id INTEGER",
                "provider_name_snapshot": "ALTER TABLE reading_questions ADD COLUMN provider_name_snapshot VARCHAR(160)",
                "status": "ALTER TABLE reading_questions ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'",
                "review_notes": "ALTER TABLE reading_questions ADD COLUMN review_notes TEXT",
                "reviewed_at": "ALTER TABLE reading_questions ADD COLUMN reviewed_at DATETIME",
                "reviewed_by_id": "ALTER TABLE reading_questions ADD COLUMN reviewed_by_id INTEGER",
                "confidence_score": "ALTER TABLE reading_questions ADD COLUMN confidence_score FLOAT",
                "auto_flag_reason": "ALTER TABLE reading_questions ADD COLUMN auto_flag_reason VARCHAR(255)",
                "is_active": "ALTER TABLE reading_questions ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
            },
            "speaking_prompts": {
                "target_duration_seconds": "ALTER TABLE speaking_prompts ADD COLUMN target_duration_seconds INTEGER",
                "min_duration_seconds": "ALTER TABLE speaking_prompts ADD COLUMN min_duration_seconds INTEGER",
                "max_duration_seconds": "ALTER TABLE speaking_prompts ADD COLUMN max_duration_seconds INTEGER",
            },
            "speaking_sessions": {
                "course_id": "ALTER TABLE speaking_sessions ADD COLUMN course_id INTEGER",
                "transcript_text": "ALTER TABLE speaking_sessions ADD COLUMN transcript_text TEXT",
                "transcript_source": "ALTER TABLE speaking_sessions ADD COLUMN transcript_source VARCHAR(30) DEFAULT 'manual'",
                "audio_file_path": "ALTER TABLE speaking_sessions ADD COLUMN audio_file_path VARCHAR(255)",
                "audio_original_name": "ALTER TABLE speaking_sessions ADD COLUMN audio_original_name VARCHAR(255)",
                "latest_word_count": "ALTER TABLE speaking_sessions ADD COLUMN latest_word_count INTEGER NOT NULL DEFAULT 0",
                "latest_char_count": "ALTER TABLE speaking_sessions ADD COLUMN latest_char_count INTEGER NOT NULL DEFAULT 0",
                "submit_count": "ALTER TABLE speaking_sessions ADD COLUMN submit_count INTEGER NOT NULL DEFAULT 0",
                "result_summary": "ALTER TABLE speaking_sessions ADD COLUMN result_summary TEXT",
                "last_submitted_at": "ALTER TABLE speaking_sessions ADD COLUMN last_submitted_at DATETIME",
                "evaluation_score": "ALTER TABLE speaking_sessions ADD COLUMN evaluation_score FLOAT",
                "relevance_score": "ALTER TABLE speaking_sessions ADD COLUMN relevance_score FLOAT",
                "is_relevant": "ALTER TABLE speaking_sessions ADD COLUMN is_relevant BOOLEAN NOT NULL DEFAULT 0",
                "feedback_text": "ALTER TABLE speaking_sessions ADD COLUMN feedback_text TEXT",
                "recommended_next_step": "ALTER TABLE speaking_sessions ADD COLUMN recommended_next_step VARCHAR(30) DEFAULT 'practice_more'",
                "retry_count": "ALTER TABLE speaking_sessions ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
                "max_retry_count": "ALTER TABLE speaking_sessions ADD COLUMN max_retry_count INTEGER NOT NULL DEFAULT 2",
                "completion_tracked": "ALTER TABLE speaking_sessions ADD COLUMN completion_tracked BOOLEAN NOT NULL DEFAULT 0",
                "coins_awarded": "ALTER TABLE speaking_sessions ADD COLUMN coins_awarded INTEGER NOT NULL DEFAULT 0",
                "is_fast_submit_flagged": "ALTER TABLE speaking_sessions ADD COLUMN is_fast_submit_flagged BOOLEAN NOT NULL DEFAULT 0",
                "fast_submit_reason": "ALTER TABLE speaking_sessions ADD COLUMN fast_submit_reason VARCHAR(255)",
            },
            "speaking_attempts": {
                "score": "ALTER TABLE speaking_attempts ADD COLUMN score FLOAT",
                "relevance_score": "ALTER TABLE speaking_attempts ADD COLUMN relevance_score FLOAT",
                "is_relevant": "ALTER TABLE speaking_attempts ADD COLUMN is_relevant BOOLEAN NOT NULL DEFAULT 0",
                "feedback_text": "ALTER TABLE speaking_attempts ADD COLUMN feedback_text TEXT",
                "recommended_next_step": "ALTER TABLE speaking_attempts ADD COLUMN recommended_next_step VARCHAR(30)",
                "retry_recommended": "ALTER TABLE speaking_attempts ADD COLUMN retry_recommended BOOLEAN NOT NULL DEFAULT 0",
            },
            "speaking_providers": {
                "official_website": "ALTER TABLE speaking_providers ADD COLUMN official_website VARCHAR(255)",
                "usage_scope": "ALTER TABLE speaking_providers ADD COLUMN usage_scope VARCHAR(60)",
                "pricing_note": "ALTER TABLE speaking_providers ADD COLUMN pricing_note VARCHAR(255)",
                "notes": "ALTER TABLE speaking_providers ADD COLUMN notes TEXT",
                "fallback_provider_id": "ALTER TABLE speaking_providers ADD COLUMN fallback_provider_id INTEGER",
            },
            "writing_topics": {
                "course_id": "ALTER TABLE writing_topics ADD COLUMN course_id INTEGER",
                "course_level_number": "ALTER TABLE writing_topics ADD COLUMN course_level_number INTEGER",
                "description": "ALTER TABLE writing_topics ADD COLUMN description TEXT",
                "display_order": "ALTER TABLE writing_topics ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0",
                "is_published": "ALTER TABLE writing_topics ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT 1",
                "category": "ALTER TABLE writing_topics ADD COLUMN category VARCHAR(120)",
            },
            "writing_tasks": {
                "course_id": "ALTER TABLE writing_tasks ADD COLUMN course_id INTEGER",
                "course_level_number": "ALTER TABLE writing_tasks ADD COLUMN course_level_number INTEGER",
                "topic_title_snapshot": "ALTER TABLE writing_tasks ADD COLUMN topic_title_snapshot VARCHAR(160)",
                "language_code": "ALTER TABLE writing_tasks ADD COLUMN language_code VARCHAR(16) NOT NULL DEFAULT 'en'",
                "display_order": "ALTER TABLE writing_tasks ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0",
                "is_published": "ALTER TABLE writing_tasks ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT 1",
                "max_words": "ALTER TABLE writing_tasks ADD COLUMN max_words INTEGER",
            },
            "writing_submissions": {
                "course_id": "ALTER TABLE writing_submissions ADD COLUMN course_id INTEGER",
                "topic_id": "ALTER TABLE writing_submissions ADD COLUMN topic_id INTEGER",
                "char_count": "ALTER TABLE writing_submissions ADD COLUMN char_count INTEGER NOT NULL DEFAULT 0",
                "paragraph_count": "ALTER TABLE writing_submissions ADD COLUMN paragraph_count INTEGER NOT NULL DEFAULT 0",
                "sentence_count": "ALTER TABLE writing_submissions ADD COLUMN sentence_count INTEGER NOT NULL DEFAULT 0",
                "feedback_text": "ALTER TABLE writing_submissions ADD COLUMN feedback_text TEXT",
                "evaluation_summary": "ALTER TABLE writing_submissions ADD COLUMN evaluation_summary TEXT",
                "evaluation_payload": "ALTER TABLE writing_submissions ADD COLUMN evaluation_payload TEXT",
                "status": "ALTER TABLE writing_submissions ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'submitted'",
            },
            "student_daily_activity": {
                "accuracy_total": "ALTER TABLE student_daily_activity ADD COLUMN accuracy_total FLOAT NOT NULL DEFAULT 0",
                "accuracy_samples": "ALTER TABLE student_daily_activity ADD COLUMN accuracy_samples INTEGER NOT NULL DEFAULT 0",
                "speaking_completed_sessions": "ALTER TABLE student_daily_activity ADD COLUMN speaking_completed_sessions INTEGER NOT NULL DEFAULT 0",
                "coins_earned": "ALTER TABLE student_daily_activity ADD COLUMN coins_earned INTEGER NOT NULL DEFAULT 0",
            },
        }.items():
            if not _table_exists(inspector, table_name):
                continue
            cols = _column_names(inspector, table_name)
            for col, sql in adds.items():
                if col not in cols:
                    conn.execute(text(sql))

        if not _table_exists(inspector, "student_reward_transactions"):
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS student_reward_transactions (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    speaking_session_id INTEGER,
                    source_type VARCHAR(40) NOT NULL DEFAULT 'speaking_completion',
                    coins INTEGER NOT NULL DEFAULT 0,
                    title VARCHAR(120) NOT NULL DEFAULT 'Speaking reward',
                    description TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            inspector = inspect(engine)

        if _table_exists(inspector, "speaking_providers"):
            conn.execute(text("""
                INSERT OR IGNORE INTO speaking_providers
                (id, name, provider_kind, provider_type, is_enabled, is_default, supports_test, last_test_status, last_test_message, created_at, updated_at) VALUES
                (1, 'Default STT Provider', 'stt', 'mock', 0, 1, 1, 'idle', 'Ready for future API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 'Default Evaluation Provider', 'evaluation', 'mock', 1, 1, 1, 'idle', 'Ready for future API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 'Default Pronunciation Provider', 'pronunciation', 'mock', 0, 1, 1, 'idle', 'Ready for future API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))

        if _table_exists(inspector, "reading_providers"):
            conn.execute(text("""
                INSERT OR IGNORE INTO reading_providers
                (id, name, provider_kind, provider_type, is_enabled, is_default, supports_test, last_test_status, last_test_message, created_at, updated_at) VALUES
                (1, 'Default Passage Provider', 'passage', 'mock', 1, 1, 1, 'idle', 'Ready for reading API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 'Default Question Provider', 'question', 'mock', 0, 1, 1, 'idle', 'Ready for reading API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 'Default Translation Provider', 'translation', 'mock', 0, 1, 1, 'idle', 'Ready for reading API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (4, 'Default Evaluation Provider', 'evaluation', 'mock', 0, 1, 1, 'idle', 'Ready for reading API configuration.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))

        if _table_exists(inspector, "reading_prompt_configs"):
            conn.execute(text("""
                INSERT OR IGNORE INTO reading_prompt_configs
                (task_type, title, prompt_text, is_active, created_at, updated_at) VALUES
                ('passage', 'Passage Generation Prompt', 'Generate one reading passage for the topic {{topic}} at {{level}} level. Keep the vocabulary suitable for the level, stay factual, and return clean paragraph text only.', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('question', 'Question Generation Prompt', 'Using the passage below, generate MCQ, fill in the blanks, and true/false questions. Respect the requested counts and return structured JSON with answers.', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('translation', 'Translation / Synonym Prompt', 'Given a selected word from the reading passage, provide a simple meaning, one close synonym, and a learner-friendly translation in the requested language.', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('evaluation', 'Answer Evaluation Prompt', 'Check the learner answer against the reading question and expected answer. Return correct/incorrect, a short reason, and a confidence score from 0 to 1.', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))


        if _table_exists(inspector, "ai_rule_configs"):
            conn.execute(text("""
                INSERT OR IGNORE INTO ai_rule_configs
                (track_key, is_enabled, rule_text, guardrails_text, scoring_notes, output_format, strictness, min_length, require_explanations, off_topic_block, status, created_at, updated_at) VALUES
                ('speaking', 1, 'Evaluate only the spoken answer. Score pronunciation, fluency, grammar, sentence making, and relevance. Keep feedback learner-friendly.', 'Flag very short answers, repeated filler words, and clearly off-topic responses.', 'Explain the main mistake clearly and suggest the next retry action.', 'Return strengths, mistakes, improvement tips, and a retry recommendation.', 3, 12, 1, 1, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('writing', 1, 'Evaluate grammar, vocabulary, coherence, and task response. Respect task instructions and word-range guidance.', 'Penalize copied, extremely short, or clearly off-topic submissions.', 'Always explain why a line or sentence is weak and how to improve it.', 'Return band-style scores, strengths, weaknesses, and line-level suggestions when possible.', 3, 40, 1, 1, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('reading', 1, 'Check student answers against the question and expected answer. Prefer accuracy and simple explanations.', 'Avoid accepting unsupported answers. Keep explanations short and classroom-ready.', 'When the answer is wrong, explain the correct reason from the passage.', 'Return correct or incorrect, score, and a short explanation.', 2, 0, 1, 0, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('listening', 1, 'Review listening content for clarity, answerability, caption quality, and lesson readiness.', 'Keep poor captions or unclear prompts in pending review.', 'Give one direct reason for approval, rejection, or pending.', 'Return decision, confidence, and review reason.', 3, 0, 1, 0, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))
        provider_runtime_adds = {
            "translation_providers": {
                "is_default": "ALTER TABLE translation_providers ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 1",
                "fallback_provider_id": "ALTER TABLE translation_providers ADD COLUMN fallback_provider_id INTEGER",
                "priority": "ALTER TABLE translation_providers ADD COLUMN priority INTEGER NOT NULL DEFAULT 100",
                "timeout_seconds": "ALTER TABLE translation_providers ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 30",
                "requests_per_minute": "ALTER TABLE translation_providers ADD COLUMN requests_per_minute INTEGER",
                "tokens_per_minute": "ALTER TABLE translation_providers ADD COLUMN tokens_per_minute INTEGER",
                "cost_per_1k_input": "ALTER TABLE translation_providers ADD COLUMN cost_per_1k_input FLOAT NOT NULL DEFAULT 0",
                "cost_per_1k_output": "ALTER TABLE translation_providers ADD COLUMN cost_per_1k_output FLOAT NOT NULL DEFAULT 0",
                "total_requests": "ALTER TABLE translation_providers ADD COLUMN total_requests INTEGER NOT NULL DEFAULT 0",
                "total_failures": "ALTER TABLE translation_providers ADD COLUMN total_failures INTEGER NOT NULL DEFAULT 0",
                "consecutive_failures": "ALTER TABLE translation_providers ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0",
                "circuit_state": "ALTER TABLE translation_providers ADD COLUMN circuit_state VARCHAR(20) NOT NULL DEFAULT 'closed'",
                "circuit_open_until": "ALTER TABLE translation_providers ADD COLUMN circuit_open_until DATETIME",
                "last_success_at": "ALTER TABLE translation_providers ADD COLUMN last_success_at DATETIME",
                "last_failure_at": "ALTER TABLE translation_providers ADD COLUMN last_failure_at DATETIME",
            },
            "speaking_providers": {
                "priority": "ALTER TABLE speaking_providers ADD COLUMN priority INTEGER NOT NULL DEFAULT 100",
                "timeout_seconds": "ALTER TABLE speaking_providers ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 30",
                "requests_per_minute": "ALTER TABLE speaking_providers ADD COLUMN requests_per_minute INTEGER",
                "tokens_per_minute": "ALTER TABLE speaking_providers ADD COLUMN tokens_per_minute INTEGER",
                "cost_per_1k_input": "ALTER TABLE speaking_providers ADD COLUMN cost_per_1k_input FLOAT NOT NULL DEFAULT 0",
                "cost_per_1k_output": "ALTER TABLE speaking_providers ADD COLUMN cost_per_1k_output FLOAT NOT NULL DEFAULT 0",
                "total_requests": "ALTER TABLE speaking_providers ADD COLUMN total_requests INTEGER NOT NULL DEFAULT 0",
                "total_failures": "ALTER TABLE speaking_providers ADD COLUMN total_failures INTEGER NOT NULL DEFAULT 0",
                "consecutive_failures": "ALTER TABLE speaking_providers ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0",
                "circuit_state": "ALTER TABLE speaking_providers ADD COLUMN circuit_state VARCHAR(20) NOT NULL DEFAULT 'closed'",
                "circuit_open_until": "ALTER TABLE speaking_providers ADD COLUMN circuit_open_until DATETIME",
                "last_success_at": "ALTER TABLE speaking_providers ADD COLUMN last_success_at DATETIME",
                "last_failure_at": "ALTER TABLE speaking_providers ADD COLUMN last_failure_at DATETIME",
            },
            "reading_providers": {
                "priority": "ALTER TABLE reading_providers ADD COLUMN priority INTEGER NOT NULL DEFAULT 100",
                "timeout_seconds": "ALTER TABLE reading_providers ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 30",
                "requests_per_minute": "ALTER TABLE reading_providers ADD COLUMN requests_per_minute INTEGER",
                "tokens_per_minute": "ALTER TABLE reading_providers ADD COLUMN tokens_per_minute INTEGER",
                "cost_per_1k_input": "ALTER TABLE reading_providers ADD COLUMN cost_per_1k_input FLOAT NOT NULL DEFAULT 0",
                "cost_per_1k_output": "ALTER TABLE reading_providers ADD COLUMN cost_per_1k_output FLOAT NOT NULL DEFAULT 0",
                "total_requests": "ALTER TABLE reading_providers ADD COLUMN total_requests INTEGER NOT NULL DEFAULT 0",
                "total_failures": "ALTER TABLE reading_providers ADD COLUMN total_failures INTEGER NOT NULL DEFAULT 0",
                "consecutive_failures": "ALTER TABLE reading_providers ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0",
                "circuit_state": "ALTER TABLE reading_providers ADD COLUMN circuit_state VARCHAR(20) NOT NULL DEFAULT 'closed'",
                "circuit_open_until": "ALTER TABLE reading_providers ADD COLUMN circuit_open_until DATETIME",
                "last_success_at": "ALTER TABLE reading_providers ADD COLUMN last_success_at DATETIME",
                "last_failure_at": "ALTER TABLE reading_providers ADD COLUMN last_failure_at DATETIME",
            },
            "security_policies": {
                "ai_daily_request_limit": "ALTER TABLE security_policies ADD COLUMN ai_daily_request_limit INTEGER NOT NULL DEFAULT 200",
                "ai_daily_token_limit": "ALTER TABLE security_policies ADD COLUMN ai_daily_token_limit INTEGER NOT NULL DEFAULT 200000",
                "translation_daily_limit": "ALTER TABLE security_policies ADD COLUMN translation_daily_limit INTEGER NOT NULL DEFAULT 100",
                "tts_daily_character_limit": "ALTER TABLE security_policies ADD COLUMN tts_daily_character_limit INTEGER NOT NULL DEFAULT 50000",
                "speech_daily_seconds_limit": "ALTER TABLE security_policies ADD COLUMN speech_daily_seconds_limit INTEGER NOT NULL DEFAULT 3600",
                "ai_circuit_breaker_threshold": "ALTER TABLE security_policies ADD COLUMN ai_circuit_breaker_threshold INTEGER NOT NULL DEFAULT 3",
                "ai_circuit_breaker_minutes": "ALTER TABLE security_policies ADD COLUMN ai_circuit_breaker_minutes INTEGER NOT NULL DEFAULT 10",
                "translation_cache_ttl_seconds": "ALTER TABLE security_policies ADD COLUMN translation_cache_ttl_seconds INTEGER NOT NULL DEFAULT 2592000",
            },
        }
        for table_name, add_map in provider_runtime_adds.items():
            if _table_exists(inspector, table_name):
                cols = _column_names(inspector, table_name)
                for col_name, sql in add_map.items():
                    if col_name not in cols:
                        conn.execute(text(sql))
                inspector = inspect(engine)


        if _table_exists(inspector, "roles"):
            conn.execute(text("INSERT OR IGNORE INTO roles (code, name, scope, created_at) VALUES ('SUB_ADMIN', 'Sub Admin', 'tenant', CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT OR IGNORE INTO roles (code, name, scope, created_at) VALUES ('TEACHER', 'Teacher', 'tenant', CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT OR IGNORE INTO roles (code, name, scope, created_at) VALUES ('PARENT', 'Parent', 'tenant', CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT OR IGNORE INTO roles (code, name, scope, created_at) VALUES ('EDITOR', 'Editor', 'tenant', CURRENT_TIMESTAMP)"))
