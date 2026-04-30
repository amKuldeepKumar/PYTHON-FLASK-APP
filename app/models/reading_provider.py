from datetime import datetime

from ..extensions import db


class ReadingProvider(db.Model):
    __tablename__ = "reading_providers"

    KIND_PASSAGE = "passage"
    KIND_QUESTION = "question"
    KIND_TRANSLATION = "translation"
    KIND_EVALUATION = "evaluation"
    KIND_PLAGIARISM = "plagiarism"

    TYPE_MOCK = "mock"
    TYPE_OPENAI_COMPATIBLE = "openai_compatible"
    TYPE_GOOGLE = "google"
    TYPE_AZURE = "azure"
    TYPE_GEMINI = "gemini"
    TYPE_ANTHROPIC = "anthropic"
    TYPE_CUSTOM = "custom"

    USAGE_PASSAGE_GENERATION = "reading_passage_generation"
    USAGE_QUESTION_GENERATION = "reading_question_generation"
    USAGE_WORD_TRANSLATION = "reading_word_translation"
    USAGE_ANSWER_EVALUATION = "reading_answer_evaluation"
    USAGE_PLAGIARISM_CHECK = "writing_plagiarism_check"

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
    fallback_provider_id = db.Column(db.Integer, db.ForeignKey("reading_providers.id"), nullable=True)
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

    fallback_provider = db.relationship("ReadingProvider", remote_side=[id], uselist=False)

    @property
    def provider_label(self) -> str:
        labels = {
            self.TYPE_MOCK: "Mock / Manual",
            self.TYPE_OPENAI_COMPATIBLE: "OpenAI Compatible",
            self.TYPE_GOOGLE: "Google",
            self.TYPE_AZURE: "Azure",
            self.TYPE_GEMINI: "Gemini",
            self.TYPE_ANTHROPIC: "Anthropic",
            self.TYPE_CUSTOM: "Custom",
        }
        return labels.get(self.provider_type, (self.provider_type or "Unknown").replace("_", " ").title())

    @property
    def kind_label(self) -> str:
        return {
            self.KIND_PASSAGE: "Passage",
            self.KIND_QUESTION: "Question",
            self.KIND_TRANSLATION: "Translation / Synonym",
            self.KIND_EVALUATION: "Answer Evaluation",
            self.KIND_PLAGIARISM: "Plagiarism Detection",
        }.get(self.provider_kind, (self.provider_kind or "Provider").replace("_", " ").title())

    @property
    def usage_scope_label(self) -> str:
        labels = {
            self.USAGE_PASSAGE_GENERATION: "Reading passage generation",
            self.USAGE_QUESTION_GENERATION: "Reading question generation",
            self.USAGE_WORD_TRANSLATION: "Word translation / synonym",
            self.USAGE_ANSWER_EVALUATION: "Reading answer evaluation",
            self.USAGE_PLAGIARISM_CHECK: "Writing plagiarism check",
        }
        return labels.get(self.usage_scope, "Not mapped")
