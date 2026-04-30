
from __future__ import annotations

import re
from collections import Counter


class EvaluationService:
    STOPWORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'because', 'but', 'by', 'for', 'from', 'had', 'has', 'have',
        'he', 'her', 'his', 'i', 'if', 'in', 'is', 'it', 'its', 'me', 'my', 'of', 'on', 'or', 'our', 'she', 'so',
        'that', 'the', 'their', 'them', 'there', 'they', 'this', 'to', 'was', 'we', 'were', 'will', 'with', 'you', 'your'
    }
    FILLER_WORDS = {
        'uh', 'um', 'er', 'ah', 'hmm', 'mmm', 'like', 'actually', 'basically', 'literally', 'so', 'well'
    }
    FILLER_PHRASES = ('you know', 'i mean', 'kind of', 'sort of')
    COMMON_GRAMMAR_PATTERNS = [
        (re.compile(r"i\s+is", re.I), "Use 'I am' instead of 'I is'."),
        (re.compile(r"he\s+go", re.I), "Use 'he goes' for third-person singular."),
        (re.compile(r"she\s+go", re.I), "Use 'she goes' for third-person singular."),
        (re.compile(r"they\s+was", re.I), "Use 'they were' instead of 'they was'."),
        (re.compile(r"we\s+was", re.I), "Use 'we were' instead of 'we was'."),
        (re.compile(r"an\s+[bcdfghjklmnpqrstvwxyz]\w*", re.I), "Check article usage: use 'a' before consonant sounds."),
        (re.compile(r"a\s+[aeiou]\w*", re.I), "Check article usage: use 'an' before vowel sounds."),
        (re.compile(r"very very", re.I), "Avoid repeating the same intensifier back to back."),
    ]

    @classmethod
    def tokenize(cls, text: str | None) -> list[str]:
        return re.findall(r"[a-zA-Z']+", (text or '').lower())

    @classmethod
    def keyword_set(cls, text: str | None) -> set[str]:
        return {token for token in cls.tokenize(text) if len(token) > 2 and token not in cls.STOPWORDS}

    @classmethod
    def sentence_parts(cls, text: str | None) -> list[str]:
        raw = (text or '').strip()
        if not raw:
            return []
        return [part.strip() for part in re.split(r'[.!?]+', raw) if part.strip()]

    @classmethod
    def sentence_count(cls, text: str | None) -> int:
        parts = cls.sentence_parts(text)
        return len(parts) if parts else (1 if (text or '').strip() else 0)

    @classmethod
    def _filler_stats(cls, text: str, tokens: list[str]) -> tuple[int, float]:
        filler_count = sum(1 for token in tokens if token in cls.FILLER_WORDS)
        normalized = f" {(text or '').lower()} "
        for phrase in cls.FILLER_PHRASES:
            filler_count += normalized.count(f" {phrase} ")
        filler_ratio = round((filler_count / len(tokens)), 3) if tokens else 0.0
        return filler_count, filler_ratio

    @classmethod
    def _grammar_feedback(cls, transcript: str, tokens: list[str], sentence_parts: list[str]) -> tuple[int, list[str]]:
        issues: list[str] = []
        for pattern, message in cls.COMMON_GRAMMAR_PATTERNS:
            if pattern.search(transcript or ''):
                issues.append(message)

        lowercase = (transcript or '').strip().lower()
        if lowercase and not re.search(r'[.!?]$', (transcript or '').strip()):
            issues.append('End your answer with clearer sentence punctuation for better structure.')

        for sentence in sentence_parts:
            if sentence and sentence[0].islower():
                issues.append('Start each sentence clearly; sentence openings look inconsistent.')
                break

        if len(sentence_parts) <= 1 and len(tokens) >= 14:
            issues.append('Your answer reads like one long incomplete sentence. Break it into shorter complete sentences.')

        repeated_prepositions = re.search(
            r"\b(from|to|for|with|at|in|on|of)\b(?:\s+\w+){0,3}\s+\1\b",
            transcript or '',
            re.I,
        )
        if repeated_prepositions:
            issues.append('The sentence structure becomes confusing because a phrase is repeated awkwardly.')

        repeated = [word for word, count in Counter(tokens).items() if count >= 5 and len(word) > 3 and word not in cls.STOPWORDS]
        if repeated:
            issues.append(f"You repeat words such as {', '.join(sorted(repeated)[:3])}. Use more variety.")

        issue_penalty = min(40, len(issues) * 8)
        base = 82
        if len(tokens) < 6:
            base = 52
        elif len(tokens) < 12:
            base = 64
        grammar_score = max(20, min(98, base - issue_penalty))
        return grammar_score, issues[:5]

    @classmethod
    def _sentence_making_score(cls, sentence_parts: list[str], tokens: list[str]) -> tuple[int, list[str]]:
        notes: list[str] = []
        sentence_count = len(sentence_parts) or (1 if tokens else 0)
        word_count = len(tokens)
        avg_sentence_length = round(word_count / sentence_count, 1) if sentence_count else 0.0

        score = 55
        if sentence_count >= 3:
            score += 18
        elif sentence_count == 2:
            score += 10
        else:
            notes.append('Try to speak in at least 2 to 3 clear sentences.')

        if 8 <= avg_sentence_length <= 20:
            score += 18
        elif 5 <= avg_sentence_length < 8 or 20 < avg_sentence_length <= 26:
            score += 10
        else:
            notes.append('Make your sentences more balanced; some are too short or too long.')

        connectors = {'because', 'however', 'therefore', 'although', 'but', 'so', 'then', 'when', 'while', 'also'}
        connector_hits = len([token for token in tokens if token in connectors])
        if connector_hits >= 2:
            score += 10
        elif connector_hits == 1:
            score += 5
        else:
            notes.append('Connect your ideas with words like because, so, or however.')

        return max(20, min(98, score)), notes[:4]

    @classmethod
    def _vocabulary_score(cls, tokens: list[str], prompt_keywords: set[str]) -> tuple[int, list[str], list[str]]:
        notes: list[str] = []
        unique_tokens = {token for token in tokens if token not in cls.STOPWORDS}
        unique_ratio = round((len(unique_tokens) / len(tokens)), 3) if tokens else 0.0
        avg_word_len = round(sum(len(token) for token in unique_tokens) / len(unique_tokens), 2) if unique_tokens else 0.0
        topic_hits = sorted(unique_tokens.intersection(prompt_keywords))

        score = 48
        if unique_ratio >= 0.7:
            score += 24
        elif unique_ratio >= 0.55:
            score += 16
        elif unique_ratio >= 0.4:
            score += 8
        else:
            notes.append('Use a wider range of words instead of repeating the same simple vocabulary.')

        if avg_word_len >= 5.2:
            score += 16
        elif avg_word_len >= 4.3:
            score += 10
        else:
            notes.append('Try a few more descriptive words to sound more natural and precise.')

        if len(topic_hits) >= 3:
            score += 12
        elif len(topic_hits) >= 1:
            score += 7
        else:
            notes.append('Use more topic words from the question so your answer feels directly connected.')

        return max(20, min(98, score)), notes[:4], topic_hits[:6]

    @classmethod
    def _punctuation_score(cls, transcript: str, sentence_parts: list[str]) -> tuple[int, list[str]]:
        notes: list[str] = []
        raw = (transcript or '').strip()
        if not raw:
            return 20, ['No clear punctuation or sentence boundary was detected.']

        score = 60
        if re.search(r'[.!?]$', raw):
            score += 14
        else:
            notes.append('Add a full stop or question mark at the end so the answer feels complete.')

        punctuation_hits = len(re.findall(r'[,.!?]', raw))
        if punctuation_hits >= max(1, len(sentence_parts)):
            score += 14
        else:
            notes.append('Use punctuation to separate your ideas more clearly.')

        if any(part and part[0].isupper() for part in sentence_parts):
            score += 8
        else:
            notes.append('Start your sentence clearly with proper capitalization when typing or checking the transcript.')

        if ', and ' in raw.lower() or ', but ' in raw.lower() or ';' in raw:
            score += 4

        return max(20, min(98, score)), notes[:4]

    @classmethod
    def _requirement_checks(cls, prompt_text: str, instruction_text: str | None, transcript: str) -> tuple[int, list[dict], list[str]]:
        combined_prompt = ' '.join(part for part in [prompt_text or '', instruction_text or ''] if part).lower()
        answer = f" {(transcript or '').lower()} "
        checks: list[dict] = []
        notes: list[str] = []

        def add_check(label: str, passed: bool, hint: str):
            checks.append({'label': label, 'passed': passed})
            if not passed:
                notes.append(hint)

        if any(token in combined_prompt for token in ['greeting', 'hello', 'hi']):
            add_check(
                'Greeting',
                any(word in answer for word in [' hello ', ' hi ', ' excuse me ']),
                'Open with a simple greeting such as Hello or Excuse me.',
            )
        if any(token in combined_prompt for token in ['price', 'cost', 'how much']):
            add_check(
                'Ask the price',
                (' how much ' in answer) or (' price ' in answer) or (' cost ' in answer),
                'Ask directly about the price, for example How much is this?',
            )
        if any(token in combined_prompt for token in ['quantity', 'kilo', 'amount', 'bunch']):
            add_check(
                'Mention quantity',
                bool(re.search(r'\b(one|two|half|some)\b|\bkilo\b|\bbunch\b|\bkg\b', answer)),
                'Mention a clear quantity like one kilo, half a kilo, or one bunch.',
            )
        if any(token in combined_prompt for token in ['politely', 'thank', 'please', 'closing']):
            add_check(
                'Polite closing',
                any(word in answer for word in [' please ', ' thank you ', ' thanks ']),
                'End politely with please or thank you.',
            )
        if any(token in combined_prompt for token in ['example', 'detail', 'reason']):
            add_check(
                'Add detail',
                len(cls.sentence_parts(transcript)) >= 2,
                'Add one more sentence or detail to develop your answer.',
            )

        if not checks:
            return 80, [], []

        passed_count = len([item for item in checks if item['passed']])
        score = round((passed_count / len(checks)) * 100) if checks else 80
        return max(20, min(100, score)), checks, notes[:5]

    @classmethod
    def _improved_answer(cls, prompt_text: str, instruction_text: str | None, transcript: str, topic_title: str | None = None) -> str:
        prompt_low = f"{topic_title or ''} {prompt_text or ''} {instruction_text or ''}".lower()
        if 'market' in prompt_low:
            return 'Hello, how much are these vegetables? I would like one kilo of potatoes and half a kilo of tomatoes, please. Can you also give me some fresh spinach? Thank you.'
        if 'introduce' in prompt_low or 'yourself' in prompt_low:
            return 'Hello, my name is Rahul. I am from Punjab, and I am learning English to improve my communication. I enjoy meeting new people and practicing spoken English every day.'
        if 'direction' in prompt_low or 'station' in prompt_low:
            return 'Excuse me, could you please tell me how to get to the station? Is it far from here, or should I take a bus? Thank you for your help.'
        if 'phone call' in prompt_low or 'call' in prompt_low:
            return 'Hello, I am calling to ask about the class timing. Could you please tell me when the next class starts? Thank you.'

        parts = cls.sentence_parts(transcript)
        if parts:
            first = parts[0].strip()
            if not re.search(r'^(hello|hi|excuse me)\b', first, re.I):
                first = f"Hello, {first[0].lower() + first[1:]}" if len(first) > 1 else f"Hello, {first}"
            if not re.search(r'[.!?]$', first):
                first += '.'
            follow_up = 'I want to answer the question clearly with one or two relevant details.'
            closing = 'Thank you.'
            return f"{first} {follow_up} {closing}"

        return 'Hello. I will answer this question clearly in two or three short sentences with relevant details. Thank you.'

    @classmethod
    def _quality_gate(
        cls,
        *,
        word_count: int,
        sentence_count: int,
        relevance_score: int,
        requirement_score: int,
        punctuation_score: int,
        grammar_score: int,
        sentence_making_score: int,
        fluency_score: int,
        pronunciation_score: int,
    ) -> tuple[int, int, int, int, list[str]]:
        penalties: list[str] = []
        total_penalty = 0

        if requirement_score <= 20:
            total_penalty += 22
            penalties.append('The answer misses the main task requirements.')
            fluency_score = min(fluency_score, 55)
            pronunciation_score = min(pronunciation_score, 60)
        elif requirement_score <= 40:
            total_penalty += 12
            penalties.append('Only part of the task requirements are covered.')

        if relevance_score < 45:
            total_penalty += 16
            penalties.append('The response is not answering the real question clearly enough.')
        elif relevance_score < 60:
            total_penalty += 8
            penalties.append('The response is only partly connected to the question.')

        if punctuation_score <= 30 and sentence_count <= 1:
            total_penalty += 10
            penalties.append('The answer structure is incomplete and lacks clear sentence boundaries.')

        if grammar_score < 70 and sentence_making_score < 70:
            total_penalty += 10
            penalties.append('Grammar and sentence control are both unstable in this answer.')

        if word_count < 10:
            total_penalty += 8
            penalties.append('The answer is too short to show enough control.')

        return total_penalty, fluency_score, pronunciation_score, requirement_score, penalties[:5]

    @classmethod
    def _fluency_score(cls, *, tokens: list[str], duration_seconds: int | None, transcript: str) -> tuple[int, dict, list[str]]:
        word_count = len(tokens)
        duration_seconds = max(0, int(duration_seconds or 0))
        wpm = round((word_count / duration_seconds) * 60, 1) if duration_seconds > 0 and word_count > 0 else 0.0
        filler_count, filler_ratio = cls._filler_stats(transcript, tokens)

        notes: list[str] = []
        score = 52
        if wpm <= 0:
            notes.append('Duration was not captured, so fluency uses transcript-only signals.')
        elif 95 <= wpm <= 155:
            score += 26
        elif 80 <= wpm < 95 or 155 < wpm <= 175:
            score += 18
        elif 65 <= wpm < 80 or 175 < wpm <= 195:
            score += 10
            notes.append('Your speed is understandable, but it can sound more natural.')
        else:
            score += 2
            notes.append('Your pace is either too slow or too fast.')

        if filler_ratio < 0.03:
            score += 18
        elif filler_ratio < 0.07:
            score += 11
            notes.append('A few filler words are present.')
        elif filler_ratio < 0.12:
            score += 4
            notes.append('Reduce filler words like uh or um.')
        else:
            score -= 6
            notes.append('Too many filler words reduce fluency.')

        if word_count >= 35:
            score += 8
        elif word_count >= 18:
            score += 4
        else:
            notes.append('Speak a little longer to show smoother flow.')

        pacing_band = 'unknown'
        if wpm > 0:
            if wpm < 70:
                pacing_band = 'too_slow'
            elif wpm < 95:
                pacing_band = 'slightly_slow'
            elif wpm <= 155:
                pacing_band = 'good'
            elif wpm <= 185:
                pacing_band = 'slightly_fast'
            else:
                pacing_band = 'too_fast'

        return max(20, min(98, round(score))), {
            'words_per_minute': wpm,
            'filler_count': filler_count,
            'filler_ratio': filler_ratio,
            'pacing_band': pacing_band,
        }, notes[:4]

    @classmethod
    def _pronunciation_proxy(cls, *, tokens: list[str], transcript: str, duration_seconds: int | None) -> tuple[int, list[str]]:
        notes: list[str] = []
        word_count = len(tokens)
        avg_word_len = (sum(len(token) for token in tokens) / word_count) if word_count else 0.0
        unique_ratio = round((len(set(tokens)) / word_count), 3) if word_count else 0.0
        all_caps_words = len(re.findall(r'[A-Z]{3,}', transcript or ''))

        score = 48
        if avg_word_len >= 4.2:
            score += 14
        elif avg_word_len >= 3.4:
            score += 9
        else:
            notes.append('Word choice is very basic, so pronunciation confidence is limited.')

        if unique_ratio >= 0.62:
            score += 14
        elif unique_ratio >= 0.5:
            score += 8
        else:
            notes.append('Repeated wording makes pronunciation confidence less reliable.')

        if word_count >= 20:
            score += 12
        elif word_count >= 10:
            score += 7
        else:
            notes.append('Speech sample is short, so pronunciation scoring is less stable.')

        if duration_seconds and duration_seconds > 0:
            score += 6
        if all_caps_words:
            score -= min(8, all_caps_words * 2)
            notes.append('Transcript contains shouting-style words, which may reduce clarity.')

        return max(20, min(95, round(score))), notes[:4]

    @classmethod
    def evaluate(
        cls,
        *,
        transcript: str,
        prompt_text: str,
        instruction_text: str | None = None,
        topic_title: str | None = None,
        estimated_seconds: int | None = None,
        retries_left: int = 0,
        duration_seconds: int | None = None,
    ) -> dict:
        transcript_tokens = cls.tokenize(transcript)
        prompt_keywords = cls.keyword_set(' '.join(filter(None, [prompt_text, topic_title or ''])))
        transcript_keywords = cls.keyword_set(transcript)
        sentences = cls.sentence_parts(transcript)

        word_count = len(transcript_tokens)
        char_count = len((transcript or '').strip())
        sentence_count = cls.sentence_count(transcript)
        unique_ratio = round((len(set(transcript_tokens)) / word_count), 3) if word_count else 0.0

        overlap = prompt_keywords.intersection(transcript_keywords)
        overlap_count = len(overlap)
        relevance_score = 0
        if prompt_keywords:
            relevance_score = round((overlap_count / len(prompt_keywords)) * 100)
        elif word_count:
            relevance_score = 100

        semantic_bonus = 0
        if topic_title and topic_title.strip().lower() in (transcript or '').lower():
            semantic_bonus += 12
        if re.search(r'(example|for example|because|in my opinion|i think|personally)', transcript or '', re.I):
            semantic_bonus += 8
        relevance_score = max(0, min(100, relevance_score + semantic_bonus))
        is_relevant = relevance_score >= 30 or overlap_count >= 2

        fluency_score, fluency_meta, fluency_notes = cls._fluency_score(
            tokens=transcript_tokens,
            duration_seconds=duration_seconds or estimated_seconds,
            transcript=transcript,
        )
        pronunciation_score, pronunciation_notes = cls._pronunciation_proxy(
            tokens=transcript_tokens,
            transcript=transcript,
            duration_seconds=duration_seconds or estimated_seconds,
        )
        grammar_score, grammar_notes = cls._grammar_feedback(transcript, transcript_tokens, sentences)
        sentence_making_score, sentence_notes = cls._sentence_making_score(sentences, transcript_tokens)
        vocabulary_score, vocabulary_notes, vocabulary_hits = cls._vocabulary_score(transcript_tokens, prompt_keywords)
        punctuation_score, punctuation_notes = cls._punctuation_score(transcript, sentences)
        requirement_score, requirement_checks, requirement_notes = cls._requirement_checks(prompt_text, instruction_text, transcript)

        quality_penalty, fluency_score, pronunciation_score, requirement_score, quality_notes = cls._quality_gate(
            word_count=word_count,
            sentence_count=sentence_count,
            relevance_score=relevance_score,
            requirement_score=requirement_score,
            punctuation_score=punctuation_score,
            grammar_score=grammar_score,
            sentence_making_score=sentence_making_score,
            fluency_score=fluency_score,
            pronunciation_score=pronunciation_score,
        )

        if estimated_seconds and estimated_seconds > 0 and word_count > 0:
            expected_words = max(12, int(estimated_seconds * 0.85 / 2))
            if word_count < max(8, expected_words // 2):
                fluency_notes.append('Speak for a little longer to match the task length.')
                sentence_notes.append('Develop your answer more fully to match the prompt length.')

        overall_100 = round(
            pronunciation_score * 0.16
            + fluency_score * 0.16
            + grammar_score * 0.16
            + sentence_making_score * 0.14
            + vocabulary_score * 0.14
            + relevance_score * 0.14
            + punctuation_score * 0.05
            + requirement_score * 0.05
        )
        overall_100 = max(0, overall_100 - quality_penalty)
        score = round(max(0.0, min(10.0, overall_100 / 10.0)), 1)

        if score >= 8:
            band_label = 'strong'
        elif score >= 5:
            band_label = 'developing'
        else:
            band_label = 'needs_work'

        strengths: list[str] = []
        improvements: list[str] = []
        if pronunciation_score >= 75:
            strengths.append('Pronunciation confidence looks strong for this sample.')
        if fluency_score >= 75:
            strengths.append('Your speaking flow is smooth overall.')
        if grammar_score >= 72:
            strengths.append('Grammar control looks fairly stable.')
        if sentence_making_score >= 72:
            strengths.append('Your ideas are arranged in clear sentences.')
        if vocabulary_score >= 72:
            strengths.append('Vocabulary choice supports the topic well.')
        if punctuation_score >= 72:
            strengths.append('Your answer structure looks easy to follow.')
        if is_relevant:
            strengths.append('Your answer stays connected to the topic.')

        for note in quality_notes + pronunciation_notes + fluency_notes + grammar_notes + sentence_notes + vocabulary_notes + punctuation_notes + requirement_notes:
            if note not in improvements:
                improvements.append(note)
        if not is_relevant:
            improvements.insert(0, 'Stay closer to the exact question and topic keywords.')

        if score >= 7 and is_relevant:
            opening_feedback = 'Good job. Your answer is clear and mostly on topic.'
        elif is_relevant:
            opening_feedback = 'Your answer matches the topic, but it needs more detail or structure.'
        else:
            opening_feedback = 'Your answer needs a closer match to the topic and clearer development.'

        feedback_items = [opening_feedback]
        feedback_items.extend(improvements[:5])
        if not improvements:
            feedback_items.append('Good attempt. Keep practicing.')

        should_retry = (not is_relevant or word_count < 8 or score < 4.5) and retries_left > 0
        if should_retry:
            recommended_next_step = 'retry'
        elif score >= 7 and is_relevant:
            recommended_next_step = 'next_prompt'
        else:
            recommended_next_step = 'practice_more'

        return {
            'score': score,
            'base_score': score,
            'overall_percent': overall_100,
            'band_label': band_label,
            'word_count': word_count,
            'char_count': char_count,
            'sentence_count': sentence_count,
            'unique_ratio': unique_ratio,
            'relevance_score': relevance_score,
            'is_relevant': is_relevant,
            'keyword_hits': sorted(overlap),
            'pronunciation_score': pronunciation_score,
            'fluency_score': fluency_score,
            'grammar_score': grammar_score,
            'sentence_making_score': sentence_making_score,
            'vocabulary_score': vocabulary_score,
            'punctuation_score': punctuation_score,
            'requirement_score': requirement_score,
            'words_per_minute': fluency_meta.get('words_per_minute'),
            'filler_count': fluency_meta.get('filler_count'),
            'filler_ratio': fluency_meta.get('filler_ratio'),
            'pacing_band': fluency_meta.get('pacing_band'),
            'strengths': strengths[:5],
            'improvements': improvements[:6],
            'grammar_notes': grammar_notes,
            'sentence_notes': sentence_notes,
            'vocabulary_notes': vocabulary_notes,
            'punctuation_notes': punctuation_notes,
            'requirement_notes': requirement_notes,
            'requirement_checks': requirement_checks,
            'vocabulary_hits': vocabulary_hits,
            'improved_answer': cls._improved_answer(prompt_text, instruction_text, transcript, topic_title),
            'feedback_items': feedback_items,
            'feedback_text': ' '.join(feedback_items),
            'should_retry': should_retry,
            'recommended_next_step': recommended_next_step,
            'dimension_scores': {
                'pronunciation': pronunciation_score,
                'fluency': fluency_score,
                'grammar': grammar_score,
                'sentence_making': sentence_making_score,
                'vocabulary': vocabulary_score,
                'relevance': relevance_score,
                'punctuation': punctuation_score,
                'task_match': requirement_score,
            },
        }
