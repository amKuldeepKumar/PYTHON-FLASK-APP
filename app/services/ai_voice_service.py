from __future__ import annotations

import random
from datetime import datetime


def _day_period(now: datetime | None = None) -> str:
    now = now or datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _welcome_variants(username: str, is_new: bool = False) -> list[str]:
    period = _day_period()
    if is_new:
        return [
            f"Good {period}, {username}. Welcome to Fluencify. Your English journey starts today.",
            f"Hello {username}. Good {period}. Your account is ready and your English journey begins now.",
            f"Welcome {username}. Wishing you a great {period}. Let's build your English confidence together.",
        ]

    return [
        f"Good {period}, {username}. Welcome back to Fluencify.",
        f"Hello {username}. Good {period}. Ready for your next English practice session?",
        f"Welcome back, {username}. Hope you're having a great {period}.",
        f"Hi {username}. Good {period}. Let's continue your English learning journey.",
    ]


def login_voice_payload(username: str, accent: str = "en-IN", last_activity: str | None = None, is_new: bool = False) -> dict:
    base = random.choice(_welcome_variants(username=username, is_new=is_new))
    message = base
    if last_activity:
        message += f" {last_activity}"

    return {
        "enabled": True,
        "event": "login",
        "accent": accent,
        "text": message,
        "created_at": datetime.utcnow().isoformat(),
    }


def registration_voice_payload(username: str, accent: str = "en-IN") -> dict:
    return {
        "enabled": True,
        "event": "registration",
        "accent": accent,
        "text": random.choice(_welcome_variants(username=username, is_new=True)),
        "created_at": datetime.utcnow().isoformat(),
    }


def placement_test_script() -> list[dict]:
    return [
        {
            "level": "warmup",
            "question": "Tell me about yourself in a few sentences.",
            "expected_seconds": 25,
        },
        {
            "level": "intermediate",
            "question": "Describe a challenge you faced and how you solved it.",
            "expected_seconds": 30,
        },
        {
            "level": "intermediate",
            "question": "Do you think online learning is better than classroom learning? Why?",
            "expected_seconds": 30,
        },
        {
            "level": "advanced",
            "question": "How should young people prepare for a changing job market?",
            "expected_seconds": 35,
        },
    ]


def placement_result_from_scores(scores: list[dict]) -> dict:
    if not scores:
        return {
            "level": "beginner",
            "recommended_course_tier": "beginner",
            "summary": "Not enough answers were recorded, so a beginner course is recommended.",
        }

    overall = int(round(sum(s.get("accuracy_score", 0) for s in scores) / len(scores)))
    grammar = int(round(sum(s.get("grammar_score", 0) for s in scores) / len(scores)))
    clarity = int(round(sum(s.get("clarity_score", 0) for s in scores) / len(scores)))
    confidence = int(round(sum(s.get("confidence_score", 0) for s in scores) / len(scores)))

    if overall >= 78 and grammar >= 70 and clarity >= 70:
        level = "advanced"
        course_tier = "advanced"
    elif overall >= 58:
        level = "intermediate"
        course_tier = "intermediate"
    else:
        level = "beginner"
        course_tier = "beginner"

    return {
        "level": level,
        "recommended_course_tier": course_tier,
        "overall_score": overall,
        "grammar_score": grammar,
        "clarity_score": clarity,
        "confidence_score": confidence,
        "summary": (
            f"Suggested level: {level.title()}. "
            f"Scores — Overall {overall}, Grammar {grammar}, Clarity {clarity}, Confidence {confidence}."
        ),
    }


def speaking_feedback_prompt(answer_text: str, target_language: str = "en") -> dict:
    answer_text = (answer_text or "").strip()
    word_count = len(answer_text.split())

    if not answer_text:
        return {
            "accuracy_score": 20,
            "grammar_score": 20,
            "clarity_score": 20,
            "confidence_score": 20,
            "feedback": "No spoken response was detected. Try speaking slowly and clearly.",
            "language": target_language,
        }

    accuracy = min(90, 35 + word_count * 2)
    grammar = 50 if word_count >= 5 else 30
    clarity = 60 if word_count >= 8 else 35
    confidence = 55 if word_count >= 10 else 30

    return {
        "accuracy_score": accuracy,
        "grammar_score": grammar,
        "clarity_score": clarity,
        "confidence_score": confidence,
        "feedback": "Your response is understandable. Try longer sentences and stronger grammar variety.",
        "language": target_language,
    }
