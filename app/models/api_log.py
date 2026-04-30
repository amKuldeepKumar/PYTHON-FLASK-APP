from datetime import datetime
from ..extensions import db

class ApiCallLog(db.Model):
    __tablename__ = "api_call_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    system = db.Column(db.String(50), nullable=False, default="LMS")
    endpoint = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(10), nullable=False, default="GET")

    status_code = db.Column(db.Integer, nullable=True)
    ok = db.Column(db.Boolean, default=False, nullable=False)

    # small debug context
    message = db.Column(db.String(255), nullable=True)
    provider_name = db.Column(db.String(120), nullable=True)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)
    estimated_cost = db.Column(db.Numeric(10, 4), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
