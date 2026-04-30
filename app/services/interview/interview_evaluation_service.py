from __future__ import annotations

import re

from ..speaking.evaluation_service import EvaluationService


class InterviewEvaluationService:
    INTERVIEW_OPENERS = (
        'thank you', 'good morning', 'good afternoon', 'good evening',
        'my name is', 'i am', 'currently', 'recently', 'experience', 'responsible',
    )
    STAR_KEYWORDS = {'situation', 'task', 'action', 'result'}
    PROFESSIONAL_WORDS = {'team', 'client', 'project', 'deadline', 'responsibility', 'learned', 'improved', 'delivered'}

    @classmethod
    def evaluate(
        cls,
        *,
        transcript: str,
        prompt_text: str,
        topic_title: str | None = None,
        estimated_seconds: int | None = None,
        retries_left: int = 0,
        duration_seconds: int | None = None,
        target_keywords: list[str] | None = None,
        role_name: str | None = None,
        question_type: str | None = None,
    ) -> dict:
        base = EvaluationService.evaluate(
            transcript=transcript,
            prompt_text=prompt_text,
            topic_title=topic_title,
            estimated_seconds=estimated_seconds,
            retries_left=retries_left,
            duration_seconds=duration_seconds,
        )

        tokens = EvaluationService.tokenize(transcript)
        token_set = set(tokens)
        word_count = len(tokens)
        sentences = EvaluationService.sentence_parts(transcript)

        structure_score = 42
        structure_notes: list[str] = []
        if len(sentences) >= 3:
            structure_score += 22
        elif len(sentences) == 2:
            structure_score += 12
        else:
            structure_notes.append('Break your answer into a clear opening, body, and closing line.')
        star_hits = len(token_set.intersection(cls.STAR_KEYWORDS))
        if star_hits >= 2:
            structure_score += 18
        elif question_type in {'behavioral', 'experience'}:
            structure_notes.append('For behavioral answers, use Situation, Task, Action, and Result.')
        if re.search(r'\b(first|second|finally|because|therefore|for example)\b', transcript, re.I):
            structure_score += 10

        confidence_score = 45
        confidence_notes: list[str] = []
        if word_count >= 45:
            confidence_score += 18
        elif word_count >= 25:
            confidence_score += 10
        else:
            confidence_notes.append('Develop the answer more fully to sound more confident.')
        if any(phrase in (transcript or '').lower() for phrase in cls.INTERVIEW_OPENERS):
            confidence_score += 12
        if (base.get('filler_ratio') or 0) <= 0.05:
            confidence_score += 10
        elif (base.get('filler_ratio') or 0) >= 0.12:
            confidence_notes.append('Reduce filler words to sound more confident and polished.')

        professionalism_score = 46
        professionalism_notes: list[str] = []
        professional_hits = len(token_set.intersection(cls.PROFESSIONAL_WORDS))
        professionalism_score += min(18, professional_hits * 3)
        if re.search(r'\b(thank you|i appreciate|opportunity)\b', transcript, re.I):
            professionalism_score += 10
        if re.search(r'\b(gonna|wanna|kinda)\b', transcript, re.I):
            professionalism_score -= 8
            professionalism_notes.append('Avoid casual words like gonna or wanna in interviews.')

        answer_quality_score = 44
        quality_notes: list[str] = []
        target_hits = 0
        if target_keywords:
            normalized_targets = {item.strip().lower() for item in target_keywords if item and item.strip()}
            target_hits = len(token_set.intersection(normalized_targets))
            if normalized_targets:
                answer_quality_score += min(18, round((target_hits / len(normalized_targets)) * 20))
            if target_hits == 0:
                quality_notes.append('Use more job-related keywords from the role and question.')
        if role_name and role_name.strip() and role_name.strip().lower() in (transcript or '').lower():
            answer_quality_score += 8
        if re.search(r'\b(example|for example|for instance|result|outcome|improved)\b', transcript, re.I):
            answer_quality_score += 12
        else:
            quality_notes.append('Add one concrete example or result to strengthen the answer.')

        structure_score = max(20, min(98, round(structure_score)))
        confidence_score = max(20, min(98, round(confidence_score)))
        professionalism_score = max(20, min(98, round(professionalism_score)))
        answer_quality_score = max(20, min(98, round(answer_quality_score)))

        overall_percent = round(
            float(base.get('relevance_score') or 0) * 0.18
            + float(base.get('fluency_score') or 0) * 0.16
            + float(base.get('grammar_score') or 0) * 0.14
            + float(base.get('pronunciation_score') or 0) * 0.12
            + structure_score * 0.16
            + confidence_score * 0.10
            + professionalism_score * 0.07
            + answer_quality_score * 0.07
        )
        score = round(max(0.0, min(10.0, overall_percent / 10.0)), 1)

        improvements = []
        for note in structure_notes + confidence_notes + professionalism_notes + quality_notes:
            if note and note not in improvements:
                improvements.append(note)

        strengths = list(base.get('strengths') or [])
        if structure_score >= 75:
            strengths.append('Your interview answer has a clear structure.')
        if confidence_score >= 75:
            strengths.append('Your tone reads as confident and steady.')
        if professionalism_score >= 75:
            strengths.append('Your language sounds professional for an interview setting.')
        if answer_quality_score >= 75:
            strengths.append('You support your answer with useful job-related detail.')

        if score >= 7.5:
            summary = 'Strong interview answer. It sounds relevant, structured, and professional.'
        elif score >= 5.5:
            summary = 'Good base for interview practice, but it needs sharper structure and stronger examples.'
        else:
            summary = 'This answer needs clearer interview structure, better relevance, and more professional detail.'

        base.update({
            'score': score,
            'base_score': score,
            'overall_percent': overall_percent,
            'band_label': 'strong' if score >= 8 else ('developing' if score >= 5 else 'needs_work'),
            'feedback_text': summary,
            'interview_mode': True,
            'interview_scores': {
                'structure': structure_score,
                'confidence': confidence_score,
                'professionalism': professionalism_score,
                'answer_quality': answer_quality_score,
            },
            'dimension_scores': {
                **(base.get('dimension_scores') or {}),
                'structure': structure_score,
                'confidence': confidence_score,
                'professionalism': professionalism_score,
                'answer_quality': answer_quality_score,
            },
            'strengths': strengths[:6],
            'improvements': improvements[:6],
            'feedback_items': [summary, *improvements[:5]],
            'recommended_next_step': 'next_prompt' if score >= 7 and base.get('is_relevant') else ('retry' if retries_left > 0 else 'practice_more'),
            'should_retry': bool((score < 5.5 or not base.get('is_relevant')) and retries_left > 0),
            'target_keyword_hits': target_hits,
        })
        return base
