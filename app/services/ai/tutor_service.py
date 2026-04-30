from __future__ import annotations

from dataclasses import dataclass

from .rule_service import AIRuleService


@dataclass
class TutorReply:
    ok: bool
    message: str
    guidance: str
    citations: list[str]


class TutorAIService:
    @classmethod
    def respond(cls, *, lesson_title: str, lesson_body: str, active_question: str, student_message: str, level: str | None = None) -> TutorReply:
        body = (lesson_body or "").strip()
        question = (active_question or "").strip()
        student = (student_message or "").strip()
        if not body and not question:
            return TutorReply(False, "Lesson context is missing.", "Open a lesson before using Tutor AI.", [])
        allowed, reason = AIRuleService.guard_learning_scope(student)
        if not allowed:
            return TutorReply(False, reason or "Off-topic request rejected.", "Ask about the current lesson, vocabulary, grammar, or answer structure.", [])
        citations = []
        if lesson_title:
            citations.append(f"Lesson: {lesson_title}")
        if question:
            citations.append(f"Question: {question}")
        guidance = f"Stay inside the lesson. Level: {(level or 'general').title()}. Use short, clear teaching steps based only on the provided lesson context."
        message = f"Based on the current lesson, here is focused help: {student[:240] if student else 'Review the main idea and answer only from the lesson text.'}"
        return TutorReply(True, message, guidance, citations)
