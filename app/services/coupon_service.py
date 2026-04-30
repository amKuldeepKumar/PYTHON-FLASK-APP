from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..models.coupon import Coupon


class CouponService:
    @staticmethod
    def validate_coupon(code: str, course=None, user=None, amount: Decimal | float | int = 0):
        code = (code or '').strip().upper()
        coupon = Coupon.query.filter_by(code=code).first()
        if not coupon or not coupon.is_active:
            return None, 'Coupon is invalid or inactive.'

        now = datetime.utcnow()
        if coupon.valid_from and coupon.valid_from > now:
            return None, 'Coupon is not active yet.'
        if coupon.valid_until and coupon.valid_until < now:
            return None, 'Coupon has expired.'
        if course and coupon.course_id and coupon.course_id != course.id:
            return None, 'Coupon is not valid for this course.'

        amount = Decimal(str(amount or 0))
        if amount < Decimal(str(coupon.min_order_amount or 0)):
            return None, 'Minimum order amount is not met.'
        return coupon, None

    @staticmethod
    def compute_discount(coupon: Coupon, amount: Decimal | float | int):
        amount = Decimal(str(amount or 0))
        if not coupon:
            return Decimal('0.00')
        value = Decimal(str(coupon.discount_value or 0))
        if coupon.discount_type == 'fixed':
            discount = min(value, amount)
        else:
            discount = (amount * value) / Decimal('100')
            if coupon.max_discount_amount:
                discount = min(discount, Decimal(str(coupon.max_discount_amount)))
        return max(Decimal('0.00'), discount.quantize(Decimal('0.01')))
