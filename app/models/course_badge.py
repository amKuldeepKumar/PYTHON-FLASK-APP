from datetime import datetime
from ..extensions import db


class CourseBadge(db.Model):
    __tablename__ = 'course_badges'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, unique=True, index=True)
    title = db.Column(db.String(80), nullable=False)
    subtitle = db.Column(db.String(120), nullable=True)
    template_key = db.Column(db.String(40), nullable=False, default='gradient')
    animation_key = db.Column(db.String(40), nullable=False, default='none')
    position = db.Column(db.String(30), nullable=False, default='top-right')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    show_on_frontpage = db.Column(db.Boolean, nullable=False, default=True)
    show_on_dashboard = db.Column(db.Boolean, nullable=False, default=True)
    show_on_library = db.Column(db.Boolean, nullable=False, default=True)
    start_at = db.Column(db.DateTime, nullable=True)
    end_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
