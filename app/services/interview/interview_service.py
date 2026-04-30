from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import math
import re

from flask import current_app

from ...extensions import db
from ...models.interview_feedback import InterviewFeedback
from ...models.interview_profile import InterviewProfile
from ...models.interview_session import InterviewSession
from ...models.interview_turn import InterviewTurn


class InterviewService:
    PURPOSE_PERSONA = {
        'job': 'recruiter',
        'hr': 'hr_manager',
        'technical': 'technical_panel',
        'visa': 'visa_officer',
        'university': 'admission_officer',
        'embassy': 'visa_officer',
        'mock': 'recruiter',
    }

    PAUSE_MESSAGES = [
        'Take your time. You can continue in simple English.',
        'You are doing well. Add one clear example in your answer.',
        'Keep going. Tell me step by step.',
        'You can start with a short introduction and then add details.',
    ]

    @classmethod
    def create_profile_from_form(cls, student_id: int, course_id: int | None, form) -> InterviewProfile:
        purpose = (form.get('interview_purpose') or 'job').strip().lower()
        target_role = (form.get('target_role') or '').strip()
        title = target_role or f"{purpose.replace('_', ' ').title()} Interview"
        profile = InterviewProfile(
            student_id=student_id,
            course_id=course_id,
            title=title[:160],
            interview_purpose=purpose,
            target_role=target_role[:160] or None,
            industry=(form.get('industry') or '').strip()[:120] or None,
            company_name=(form.get('company_name') or '').strip()[:160] or None,
            country_target=(form.get('country_target') or '').strip()[:120] or None,
            english_level=(form.get('english_level') or 'intermediate').strip().lower(),
            difficulty_level=(form.get('difficulty_level') or 'medium').strip().lower(),
            interview_style=(form.get('interview_style') or 'realistic').strip().lower(),
            focus_area=(form.get('focus_area') or 'mixed').strip().lower(),
            resume_summary=(form.get('resume_summary') or '').strip() or None,
            job_description=(form.get('job_description') or '').strip() or None,
            extra_notes=(form.get('extra_notes') or '').strip() or None,
        )
        db.session.add(profile)
        db.session.flush()
        return profile

    @classmethod
    def start_session(cls, student_id: int, course_id: int | None, profile: InterviewProfile, retry_only_weak: bool = False) -> InterviewSession:
        plan = cls._build_plan(profile, retry_only_weak=retry_only_weak)
        session = InterviewSession(
            student_id=student_id,
            course_id=course_id,
            profile_id=profile.id,
            session_mode='practice_retry' if retry_only_weak else 'mock_interview',
            ai_persona=cls.PURPOSE_PERSONA.get(profile.interview_purpose, 'recruiter'),
            question_plan_json=json.dumps(plan),
            status='active',
            current_turn_no=1,
            completion_percent=0,
        )
        db.session.add(session)
        db.session.flush()

        first = plan[0]
        turn = InterviewTurn(
            session_id=session.id,
            turn_no=1,
            question_type=first.get('question_type') or 'intro',
            ai_question_text=first.get('question') or 'Tell me about yourself.',
        )
        db.session.add(turn)
        db.session.commit()
        return session

    @classmethod
    def recent_sessions(cls, student_id: int, course_id: int | None = None, limit: int = 10):
        query = InterviewSession.query.filter_by(student_id=student_id)
        if course_id is not None:
            query = query.filter_by(course_id=course_id)
        return query.order_by(InterviewSession.created_at.desc()).limit(limit).all()

    @classmethod
    def get_session(cls, student_id: int, session_id: int) -> InterviewSession | None:
        return InterviewSession.query.filter_by(id=session_id, student_id=student_id).first()

    @classmethod
    def current_turn(cls, session: InterviewSession) -> InterviewTurn | None:
        return session.turns.filter_by(turn_no=session.current_turn_no).first()

    @classmethod
    def submit_turn(
        cls,
        session: InterviewSession,
        answer_text: str,
        duration_seconds: int = 0,
        pause_count: int = 0,
        long_pause_count: int = 0,
    ) -> dict:
        turn = cls.current_turn(session)
        if not turn:
            raise ValueError('Interview turn not found.')
        if session.is_completed:
            raise ValueError('This interview session is already completed.')

        cleaned = (answer_text or '').strip()
        if not cleaned:
            raise ValueError('Please speak or type your answer before continuing.')

        metrics = cls._score_answer(cleaned, session.profile, turn.ai_question_text, duration_seconds, pause_count, long_pause_count)
        turn.student_answer_text = cleaned
        turn.live_transcript = cleaned
        turn.response_started_at = turn.response_started_at or datetime.utcnow()
        turn.response_ended_at = datetime.utcnow()
        turn.response_duration_seconds = max(0, int(duration_seconds or 0))
        turn.pause_count = max(0, int(pause_count or 0))
        turn.long_pause_detected = int(long_pause_count or 0) > 0
        turn.nudge_count = max(turn.nudge_count or 0, int(long_pause_count or 0))
        turn.ai_nudge_text = cls.pause_message(turn.nudge_count)
        turn.grammar_score = metrics['grammar_score']
        turn.fluency_score = metrics['fluency_score']
        turn.confidence_score = metrics['confidence_score']
        turn.relevance_score = metrics['relevance_score']
        turn.vocabulary_score = metrics['vocabulary_score']
        turn.professional_tone_score = metrics['professional_tone_score']
        turn.clarity_score = metrics['clarity_score']
        turn.turn_score = metrics['turn_score']
        turn.turn_feedback = metrics['turn_feedback']
        turn.improved_answer = metrics['improved_answer']
        turn.metrics_json = json.dumps(metrics)

        session.total_duration_seconds = int(session.total_duration_seconds or 0) + int(duration_seconds or 0)
        session.total_pause_count = int(session.total_pause_count or 0) + int(pause_count or 0)
        session.long_pause_count = int(session.long_pause_count or 0) + int(long_pause_count or 0)

        plan = session.question_plan
        next_index = int(session.current_turn_no)
        if next_index >= len(plan):
            session.status = 'completed'
            session.ended_at = datetime.utcnow()
            session.completion_percent = 100.0
            feedback = cls._finalize_feedback(session)
            db.session.commit()
            return {'completed': True, 'feedback': feedback, 'turn': turn}

        next_item = plan[next_index]
        session.current_turn_no = next_index + 1
        session.completion_percent = round((next_index / len(plan)) * 100, 1)
        next_turn = InterviewTurn(
            session_id=session.id,
            turn_no=session.current_turn_no,
            question_type=next_item.get('question_type') or 'general',
            ai_question_text=cls._adapt_next_question(next_item.get('question') or 'Can you explain more?', session.profile, turn, metrics),
            ai_followup_text=cls._followup_hint(turn, metrics),
        )
        db.session.add(next_turn)
        db.session.commit()
        return {'completed': False, 'turn': next_turn, 'previous_turn': turn}

    @classmethod
    def pause_message(cls, pause_level: int) -> str:
        if pause_level <= 0:
            return ''
        return cls.PAUSE_MESSAGES[(pause_level - 1) % len(cls.PAUSE_MESSAGES)]

    @classmethod
    def get_or_create_feedback(cls, session: InterviewSession) -> InterviewFeedback | None:
        feedback = session.latest_feedback
        if feedback or not session.is_completed:
            return feedback
        return cls._finalize_feedback(session)

    @classmethod
    def _build_plan(cls, profile: InterviewProfile, retry_only_weak: bool = False) -> list[dict]:
        role = profile.target_role or 'this position'
        purpose = profile.interview_purpose
        level = profile.english_level
        if retry_only_weak:
            return [
                {'question_type': 'retry', 'question': f'Give a short, stronger self-introduction for {role}.'},
                {'question_type': 'retry', 'question': f'Why are you a good fit for {role}?'},
                {'question_type': 'retry', 'question': 'Tell me about a challenge and how you solved it.'},
            ]

        if purpose in {'visa', 'embassy'}:
            base = [
                'Please introduce yourself and explain why you want to travel or study.',
                'Why did you choose this country or institution?',
                'Who is sponsoring you, and how will you manage expenses?',
                'What are your plans after completing your purpose abroad?',
            ]
        elif purpose == 'university':
            base = [
                'Please introduce yourself and your academic background.',
                'Why did you choose this course or university?',
                'What are your strengths as a student?',
                'What are your future career goals?',
            ]
        elif purpose == 'technical':
            base = [
                f'Please introduce yourself for the {role} role.',
                f'What technical skills make you suitable for {role}?',
                'Describe one project you worked on and your contribution.',
                'How do you solve problems when you are stuck?',
            ]
        else:
            base = [
                f'Tell me about yourself for the {role} interview.',
                f'Why do you want this {role} role?',
                'What is one strength and one weakness of yours?',
                'Describe a challenge you handled well.',
                'Do you have any final message for the interviewer?',
            ]

        if level == 'basic':
            base = [q.replace('Describe', 'Tell me simply about').replace('contribution', 'role').replace('suitable', 'good') for q in base]
        elif level == 'advanced':
            base = [f'{q} Please structure your answer clearly with one example.' for q in base]

        return [{'question_type': cls._guess_type(item), 'question': item} for item in base]

    @classmethod
    def _guess_type(cls, question: str) -> str:
        text = question.lower()
        if 'introduce' in text or 'yourself' in text:
            return 'intro'
        if 'strength' in text or 'weakness' in text:
            return 'hr'
        if 'project' in text or 'technical' in text:
            return 'technical'
        if 'why did you choose' in text or 'why do you want' in text:
            return 'motivation'
        if 'challenge' in text or 'problem' in text:
            return 'behavioral'
        return 'general'

    @classmethod
    def _adapt_next_question(cls, question: str, profile: InterviewProfile, previous_turn: InterviewTurn, metrics: dict) -> str:
        if metrics['turn_score'] < 5.5:
            return f"{question} You can answer in simple English with one example."
        if metrics['confidence_score'] < 5.5:
            return f"{question} Please answer confidently and in complete sentences."
        return question

    @classmethod
    def _followup_hint(cls, previous_turn: InterviewTurn, metrics: dict) -> str:
        if metrics['relevance_score'] < 5.5:
            return 'Stay closer to the question.'
        if metrics['fluency_score'] < 5.5:
            return 'Try speaking in longer complete sentences.'
        return 'Good. Keep your next answer clear and direct.'

    @classmethod
    def _score_answer(cls, answer: str, profile: InterviewProfile, question: str, duration_seconds: int, pause_count: int, long_pause_count: int) -> dict:
        words = re.findall(r"[A-Za-z']+", answer)
        word_count = len(words)
        unique_count = len({w.lower() for w in words})
        sentence_count = max(1, len(re.findall(r'[.!?]+', answer)) or 1)
        avg_sentence_len = word_count / sentence_count if sentence_count else word_count
        filler_count = len(re.findall(r'\b(um|uh|like|you know|actually|basically)\b', answer, flags=re.I))
        lower = answer.lower()
        grammar_score = 5.0 + min(3.0, avg_sentence_len / 8.0) + (0.5 if re.search(r'\b(i am|i have|i worked|i studied|because|therefore)\b', lower) else 0.0)
        fluency_score = 5.0 + min(2.5, word_count / 35.0) - min(2.0, filler_count * 0.4) - min(1.5, long_pause_count * 0.7)
        confidence_score = 5.0 + (0.8 if re.search(r'\b(i can|i will|i am confident|i believe|i handled|i led)\b', lower) else 0.0) - min(1.5, long_pause_count * 0.8)
        keywords = [w for w in re.findall(r"[A-Za-z']+", question.lower()) if len(w) > 4]
        overlap = sum(1 for w in set(words) if w.lower() in keywords)
        relevance_score = 4.5 + min(3.5, overlap) + (0.8 if profile.target_role and profile.target_role.lower() in lower else 0.0)
        vocabulary_score = 4.5 + min(3.0, unique_count / 18.0)
        professional_tone_score = 5.0 + (1.0 if re.search(r'\b(thank you|opportunity|responsibility|team|experience|learn)\b', lower) else 0.0)
        clarity_score = 5.0 + (0.8 if sentence_count >= 2 else 0.0) + (0.5 if re.search(r'\b(first|second|finally|for example)\b', lower) else 0.0)

        def clamp(value: float) -> float:
            return max(1.0, min(10.0, round(value, 1)))

        grammar_score = clamp(grammar_score)
        fluency_score = clamp(fluency_score)
        confidence_score = clamp(confidence_score)
        relevance_score = clamp(relevance_score)
        vocabulary_score = clamp(vocabulary_score)
        professional_tone_score = clamp(professional_tone_score)
        clarity_score = clamp(clarity_score)
        hesitation_score = clamp(10.0 - min(6.0, long_pause_count * 1.5 + pause_count * 0.4))

        turn_score = round(
            (fluency_score * 0.20)
            + (grammar_score * 0.15)
            + (confidence_score * 0.20)
            + (relevance_score * 0.20)
            + (vocabulary_score * 0.10)
            + (professional_tone_score * 0.10)
            + (hesitation_score * 0.05),
            1,
        )
        feedback_parts = []
        if relevance_score < 6:
            feedback_parts.append('Stay more focused on the interview question.')
        if fluency_score < 6:
            feedback_parts.append('Reduce long pauses and keep speaking in connected sentences.')
        if confidence_score < 6:
            feedback_parts.append('Use stronger and more confident phrases.')
        if vocabulary_score >= 7:
            feedback_parts.append('Your word choice is improving well.')
        if not feedback_parts:
            feedback_parts.append('Good answer. Keep your structure clear and professional.')

        improved_answer = cls._improved_answer(answer, profile, question)
        return {
            'word_count': word_count,
            'unique_word_count': unique_count,
            'sentence_count': sentence_count,
            'filler_count': filler_count,
            'grammar_score': grammar_score,
            'fluency_score': fluency_score,
            'confidence_score': confidence_score,
            'relevance_score': relevance_score,
            'vocabulary_score': vocabulary_score,
            'professional_tone_score': professional_tone_score,
            'clarity_score': clarity_score,
            'hesitation_score': hesitation_score,
            'turn_score': turn_score,
            'turn_feedback': ' '.join(feedback_parts),
            'improved_answer': improved_answer,
        }

    @classmethod
    def _improved_answer(cls, answer: str, profile: InterviewProfile, question: str) -> str:
        role = profile.target_role or 'this role'
        text = (answer or '').strip()
        if len(text.split()) < 20:
            return f"I am interested in {role} because it matches my skills and goals. I have prepared carefully, I learn quickly, and I can contribute with responsibility and a positive attitude."
        return f"A stronger version would be: {text[:320].rstrip('. ')}. I can support this with a clear example, explain the result, and connect it directly to {role}."

    @classmethod
    def _finalize_feedback(cls, session: InterviewSession) -> InterviewFeedback:
        existing = session.latest_feedback
        if existing:
            return existing
        turns = session.turns.order_by(InterviewTurn.turn_no.asc()).all()
        answered = [t for t in turns if t.is_answered and t.turn_score is not None]
        if not answered:
            feedback = InterviewFeedback(session_id=session.id, ai_summary='No valid answers were captured.')
            db.session.add(feedback)
            db.session.flush()
            return feedback

        avg = lambda field: round(sum(float(getattr(t, field) or 0) for t in answered) / len(answered), 1)
        fluency = avg('fluency_score')
        grammar = avg('grammar_score')
        confidence = avg('confidence_score')
        relevance = avg('relevance_score')
        vocab = avg('vocabulary_score')
        tone = avg('professional_tone_score')
        hesitation = max(1.0, min(10.0, round(10.0 - (session.long_pause_count * 0.9) - (session.total_pause_count * 0.15), 1)))
        role_fit = round((relevance + confidence + tone) / 3.0, 1)
        overall = round((fluency * 0.20) + (grammar * 0.15) + (confidence * 0.20) + (relevance * 0.20) + (vocab * 0.10) + (tone * 0.10) + (hesitation * 0.05), 1)

        best_turn = max(answered, key=lambda t: float(t.turn_score or 0))
        weakest_turn = min(answered, key=lambda t: float(t.turn_score or 0))
        strengths = []
        weaknesses = []
        if confidence >= 7:
            strengths.append('Good confidence in interview responses.')
        if relevance >= 7:
            strengths.append('Answers usually stayed relevant to the question.')
        if tone >= 7:
            strengths.append('Professional tone was suitable for interview speaking.')
        if fluency < 6:
            weaknesses.append('Fluency needs more continuous speaking practice.')
        if grammar < 6:
            weaknesses.append('Grammar needs cleaner sentence control.')
        if hesitation < 6:
            weaknesses.append('Long pauses reduced interview impact.')
        if not strengths:
            strengths.append('You completed the interview and maintained answer flow in multiple turns.')
        if not weaknesses:
            weaknesses.append('Keep improving examples, precision, and answer depth.')

        practice = [
            'Retry weak questions with one example in each answer.',
            'Practice self-introduction until it sounds natural and confident.',
            'Speak for 30-60 seconds without filler words.',
        ]
        summary = f"Overall interview readiness is {overall}/10. Best area: {max([('fluency', fluency), ('grammar', grammar), ('confidence', confidence), ('relevance', relevance), ('vocabulary', vocab), ('tone', tone)], key=lambda item: item[1])[0]}. Main improvement area: {min([('fluency', fluency), ('grammar', grammar), ('confidence', confidence), ('relevance', relevance), ('vocabulary', vocab), ('tone', tone), ('hesitation', hesitation)], key=lambda item: item[1])[0]}."
        coach_tips = 'Use complete sentences, add one clear example, and avoid stopping for too long before your main point.'

        feedback = InterviewFeedback(
            session_id=session.id,
            overall_score=overall,
            fluency_score=fluency,
            grammar_score=grammar,
            confidence_score=confidence,
            relevance_score=relevance,
            professional_tone_score=tone,
            vocabulary_score=vocab,
            hesitation_score=hesitation,
            role_fit_score=role_fit,
            strengths_json=json.dumps(strengths),
            weaknesses_json=json.dumps(weaknesses),
            recommended_practice_json=json.dumps(practice),
            best_answer_turn_id=best_turn.id,
            weakest_answer_turn_id=weakest_turn.id,
            ai_summary=summary,
            coach_tips=coach_tips,
        )
        session.final_score = overall
        db.session.add(feedback)
        db.session.flush()
        return feedback
