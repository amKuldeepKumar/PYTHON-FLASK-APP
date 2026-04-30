from __future__ import annotations

from copy import deepcopy


GOAL_LABELS = {
    "daily_speaking": "Daily speaking confidence",
    "job_interview": "Job / interview preparation",
    "school_success": "School / academic improvement",
    "grammar_focus": "Grammar improvement",
    "writing_focus": "Writing improvement",
    "overall_growth": "Overall English growth",
}

TRACK_LABELS = {
    "speaking": "Speaking",
    "reading": "Reading",
    "writing": "Writing",
    "listening": "Listening",
    "grammar": "Grammar",
    "confidence": "Confidence",
    "interview": "Interview Prep",
}


class CourseRecommendationService:
    @staticmethod
    def _title(value: str | None, fallback: str = "") -> str:
        text = str(value or "").strip().replace("_", " ")
        return text.title() if text else fallback

    @staticmethod
    def _safe_list(value):
        return value if isinstance(value, list) else []

    @staticmethod
    def _safe_dict(value):
        return value if isinstance(value, dict) else {}

    @classmethod
    def goal_label(cls, goal: str | None) -> str:
        return GOAL_LABELS.get(str(goal or "").strip().lower(), cls._title(goal, "Overall English growth"))

    @classmethod
    def track_label(cls, track: str | None) -> str:
        return TRACK_LABELS.get(str(track or "").strip().lower(), cls._title(track, "English"))

    @classmethod
    def course_fit_for_card(cls, card: dict, result: dict | None) -> dict:
        if not result or not card:
            return {
                "score": 0,
                "label": "Take test first",
                "badge_class": "library-badge--level",
                "reason": "Take the placement test to unlock your best-fit path.",
                "match_label": "Unknown",
            }

        title = str(card.get("course_title") or card.get("card_title") or "").lower()
        difficulty = str(card.get("difficulty") or "").strip().lower()
        track = str(card.get("track_type") or card.get("skill_code") or "").strip().lower()
        target_level = str(result.get("recommended_level") or result.get("level") or "").strip().lower()
        preferred_tracks = {str(v).strip().lower() for v in cls._safe_list(result.get("recommended_tracks")) if str(v).strip()}
        preferred_titles = {str(v).strip().lower() for v in cls._safe_list(result.get("recommended_titles")) if str(v).strip()}
        preferred_keywords = {str(v).strip().lower() for v in cls._safe_list(result.get("recommended_keywords")) if str(v).strip()}

        score = 32
        reasons = []

        if target_level and difficulty == target_level:
            score += 28
            reasons.append(f"Matches your {target_level.title()} level")
        elif target_level and difficulty:
            level_rank = {"basic": 1, "intermediate": 2, "advanced": 3}
            gap = abs(level_rank.get(difficulty, 2) - level_rank.get(target_level, 2))
            if gap == 1:
                score += 10
                reasons.append("Close to your current level")
            else:
                score -= 6
                reasons.append("May feel too early or too advanced right now")

        if preferred_tracks and track in preferred_tracks:
            score += 24
            reasons.append(f"Supports your focus on {cls.track_label(track).lower()}")
        if preferred_titles and any(label in title for label in preferred_titles):
            score += 18
            reasons.append("Named in your recommended path")
        if preferred_keywords and any(keyword in title for keyword in preferred_keywords):
            score += 10
            reasons.append("Matches your test goal and keyword profile")
        if card.get("is_enrolled"):
            score += 6
            reasons.append("Already active in your account")
        if not card.get("is_premium"):
            score += 4

        score = max(0, min(int(score), 100))

        if score >= 80:
            label = "Best fit now"
            badge = "library-badge--track"
            match_label = "Start now"
        elif score >= 62:
            label = "Good next step"
            badge = "library-badge--level"
            match_label = "Next"
        else:
            label = "Better later"
            badge = "library-badge--premium"
            match_label = "Later"

        return {
            "score": score,
            "label": label,
            "badge_class": badge,
            "reason": ". ".join(reasons[:2]) if reasons else "Matched from your placement result.",
            "match_label": match_label,
        }

    @classmethod
    def annotate_cards(cls, cards: list[dict], result: dict | None) -> list[dict]:
        annotated = []
        for card in cards or []:
            copy = deepcopy(card)
            copy["recommendation_fit"] = cls.course_fit_for_card(copy, result)
            annotated.append(copy)
        return annotated

    @classmethod
    def learning_path_payload(cls, result: dict | None, cards: list[dict] | None = None) -> dict:
        payload = {
            "has_result": bool(result),
            "goal_label": "",
            "focus_skill_label": "",
            "current_level": "",
            "summary": "",
            "fit_summary": "",
            "weak_labels": [],
            "strong_labels": [],
            "next_steps": [],
            "path_steps": [],
            "recommended_now": None,
            "recommended_next": None,
            "recommended_later": None,
        }

        if not result:
            payload["summary"] = "Take the placement test to unlock your personalized learning path."
            return payload

        strengths = []
        for item in cls._safe_list(result.get("strengths")):
            if isinstance(item, dict) and item.get("label"):
                strengths.append(item["label"])
            elif isinstance(item, str) and item.strip():
                strengths.append(item.strip())

        weak_areas = []
        for item in cls._safe_list(result.get("weak_areas")):
            if isinstance(item, dict) and item.get("label"):
                weak_areas.append(item["label"])
            elif isinstance(item, str) and item.strip():
                weak_areas.append(item.strip())

        path_steps = []
        for step in cls._safe_list(result.get("learning_path")):
            if isinstance(step, dict):
                path_steps.append({
                    "step": step.get("step") or len(path_steps) + 1,
                    "stage": step.get("stage") or f"Stage {len(path_steps) + 1}",
                    "title": step.get("title") or "Recommended step",
                    "reason": step.get("reason") or "Follow this step in your path.",
                })
            elif isinstance(step, str) and step.strip():
                path_steps.append({
                    "step": len(path_steps) + 1,
                    "stage": f"Stage {len(path_steps) + 1}",
                    "title": step.strip(),
                    "reason": "Recommended from your placement result.",
                })

        payload.update({
            "goal_label": cls.goal_label(result.get("goal")),
            "focus_skill_label": cls.track_label(result.get("focus_skill")),
            "current_level": cls._title(result.get("recommended_level") or result.get("level"), "Basic"),
            "summary": result.get("summary") or "Your learning path is ready.",
            "fit_summary": result.get("fit_summary") or "",
            "weak_labels": weak_areas[:3],
            "strong_labels": strengths[:3],
            "next_steps": [str(v).strip() for v in cls._safe_list(result.get("next_steps")) if str(v).strip()][:3],
            "path_steps": path_steps[:3],
        })

        ranked = sorted(
            cls.annotate_cards(cards or [], result),
            key=lambda c: int((c.get("recommendation_fit") or {}).get("score") or 0),
            reverse=True,
        )
        course_ranked = [c for c in ranked if (c.get("card_kind") or "") == "course"]

        if len(course_ranked) > 0:
            payload["recommended_now"] = course_ranked[0]
        if len(course_ranked) > 1:
            payload["recommended_next"] = course_ranked[1]
        if len(course_ranked) > 2:
            payload["recommended_later"] = course_ranked[2]

        return payload
