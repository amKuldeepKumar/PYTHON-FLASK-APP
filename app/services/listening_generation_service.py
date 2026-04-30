from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from ..models.lms import Course, Lesson, Question, Subsection


@dataclass
class ListeningScriptDraft:
    title: str
    script_text: str
    provider_label: str = "Internal AI Draft"
    difficulty: str = "basic"
    estimated_minutes: int = 2
    target_word_count: int = 180


class ListeningGenerationService:
    """Practical single-shot listening generator.

    It creates a level-aware script first, then derives written-answer question drafts
    from the final script. The output is deterministic so the admin workflow stays stable.
    """

    PROVIDER_LABEL = "Internal AI Draft"
    WORDS_PER_MINUTE = 120
    DURATION_RULES = {
        'basic': (2, 180),
        'intermediate': (3, 360),
        'advanced': (4, 520),
    }
    VOCAB_BANK = {
        'basic': [
            'family', 'school', 'market', 'daily', 'simple', 'helpful', 'morning',
            'practice', 'routine', 'clean', 'friendly', 'important', 'clear', 'easy',
        ],
        'intermediate': [
            'practical', 'responsibility', 'habit', 'community', 'regular', 'benefit',
            'challenge', 'decision', 'organised', 'example', 'explain', 'support',
            'improve', 'confidence', 'purpose',
        ],
        'advanced': [
            'significant', 'perspective', 'consistent', 'approach', 'effective',
            'responsibility', 'development', 'influence', 'motivation', 'practical',
            'strategy', 'essential', 'balanced', 'meaningful', 'conclusion',
        ],
    }

    @staticmethod
    def _clean_topic(title: Optional[str]) -> str:
        text = (title or 'Listening topic').strip()
        return text or 'Listening topic'

    @staticmethod
    def _difficulty_label(course: Optional[Course]) -> str:
        value = (getattr(course, 'difficulty', '') or 'basic').strip().lower()
        if value.startswith('adv'):
            return 'advanced'
        if value.startswith('int'):
            return 'intermediate'
        return 'basic'

    @classmethod
    def target_minutes_for(cls, course: Optional[Course], lesson: Optional[Lesson] = None) -> int:
        difficulty = cls._difficulty_label(course)
        minimum_minutes, _ = cls.DURATION_RULES[difficulty]
        requested = int(getattr(lesson, 'estimated_minutes', 0) or 0) if lesson else 0
        if requested > 0:
            return max(requested, minimum_minutes)
        return minimum_minutes

    @classmethod
    def target_word_count_for(cls, course: Optional[Course], lesson: Optional[Lesson] = None) -> int:
        difficulty = cls._difficulty_label(course)
        minimum_minutes, minimum_words = cls.DURATION_RULES[difficulty]
        target_minutes = cls.target_minutes_for(course, lesson)
        return max(minimum_words, target_minutes * cls.WORDS_PER_MINUTE)

    @classmethod
    def _intro_block(cls, topic: str, difficulty: str) -> str:
        if difficulty == 'advanced':
            return (
                f"Today's listening explores {topic} through a more developed spoken explanation. "
                f"The speaker introduces the subject, builds an argument with supporting examples, "
                f"and closes with a thoughtful conclusion."
            )
        if difficulty == 'intermediate':
            return (
                f"Today's listening focuses on {topic}. The speaker explains the main idea, adds practical details, "
                f"and shows why the topic matters in everyday life."
            )
        return (
            f"Today's listening is about {topic}. The speaker gives the main idea clearly, shares a few easy details, "
            f"and repeats the key point in simple language."
        )

    @classmethod
    def _detail_sentences(cls, topic: str, difficulty: str, count: int) -> list[str]:
        vocab = cls.VOCAB_BANK[difficulty]
        sentences: list[str] = []
        for idx in range(count):
            a = vocab[idx % len(vocab)]
            b = vocab[(idx + 3) % len(vocab)]
            c = vocab[(idx + 6) % len(vocab)]
            if difficulty == 'advanced':
                sentence = (
                    f"The speaker explains that {topic} requires a {a} perspective, because one strong idea rarely works "
                    f"without {b} planning, {c} action, and careful reflection."
                )
            elif difficulty == 'intermediate':
                sentence = (
                    f"The speaker adds that {topic} becomes more useful when people build a {a} habit, notice one {b} detail, "
                    f"and take a {c} step each day."
                )
            else:
                sentence = (
                    f"The speaker says {topic} is easier when people follow a {a} routine, remember one {b} point, "
                    f"and do one {c} thing regularly."
                )
            sentences.append(sentence)
        return sentences

    @classmethod
    def _closing_block(cls, topic: str, difficulty: str) -> str:
        if difficulty == 'advanced':
            return (
                f"In conclusion, the listening suggests that {topic} is not only a useful subject to understand, "
                f"but also a meaningful skill that grows through consistent attention, higher-level vocabulary, and deliberate practice."
            )
        if difficulty == 'intermediate':
            return (
                f"In conclusion, the speaker reminds the listener that {topic} becomes easier with regular practice, "
                f"clear attention, and one practical action after listening."
            )
        return (
            f"In the end, the speaker repeats that {topic} is important, simple to understand step by step, "
            f"and easier when the listener remembers the main idea and one key detail."
        )

    @classmethod
    def build_script(cls, course: Optional[Course], lesson: Lesson) -> ListeningScriptDraft:
        topic = cls._clean_topic(lesson.title)
        difficulty = cls._difficulty_label(course)
        target_minutes = cls.target_minutes_for(course, lesson)
        target_words = cls.target_word_count_for(course, lesson)

        blocks = [cls._intro_block(topic, difficulty)]
        words_so_far = len(blocks[0].split())
        detail_count = max(4, math.ceil((target_words - words_so_far) / 24))
        blocks.extend(cls._detail_sentences(topic, difficulty, detail_count))
        blocks.append(cls._closing_block(topic, difficulty))
        blocks.append('After listening, answer the questions in writing using short and clear sentences.')

        script = ' '.join(blocks)
        return ListeningScriptDraft(
            title=topic,
            script_text=script,
            provider_label=cls.PROVIDER_LABEL,
            difficulty=difficulty,
            estimated_minutes=target_minutes,
            target_word_count=target_words,
        )

    @staticmethod
    def _sentences(script_text: str) -> list[str]:
        return [part.strip() for part in re.split(r'(?<=[.!?])\s+', script_text or '') if part.strip()]

    @staticmethod
    def _keyword_seed(text: str) -> list[str]:
        words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or '')
        seen: list[str] = []
        for word in words:
            lower = word.lower()
            if lower in {'about','after','answer','daily','clear','clearly','detail','details','first','gives','give','important','listening','message','practice','short','speaker','simple','today','topic','using','welcome','words','writing','listener','listening'}:
                continue
            if lower not in seen:
                seen.append(lower)
        return seen[:6]

    @classmethod
    def _extract_detail_sentences(cls, script_text: str) -> list[str]:
        sentences = cls._sentences(script_text)
        if len(sentences) <= 3:
            return sentences
        return sentences[1:-1]

    @classmethod
    def build_question_rows(
        cls,
        lesson: Lesson,
        script_text: str,
        *,
        short_answer_count: int = 2,
        fill_blank_count: int = 1,
        true_false_count: int = 1,
    ) -> list[dict]:
        topic = cls._clean_topic(lesson.title)
        all_sentences = cls._sentences(script_text)
        detail_sentences = cls._extract_detail_sentences(script_text) or all_sentences
        if not all_sentences:
            return []

        rows: list[dict] = []
        first_sentence = all_sentences[0]
        rows.append({
            'prompt': 'What is the main topic of this listening?',
            'model_answer': topic,
            'explanation': 'Write the topic in one short sentence.',
            'expected_keywords': ', '.join(cls._keyword_seed(topic) or [topic.lower()]),
            'alt_answers': [f'The listening is about {topic}.'],
            'question_style': 'short_answer',
        })

        for sentence in detail_sentences[:max(1, short_answer_count - 1)]:
            answer = sentence.rstrip('. ')
            rows.append({
                'prompt': 'Write one key detail from the audio.',
                'model_answer': answer,
                'explanation': 'Choose one clear fact or point that the speaker mentioned.',
                'expected_keywords': ', '.join(cls._keyword_seed(answer)),
                'alt_answers': [],
                'question_style': 'short_answer',
            })

        for sentence in detail_sentences[:fill_blank_count]:
            keywords = cls._keyword_seed(sentence)
            blank_word = keywords[0] if keywords else sentence.split()[-1].strip('.,')
            blank_prompt = re.sub(rf'{re.escape(blank_word)}', '_____', sentence, count=1, flags=re.IGNORECASE)
            rows.append({
                'prompt': f'Fill in the blank from the listening: {blank_prompt}',
                'model_answer': blank_word,
                'explanation': 'Write only the missing word or short phrase.',
                'expected_keywords': blank_word.lower(),
                'alt_answers': [],
                'question_style': 'fill_blank',
            })

        for sentence in detail_sentences[:true_false_count]:
            statement = sentence.rstrip('. ') + '.'
            rows.append({
                'prompt': f"Write True or False: {statement}",
                'model_answer': 'True',
                'explanation': 'Type True if the statement matches the audio, or False if it does not.',
                'expected_keywords': 'true,false',
                'alt_answers': [],
                'question_style': 'true_false',
            })

        cleaned = []
        seen_prompts = set()
        for row in rows:
            row['model_answer'] = (row['model_answer'] or '').strip()
            prompt = (row['prompt'] or '').strip()
            if not row['model_answer'] or not prompt or prompt.lower() in seen_prompts:
                continue
            seen_prompts.add(prompt.lower())
            cleaned.append(row)
        return cleaned

    @classmethod
    def sync_questions(
        cls,
        lesson: Lesson,
        subsection: Subsection,
        *,
        replace_existing: bool = False,
        short_answer_count: int = 2,
        fill_blank_count: int = 1,
        true_false_count: int = 1,
    ) -> int:
        script_text = (lesson.explanation_tts_text or lesson.explanation_text or '').strip()
        if not script_text:
            return 0
        if replace_existing:
            for question in list(subsection.questions):
                question.is_active = False
        rows = cls.build_question_rows(
            lesson,
            script_text,
            short_answer_count=short_answer_count,
            fill_blank_count=fill_blank_count,
            true_false_count=true_false_count,
        )
        existing_prompts = {(q.prompt or '').strip().lower() for q in subsection.questions}
        created = 0
        base_order = max([int(getattr(q, 'sort_order', 0) or 0) for q in subsection.questions] + [0])
        for index, row in enumerate(rows, start=1):
            prompt = (row['prompt'] or '').strip()
            if prompt.lower() in existing_prompts:
                continue
            alt_answers = [part for part in [row['model_answer'], *row.get('alt_answers', [])] if str(part).strip()]
            question = Question(
                subsection_id=subsection.id,
                prompt=prompt,
                prompt_type=row.get('question_style') or 'listening',
                model_answer=row['model_answer'],
                hint_text=row['explanation'],
                expected_keywords=row.get('expected_keywords') or None,
                answer_patterns_text='\n'.join(alt_answers) or None,
                evaluation_rubric='Listening answer check',
                answer_generation_status='done',
                is_active=True,
                sort_order=base_order + index,
            )
            subsection.questions.append(question)
            created += 1
        return created
