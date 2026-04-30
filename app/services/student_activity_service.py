from __future__ import annotations

from calendar import Calendar
from datetime import date, datetime, timedelta
import math

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models.student_daily_activity import StudentDailyActivity


class StudentActivityService:
    @staticmethod
    def _recover_schema() -> None:
        db.session.rollback()
        db.create_all()

    @staticmethod
    def get_or_create(student_id: int, activity_date: date | None = None) -> StudentDailyActivity:
        activity_date = activity_date or date.today()
        try:
            row = StudentDailyActivity.query.filter_by(
                student_id=student_id,
                activity_date=activity_date,
            ).first()
        except SQLAlchemyError:
            StudentActivityService._recover_schema()
            row = StudentDailyActivity.query.filter_by(
                student_id=student_id,
                activity_date=activity_date,
            ).first()
        if not row:
            row = StudentDailyActivity(student_id=student_id, activity_date=activity_date)
            db.session.add(row)
            db.session.flush()
        return row

    @staticmethod
    def track_login(student_id: int, when: datetime | None = None) -> StudentDailyActivity:
        when = when or datetime.utcnow()
        row = StudentActivityService.get_or_create(student_id, when.date())
        row.login_count = int(row.login_count or 0) + 1
        if not row.first_login_at or when < row.first_login_at:
            row.first_login_at = when
        if not row.last_login_at or when > row.last_login_at:
            row.last_login_at = when
        db.session.flush()
        return row

    @staticmethod
    def track_attempt(attempt, *, lesson_completed: bool = False) -> StudentDailyActivity:
        when = getattr(attempt, "attempted_at", None) or datetime.utcnow()
        row = StudentActivityService.get_or_create(attempt.student_id, when.date())
        kind = (getattr(attempt, "attempt_kind", "") or "").strip().lower()
        if kind == "final":
            row.questions_attempted = int(row.questions_attempted or 0) + 1
            if bool(getattr(attempt, "is_correctish", False)):
                row.questions_correct = int(row.questions_correct or 0) + 1
            if getattr(attempt, "response_mode", "") == "spoken":
                row.speaking_attempts = int(row.speaking_attempts or 0) + 1
            score = getattr(attempt, "accuracy_score", None)
            if score is not None:
                row.accuracy_total = float(row.accuracy_total or 0.0) + float(score)
                row.accuracy_samples = int(row.accuracy_samples or 0) + 1
            seconds = int(getattr(attempt, "duration_seconds", None) or 0)
            if seconds > 0:
                row.practice_minutes = int(row.practice_minutes or 0) + max(1, math.ceil(seconds / 60))
            else:
                row.practice_minutes = int(row.practice_minutes or 0) + 1
        if lesson_completed:
            row.lessons_completed = int(row.lessons_completed or 0) + 1
        db.session.flush()
        return row

    @staticmethod
    def monthly_rows(student_id: int, month_start: date, month_end: date) -> list[StudentDailyActivity]:
        try:
            return (
                StudentDailyActivity.query.filter(
                    StudentDailyActivity.student_id == student_id,
                    StudentDailyActivity.activity_date >= month_start,
                    StudentDailyActivity.activity_date <= month_end,
                )
                .order_by(StudentDailyActivity.activity_date.asc())
                .all()
            )
        except SQLAlchemyError:
            StudentActivityService._recover_schema()
            return []

    @staticmethod
    def active_streak(student_id: int) -> int:
        try:
            rows = (
                StudentDailyActivity.query.filter(StudentDailyActivity.student_id == student_id)
                .order_by(StudentDailyActivity.activity_date.desc())
                .limit(365)
                .all()
            )
        except SQLAlchemyError:
            StudentActivityService._recover_schema()
            return 0
        active_days = {
            row.activity_date
            for row in rows
            if (row.questions_attempted or 0) > 0
            or (row.login_count or 0) > 0
            or (row.speaking_attempts or 0) > 0
            or (row.speaking_completed_sessions or 0) > 0
            or (row.practice_minutes or 0) > 0
        }
        if not active_days:
            return 0
        streak = 0
        day = date.today()
        if day not in active_days and (day - timedelta(days=1)) in active_days:
            day = day - timedelta(days=1)
        while day in active_days:
            streak += 1
            day = day - timedelta(days=1)
        return streak

    @staticmethod
    def build_month_grid(student_id: int, year: int, month: int) -> dict:
        cal = Calendar(firstweekday=0)
        today = date.today()
        month_weeks = cal.monthdatescalendar(year, month)
        start = month_weeks[0][0]
        end = month_weeks[-1][-1]
        rows = StudentActivityService.monthly_rows(student_id, start, end)
        row_map = {row.activity_date: row for row in rows}
        max_attempts = max([int(row.questions_attempted or 0) for row in rows] + [1])

        weeks = []
        active_days = 0
        previous_present_accuracy: int | None = None
        for week in month_weeks:
            week_cells = []
            for day in week:
                row = row_map.get(day)
                attempts = int(getattr(row, 'questions_attempted', 0) or 0)
                logins = int(getattr(row, 'login_count', 0) or 0)
                accuracy = int(row.accuracy_percent) if row else 0
                in_month = day.month == month
                is_future = day > today
                was_present = logins > 0
                improvement_value = None
                improvement_label = "No score yet"
                if was_present:
                    active_days += 1
                    if previous_present_accuracy is None:
                        improvement_label = "Baseline"
                    else:
                        improvement_value = accuracy - previous_present_accuracy
                        if improvement_value > 0:
                            improvement_label = f"+{improvement_value}% improvement"
                        elif improvement_value < 0:
                            improvement_label = f"{improvement_value}% change"
                        else:
                            improvement_label = "No change"
                    previous_present_accuracy = accuracy
                intensity = 0
                if was_present:
                    intensity = max(1, min(4, math.ceil((attempts / max_attempts) * 4))) if attempts > 0 else 1
                speaking_completed = int(getattr(row, 'speaking_completed_sessions', 0) or 0)
                day_label = day.strftime('%d %b %Y')
                if is_future:
                    tooltip = ""
                elif not in_month:
                    tooltip = f"{day_label} • Outside {date(year, month, 1).strftime('%B %Y')}."
                elif was_present:
                    tooltip = (
                        f"{day_label} • Present: {logins} login{'s' if logins != 1 else ''} "
                        f"• Questions practiced: {attempts} • Score: {accuracy}% "
                        f"• Improvement: {improvement_label}"
                    )
                    if speaking_completed:
                        tooltip += f" • Speaking completions: {speaking_completed}"
                else:
                    tooltip = f"{day_label} • You were not present on this date."
                if was_present and row and row.last_login_at:
                    tooltip += f" • Last login: {row.last_login_at.strftime('%I:%M %p')}"
                week_cells.append({
                    'date': day.isoformat(),
                    'display_label': day_label,
                    'day': day.day,
                    'in_month': in_month,
                    'is_future': is_future,
                    'was_present': was_present,
                    'is_absent': in_month and not is_future and not was_present,
                    'status_label': 'Upcoming' if is_future else ('Present' if was_present else 'Not present'),
                    'intensity': intensity,
                    'tooltip': tooltip,
                    'logins': logins,
                    'questions': attempts,
                    'accuracy': accuracy,
                    'improvement_value': improvement_value,
                    'improvement_label': improvement_label,
                    'speaking_completed': speaking_completed,
                })
            weeks.append(week_cells)
        return {
            'weeks': weeks,
            'month_label': date(year, month, 1).strftime('%B %Y'),
            'active_days': active_days,
        }
