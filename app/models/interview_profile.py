from __future__ import annotations

from datetime import datetime

from ..extensions import db


class InterviewProfile(db.Model):
    __tablename__ = 'interview_profiles'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True, index=True)

    title = db.Column(db.String(160), nullable=False, default='Interview Profile')
    interview_purpose = db.Column(db.String(60), nullable=False, default='job', index=True)
    target_role = db.Column(db.String(160), nullable=True)
    industry = db.Column(db.String(120), nullable=True)
    company_name = db.Column(db.String(160), nullable=True)
    country_target = db.Column(db.String(120), nullable=True)
    english_level = db.Column(db.String(30), nullable=False, default='intermediate', index=True)
    difficulty_level = db.Column(db.String(30), nullable=False, default='medium', index=True)
    interview_style = db.Column(db.String(30), nullable=False, default='realistic')
    focus_area = db.Column(db.String(40), nullable=False, default='mixed')
    resume_summary = db.Column(db.Text, nullable=True)
    job_description = db.Column(db.Text, nullable=True)
    extra_notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course = db.relationship(
        'Course',
        lazy='joined',
        overlaps="interview_profiles"
    )
    sessions = db.relationship(
        'InterviewSession',
        back_populates='profile',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='desc(InterviewSession.created_at)',
    )

    def __repr__(self) -> str:
        return f'<InterviewProfile {self.id} student={self.student_id} purpose={self.interview_purpose}>'
