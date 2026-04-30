from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    DecimalField,
    IntegerField,
    DateField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange

from ...models.user import Role


class AdminCreateForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=160)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField(
        "Role",
        choices=[
            (Role.ADMIN.value, "Principal / Admin"),
            (Role.SUB_ADMIN.value, "Sub Admin"),
            (Role.TEACHER.value, "Teacher"),
            (Role.SEO.value, "SEO"),
            (Role.ACCOUNTS.value, "Accounts"),
            (Role.SUPPORT.value, "Support"),
            (Role.EDITOR.value, "Editor"),
        ],
        default=Role.ADMIN.value,
    )
    organization_name = StringField("Institute Name", validators=[Optional(), Length(max=120)])
    parent_admin_id = SelectField("Parent Admin", coerce=int, choices=[(0, "Standalone admin / direct owner")], default=0)
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Create User")


class AdminEditForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=160)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField(
        "Role",
        choices=[
            (Role.ADMIN.value, "Principal / Admin"),
            (Role.SUB_ADMIN.value, "Sub Admin"),
            (Role.TEACHER.value, "Teacher"),
            (Role.SEO.value, "SEO"),
            (Role.ACCOUNTS.value, "Accounts"),
            (Role.SUPPORT.value, "Support"),
            (Role.EDITOR.value, "Editor"),
        ],
        default=Role.ADMIN.value,
    )
    organization_name = StringField("Institute Name", validators=[Optional(), Length(max=120)])
    parent_admin_id = SelectField("Parent Admin", coerce=int, choices=[(0, "Standalone admin / direct owner")], default=0)
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Changes")


class AdminPasswordForm(FlaskForm):
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("Change Password")


class StudentEditForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=160)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    current_level = SelectField(
        "Current Level",
        validators=[Optional()],
        choices=[("", "Select"), ("Beginner", "Beginner"), ("Intermediate", "Intermediate"), ("Advanced", "Advanced")],
    )
    target_exam = SelectField(
        "Target Exam",
        validators=[Optional()],
        choices=[("", "Select"), ("IELTS", "IELTS"), ("PTE", "PTE"), ("TOEFL", "TOEFL"), ("Spoken English", "Spoken English")],
    )
    organization_id = SelectField("Institute", coerce=int, choices=[(0, "Independent learner")], default=0)
    teacher_id = SelectField("Teacher", coerce=int, choices=[(0, "Not assigned yet")], default=0)
    managed_by_user_id = SelectField("Managed By", coerce=int, choices=[(0, "Auto / none")], default=0)
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Student")


class StudentPasswordForm(FlaskForm):
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("Change Password")


class AdminPermissionForm(FlaskForm):
    permissions = SelectMultipleField("Permissions", choices=[], validators=[Optional()])
    submit = SubmitField("Save Permissions")


class PageForm(FlaskForm):
    title = StringField("Page Title", validators=[DataRequired(), Length(min=2, max=180)])
    slug = StringField("Slug", validators=[DataRequired(), Length(min=2, max=180)])
    is_published = BooleanField("Published", default=True)
    is_in_menu = BooleanField("Show In Menu", default=True)
    menu_order = StringField("Menu Order", validators=[Optional(), Length(max=10)])

    lang_code = SelectField("Language", choices=[("en", "English"), ("hi", "Hindi"), ("pa", "Punjabi")], default="en")
    content_title = StringField("Content Title", validators=[Optional(), Length(max=255)])
    subtitle = StringField("Subtitle", validators=[Optional(), Length(max=255)])
    body_html = TextAreaField("Body HTML", validators=[Optional()])
    hero_title = StringField("Hero Title", validators=[Optional(), Length(max=255)])
    hero_subtitle = TextAreaField("Hero Subtitle", validators=[Optional()])
    hero_cta_text = StringField("Hero CTA Text", validators=[Optional(), Length(max=120)])
    hero_cta_url = StringField("Hero CTA URL", validators=[Optional(), Length(max=255)])
    hero_image = StringField("Hero Image", validators=[Optional(), Length(max=255)])

    meta_title = StringField("Meta Title", validators=[Optional(), Length(max=255)])
    meta_description = TextAreaField("Meta Description", validators=[Optional()])
    canonical_url = StringField("Canonical URL", validators=[Optional(), Length(max=255)])
    og_title = StringField("OG Title", validators=[Optional(), Length(max=255)])
    og_description = TextAreaField("OG Description", validators=[Optional()])
    og_image = StringField("OG Image", validators=[Optional(), Length(max=255)])
    twitter_card = SelectField(
        "Twitter Card",
        choices=[("summary_large_image", "summary_large_image"), ("summary", "summary")],
        default="summary_large_image",
    )

    sections_json = TextAreaField("Sections JSON", validators=[Optional()])
    faq_json = TextAreaField("FAQ JSON", validators=[Optional()])
    links_json = TextAreaField("Links JSON", validators=[Optional()])
    json_ld = TextAreaField("JSON-LD", validators=[Optional()])

    submit = SubmitField("Save Page")


