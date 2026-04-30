from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from ...models.speaking_attempt import SpeakingAttempt
from ...models.speaking_session import SpeakingSession
from ...models.user import User
from ..tenancy_service import tenant_students_for


@dataclass
class _WeakArea:
    label: str
    attempts: int
    avg_score: float
    avg_relevance: float
    retry_rate: float


class SpeakingAnalyticsService:
    @staticmethod
    def _safe_avg(values: list[float | int]) -> float:
        cleaned = [float(v) for v in values if v is not None]
        return round(mean(cleaned), 2) if cleaned else 0.0

    @staticmethod
    def _fmt_seconds(total_seconds: int | float | None) -> str:
        seconds = max(0, int(total_seconds or 0))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    @classmethod
    def _trend_label(cls, scores: list[float]) -> tuple[str, float]:
        if len(scores) < 2:
            return "Not enough data", 0.0
        split = max(1, len(scores) // 2)
        first_avg = cls._safe_avg(scores[:split])
        second_avg = cls._safe_avg(scores[split:])
        delta = round(second_avg - first_avg, 2)
        if delta >= 1.0:
            return "Improving", delta
        if delta <= -1.0:
            return "Needs attention", delta
        return "Stable", delta

    @classmethod
    def _attempts_for_student(cls, student_id: int) -> list[SpeakingAttempt]:
        return (
            SpeakingAttempt.query.filter_by(student_id=student_id)
            .order_by(SpeakingAttempt.created_at.asc(), SpeakingAttempt.id.asc())
            .all()
        )

    @classmethod
    def _sessions_for_student(cls, student_id: int) -> list[SpeakingSession]:
        return (
            SpeakingSession.query.filter_by(student_id=student_id)
            .order_by(SpeakingSession.created_at.asc(), SpeakingSession.id.asc())
            .all()
        )

    @classmethod
    def student_report(cls, student: User | int) -> dict:
        student_obj = student if isinstance(student, User) else User.query.get(int(student))
        if not student_obj:
            return {
                "student": None,
                "summary": {},
                "chart_data": {},
                "weak_areas": [],
                "recent_attempts": [],
                "topic_cards": [],
            }

        attempts = cls._attempts_for_student(student_obj.id)
        sessions = cls._sessions_for_student(student_obj.id)
        completed_sessions = [s for s in sessions if s.is_completed]
        scores = [float(a.score) for a in attempts if a.score is not None]
        relevance_scores = [float(a.relevance_score) for a in attempts if a.relevance_score is not None]
        durations = [int(a.duration_seconds or 0) for a in attempts]
        word_counts = [int(a.word_count or 0) for a in attempts]
        trend_label, trend_delta = cls._trend_label(scores)

        topic_bucket: dict[str, list[SpeakingAttempt]] = defaultdict(list)
        for attempt in attempts:
            label = getattr(getattr(attempt, "topic", None), "title", None) or "Untitled topic"
            topic_bucket[label].append(attempt)

        weak_area_rows: list[_WeakArea] = []
        topic_cards: list[dict] = []
        for label, topic_attempts in topic_bucket.items():
            topic_scores = [float(a.score) for a in topic_attempts if a.score is not None]
            topic_rel = [float(a.relevance_score) for a in topic_attempts if a.relevance_score is not None]
            retry_rate = round((sum(1 for a in topic_attempts if a.retry_recommended) / max(1, len(topic_attempts))) * 100, 2)
            avg_score = cls._safe_avg(topic_scores)
            avg_relevance = cls._safe_avg(topic_rel)
            card = {
                "label": label,
                "attempts": len(topic_attempts),
                "avg_score": avg_score,
                "avg_relevance": avg_relevance,
                "retry_rate": retry_rate,
            }
            topic_cards.append(card)
            if avg_score < 7 or avg_relevance < 70 or retry_rate >= 30:
                weak_area_rows.append(
                    _WeakArea(
                        label=label,
                        attempts=len(topic_attempts),
                        avg_score=avg_score,
                        avg_relevance=avg_relevance,
                        retry_rate=retry_rate,
                    )
                )

        weak_areas = [
            {
                "label": row.label,
                "attempts": row.attempts,
                "avg_score": row.avg_score,
                "avg_relevance": row.avg_relevance,
                "retry_rate": row.retry_rate,
            }
            for row in sorted(weak_area_rows, key=lambda item: (item.avg_score, item.avg_relevance, -item.attempts))[:5]
        ]
        topic_cards.sort(key=lambda item: (-item["avg_score"], -item["attempts"], item["label"]))

        recent_attempts = [
            {
                "date_label": attempt.created_at.strftime("%d %b %Y"),
                "topic": getattr(getattr(attempt, "topic", None), "title", None) or "Untitled topic",
                "prompt": getattr(getattr(attempt, "prompt", None), "title", None) or "Prompt",
                "score": round(float(attempt.score or 0), 2),
                "relevance": round(float(attempt.relevance_score or 0), 2),
                "duration_text": cls._fmt_seconds(attempt.duration_seconds),
                "feedback": (attempt.feedback_text or "").strip(),
            }
            for attempt in sorted(attempts, key=lambda row: (row.created_at, row.id), reverse=True)[:8]
        ]

        chart_data = {
            "score_history": {
                "labels": [f"A{idx}" for idx, _ in enumerate(attempts, start=1)],
                "scores": [round(float(a.score or 0), 2) for a in attempts],
                "relevance": [round(float(a.relevance_score or 0), 2) for a in attempts],
            },
            "time_history": {
                "labels": [f"A{idx}" for idx, _ in enumerate(attempts, start=1)],
                "minutes": [round((int(a.duration_seconds or 0) / 60.0), 2) for a in attempts],
                "words": [int(a.word_count or 0) for a in attempts],
            },
            "topic_breakdown": {
                "labels": [row["label"] for row in sorted(topic_cards, key=lambda item: item["label"])],
                "scores": [row["avg_score"] for row in sorted(topic_cards, key=lambda item: item["label"])],
                "attempts": [row["attempts"] for row in sorted(topic_cards, key=lambda item: item["label"])],
            },
        }

        return {
            "student": student_obj,
            "summary": {
                "sessions_started": len(sessions),
                "sessions_completed": len(completed_sessions),
                "attempts_count": len(attempts),
                "time_spent_seconds": sum(durations),
                "time_spent_text": cls._fmt_seconds(sum(durations)),
                "avg_score": cls._safe_avg(scores),
                "best_score": round(max(scores), 2) if scores else 0.0,
                "avg_relevance": cls._safe_avg(relevance_scores),
                "avg_words": round(cls._safe_avg(word_counts), 1) if word_counts else 0.0,
                "score_trend": trend_label,
                "score_trend_delta": trend_delta,
                "weak_areas_count": len(weak_areas),
            },
            "chart_data": chart_data,
            "weak_areas": weak_areas,
            "recent_attempts": recent_attempts,
            "topic_cards": topic_cards,
        }

    @classmethod
    def admin_scope_report(cls, admin_user: User, *, selected_student_id: int | None = None) -> dict:
        students = tenant_students_for(admin_user)
        student_rows: list[dict] = []
        total_attempts = 0
        total_completed_sessions = 0
        total_seconds = 0
        all_scores: list[float] = []
        students_with_weak_areas = 0

        selected_student = None
        for student in students:
            report = cls.student_report(student)
            summary = report["summary"]
            if not summary:
                continue
            total_attempts += int(summary.get("attempts_count") or 0)
            total_completed_sessions += int(summary.get("sessions_completed") or 0)
            total_seconds += int(summary.get("time_spent_seconds") or 0)
            if summary.get("avg_score"):
                all_scores.append(float(summary.get("avg_score") or 0))
            if int(summary.get("weak_areas_count") or 0) > 0:
                students_with_weak_areas += 1

            row = {
                "student": student,
                "attempts_count": int(summary.get("attempts_count") or 0),
                "sessions_completed": int(summary.get("sessions_completed") or 0),
                "time_spent_text": summary.get("time_spent_text") or "0s",
                "avg_score": float(summary.get("avg_score") or 0),
                "best_score": float(summary.get("best_score") or 0),
                "score_trend": summary.get("score_trend") or "Not enough data",
                "score_trend_delta": float(summary.get("score_trend_delta") or 0),
                "weak_areas_count": int(summary.get("weak_areas_count") or 0),
                "report": report,
            }
            student_rows.append(row)
            if selected_student_id and int(student.id) == int(selected_student_id):
                selected_student = row

        student_rows.sort(key=lambda item: (-item["attempts_count"], item["student"].full_name.lower()))

        chart_rows = sorted(
            [row for row in student_rows if row["attempts_count"] > 0],
            key=lambda item: (-item["avg_score"], -item["attempts_count"], item["student"].full_name.lower())
        )[:10]

        return {
            "students": student_rows,
            "selected_student": selected_student,
            "summary": {
                "student_count": len(students),
                "active_speakers": sum(1 for row in student_rows if row["attempts_count"] > 0),
                "attempts_count": total_attempts,
                "completed_sessions": total_completed_sessions,
                "time_spent_text": cls._fmt_seconds(total_seconds),
                "avg_score": cls._safe_avg(all_scores),
                "students_with_weak_areas": students_with_weak_areas,
            },
            "chart_data": {
                "labels": [row["student"].full_name for row in chart_rows],
                "avg_scores": [row["avg_score"] for row in chart_rows],
                "attempts": [row["attempts_count"] for row in chart_rows],
            },
        }
