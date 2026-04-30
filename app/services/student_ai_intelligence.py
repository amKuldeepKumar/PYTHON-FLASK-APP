from __future__ import annotations

from dataclasses import dataclass

from .student_progress_analytics import StudentProgressAnalyticsService


LEVEL_BANDS = [
    (0, 44.99, 'foundation'),
    (45, 64.99, 'developing'),
    (65, 79.99, 'confident'),
    (80, 1000, 'advanced'),
]

TRACK_ORDER = ['speaking', 'reading', 'writing', 'listening']
TRACK_LABELS = {
    'speaking': 'Speaking',
    'reading': 'Reading',
    'writing': 'Writing',
    'listening': 'Listening',
}
TRACK_SKILL_MAP = {
    'speaking': ['fluency', 'pronunciation', 'confidence', 'relevance'],
    'reading': ['accuracy', 'speed', 'comprehension'],
    'writing': ['grammar', 'coherence', 'task response', 'vocabulary'],
    'listening': ['comprehension', 'focus', 'audio retention'],
}
CROSS_MODULE_LINKS = {
    'speaking': [('listening', 'Listening support will improve response clarity before the next speaking task.')],
    'reading': [('writing', 'Writing short summaries after reading will strengthen retention and structure.')],
    'writing': [('reading', 'Reading stronger model passages will improve sentence control and idea flow.')],
    'listening': [('speaking', 'Shadowing and short oral retelling will convert listening gains into speaking confidence.')],
}


@dataclass
class IntelligenceTrack:
    key: str
    label: str
    avg_score: float
    best_score: float
    completed_count: int
    items_count: int
    weak_count: int
    current_band: str
    recommended_band: str
    confidence: int
    action: str
    reason: str
    tutor_tip: str
    next_step: str
    weak_skills: list[str]
    linked_track: str | None
    linked_reason: str | None