class SeoSettingsForm(FlaskForm):
    site_name = StringField("Site Name", validators=[Optional(), Length(max=255)])
    default_meta_title = StringField("Default Meta Title", validators=[Optional(), Length(max=255)])
    default_meta_description = TextAreaField("Default Meta Description", validators=[Optional()])
    default_og_image = StringField("Default OG Image", validators=[Optional(), Length(max=255)])
    favicon_url = StringField("Favicon URL", validators=[Optional(), Length(max=255)])
    site_logo_url = StringField("Header Logo URL", validators=[Optional(), Length(max=255)])
    footer_logo_url = StringField("Footer Logo URL", validators=[Optional(), Length(max=255)])
    google_site_verification = StringField("Google Verification", validators=[Optional(), Length(max=255)])
    bing_site_verification = StringField("Bing Verification", validators=[Optional(), Length(max=255)])
    ga4_measurement_id = StringField("GA4 Measurement ID", validators=[Optional(), Length(max=255)])
    gtm_container_id = StringField("GTM Container ID", validators=[Optional(), Length(max=255)])
    head_html = TextAreaField("Head HTML", validators=[Optional()])
    body_start_html = TextAreaField("Body Start HTML", validators=[Optional()])
    body_end_html = TextAreaField("Body End HTML", validators=[Optional()])
    custom_json_ld = TextAreaField("Custom JSON-LD", validators=[Optional()])
    robots_policy = StringField("Robots Policy", validators=[Optional(), Length(max=255)])
    extra_robots_lines = TextAreaField("Extra Robots Lines", validators=[Optional()])
    robots_enabled = BooleanField("robots.txt Enabled", default=True)
    sitemap_enabled = BooleanField("Sitemap Enabled", default=True)
    sitemap_include_pages = BooleanField("Include CMS Pages", default=True)
    sitemap_include_public_reading = BooleanField("Include Public Reading", default=True)
    sitemap_include_courses = BooleanField("Include Courses", default=True)
    htaccess_enabled = BooleanField(".htaccess Builder Enabled", default=False)
    htaccess_force_https = BooleanField("Force HTTPS", default=True)
    htaccess_force_www = BooleanField("Force WWW", default=False)
    htaccess_enable_compression = BooleanField("Enable Compression", default=True)
    htaccess_enable_browser_cache = BooleanField("Enable Browser Cache", default=True)
    htaccess_custom_rules = TextAreaField("Custom .htaccess Rules", validators=[Optional()])
    header_announcement_enabled = BooleanField("Announcement Bar Enabled", default=False)
    header_announcement_text = StringField("Announcement Text", validators=[Optional(), Length(max=255)])
    header_cta_text = StringField("Header CTA Text", validators=[Optional(), Length(max=120)])
    header_cta_url = StringField("Header CTA URL", validators=[Optional(), Length(max=255)])
    header_links_json = TextAreaField("Header Links JSON", validators=[Optional()])
    footer_columns = IntegerField("Footer Columns", validators=[Optional(), NumberRange(min=1, max=6)])
    footer_widgets_json = TextAreaField("Footer Widgets JSON", validators=[Optional()])
    footer_copyright = StringField("Footer Copyright", validators=[Optional(), Length(max=255)])
    whatsapp_number = StringField("WhatsApp Number", validators=[Optional(), Length(max=30)])
    whatsapp_button_text = StringField("Button Text", validators=[Optional(), Length(max=80)])
    whatsapp_help_text = StringField("Small Helper Text", validators=[Optional(), Length(max=180)])
    whatsapp_default_category = StringField("Default Inquiry Category", validators=[Optional(), Length(max=120)])
    whatsapp_message = TextAreaField("Auto Message / Prefilled Message", validators=[Optional()])
    whatsapp_enabled = BooleanField("WhatsApp Enabled", default=False)
    whatsapp_show_on_public = BooleanField("Show Only For Public Visitors", default=True)
    whatsapp_click_tracking_enabled = BooleanField("Track WhatsApp Clicks", default=True)
    submit = SubmitField("Save SEO Settings")


