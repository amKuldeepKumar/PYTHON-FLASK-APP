from datetime import datetime

from ..extensions import db


class SpeakingProvider(db.Model):
    __tablename__ = "speaking_providers"

    KIND_STT = "stt"
    KIND_EVALUATION = "evaluation"
    KIND_PRONUNCIATION = "pronunciation"
    KIND_TTS = "tts"

    TYPE_MOCK = "mock"
    TYPE_OPENAI_COMPATIBLE = "openai_compatible"
    TYPE_GOOGLE = "google_speech"
    TYPE_AZURE = "azure_speech"
    TYPE_DEEPGRAM = "deepgram"
    TYPE_ELEVENLABS = "elevenlabs"
    TYPE_CUSTOM = "custom"

    USAGE_STT_MIC = "stt_mic_input"
    USAGE_STT_UPLOAD = "stt_audio_upload"
    USAGE_EVAL_SPEAKING = "evaluation_speaking_scoring"
    USAGE_EVAL_FEEDBACK = "evaluation_feedback_generation"
    USAGE_PRONUNCIATION_SCORING = "pronunciation_scoring"
    USAGE_PRONUNCIATION_ACCENT = "pronunciation_accent_check"
    USAGE_TTS_LESSON = "tts_lesson_playback"
    USAGE_TTS_WELCOME = "tts_welcome_voice"
    USAGE_TTS_MULTILINGUAL = "tts_multilingual_voice"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    provider_kind = db.Column(db.String(30), nullable=False, index=True)
    provider_type = db.Column(db.String(40), nullable=False, default=TYPE_MOCK)
    api_key = db.Column(db.Text, nullable=True)
    api_base_url = db.Column(db.String(255), nullable=True)
    official_website = db.Column(db.String(255), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    config_json = db.Column(db.Text, nullable=True)
    usage_scope = db.Column(db.String(60), nullable=True, index=True)
    pricing_note = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    fallback_provider_id = db.Column(db.Integer, db.ForeignKey("speaking_providers.id"), nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    supports_test = db.Column(db.Boolean, nullable=False, default=True)
    priority = db.Column(db.Integer, nullable=False, default=100, index=True)
    timeout_seconds = db.Column(db.Integer, nullable=False, default=30)
    requests_per_minute = db.Column(db.Integer, nullable=True)
    tokens_per_minute = db.Column(db.Integer, nullable=True)
    cost_per_1k_input = db.Column(db.Float, nullable=False, default=0.0)
    cost_per_1k_output = db.Column(db.Float, nullable=False, default=0.0)
    total_requests = db.Column(db.Integer, nullable=False, default=0)
    total_failures = db.Column(db.Integer, nullable=False, default=0)
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)
    circuit_state = db.Column(db.String(20), nullable=False, default="closed")
    circuit_open_until = db.Column(db.DateTime, nullable=True)
    last_success_at = db.Column(db.DateTime, nullable=True)
    last_failure_at = db.Column(db.DateTime, nullable=True)
    last_test_status = db.Column(db.String(20), nullable=True)
    last_test_message = db.Column(db.String(255), nullable=True)
    last_tested_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    fallback_provider = db.relationship("SpeakingProvider", remote_side=[id], uselist=False)

    @property
    def provider_label(self) -> str:
        labels = {
            self.TYPE_MOCK: "Mock / Manual",
            self.TYPE_OPENAI_COMPATIBLE: "OpenAI Compatible",
            self.TYPE_GOOGLE: "Google Speech",
            self.TYPE_AZURE: "Azure Speech",
            self.TYPE_DEEPGRAM: "Deepgram",
            self.TYPE_ELEVENLABS: "ElevenLabs",
            self.TYPE_CUSTOM: "Custom",
        }
        return labels.get(self.provider_type, (self.provider_type or "Unknown").replace("_", " ").title())

    @property
    def kind_label(self) -> str:
        return {
            self.KIND_STT: "STT",
            self.KIND_EVALUATION: "Evaluation",
            self.KIND_PRONUNCIATION: "Pronunciation",
            self.KIND_TTS: "Text to Speech",
        }.get(self.provider_kind, (self.provider_kind or "Provider").title())

    @property
    def usage_scope_label(self) -> str:
        labels = {
            self.USAGE_STT_MIC: "Mic to text",
            self.USAGE_STT_UPLOAD: "Audio upload to text",
            self.USAGE_EVAL_SPEAKING: "Speaking score",
            self.USAGE_EVAL_FEEDBACK: "AI feedback",
            self.USAGE_PRONUNCIATION_SCORING: "Pronunciation score",
            self.USAGE_PRONUNCIATION_ACCENT: "Accent confidence",
            self.USAGE_TTS_LESSON: "Lesson playback voice",
            self.USAGE_TTS_WELCOME: "Welcome/dashboard voice",
            self.USAGE_TTS_MULTILINGUAL: "Multilingual voice output",
        }
        return labels.get(self.usage_scope, "Not mapped")
