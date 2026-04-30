from datetime import datetime
from ..extensions import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'), nullable=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    final_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    currency_code = db.Column(db.String(8), nullable=False, default='INR')
    purchase_scope = db.Column(db.String(20), nullable=False, default='full_course', index=True)
    level_number = db.Column(db.Integer, nullable=True, index=True)
    gateway = db.Column(db.String(30), nullable=False, default='razorpay')
    gateway_order_id = db.Column(db.String(128), nullable=True, index=True)
    gateway_payment_id = db.Column(db.String(128), nullable=True, index=True)
    gateway_signature = db.Column(db.String(255), nullable=True)
    payment_method = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='created')  # created|paid|failed|refunded
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