class SecuritySettingsForm(FlaskForm):
    otp_mode = SelectField(
        "Global OTP Mode",
        choices=[("OFF", "OFF"), ("RISK", "RISK"), ("ALWAYS", "ALWAYS")],
        default="OFF",
        validators=[DataRequired()],
    )
    otp_mode_admin = SelectField(
        "Admin OTP Override",
        choices=[("", "Inherit"), ("OFF", "OFF"), ("RISK", "RISK"), ("ALWAYS", "ALWAYS")],
        default="",
        validators=[Optional()],
    )
    otp_mode_student = SelectField(
        "Student OTP Override",
        choices=[("", "Inherit"), ("OFF", "OFF"), ("RISK", "RISK"), ("ALWAYS", "ALWAYS")],
        default="",
        validators=[Optional()],
    )
    otp_mode_staff = SelectField(
        "Staff OTP Override",
        choices=[("", "Inherit"), ("OFF", "OFF"), ("RISK", "RISK"), ("ALWAYS", "ALWAYS")],
        default="",
        validators=[Optional()],
    )

    otp_ttl_minutes = IntegerField(
        "OTP TTL (minutes)",
        validators=[DataRequired(), NumberRange(min=1, max=120)],
        default=10,
    )

    otp_rate_limit = IntegerField(
        "OTP sends/hour",
        validators=[Optional(), NumberRange(min=1, max=50)],
        default=5,
    )
    otp_max_sends_per_hour = IntegerField(
        "OTP sends per hour",
        validators=[DataRequired(), NumberRange(min=1, max=50)],
        default=5,
    )

    otp_max_verify_attempts = IntegerField(
        "OTP verify attempts",
        validators=[DataRequired(), NumberRange(min=1, max=20)],
        default=5,
    )

    failed_login_threshold = IntegerField(
    "Failed login threshold",
    validators=[DataRequired(), NumberRange(min=1, max=20)],
    default=5,
    )

    failed_login_lock_minutes = IntegerField(
        "Lockout minutes",
        validators=[Optional(), NumberRange(min=1, max=1440)],
        default=15,
    )

    lockout_minutes = IntegerField(
        "Lockout minutes",
        validators=[DataRequired(), NumberRange(min=1, max=1440)],
        default=15,
    )

    suspicious_window_days = IntegerField(
        "Suspicious login window (days)",
        validators=[DataRequired(), NumberRange(min=1, max=365)],
        default=45,
    )

    trust_device_days = IntegerField(
        "Trusted device duration (days)",
        validators=[DataRequired(), NumberRange(min=1, max=365)],
        default=45,
    )

    enable_suspicious_login_detection = BooleanField(
        "Enable suspicious login detection",
        default=True,
    )

    api_rate_limit = StringField(
        "API rate limit",
        validators=[DataRequired(), Length(min=3, max=64)],
        default="30 per minute",
    )
    ai_rate_limit = StringField(
        "AI rate limit",
        validators=[DataRequired(), Length(min=3, max=64)],
        default="10 per minute",
    )

    max_upload_mb = IntegerField(
        "Max upload MB",
        validators=[DataRequired(), NumberRange(min=1, max=100)],
        default=5,
    )
    allowed_upload_extensions = StringField(
        "Allowed extensions",
        validators=[DataRequired(), Length(min=3, max=255)],
        default="jpg,jpeg,png,webp,pdf",
    )

    csp_report_only = BooleanField("CSP report-only", default=False)
    csp_report_uri = StringField(
        "CSP report URI",
        validators=[Optional(), Length(max=255)],
    )

    submit = SubmitField("Save Security Settings")


