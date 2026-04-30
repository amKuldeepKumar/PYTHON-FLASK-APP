from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ..models.lms import Lesson, LessonProgress, QuestionAttempt
from ..models.reading_session_log import ReadingSessionLog
from ..models.speaking_attempt import SpeakingAttempt
from ..models.speaking_session import SpeakingSession
from ..models.speaking_topic import SpeakingTopic
from ..models.writing_submission import WritingSubmission


class StudentProgressAnalyticsService:
    @staticmethod
    def _avg(values):
        cleaned = [float(v) for v in values if v is not None]
        return round(mean(cleaned), 1) if cleaned else 0.0

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
    def speaking_block(cls, student_id: int) -> dict:
        attempts = (
            SpeakingAttempt.query.filter_by(student_id=student_id)
            .order_by(SpeakingAttempt.created_at.desc(), SpeakingAttempt.id.desc())
            .all()
        )
        sessions = SpeakingSession.query.filter_by(student_id=student_id).all()
        scores_100 = [float(a.score or 0) * 10 for a in attempts if a.score is not None]
        relevance = [float(a.relevance_score or 0) for a in attempts if a.relevance_score is not None]
        durations = [int(a.duration_seconds or 0) for a in attempts]
        weak_rows = []
        bucket = defaultdict(list)
        for row in attempts:
            label = getattr(getattr(row, 'topic', None), 'title', None) or 'Speaking topic'
            bucket[label].append(row)
        for label, rows in bucket.items():
            avg_score = cls._avg([(float(r.score or 0) * 10) for r in rows if r.score is not None])
            retry_rate = round((sum(1 for r in rows if r.retry_recommended) / max(1, len(rows))) * 100, 1)
            if avg_score < 65 or retry_rate >= 30:
                weak_rows.append({
                    'label': label,
                    'score': avg_score,
                    'note': f"Speaking score {avg_score:.0f}% • Retry {retry_rate:.0f}%",
                    'track': 'Speaking',
                })
        weak_rows.sort(key=lambda item: item['score'])
        recent = []
        for row in attempts[:6]:
            recent.append({
                'date': row.created_at,
                'label': getattr(getattr(row, 'topic', None), 'title', None) or 'Speaking topic',
                'score': round(float(row.score or 0) * 10, 1) if row.score is not None else 0.0,
                'sub': getattr(getattr(row, 'prompt', None), 'prompt_text', None) or getattr(getattr(row, 'prompt', None), 'title', None) or 'Speaking prompt',
                'track': 'Speaking',
            })
        return {
            'key': 'speaking',
            'label': 'Speaking',
            'items_count': len(attempts),
            'completed_count': sum(1 for s in sessions if getattr(s, 'is_completed', False)),
            'avg_score': cls._avg(scores_100),
            'best_score': round(max(scores_100), 1) if scores_100 else 0.0,
            'time_seconds': sum(durations),
            'time_text': cls._fmt_seconds(sum(durations)),
            'secondary_metric_label': 'Avg relevance',
            'secondary_metric_value': cls._avg(relevance),
            'secondary_metric_suffix': '%',
            'weak_areas': weak_rows[:5],
            'recent': recent,
        }


    @classmethod
    def interview_block(cls, student_id: int) -> dict:
        attempts = (
            SpeakingAttempt.query.join(SpeakingTopic, SpeakingTopic.id == SpeakingAttempt.topic_id)
            .filter(SpeakingAttempt.student_id == student_id, SpeakingTopic.topic_kind == 'interview')
            .order_by(SpeakingAttempt.created_at.desc(), SpeakingAttempt.id.desc())
            .all()
        )
        sessions = (
            SpeakingSession.query.join(SpeakingTopic, SpeakingTopic.id == SpeakingSession.topic_id)
            .filter(SpeakingSession.student_id == student_id, SpeakingTopic.topic_kind == 'interview')
            .all()
        )
        scores_100 = [float(a.score or 0) * 10 for a in attempts if a.score is not None]
        confidence_scores = []
        for row in attempts:
            payload = getattr(row, 'evaluation_payload', {}) or {}
            confidence_scores.append(float(((payload.get('interview_scores') or {}).get('confidence')) or 0))
        durations = [int(a.duration_seconds or 0) for a in attempts]
        recent = []
        for row in attempts[:6]:
            recent.append({
                'date': row.created_at,
                'label': getattr(getattr(row, 'topic', None), 'title', None) or 'Interview topic',
                'score': round(float(row.score or 0) * 10, 1) if row.score is not None else 0.0,
                'sub': getattr(getattr(row, 'prompt', None), 'title', None) or 'Interview question',
                'track': 'Interview Prep',
            })
        return {
            'key': 'interview',
            'label': 'Interview Prep',
            'items_count': len(attempts),
            'completed_count': sum(1 for s in sessions if getattr(s, 'is_completed', False)),
            'avg_score': cls._avg(scores_100),
            'best_score': round(max(scores_100), 1) if scores_100 else 0.0,
            'time_seconds': sum(durations),
            'time_text': cls._fmt_seconds(sum(durations)),
            'secondary_metric_label': 'Avg confidence',
            'secondary_metric_value': cls._avg(confidence_scores),
            'secondary_metric_suffix': '%',
            'weak_areas': [],
            'recent': recent,
        }

    @classmethod
    def reading_block(cls, student_id: int) -> dict:
        rows = (
            ReadingSessionLog.query.filter_by(student_id=student_id)
            .order_by(ReadingSessionLog.submitted_at.desc(), ReadingSessionLog.id.desc())
            .all()
        )
        accuracies = [float(r.accuracy or 0) for r in rows]
        speeds = [float(r.reading_speed_wpm or 0) for r in rows]
        weak_rows = []
        bucket = defaultdict(list)
        for row in rows:
            label = getattr(getattr(row, 'topic', None), 'title', None) or getattr(getattr(row, 'passage', None), 'title', None) or 'Reading set'
            bucket[label].append(row)
        for label, items in bucket.items():
            avg_score = cls._avg([float(item.accuracy or 0) for item in items])
            if avg_score < 70:
                weak_rows.append({
                    'label': label,
                    'score': avg_score,
                    'note': f"Reading accuracy {avg_score:.0f}%",
                    'track': 'Reading',
                })
        weak_rows.sort(key=lambda item: item['score'])
        recent = []
        for row in rows[:6]:
            recent.append({
                'date': row.submitted_at,
                'label': getattr(getattr(row, 'passage', None), 'title', None) or 'Reading passage',
                'score': round(float(row.accuracy or 0), 1),
                'sub': f"{int(row.correct_count or 0)}/{int(row.total_questions or 0)} correct",
                'track': 'Reading',
            })
        total_seconds = sum(int(r.elapsed_seconds or 0) for r in rows)
        return {
            'key': 'reading',
            'label': 'Reading',
            'items_count': len(rows),
            'completed_count': len(rows),
            'avg_score': cls._avg(accuracies),
            'best_score': round(max(accuracies), 1) if accuracies else 0.0,
            'time_seconds': total_seconds,
            'time_text': cls._fmt_seconds(total_seconds),
            'secondary_metric_label': 'Avg speed',
            'secondary_metric_value': cls._avg(speeds),
            'secondary_metric_suffix': ' WPM',
            'weak_areas': weak_rows[:5],
            'recent': recent,
        }

    @classmethod
    def writing_block(cls, student_id: int) -> dict:
        rows = (
            WritingSubmission.query.filter_by(student_id=student_id)
            .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
            .all()
        )
        scores = [float(r.score or 0) * 10 for r in rows if r.score is not None]
        word_counts = [int(r.word_count or 0) for r in rows]
        weak_rows = []
        bucket = defaultdict(list)
        for row in rows:
            label = getattr(getattr(row, 'topic', None), 'title', None) or getattr(getattr(row, 'task', None), 'title', None) or 'Writing task'
            bucket[label].append(row)
        for label, items in bucket.items():
            avg_score = cls._avg([float(item.score or 0) * 10 for item in items if item.score is not None])
            if avg_score and avg_score < 65:
                weak_rows.append({
                    'label': label,
                    'score': avg_score,
                    'note': f"Writing score {avg_score:.0f}%",
                    'track': 'Writing',
                })
        weak_rows.sort(key=lambda item: item['score'])
        recent = []
        for row in rows[:6]:
            recent.append({
                'date': row.submitted_at,
                'label': getattr(getattr(row, 'task', None), 'title', None) or 'Writing task',
                'score': round(float(row.score or 0) * 10, 1) if row.score is not None else 0.0,
                'sub': f"{int(row.word_count or 0)} words",
                'track': 'Writing',
            })
        est_seconds = sum(max(60, int((row.word_count or 0) * 12)) for row in rows)
        return {
            'key': 'writing',
            'label': 'Writing',
            'items_count': len(rows),
            'completed_count': sum(1 for r in rows if (r.status or '').strip().lower() == WritingSubmission.STATUS_SUBMITTED),
            'avg_score': cls._avg(scores),
            'best_score': round(max(scores), 1) if scores else 0.0,
            'time_seconds': est_seconds,
            'time_text': cls._fmt_seconds(est_seconds),
            'secondary_metric_label': 'Avg words',
            'secondary_metric_value': round(cls._avg(word_counts), 1),
            'secondary_metric_suffix': '',
            'weak_areas': weak_rows[:5],
            'recent': recent,
        }

    @classmethod
    def listening_block(cls, student_id: int) -> dict:
        attempts = (
            QuestionAttempt.query.join(Lesson, Lesson.id == QuestionAttempt.lesson_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.attempt_kind == 'final',
                Lesson.lesson_type == 'listening',
            )
            .order_by(QuestionAttempt.attempted_at.desc(), QuestionAttempt.id.desc())
            .all()
        )
        lesson_bucket = defaultdict(list)
        for row in attempts:
            lesson_bucket[row.lesson_id].append(row)
        lesson_scores = []
        weak_rows = []
        recent = []
        for lesson_id, rows in lesson_bucket.items():
            label = getattr(rows[0].lesson, 'title', None) or 'Listening lesson'
            accuracy = round((sum(1 for r in rows if r.is_correctish) / max(1, len(rows))) * 100, 1)
            lesson_scores.append(accuracy)
            if accuracy < 70:
                weak_rows.append({
                    'label': label,
                    'score': accuracy,
                    'note': f"Listening accuracy {accuracy:.0f}%",
                    'track': 'Listening',
                })
        weak_rows.sort(key=lambda item: item['score'])
        for row in attempts[:6]:
            recent.append({
                'date': row.attempted_at,
                'label': getattr(row.lesson, 'title', None) or 'Listening lesson',
                'score': 100.0 if row.is_correctish else 0.0,
                'sub': getattr(row.question, 'prompt', None) or 'Listening answer',
                'track': 'Listening',
            })
        total_seconds = sum(int(row.duration_seconds or 0) for row in attempts)
        return {
            'key': 'listening',
            'label': 'Listening',
            'items_count': len(attempts),
            'completed_count': len(lesson_bucket),
            'avg_score': cls._avg(lesson_scores),
            'best_score': round(max(lesson_scores), 1) if lesson_scores else 0.0,
            'time_seconds': total_seconds,
            'time_text': cls._fmt_seconds(total_seconds),
            'secondary_metric_label': 'Lessons done',
            'secondary_metric_value': len(lesson_bucket),
            'secondary_metric_suffix': '',
            'weak_areas': weak_rows[:5],
            'recent': recent,
        }

    @classmethod
    def overview(cls, student_id: int) -> dict:
        tracks = [
            cls.speaking_block(student_id),
            cls.interview_block(student_id),
            cls.writing_block(student_id),
            cls.reading_block(student_id),
            cls.listening_block(student_id),
        ]
        total_time = sum(int(t['time_seconds'] or 0) for t in tracks)
        active_tracks = sum(1 for t in tracks if int(t['items_count'] or 0) > 0)
        avg_scores = [float(t['avg_score']) for t in tracks if float(t['avg_score'] or 0) > 0]
        recent_activity = []
        weak_areas = []
        for track in tracks:
            recent_activity.extend(track.get('recent', []))
            weak_areas.extend(track.get('weak_areas', []))
        recent_activity.sort(key=lambda item: item.get('date') or 0, reverse=True)
        weak_areas.sort(key=lambda item: (item.get('score', 999), item.get('label', '')))
        lesson_rows = LessonProgress.query.filter_by(student_id=student_id).all()
        completion_values = [int(row.completion_percent or 0) for row in lesson_rows]
        overall_completion = int(round(sum(completion_values) / len(completion_values))) if completion_values else 0
        return {
            'summary': {
                'active_tracks': active_tracks,
                'overall_avg_score': cls._avg(avg_scores),
                'overall_completion': overall_completion,
                'total_practice_items': sum(int(t['items_count'] or 0) for t in tracks),
                'total_time_seconds': total_time,
                'total_time_text': cls._fmt_seconds(total_time),
                'weak_areas_count': len(weak_areas),
            },
            'tracks': tracks,
            'weak_areas': weak_areas[:8],
            'recent_activity': recent_activity[:12],
        }
