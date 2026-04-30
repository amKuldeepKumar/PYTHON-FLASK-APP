from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from ..extensions import db
from ..models.student_placement_result import StudentPlacementResult
from .ai_voice_service import speaking_feedback_prompt

RESULT_VERSION = "phase-b-v1"


PROFILE_FIELDS = [
    {
        "name": "goal",
        "label": "What is your main goal?",
        "type": "select",
        "required": True,
        "options": [
            ("daily_speaking", "Daily speaking confidence"),
            ("job_interview", "Job / interview preparation"),
            ("school_success", "School / academic improvement"),
            ("grammar_focus", "Grammar improvement"),
            ("writing_focus", "Writing improvement"),
            ("overall_growth", "Overall English growth"),
        ],
    },
    {
        "name": "comfort_level",
        "label": "How comfortable are you in English right now?",
        "type": "select",
        "required": True,
        "options": [
            ("beginner", "I need a simple start"),
            ("growing", "I understand some English but hesitate"),
            ("confident", "I can manage most situations"),
        ],
    },
    {
        "name": "focus_skill",
        "label": "Which skill do you want to improve first?",
        "type": "select",
        "required": True,
        "options": [
            ("speaking", "Speaking"),
            ("grammar", "Grammar"),
            ("reading", "Reading"),
            ("writing", "Writing"),
            ("listening", "Listening"),
            ("confidence", "Confidence"),
        ],
    },
    {
        "name": "study_style",
        "label": "What kind of learning feels best for you?",
        "type": "select",
        "required": True,
        "options": [
            ("guided", "Step-by-step guidance"),
            ("practice", "Practice and repetition"),
            ("mixed", "A mixed path"),
        ],
    },
]

MCQ_QUESTIONS = [
    {
        "key": "grammar_1",
        "skill": "grammar",
        "label": "Choose the correct sentence.",
        "options": [
            ("a", "She go to school every day."),
            ("b", "She goes to school every day."),
            ("c", "She going to school every day."),
        ],
        "correct": "b",
    },
    {
        "key": "vocab_1",
        "skill": "vocabulary",
        "label": "Choose the best word.",
        "options": [
            ("a", "I am very excite."),
            ("b", "I am very exciting."),
            ("c", "I am very excited."),
        ],
        "correct": "c",
    },
    {
        "key": "reading_1",
        "skill": "reading",
        "label": "Complete the sentence correctly.",
        "options": [
            ("a", "He don't like coffee."),
            ("b", "He doesn't like coffee."),
            ("c", "He not like coffee."),
        ],
        "correct": "b",
    },
    {
        "key": "grammar_2",
        "skill": "grammar",
        "label": "Choose the correct question.",
        "options": [
            ("a", "Where you are going?"),
            ("b", "Where are you going?"),
            ("c", "Where going you are?"),
        ],
        "correct": "b",
    },
    {
        "key": "vocab_2",
        "skill": "vocabulary",
        "label": "Pick the best word for this sentence: 'I need to ___ my homework before dinner.'",
        "options": [
            ("a", "finish"),
            ("b", "finishing"),
            ("c", "finished"),
        ],
        "correct": "a",
    },
    {
        "key": "reading_2",
        "skill": "reading",
        "label": "Read the meaning and choose the correct sentence.",
        "options": [
            ("a", "Yesterday I go to market."),
            ("b", "Yesterday I went to the market."),
            ("c", "Yesterday I going to market."),
        ],
        "correct": "b",
    },
]

SHORT_ANSWER_QUESTIONS = [
    {
        "key": "intro",
        "skill": "speaking",
        "level": "warmup",
        "question": "Introduce yourself in a few sentences.",
        "placeholder": "Write as if you are speaking.",
        "expected_seconds": 25,
    },
    {
        "key": "challenge",
        "skill": "writing",
        "level": "intermediate",
        "question": "Describe one challenge you faced and how you solved it.",
        "placeholder": "Use 3-5 clear sentences.",
        "expected_seconds": 30,
    },
    {
        "key": "opinion",
        "skill": "reading",
        "level": "intermediate",
        "question": "Is online learning better than classroom learning? Give your opinion.",
        "placeholder": "Give a simple reason with an example.",
        "expected_seconds": 30,
    },
    {
        "key": "future",
        "skill": "confidence",
        "level": "advanced",
        "question": "How should young people prepare for a changing job market?",
        "placeholder": "Explain your idea in a few connected sentences.",
        "expected_seconds": 35,
    },
]