class CouponForm(FlaskForm):
    code = StringField("Coupon Code", validators=[DataRequired(), Length(min=3, max=64)])
    title = StringField("Title", validators=[Optional(), Length(max=140)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])

    discount_type = SelectField(
        "Discount Type",
        choices=[
            ("percentage", "Percentage"),
            ("fixed", "Fixed Amount"),
        ],
        default="percentage",
        validators=[DataRequired()],
    )

    discount_value = DecimalField(
        "Discount Value",
        places=2,
        default=0,
        validators=[DataRequired(), NumberRange(min=0)],
    )

    min_order_amount = DecimalField(
        "Minimum Purchase",
        places=2,
        default=0,
        validators=[Optional(), NumberRange(min=0)],
    )

    valid_from = DateField(
        "Valid From",
        format="%Y-%m-%d",
        validators=[Optional()],
    )

    valid_until = DateField(
        "Valid Until",
        format="%Y-%m-%d",
        validators=[Optional()],
    )

    usage_limit_total = IntegerField(
        "Usage Limit",
        validators=[Optional(), NumberRange(min=1)],
    )

    usage_limit_per_user = IntegerField(
        "Per User Limit",
        validators=[Optional(), NumberRange(min=1)],
    )

    course_id = SelectField(
        "Course",
        coerce=int,
        choices=[(0, "All Courses")],
        default=0,
        validators=[Optional()],
    )

    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Coupon")


class LanguageForm(FlaskForm):
    code = StringField("Language Code", validators=[DataRequired(), Length(min=2, max=16)])
    name = StringField("Language Name", validators=[DataRequired(), Length(min=2, max=80)])
    native_name = StringField("Native Name", validators=[Optional(), Length(max=80)])
    direction = SelectField("Direction", choices=[("ltr", "LTR"), ("rtl", "RTL")], default="ltr")
    is_enabled = BooleanField("Enabled", default=True)
    submit = SubmitField("Save Language")


class LanguageImportForm(FlaskForm):
    submit = SubmitField("Import Default Registry")


class TranslationProviderForm(FlaskForm):
    name = StringField("Provider Name", validators=[DataRequired(), Length(min=2, max=80)], default="Primary Translation Provider")
    provider_type = SelectField(
        "Provider Type",
        choices=[("mock", "Mock / Manual"), ("openai_compatible", "OpenAI Compatible")],
        default="mock",
        validators=[DataRequired()],
    )
    api_base_url = StringField("API Base URL", validators=[Optional(), Length(max=255)])
    api_key = PasswordField("API Key", validators=[Optional(), Length(max=500)])
    model_name = StringField("Model / Service Name", validators=[Optional(), Length(max=120)])
    source_language_code = StringField("Source Language Code", validators=[DataRequired(), Length(min=2, max=16)], default="en")
    credits_remaining = DecimalField("Credits Left", places=2, validators=[Optional(), NumberRange(min=0)], default=0)
    credit_unit = StringField("Credit Unit", validators=[DataRequired(), Length(min=2, max=30)], default="credits")
    per_request_cost = DecimalField("Cost per uncached translation", places=4, validators=[Optional(), NumberRange(min=0)], default=1)
    supports_live_credit_check = BooleanField("Supports live credit sync", default=False)
    is_enabled = BooleanField("Enabled", default=False)
    submit = SubmitField("Save Translation Provider")


class TranslationTestForm(FlaskForm):
    text = TextAreaField("English Source Text", validators=[DataRequired(), Length(min=2, max=5000)])
    target_language_code = SelectField("Target Language", choices=[], validators=[DataRequired()])
    submit = SubmitField("Translate & Cache")


