from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DecimalField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional


LANGUAGE_CHOICES = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("pa", "Punjabi"),
]

TRACK_CHOICES = [
    ('speaking', 'Speaking'),
    ('interview', 'Interview Prep'),
    ('reading', 'Reading'),
    ('writing', 'Writing'),
    ('listening', 'Listening'),
]

DIFFICULTY_CHOICES = [
    ("", "Select"),
    ("basic", "Basic"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced"),
]

PROMPT_TYPE_CHOICES = [
    ("question", "General Question"),
    ("speaking", "Speaking"),
    ("reading", "Reading"),
    ("writing", "Writing"),
    ("listening", "Listening"),
    ("topic", "Topic Task"),
]

LESSON_TYPE_CHOICES = [
    ("guided", "Guided"),
    ("speaking", "Speaking"),
    ("reading", "Reading"),
    ("writing", "Writing"),
    ("listening", "Listening"),
    ("interview", "Interview"),
    ("topic", "Topic"),
]


class CourseForm(FlaskForm):
    title = StringField("Course Title", validators=[DataRequired(), Length(min=3, max=180)])
    slug = StringField("Slug", validators=[Optional(), Length(max=180)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    welcome_intro_script = TextAreaField("AI Welcome Script", validators=[Optional(), Length(max=6000)])
    learning_outcomes_script = TextAreaField("AI Learning Outcomes Script", validators=[Optional(), Length(max=6000)])

    language_code = SelectField("Language", choices=LANGUAGE_CHOICES, default="en")
    track_type = SelectField("Track", choices=TRACK_CHOICES, default="speaking")
    difficulty = SelectField("Difficulty", choices=DIFFICULTY_CHOICES, default="")
    currency_code = SelectField("Currency", choices=[("INR", "INR")], default="INR")
    max_level = IntegerField("Max Level", validators=[InputRequired(), NumberRange(min=1, max=999)], default=1)
    access_type = SelectField("Full Course Access", choices=[("free", "Free"), ("paid", "Paid")], default="free")
    allow_level_purchase = BooleanField("Allow Level Purchase", default=False)
    level_access_type = SelectField("Single Level Access", choices=[("free", "Free"), ("paid", "Paid")], default="free")

    base_price = DecimalField("Full Course Base Price", validators=[InputRequired(), NumberRange(min=0)], default=0, places=2)
    sale_price = DecimalField("Full Course Sale Price", validators=[Optional(), NumberRange(min=0)], places=2)
    level_price = DecimalField("Single Level Base Price", validators=[InputRequired(), NumberRange(min=0)], default=0, places=2)
    level_sale_price = DecimalField("Single Level Sale Price", validators=[Optional(), NumberRange(min=0)], places=2)

    level_title = StringField("First Level", validators=[Optional(), Length(max=150)], default="Level 1")
    lesson_title = StringField("First Lesson", validators=[Optional(), Length(max=180)], default="Lesson 1")
    lesson_type = SelectField("Lesson Type", choices=LESSON_TYPE_CHOICES, default="guided")
    explanation_text = TextAreaField("Lesson Explanation", validators=[Optional(), Length(max=5000)])
    grammar_formula = StringField("Starter Grammar Formula", validators=[Optional(), Length(max=180)])

    badge_title = StringField("Promo Badge Title", validators=[Optional(), Length(max=80)])
    badge_subtitle = StringField("Promo Badge Subtitle", validators=[Optional(), Length(max=120)])
    badge_template = SelectField(
        "Badge Template",
        choices=[("gradient", "Gradient"), ("gold", "Gold"), ("glass", "Glass"), ("ribbon", "Ribbon")],
        default="gradient",
    )
    badge_animation = SelectField(
        "Badge Animation",
        choices=[("none", "None"), ("pulse", "Pulse"), ("glow", "Glow"), ("shimmer", "Shimmer")],
        default="none",
    )

    is_published = BooleanField("Published", default=True)
    is_premium = BooleanField("Premium", default=False)
    submit = SubmitField("Create Course")


class LevelForm(FlaskForm):
    title = StringField("Level Title", validators=[DataRequired(), Length(min=2, max=150)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])
    sort_order = IntegerField("Sort Order", validators=[InputRequired(), NumberRange(min=1, max=9999)], default=1)
    submit = SubmitField("Save Level")


class ModuleForm(FlaskForm):
    level_id = SelectField("Level", coerce=int, choices=[], validators=[DataRequired()])
    title = StringField("Module Title", validators=[DataRequired(), Length(min=2, max=180)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])
    sort_order = IntegerField("Sort Order", validators=[InputRequired(), NumberRange(min=1, max=9999)], default=1)
    submit = SubmitField("Save Module")


class LessonForm(FlaskForm):
    level_id = SelectField("Level", coerce=int, choices=[], validators=[Optional()])
    module_id = SelectField("Module", coerce=int, choices=[], validators=[Optional()])
    title = StringField("Lesson Title", validators=[DataRequired(), Length(min=2, max=180)])
    slug = StringField("Slug", validators=[Optional(), Length(max=180)])
    lesson_type = SelectField("Lesson Type", choices=LESSON_TYPE_CHOICES, default="guided")
    explanation_text = TextAreaField("Explanation", validators=[Optional(), Length(max=5000)])
    explanation_tts_text = TextAreaField("TTS Text", validators=[Optional(), Length(max=5000)])
    estimated_minutes = IntegerField("Estimated Minutes", validators=[InputRequired(), NumberRange(min=1, max=300)], default=10)
    grammar_formula = StringField("Grammar Formula", validators=[Optional(), Length(max=180)])
    is_published = BooleanField("Published", default=True)
    submit = SubmitField("Save Lesson")


class ChapterForm(FlaskForm):
    lesson_id = SelectField("Lesson", coerce=int, choices=[], validators=[DataRequired()])
    title = StringField("Chapter Title", validators=[DataRequired(), Length(min=2, max=180)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])
    sort_order = IntegerField("Sort Order", validators=[InputRequired(), NumberRange(min=1, max=9999)], default=1)
    submit = SubmitField("Save Chapter")


class SubsectionForm(FlaskForm):
    chapter_id = SelectField("Chapter", coerce=int, choices=[], validators=[DataRequired()])
    title = StringField("Subsection Title", validators=[DataRequired(), Length(min=2, max=180)])
    grammar_formula = StringField("Grammar Formula", validators=[Optional(), Length(max=180)])
    grammar_tags = StringField("Grammar Tags", validators=[Optional(), Length(max=500)])
    hint_seed = TextAreaField("Hint Seed", validators=[Optional(), Length(max=3000)])
    sort_order = IntegerField("Sort Order", validators=[InputRequired(), NumberRange(min=1, max=9999)], default=1)
    submit = SubmitField("Save Subsection")


class QuestionForm(FlaskForm):
    subsection_id = SelectField("Subsection", coerce=int, choices=[], validators=[Optional()])
    title = StringField("Question Title", validators=[Optional(), Length(max=180)])
    prompt = TextAreaField("Prompt", validators=[DataRequired(), Length(min=3, max=10000)])
    image_url = StringField("Image URL / Static Path", validators=[Optional(), Length(max=255)])
    prompt_type = SelectField("Task Type", choices=PROMPT_TYPE_CHOICES, default="question")
    language_code = SelectField("Language", choices=LANGUAGE_CHOICES, default="en")
    hint_text = TextAreaField("Hint", validators=[Optional(), Length(max=5000)])
    model_answer = TextAreaField("Model Answer", validators=[Optional(), Length(max=8000)])
    evaluation_rubric = TextAreaField("Evaluation Rubric", validators=[Optional(), Length(max=5000)])
    expected_keywords = StringField("Expected Keywords", validators=[Optional(), Length(max=1000)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Question")


class QuestionUploadForm(FlaskForm):
    lesson_id = SelectField("Lesson", coerce=int, choices=[], validators=[DataRequired()])
    auto_split_size = IntegerField(
        "Questions per auto chapter",
        validators=[InputRequired(), NumberRange(min=1, max=100)],
        default=10,
    )
    upload = FileField(
        "CSV/TXT file",
        validators=[FileRequired(), FileAllowed(["csv", "txt"], "Only CSV or TXT files are allowed.")],
    )
    submit = SubmitField("Upload Questions")


class DeleteForm(FlaskForm):
    submit = SubmitField("Delete")


class StatusForm(FlaskForm):
    action = HiddenField("Action", validators=[DataRequired()])
    submit = SubmitField("Apply")
