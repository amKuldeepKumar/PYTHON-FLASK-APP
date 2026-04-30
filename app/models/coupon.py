from datetime import datetime
from ..extensions import db


class Coupon(db.Model):
    __tablename__ = 'coupons'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(140), nullable=True)
    description = db.Column(db.Text, nullable=True)
    discount_type = db.Column(db.String(20), nullable=False, default='percentage')  # percentage|fixed
    discount_value = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    min_order_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    max_discount_amount = db.Column(db.Numeric(10, 2), nullable=True)
    usage_limit_total = db.Column(db.Integer, nullable=True)
    usage_limit_per_user = db.Column(db.Integer, nullable=True, default=1)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True, index=True)
    first_purchase_only = db.Column(db.Boolean, nullable=False, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship('Course', back_populates='coupons')
    redemptions = db.relationship('CouponRedemption', back_populates='coupon', cascade='all, delete-orphan')


class CouponRedemption(db.Model):
    __tablename__ = 'coupon_redemptions'

    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True, index=True)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    redeemed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    coupon = db.relationship('Coupon', back_populates='redemptions')