class SpeakingProviderForm(FlaskForm):
    provider_id = IntegerField("Provider ID", validators=[Optional()])
    provider_kind = SelectField(
        "Registry",
        choices=[("stt", "STT"), ("evaluation", "Evaluation"), ("pronunciation", "Pronunciation"), ("tts", "Text to Speech")],
        validators=[DataRequired()],
        default="stt",
    )
    name = StringField("Provider Name", validators=[DataRequired(), Length(min=2, max=120)])
    provider_type = SelectField(
        "Provider Type",
        choices=[
            ("mock", "Mock / Manual"),
            ("openai_compatible", "OpenAI Compatible"),
            ("google_speech", "Google Speech"),
            ("azure_speech", "Azure Speech"),
            ("deepgram", "Deepgram"),
            ("elevenlabs", "ElevenLabs"),
            ("custom", "Custom"),
        ],
        validators=[DataRequired()],
        default="mock",
    )
    official_website = StringField("Official Website", validators=[Optional(), Length(max=255)])
    api_base_url = StringField("API Base URL", validators=[Optional(), Length(max=255)])
    api_key = PasswordField("API Key", validators=[Optional(), Length(max=500)])
    model_name = StringField("Model / Service Name", validators=[Optional(), Length(max=120)])
    usage_scope = SelectField(
        "Used In Project",
        choices=[
            ("", "Select placement"),
            ("stt_mic_input", "Mic to text"),
            ("stt_audio_upload", "Audio upload to text"),
            ("evaluation_speaking_scoring", "Speaking score"),
            ("evaluation_feedback_generation", "AI feedback"),
            ("pronunciation_scoring", "Pronunciation score"),
            ("pronunciation_accent_check", "Accent confidence"),
            ("tts_lesson_playback", "Lesson playback voice"),
            ("tts_welcome_voice", "Welcome voice"),
            ("tts_multilingual_voice", "Multilingual voice output"),
        ],
        validators=[Optional()],
        default="",
    )
    fallback_provider_id = SelectField("Fallback Provider", coerce=int, choices=[(0, "No fallback")], default=0)
    pricing_note = StringField("Pricing Note", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Internal Notes", validators=[Optional(), Length(max=5000)])
    config_json = TextAreaField("Advanced Config JSON", validators=[Optional(), Length(max=5000)])
    is_enabled = BooleanField("Enabled", default=False)
    supports_test = BooleanField("Show test button", default=True)
    submit = SubmitField("Save Provider")


class SpeakingProviderTestForm(FlaskForm):
    provider_id = IntegerField("Provider ID", validators=[DataRequired()])
    submit = SubmitField("Test Provider")



class ReadingProviderForm(FlaskForm):
    provider_id = IntegerField("Provider ID", validators=[Optional()])
    provider_kind = SelectField(
        "Registry",
        choices=[("passage", "Passage"), ("question", "Question"), ("translation", "Translation / Synonym"), ("evaluation", "Answer Evaluation"), ("plagiarism", "Plagiarism Detection")],
        validators=[DataRequired()],
        default="passage",
    )
    name = StringField("Provider Name", validators=[DataRequired(), Length(min=2, max=120)])
    provider_type = SelectField(
        "Provider Type",
        choices=[
            ("mock", "Mock / Manual"),
            ("openai_compatible", "OpenAI Compatible"),
            ("google", "Google"),
            ("azure", "Azure"),
            ("gemini", "Gemini"),
            ("anthropic", "Anthropic"),
            ("custom", "Custom"),
        ],
        validators=[DataRequired()],
        default="mock",
    )
    official_website = StringField("Official Website", validators=[Optional(), Length(max=255)])
    api_base_url = StringField("API Base URL", validators=[Optional(), Length(max=255)])
    api_key = PasswordField("API Key", validators=[Optional(), Length(max=500)])
    model_name = StringField("Model / Service Name", validators=[Optional(), Length(max=120)])
    usage_scope = SelectField(
        "Used In Project",
        choices=[
            ("", "Select placement"),
            ("reading_passage_generation", "Reading passage generation"),
            ("reading_question_generation", "Reading question generation"),
            ("reading_word_translation", "Word translation / synonym"),
            ("reading_answer_evaluation", "Reading answer evaluation"),
            ("writing_plagiarism_check", "Writing plagiarism check"),
        ],
        validators=[Optional()],
        default="",
    )
    fallback_provider_id = SelectField("Fallback Provider", coerce=int, choices=[(0, "No fallback")], default=0)
    pricing_note = StringField("Pricing Note", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Internal Notes", validators=[Optional(), Length(max=5000)])
    config_json = TextAreaField("Advanced Config JSON", validators=[Optional(), Length(max=5000)])
    is_enabled = BooleanField("Enabled", default=False)
    supports_test = BooleanField("Show test button", default=True)
    submit = SubmitField("Save Reading Provider")


class ReadingProviderTestForm(FlaskForm):
    provider_id = IntegerField("Provider ID", validators=[DataRequired()])
    submit = SubmitField("Test Provider")


class ReadingPromptConfigForm(FlaskForm):
    task_type = SelectField(
        "Prompt Task",
        choices=[("passage", "Passage"), ("question", "Question"), ("translation", "Translation / Synonym"), ("evaluation", "Answer Evaluation"), ("plagiarism", "Plagiarism Detection")],
        validators=[DataRequired()],
        default="passage",
    )
    title = StringField("Prompt Title", validators=[DataRequired(), Length(min=2, max=120)])
    prompt_text = TextAreaField("Prompt Text", validators=[DataRequired(), Length(min=10, max=10000)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Prompt Config")
