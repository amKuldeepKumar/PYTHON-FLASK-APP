"""
Phase 3: Language registry.

Stores languages available for UI and content/learning.
Adding a language should be as easy as adding a record and enabling it.
"""

from datetime import datetime
from ..extensions import db


class Language(db.Model):
    __tablename__ = "languages"

    id = db.Column(db.Integer, primary_key=True)

    # ISO code like "en", "hi", "pa", "ar"
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)

    # English name (display)
    name = db.Column(db.String(80), nullable=False)

    # Optional native name
    native_name = db.Column(db.String(80), nullable=True)

    # Text direction: "ltr" / "rtl"
    direction = db.Column(db.String(3), nullable=False, default="ltr")

    # Enabled languages appear in pickers/navigation
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Language {self.code}>"