class StudentAIIntelligenceService:
    @staticmethod
    def _band(score: float) -> str:
        value = float(score or 0.0)
        for low, high, label in LEVEL_BANDS:
            if low <= value <= high:
                return label
        return 'foundation'

    @staticmethod
    def _nice_band(label: str) -> str:
        return {
            'foundation': 'Foundation',
            'developing': 'Developing',
            'confident': 'Confident',
            'advanced': 'Advanced',
        }.get(label, 'Foundation')

    @staticmethod
    def _clamp(value: float, low: int = 0, high: int = 100) -> int:
        return max(low, min(high, int(round(value))))

    @classmethod
    def _confidence(cls, track: dict) -> int:
        items = int(track.get('items_count') or 0)
        completed = int(track.get('completed_count') or 0)
        avg = float(track.get('avg_score') or 0.0)
        weak_penalty = min(15, len(track.get('weak_areas') or []) * 4)
        base = 28 + min(items, 8) * 6 + min(completed, 5) * 4 + (avg * 0.18) - weak_penalty
        return cls._clamp(base, 32, 96)

    @staticmethod
    def _weak_skills(track_key: str, track: dict) -> list[str]:
        explicit = []
        for item in (track.get('weak_areas') or [])[:3]:
            label = str(item.get('label') or '').strip()
            if label:
                explicit.append(label)
        if explicit:
            return explicit
        return TRACK_SKILL_MAP.get(track_key, [])[:2]

    @classmethod
    def _recommended_band(cls, avg: float, completed: int, weak_count: int) -> tuple[str, str, str, str]:
        current_band = cls._band(avg)
        recommended_band = current_band
        action = 'Stay on the same level and clean up mistakes.'
        reason = 'The system sees enough progress to continue, but accuracy still needs to stabilize.'
        tutor_tip = 'Do one guided retry on the same level before moving up.'

        if completed == 0:
            recommended_band = 'foundation'
            action = 'Start with a guided task.'
            reason = 'There is not enough finished activity yet, so the safest entry point stays active.'
            tutor_tip = 'Complete one short activity first so the AI can personalize the next step.'
        elif avg >= 82 and completed >= 3 and weak_count <= 1:
            recommended_band = 'advanced'
            action = 'Move to a harder task.'
            reason = 'High scores and stable completion show readiness for stronger difficulty.'
            tutor_tip = 'Increase complexity, but keep answers accurate and complete.'
        elif avg >= 68 and completed >= 2:
            recommended_band = 'confident'
            action = 'Build consistency on this level.'
            reason = 'Performance is solid, but one more stable cycle should come before the next jump.'
            tutor_tip = 'Repeat one similar task and focus on cleaner execution.'
        elif avg >= 50:
            recommended_band = 'developing'
            action = 'Use guided practice with support.'
            reason = 'Scores are improving, but control is still uneven across attempts.'
            tutor_tip = 'Use hints after your first try, not before it.'
        else:
            recommended_band = 'foundation'
            action = 'Step back to simpler practice.'
            reason = 'Low scores or repeated weak areas show that a lighter level will rebuild control.'
            tutor_tip = 'Slow down and complete one accurate answer at a time.'

        if weak_count >= 2 and avg < 75:
            tutor_tip = 'Repeated weak areas are blocking progress, so review those first and then retry once.'

        return current_band, recommended_band, action, reason + ' ' + tutor_tip

    @classmethod
    def _track_plan(cls, track: dict) -> IntelligenceTrack:
        key = (track.get('key') or 'track').strip().lower()
        label = track.get('label') or TRACK_LABELS.get(key, 'Track')
        avg = float(track.get('avg_score') or 0.0)
        best = float(track.get('best_score') or 0.0)
        completed = int(track.get('completed_count') or 0)
        items_count = int(track.get('items_count') or 0)
        weak_count = len(track.get('weak_areas') or [])
        current_band, recommended_band, action, reason = cls._recommended_band(avg, completed, weak_count)
        weak_skills = cls._weak_skills(key, track)
        linked = CROSS_MODULE_LINKS.get(key, [])
        linked_track = linked[0][0] if linked else None
        linked_reason = linked[0][1] if linked else None
        next_step = {
            'speaking': 'Complete one short speaking response and review the fluency feedback.',
            'reading': 'Finish one reading passage and write a one-line summary.',
            'writing': 'Submit one guided writing task and fix the first two mistakes.',
            'listening': 'Do one listening lesson and replay only after your first answer.',
        }.get(key, 'Complete one guided activity.')
        return IntelligenceTrack(
            key=key,
            label=label,
            avg_score=round(avg, 1),
            best_score=round(best, 1),
            completed_count=completed,
            items_count=items_count,
            weak_count=weak_count,
            current_band=current_band,
            recommended_band=recommended_band,
            confidence=cls._confidence(track),
            action=action,
            reason=reason,
            tutor_tip=reason.split('. ', 1)[-1] if '. ' in reason else reason,
            next_step=next_step,
            weak_skills=weak_skills,
            linked_track=TRACK_LABELS.get(linked_track, linked_track.title()) if linked_track else None,
            linked_reason=linked_reason,
        )

    @classmethod
    def _overall_confidence(cls, tracks: list[IntelligenceTrack]) -> int:
        active = [t for t in tracks if t.items_count > 0]
        if not active:
            return 38
        weighted_total = sum(t.confidence * max(1, t.items_count) for t in active)
        weight = sum(max(1, t.items_count) for t in active)
        return cls._clamp(weighted_total / max(1, weight), 38, 95)

    @classmethod
    def _learning_path(cls, tracks: list[IntelligenceTrack]) -> list[dict]:
        ordered = sorted(
            tracks,
            key=lambda t: (
                0 if t.items_count == 0 else 1,
                t.avg_score if t.items_count > 0 else -1,
                -t.weak_count,
                TRACK_ORDER.index(t.key) if t.key in TRACK_ORDER else 99,
            )
        )
        steps = []
        for idx, track in enumerate(ordered[:4], start=1):
            status = 'Start' if track.items_count == 0 else ('Repair' if track.avg_score < 65 else ('Strengthen' if track.avg_score < 80 else 'Advance'))
            steps.append({
                'step': idx,
                'track': track.label,
                'status': status,
                'goal': track.next_step,
                'band': cls._nice_band(track.recommended_band),
            })
        return steps

    @classmethod
    def _cross_module_map(cls, tracks: list[IntelligenceTrack]) -> list[dict]:
        rows = []
        for track in tracks:
            if track.linked_track and track.linked_reason:
                rows.append({
                    'from_track': track.label,
                    'to_track': track.linked_track,
                    'reason': track.linked_reason,
                })
        return rows[:4]

    @classmethod
    def _next_steps(cls, focus_track: IntelligenceTrack | None, strongest_track: IntelligenceTrack | None, weak_areas: list[dict]) -> list[str]:
        steps = []
        if focus_track:
            steps.append(f'Priority: {focus_track.next_step}')
        if weak_areas:
            first = weak_areas[0]
            label = str(first.get('label') or 'weak area').strip()
            steps.append(f'Fix this weak area next: {label}.')
        if strongest_track:
            steps.append(f'Use {strongest_track.label} as a confidence booster after the priority task.')
        steps.append('End the session by reviewing one mistake and one improvement.')
        return steps[:4]

    @classmethod
    def build(cls, student_id: int) -> dict:
        analytics = StudentProgressAnalyticsService.overview(student_id)
        tracks = [cls._track_plan(track) for track in analytics.get('tracks') or []]
        active_tracks = [track for track in tracks if track.items_count > 0]
        focus_track = min(
            active_tracks or tracks,
            key=lambda track: (track.avg_score if track.items_count > 0 else 101, -track.weak_count, track.label),
        ) if tracks else None
        strongest_track = max(
            active_tracks or tracks,
            key=lambda track: (track.avg_score, track.best_score, track.completed_count),
        ) if tracks else None
        weak_areas = analytics.get('weak_areas') or []

        recommendations: list[dict] = []
        if focus_track:
            recommendations.append({
                'title': f'Primary focus: {focus_track.label}',
                'summary': focus_track.action,
                'reason': focus_track.reason,
                'badge': f'{focus_track.confidence}% confidence',
                'track_key': focus_track.key,
                'priority': 'high',
            })
        if weak_areas:
            first_weak = weak_areas[0]
            recommendations.append({
                'title': 'Repair the weakest area first',
                'summary': str(first_weak.get('label') or 'Weak area'),
                'reason': str(first_weak.get('note') or 'This issue is reducing your overall progress.'),
                'badge': f"{round(float(first_weak.get('score') or 0))}%",
                'track_key': str(first_weak.get('track') or '').strip().lower(),
                'priority': 'high',
            })
        if strongest_track:
            recommendations.append({
                'title': f'Keep {strongest_track.label} as your strength track',
                'summary': 'Use your strongest module to maintain confidence while you fix weaker areas.',
                'reason': f'{strongest_track.label} is currently your most stable track.',
                'badge': f'{strongest_track.avg_score:.0f}% avg',
                'track_key': strongest_track.key,
                'priority': 'medium',
            })
        for track in tracks:
            if track.linked_track and track.avg_score < 72:
                recommendations.append({
                    'title': f'Cross-module support: {track.linked_track}',
                    'summary': f'Use {track.linked_track} to support {track.label.lower()}.',
                    'reason': track.linked_reason,
                    'badge': 'Linked',
                    'track_key': track.key,
                    'priority': 'medium',
                })
                break

        adaptive_tracks = []
        for track in tracks:
            adaptive_tracks.append({
                'key': track.key,
                'label': track.label,
                'current_band': cls._nice_band(track.current_band),
                'recommended_band': cls._nice_band(track.recommended_band),
                'confidence': track.confidence,
                'avg_score': track.avg_score,
                'action': track.action,
                'reason': track.reason,
                'tutor_tip': track.tutor_tip,
                'items_count': track.items_count,
                'next_step': track.next_step,
                'weak_skills': track.weak_skills,
                'linked_track': track.linked_track,
                'linked_reason': track.linked_reason,
            })

        overall_confidence = cls._overall_confidence(tracks)
        readiness = round(float(analytics.get('summary', {}).get('overall_avg_score') or 0.0), 1)
        next_steps = cls._next_steps(focus_track, strongest_track, weak_areas)
        learning_path = cls._learning_path(tracks)
        cross_module = cls._cross_module_map(tracks)

        return {
            'summary': {
                'focus_track': focus_track.label if focus_track else 'No track yet',
                'strongest_track': strongest_track.label if strongest_track else 'No track yet',
                'readiness_score': readiness,
                'recommendations_count': len(recommendations[:5]),
                'confidence_score': overall_confidence,
            },
            'recommendations': recommendations[:5],
            'adaptive_tracks': adaptive_tracks,
            'tutor': {
                'title': 'AI Tutor',
                'summary': 'One clear next move, one weak-area fix, and one confidence builder.',
                'message': 'The tutor now combines weak areas, recent scores, completion history, and cross-module signals.',
                'drills': next_steps,
                'coach_tip': focus_track.tutor_tip if focus_track else 'Complete one task first so the tutor can adapt the next step.',
            },
            'next_steps': next_steps,
            'learning_path': learning_path,
            'cross_module': cross_module,
            'track_map': {track['key']: track for track in adaptive_tracks},
        }

    @classmethod
    def for_track(cls, student_id: int, track_key: str) -> dict:
        payload = cls.build(student_id)
        return payload.get('track_map', {}).get(track_key, {
            'key': track_key,
            'label': track_key.title(),
            'current_band': 'Foundation',
            'recommended_band': 'Foundation',
            'confidence': 38,
            'avg_score': 0.0,
            'action': f'Start your first {track_key} activity.',
            'reason': 'No tracked activity exists yet, so the system cannot personalize difficulty.',
            'tutor_tip': 'Complete one activity first, then the AI tutor will adapt the next step.',
            'items_count': 0,
            'next_step': f'Complete one guided {track_key} activity.',
            'weak_skills': TRACK_SKILL_MAP.get(track_key, ['core skill'])[:2],
            'linked_track': None,
            'linked_reason': None,
        })
