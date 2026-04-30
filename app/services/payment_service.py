from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..extensions import db
from ..models.payment import Payment
from ..services.coupon_service import CouponService
from ..services.lms_service import LMSService


class PaymentService:
    @staticmethod
    def create_checkout(user_id: int, course, coupon_code: str | None = None, *, purchase_scope: str = "full_course", level_number: int | None = None) -> Payment:
        purchase_scope = (purchase_scope or "full_course").strip().lower()
        if purchase_scope not in {"full_course", "single_level"}:
            purchase_scope = "full_course"

        if purchase_scope == "single_level":
            amount = Decimal(str(getattr(course, "current_level_price", 0) or 0))
            if level_number is None:
                raise ValueError("Please choose a level to continue.")
        else:
            amount = Decimal(str(course.current_price or 0))
            level_number = None

        coupon = None
        discount = Decimal('0.00')
        if coupon_code:
            coupon, err = CouponService.validate_coupon(coupon_code, course=course, amount=amount)
            if err:
                raise ValueError(err)
            discount = CouponService.compute_discount(coupon, amount)
        payment = Payment(
            user_id=user_id,
            course_id=course.id,
            coupon_id=coupon.id if coupon else None,
            amount=amount,
            discount_amount=discount,
            final_amount=max(Decimal('0.00'), amount - discount),
            currency_code=course.currency_code or 'INR',
            gateway='razorpay',
            status='created',
            purchase_scope=purchase_scope,
            level_number=level_number,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def mark_paid(payment: Payment, gateway_payment_id: str | None = None, method: str | None = None):
        payment.status = 'paid'
        payment.gateway_payment_id = gateway_payment_id
        payment.payment_method = method
        payment.paid_at = datetime.utcnow()
        db.session.commit()
        if (payment.purchase_scope or 'full_course') == 'single_level':
            LMSService.enroll_course_level(payment.user_id, payment.course_id, int(payment.level_number or 1))
        else:
            LMSService.auto_enroll_paid_student(payment.user_id, payment.course_id)
        return payment