TRACK_LABELS = {
    "speaking": "Speaking",
    "reading": "Reading",
    "writing": "Writing",
    "listening": "Listening",
    "grammar": "Grammar",
    "confidence": "Confidence",
}

GOAL_RULES = {
    "daily_speaking": {
        "tracks": ["speaking", "confidence", "reading"],
        "keywords": ["spoken english", "speaking", "conversation", "english basic"],
        "titles": {
            "basic": ["Spoken English", "English Basic", "Reading Basics"],
            "intermediate": ["Spoken English", "English Intermediate", "Interview Prep"],
            "advanced": ["Advanced Speaking", "Interview Prep", "English Advanced"],
        },
    },
    "job_interview": {
        "tracks": ["speaking", "writing", "listening"],
        "keywords": ["interview", "spoken english", "speaking", "job"],
        "titles": {
            "basic": ["Spoken English", "Interview Prep", "English Basic"],
            "intermediate": ["Interview Prep", "Spoken English", "English Intermediate"],
            "advanced": ["Interview Prep", "Advanced Speaking", "English Advanced"],
        },
    },
    "school_success": {
        "tracks": ["reading", "writing", "grammar"],
        "keywords": ["reading", "writing", "english", "foundation"],
        "titles": {
            "basic": ["English Basic", "Reading Basics", "Writing Basics"],
            "intermediate": ["English Intermediate", "Writing Practice", "Reading Practice"],
            "advanced": ["English Advanced", "Writing Practice", "Advanced Reading"],
        },
    },
    "grammar_focus": {
        "tracks": ["grammar", "writing", "reading"],
        "keywords": ["grammar", "writing", "english"],
        "titles": {
            "basic": ["English Basic", "Writing Basics", "Reading Basics"],
            "intermediate": ["English Intermediate", "Writing Practice", "Spoken English"],
            "advanced": ["English Advanced", "Advanced Speaking", "Writing Practice"],
        },
    },
    "writing_focus": {
        "tracks": ["writing", "reading", "grammar"],
        "keywords": ["writing", "reading", "english"],
        "titles": {
            "basic": ["Writing Basics", "English Basic", "Reading Basics"],
            "intermediate": ["Writing Practice", "English Intermediate", "Reading Practice"],
            "advanced": ["English Advanced", "Writing Practice", "Interview Prep"],
        },
    },
    "overall_growth": {
        "tracks": ["speaking", "reading", "writing"],
        "keywords": ["english", "spoken english", "reading", "writing"],
        "titles": {
            "basic": ["English Basic", "Spoken English", "Reading Basics"],
            "intermediate": ["English Intermediate", "Spoken English", "Writing Practice"],
            "advanced": ["English Advanced", "Interview Prep", "Advanced Speaking"],
        },
    },
}

COMFORT_BONUS = {"beginner": -6, "growing": 0, "confident": 5}
STUDY_STYLE_BONUS = {"guided": 0, "practice": 2, "mixed": 3}


@dataclass
class PlacementComputation:
    payload: dict


