from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, BooleanField, SubmitField, PasswordField, DateField, TextAreaField
from wtforms.validators import Optional, Length, NumberRange, DataRequired, EqualTo


class ProfileForm(FlaskForm):
    first_name = StringField("First Name", validators=[Optional(), Length(max=80)])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=80)])
    father_name = StringField("Father Name", validators=[Optional(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    gender = SelectField(
        "Gender",
        validators=[Optional()],
        choices=[("", "Select"), ("Male", "Male"), ("Female", "Female"), ("Other", "Other"), ("Prefer not to say", "Prefer not to say")],
    )
    date_of_birth = DateField("Date of Birth", validators=[Optional()], format="%Y-%m-%d")
    country = StringField("Country", validators=[Optional(), Length(max=80)])
    state = StringField("State", validators=[Optional(), Length(max=80)])
    city = StringField("City", validators=[Optional(), Length(max=80)])
    address = TextAreaField("Full Address", validators=[Optional(), Length(max=1000)])
    organization_id = SelectField("Institute", coerce=int, validators=[Optional()], choices=[(0, "Independent Learner")])
    teacher_id = SelectField("Teacher", coerce=int, validators=[Optional()], choices=[(0, "Not assigned yet")])
    target_exam = SelectField("Target Exam", validators=[Optional()], choices=[("", "Select"), ("IELTS", "IELTS"), ("PTE", "PTE"), ("TOEFL", "TOEFL"), ("Spoken English", "Spoken English")])
    current_level = SelectField("Current Level", validators=[Optional()], choices=[("", "Select"), ("Beginner", "Beginner"), ("Intermediate", "Intermediate"), ("Advanced", "Advanced")])
    target_score = StringField("Target Score", validators=[Optional(), Length(max=40)])
    preferred_study_time = SelectField("Preferred Study Time", validators=[Optional()], choices=[("", "Select"), ("Early Morning", "Early Morning"), ("Morning", "Morning"), ("Afternoon", "Afternoon"), ("Evening", "Evening"), ("Late Night", "Late Night")])
    native_language = SelectField("Native Language", validators=[Optional()], choices=[])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=500)])
    study_goal = TextAreaField("Study Goal", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save Profile")


class PreferencesForm(FlaskForm):
    ui_language_code = SelectField("UI Language", validators=[DataRequired()], choices=[])
    learning_language_code = SelectField("Learning Language", validators=[DataRequired()], choices=[])
    translation_support_language_code = SelectField("Translation Support Language", validators=[DataRequired()], choices=[])
    use_native_language_support = BooleanField("Enable translation support", default=True)
    speaking_speed = FloatField("Speaking Speed", validators=[NumberRange(min=0.5, max=2.0)], default=1.0)
    playback_speed = FloatField("Question Playback Speed", validators=[NumberRange(min=0.5, max=2.0)], default=1.0)
    voice_pitch = FloatField("Voice Pitch", validators=[NumberRange(min=0.5, max=1.8)], default=1.0)
    accent = SelectField("Accent", validators=[Optional()], choices=[])
    voice_gender = SelectField("Voice Gender", validators=[DataRequired()], choices=[('female', 'Female'), ('male', 'Male')], default='female')
    autoplay_voice = BooleanField("Autoplay Voice", default=True)
    dark_mode = BooleanField("Dark Mode", default=True)
    auto_play_question = BooleanField("Auto play question", default=True)
    auto_start_listening = BooleanField("Auto start listening after question", default=True)
    question_beep_enabled = BooleanField("Play beep before listening", default=True)
    voice_name = StringField("Preferred Voice Name", validators=[Optional(), Length(max=80)])
    preferred_study_time = StringField("Preferred Study Time Label", validators=[Optional(), Length(max=40)])
    welcome_voice_mode = SelectField("Welcome Voice", validators=[DataRequired()], choices=[("once", "Play once"), ("muted", "Mute forever")], default="once")
    notify_email = BooleanField("Email notifications", default=True)
    notify_push = BooleanField("Push notifications", default=False)
    allow_ml_training = BooleanField("Allow anonymized ML training", default=False)
    submit = SubmitField("Save Preferences")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired(), Length(min=6, max=128)])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField("Confirm New Password", validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")])
    submit = SubmitField("Change Password")