class PlacementTestService:
    @classmethod
    def form_blueprint(cls) -> dict:
        return {
            "version": RESULT_VERSION,
            "profile_fields": PROFILE_FIELDS,
            "mcq_questions": MCQ_QUESTIONS,
            "short_answer_questions": SHORT_ANSWER_QUESTIONS,
            "total_questions": len(MCQ_QUESTIONS) + len(SHORT_ANSWER_QUESTIONS),
        }

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return default

    @classmethod
    def _normalise_profile(cls, form_data) -> dict:
        profile = {}
        for field in PROFILE_FIELDS:
            name = field["name"]
            profile[name] = (form_data.get(name) or "").strip().lower()
        return profile

    @classmethod
    def _mcq_results(cls, form_data) -> tuple[list[dict], dict, int]:
        per_skill = {"grammar": [], "vocabulary": [], "reading": []}
        rows = []
        total_correct = 0
        for item in MCQ_QUESTIONS:
            selected = (form_data.get(f"mcq_{item['key']}") or "").strip().lower()
            is_correct = selected == item["correct"]
            score = 100 if is_correct else 35 if selected else 0
            per_skill.setdefault(item["skill"], []).append(score)
            rows.append({
                "skill": item["skill"],
                "question": item["label"],
                "selected": selected,
                "correct": item["correct"],
                "is_correct": is_correct,
                "score": score,
            })
            if is_correct:
                total_correct += 1
        return rows, per_skill, total_correct

    @classmethod
    def _short_answer_results(cls, form_data) -> tuple[list[dict], dict]:
        rows = []
        per_skill = {"speaking": [], "writing": [], "reading": [], "confidence": [], "grammar": [], "listening": []}
        for item in SHORT_ANSWER_QUESTIONS:
            answer = (form_data.get(f"answer_{item['key']}") or "").strip()
            feedback = speaking_feedback_prompt(answer, target_language="en")
            word_count = len(answer.split())
            structure_bonus = 0
            if any(marker in answer.lower() for marker in ["because", "but", "so", "when", "if"]):
                structure_bonus += 8
            if word_count >= 25:
                structure_bonus += 10
            elif word_count >= 14:
                structure_bonus += 5
            elif word_count <= 3:
                structure_bonus -= 10
            grammar_score = max(10, min(100, cls._safe_int(feedback.get("grammar_score")) + structure_bonus))
            clarity_score = max(10, min(100, cls._safe_int(feedback.get("clarity_score")) + structure_bonus))
            confidence_score = max(10, min(100, cls._safe_int(feedback.get("confidence_score")) + (4 if word_count >= 18 else 0)))
            overall = max(10, min(100, cls._safe_int(mean([
                cls._safe_int(feedback.get("accuracy_score")),
                grammar_score,
                clarity_score,
                confidence_score,
            ]))))
            rows.append({
                "skill": item["skill"],
                "question": item["question"],
                "answer": answer,
                "word_count": word_count,
                "score": overall,
                "grammar_score": grammar_score,
                "clarity_score": clarity_score,
                "confidence_score": confidence_score,
                "feedback": feedback.get("feedback") or "",
            })
            per_skill[item["skill"]].append(overall)
            per_skill["grammar"].append(grammar_score)
            per_skill["listening"].append(50 if answer else 20)
        return rows, per_skill

    @classmethod
    def _skill_scores(cls, profile: dict, mcq_skill_scores: dict, short_skill_scores: dict) -> dict:
        comfort = profile.get("comfort_level") or "growing"
        focus_skill = profile.get("focus_skill") or "speaking"
        study_style = profile.get("study_style") or "guided"

        def avg(values, fallback=0):
            valid = [cls._safe_int(v) for v in values if v is not None]
            if not valid:
                return fallback
            return cls._safe_int(mean(valid))

        grammar = avg((mcq_skill_scores.get("grammar") or []) + (short_skill_scores.get("grammar") or []), 30)
        vocabulary = avg(mcq_skill_scores.get("vocabulary") or [], 30)
        reading = avg((mcq_skill_scores.get("reading") or []) + (short_skill_scores.get("reading") or []), 35)
        writing = avg(short_skill_scores.get("writing") or [], 30)
        speaking = avg(short_skill_scores.get("speaking") or [], 30)
        listening = avg(short_skill_scores.get("listening") or [], 35)
        confidence = avg(short_skill_scores.get("confidence") or [], 30)
        confidence = max(10, min(100, confidence + COMFORT_BONUS.get(comfort, 0) + (4 if focus_skill == "confidence" else 0)))

        if focus_skill in {"speaking", "grammar", "reading", "writing", "listening", "confidence"}:
            focus_bonus = 4 if study_style == "mixed" else (2 if study_style == "practice" else 0)
            if focus_skill == "grammar":
                grammar = max(10, min(100, grammar + focus_bonus))
            elif focus_skill == "confidence":
                confidence = max(10, min(100, confidence + focus_bonus))
            elif focus_skill == "speaking":
                speaking = max(10, min(100, speaking + focus_bonus))
            elif focus_skill == "reading":
                reading = max(10, min(100, reading + focus_bonus))
            elif focus_skill == "writing":
                writing = max(10, min(100, writing + focus_bonus))
            elif focus_skill == "listening":
                listening = max(10, min(100, listening + focus_bonus))

        overall = cls._safe_int(mean([
            grammar,
            vocabulary,
            reading,
            writing,
            speaking,
            listening,
            confidence,
        ]) + STUDY_STYLE_BONUS.get(study_style, 0))
        overall = max(10, min(100, overall))
        return {
            "grammar": grammar,
            "vocabulary": vocabulary,
            "reading": reading,
            "writing": writing,
            "speaking": speaking,
            "listening": listening,
            "confidence": confidence,
            "overall": overall,
        }

    @classmethod
    def _level_from_scores(cls, scores: dict, profile: dict) -> str:
        overall = cls._safe_int(scores.get("overall"))
        comfort = profile.get("comfort_level") or "growing"
        if overall >= 80 and min(scores.get("grammar", 0), scores.get("reading", 0), scores.get("writing", 0)) >= 65:
            level = "advanced"
        elif overall >= 58:
            level = "intermediate"
        else:
            level = "basic"
        if comfort == "beginner" and overall < 72:
            return "basic"
        return level

    @classmethod
    def _strengths_and_weaknesses(cls, scores: dict) -> tuple[list[dict], list[dict]]:
        visible = [
            ("grammar", scores.get("grammar", 0)),
            ("vocabulary", scores.get("vocabulary", 0)),
            ("reading", scores.get("reading", 0)),
            ("writing", scores.get("writing", 0)),
            ("speaking", scores.get("speaking", 0)),
            ("listening", scores.get("listening", 0)),
            ("confidence", scores.get("confidence", 0)),
        ]
        ordered = sorted(visible, key=lambda row: (row[1], row[0]))
        strengths = [
            {"key": key, "label": TRACK_LABELS.get(key, key.title()), "score": cls._safe_int(score)}
            for key, score in sorted(visible, key=lambda row: (-row[1], row[0]))[:3]
        ]
        weak_areas = [
            {"key": key, "label": TRACK_LABELS.get(key, key.title()), "score": cls._safe_int(score)}
            for key, score in ordered[:3]
        ]
        return strengths, weak_areas

    @classmethod
    def _recommendation_payload(cls, level: str, profile: dict, strengths: list[dict], weak_areas: list[dict]) -> dict:
        goal = profile.get("goal") or "overall_growth"
        focus_skill = profile.get("focus_skill") or "speaking"
        rules = GOAL_RULES.get(goal, GOAL_RULES["overall_growth"])

        recommended_tracks = list(dict.fromkeys((rules.get("tracks") or []) + [focus_skill]))
        recommended_titles = list(rules.get("titles", {}).get(level, []))
        recommended_keywords = list(dict.fromkeys((rules.get("keywords") or []) + recommended_titles + [focus_skill]))

        weakest = weak_areas[0]["label"] if weak_areas else "Foundation"
        strongest = strengths[0]["label"] if strengths else "Effort"

        next_steps = [
            f"Start with a {level.title()}-level course that matches your goal.",
            f"Repair {weakest.lower()} first with short daily practice.",
            f"Use {strongest.lower()} as your confidence booster while learning.",
        ]
        if goal == "job_interview":
            next_steps.insert(1, "Add interview-style speaking practice after your foundation work.")
        elif goal == "daily_speaking":
            next_steps.insert(1, "Choose a speaking-first course and practise short answers every day.")
        elif goal in {"writing_focus", "school_success"}:
            next_steps.insert(1, "Do one writing or reading task after every lesson to lock in accuracy.")

        path_labels = {
            "basic": ("Start now", "Next", "Later"),
            "intermediate": ("Start now", "Build next", "Advance later"),
            "advanced": ("Start now", "Deepen next", "Master later"),
        }[level]
        learning_path = []
        for idx, title in enumerate(recommended_titles[:3], start=1):
            learning_path.append({
                "step": idx,
                "stage": path_labels[idx - 1],
                "title": title,
                "reason": (
                    f"This supports your {goal.replace('_', ' ')} goal and helps improve {weakest.lower()}."
                    if idx == 1 else
                    f"This continues your path after your {level} foundation becomes stronger."
                ),
            })

        fit_summary = (
            f"Best path for you: {recommended_titles[0] if recommended_titles else 'English Basic'}. "
            f"You are strongest in {strongest.lower()} and need the most support in {weakest.lower()}."
        )
        return {
            "recommended_tracks": recommended_tracks,
            "recommended_titles": recommended_titles,
            "recommended_keywords": recommended_keywords,
            "next_steps": next_steps[:4],
            "learning_path": learning_path,
            "fit_summary": fit_summary,
        }

    @classmethod
    def evaluate_submission(cls, form_data) -> dict:
        profile = cls._normalise_profile(form_data)
        mcq_rows, mcq_skill_scores, mcq_total_correct = cls._mcq_results(form_data)
        answer_rows, short_skill_scores = cls._short_answer_results(form_data)
        scores = cls._skill_scores(profile, mcq_skill_scores, short_skill_scores)
        level = cls._level_from_scores(scores, profile)
        strengths, weak_areas = cls._strengths_and_weaknesses(scores)
        recommendations = cls._recommendation_payload(level, profile, strengths, weak_areas)

        summary = (
            f"Recommended level: {level.title()}. Overall score {scores['overall']}/100. "
            f"Best area: {strengths[0]['label'] if strengths else 'Effort'}. "
            f"Main repair area: {weak_areas[0]['label'] if weak_areas else 'Foundation'}."
        )

        payload = {
            "version": RESULT_VERSION,
            "target_language": "english",
            "goal": profile.get("goal"),
            "focus_skill": profile.get("focus_skill"),
            "comfort_level": profile.get("comfort_level"),
            "study_style": profile.get("study_style"),
            "level": level,
            "recommended_level": level,
            "overall_score": scores["overall"],
            "grammar_score": scores["grammar"],
            "vocabulary_score": scores["vocabulary"],
            "reading_score": scores["reading"],
            "writing_score": scores["writing"],
            "speaking_score": scores["speaking"],
            "listening_score": scores["listening"],
            "confidence_score": scores["confidence"],
            "mcq_score": mcq_total_correct,
            "mcq_total": len(MCQ_QUESTIONS),
            "recommended_tracks": recommendations["recommended_tracks"],
            "recommended_titles": recommendations["recommended_titles"],
            "recommended_keywords": recommendations["recommended_keywords"],
            "strengths": strengths,
            "weak_areas": weak_areas,
            "next_steps": recommendations["next_steps"],
            "learning_path": recommendations["learning_path"],
            "answers": answer_rows + mcq_rows,
            "profile_answers": profile,
            "skill_scores": scores,
            "summary": summary,
            "fit_summary": recommendations["fit_summary"],
        }
        return payload

    @classmethod
    def save_result(cls, student_id: int, result: dict) -> StudentPlacementResult:
        record = StudentPlacementResult(
            student_id=student_id,
            version=str(result.get("version") or RESULT_VERSION),
            target_language=str(result.get("target_language") or "english"),
            goal=result.get("goal"),
            focus_skill=result.get("focus_skill"),
            comfort_level=result.get("comfort_level"),
            overall_score=cls._safe_int(result.get("overall_score")),
            grammar_score=cls._safe_int(result.get("grammar_score")),
            vocabulary_score=cls._safe_int(result.get("vocabulary_score")),
            reading_score=cls._safe_int(result.get("reading_score")),
            writing_score=cls._safe_int(result.get("writing_score")),
            speaking_score=cls._safe_int(result.get("speaking_score")),
            listening_score=cls._safe_int(result.get("listening_score")),
            confidence_score=cls._safe_int(result.get("confidence_score")),
            mcq_score=cls._safe_int(result.get("mcq_score")),
            mcq_total=cls._safe_int(result.get("mcq_total")),
            level=str(result.get("level") or "basic"),
            recommended_level=str(result.get("recommended_level") or result.get("level") or "basic"),
            summary=result.get("summary"),
            fit_summary=result.get("fit_summary"),
        )
        record.recommended_tracks = result.get("recommended_tracks") or []
        record.recommended_titles = result.get("recommended_titles") or []
        record.recommended_keywords = result.get("recommended_keywords") or []
        record.strengths = result.get("strengths") or []
        record.weak_areas = result.get("weak_areas") or []
        record.next_steps = result.get("next_steps") or []
        record.learning_path = result.get("learning_path") or []
        record.answers = result.get("answers") or []
        record.profile_answers = result.get("profile_answers") or {}
        record.skill_scores = result.get("skill_scores") or {}
        db.session.add(record)
        db.session.commit()
        return record

    @classmethod
    def latest_result_for_student(cls, student_id: int) -> StudentPlacementResult | None:
        return (
            StudentPlacementResult.query
            .filter_by(student_id=student_id)
            .order_by(StudentPlacementResult.created_at.desc(), StudentPlacementResult.id.desc())
            .first()
        )

    @classmethod
    def recent_history(cls, student_id: int, limit: int = 5) -> list[StudentPlacementResult]:
        return (
            StudentPlacementResult.query
            .filter_by(student_id=student_id)
            .order_by(StudentPlacementResult.created_at.desc(), StudentPlacementResult.id.desc())
            .limit(max(1, min(limit, 10)))
            .all()
        )
