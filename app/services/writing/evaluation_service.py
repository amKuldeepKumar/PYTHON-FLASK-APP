from __future__ import annotations

import re
from collections import Counter

TRANSITION_WORDS = {
    "first", "firstly", "second", "secondly", "third", "thirdly", "however", "therefore",
    "moreover", "furthermore", "because", "although", "also", "finally", "in conclusion",
    "for example", "for instance", "on the other hand", "overall", "thus", "so", "meanwhile",
    "as a result", "in addition", "for this reason", "to begin with"
}
COMMON_ERROR_PATTERNS = [
    (r"\bi\b", "Capitalize the pronoun 'I'."),
    (r"\bdont\b", "Use the apostrophe form 'don't'."),
    (r"\bdoesnt\b", "Use the apostrophe form 'doesn't'."),
    (r"\bdidnt\b", "Use the apostrophe form 'didn't'."),
    (r"\bcant\b", "Use the apostrophe form 'can't'."),
    (r"\bwont\b", "Use the apostrophe form 'won't'."),
    (r"\bim\b", "Use 'I'm' instead of 'im'."),
    (r"\bteh\b", "Correct the spelling 'teh' to 'the'."),
]
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are", "was", "were",
    "be", "been", "being", "that", "this", "it", "as", "at", "by", "from", "but", "if", "then", "than",
    "into", "about", "their", "there", "them", "they", "we", "you", "your", "our", "can", "could", "would"
}
LEVEL_TARGETS = {
    "basic": {"min_paragraphs": 1, "avg_sentence_low": 6, "avg_sentence_high": 20, "long_word_ratio": 0.06},
    "intermediate": {"min_paragraphs": 2, "avg_sentence_low": 8, "avg_sentence_high": 24, "long_word_ratio": 0.10},
    "advanced": {"min_paragraphs": 3, "avg_sentence_low": 10, "avg_sentence_high": 28, "long_word_ratio": 0.14},
}
TASK_TYPE_HINTS = {
    "essay": ["clear introduction", "body development", "short conclusion"],
    "letter": ["tone and purpose", "clear message", "appropriate closing"],
    "story": ["sequence of events", "description", "ending"],
    "paragraph": ["topic sentence", "supporting details", "clear final line"],
}

COMMON_REAL_WORDS = {
    "i", "my", "me", "we", "our", "you", "your", "he", "she", "they", "their",
    "is", "are", "was", "were", "be", "have", "has", "had", "do", "did", "does",
    "go", "went", "make", "made", "take", "took", "see", "saw", "say", "said",
    "good", "bad", "big", "small", "important", "help", "work", "school", "teacher",
    "student", "education", "war", "world", "history", "life", "people", "family",
    "mother", "father", "home", "country", "language", "english", "reading", "writing",
    "speaking", "listening", "because", "however", "therefore", "first", "second",
    "finally", "example", "reason", "problem", "solution", "benefit", "disadvantage",
    "technology", "computer", "internet", "child", "children", "important", "answer",
    "question", "topic", "idea", "paragraph", "sentence"
}


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def _round1(value: float) -> float:
    return round(float(value), 1)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text or "")


def _keywords_from_prompt(*parts: str) -> set[str]:
    tokens: list[str] = []
    for part in parts:
        tokens.extend([w.lower() for w in _tokenize(part)])
    return {w for w in tokens if len(w) >= 4 and w not in STOPWORDS}


def _sentence_alerts(sentences: list[str]) -> list[str]:
    alerts: list[str] = []
    for idx, sentence in enumerate(sentences[:8], start=1):
        words = _tokenize(sentence)
        if sentence and not sentence[:1].isupper():
            alerts.append(f"Sentence {idx} should start with a capital letter.")
        if sentence and sentence[-1] not in ".!?":
            alerts.append(f"Sentence {idx} needs ending punctuation.")
        if len(words) <= 3:
            alerts.append(f"Sentence {idx} is very short. Develop the idea more clearly.")
    return alerts[:6]


def _rewrite_suggestions(sentences: list[str], transitions: int, keyword_overlap: int) -> list[str]:
    suggestions: list[str] = []
    if sentences:
        first_sentence = sentences[0]
        if len(_tokenize(first_sentence)) < 8:
            suggestions.append("Rewrite the opening sentence to introduce the topic more clearly.")
    if transitions == 0:
        suggestions.append("Add linking words such as 'however', 'because', or 'for example' to connect ideas.")
    if keyword_overlap <= 1:
        suggestions.append("Use more task-related keywords so the answer stays focused on the question.")
    if len(sentences) >= 2:
        suggestions.append("Combine two short sentences into one stronger sentence with a connector.")
    suggestions.append("After writing, reread once for capitalization, punctuation, and repeated words.")
    return suggestions[:4]


def _rubric_cards(scores: dict, level: str, task_type: str) -> list[dict]:
    descriptors = {
        "grammar": "sentence control, punctuation, and accuracy",
        "vocabulary": "range, precision, and repetition control",
        "coherence": "organization, paragraphing, and linking",
        "task_response": "task focus, idea coverage, and length control",
    }
    cards = []
    for key, label in descriptors.items():
        score = float(scores.get(key, 0) or 0)
        if score >= 8:
            band = "Strong"
        elif score >= 6.5:
            band = "Good"
        elif score >= 5:
            band = "Developing"
        else:
            band = "Needs work"
        cards.append({
            "key": key,
            "score": _round1(score),
            "band": band,
            "label": label,
            "target": f"{level.title()} {task_type.title()} standard",
        })
    return cards


def _basic_text_quality_flags(clean: str, words: list[str], sentences: list[str], min_words: int) -> dict:
    lc_words = [w.lower() for w in words]
    alpha_words = [w for w in lc_words if w.isalpha()]
    unique_alpha = set(alpha_words)

    repeated_char_noise = bool(re.search(r"(.)\1{4,}", clean.lower()))
    very_short = len(words) < max(5, min_words // 4 if min_words else 5)
    too_short_for_real_eval = len(words) < max(12, min_words // 3 if min_words else 12)
    missing_sentence_shape = len(sentences) == 0 or all(len(_tokenize(s)) <= 3 for s in sentences[:2])

    real_word_hits = sum(1 for w in unique_alpha if w in COMMON_REAL_WORDS)
    real_word_ratio = real_word_hits / max(1, len(unique_alpha))
    alpha_ratio = len(alpha_words) / max(1, len(words))

    nonsense_like = (
        (len(words) >= 2 and real_word_ratio < 0.15 and alpha_ratio > 0.7)
        or repeated_char_noise
    )

    return {
        "very_short": very_short,
        "too_short_for_real_eval": too_short_for_real_eval,
        "missing_sentence_shape": missing_sentence_shape,
        "nonsense_like": nonsense_like,
        "real_word_ratio": round(real_word_ratio, 3),
        "alpha_ratio": round(alpha_ratio, 3),
    }


def _invalid_submission_response(
    text: str,
    level: str,
    task_type: str,
    min_words: int,
    max_words: int,
    reason: str,
) -> tuple[float, str, str, dict]:
    words = _tokenize(text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]
    word_count = len(words)
    char_count = len((text or "").strip())

    dimensions = {
        "grammar": 0.5 if word_count > 0 else 0.0,
        "vocabulary": 0.0,
        "coherence": 0.0,
        "task_response": 0.0,
    }
    overall_score = _round1(sum(dimensions.values()) / 4.0)

    feedback = (
        f"This submission cannot receive a normal writing score because {reason} "
        f"Write a meaningful response with complete sentences and enough task-related content."
    )
    summary = (
        f"{word_count} words, {len(sentences)} sentences, {len(paragraphs)} paragraphs. "
        f"Submission quality too low for full evaluation."
    )

    evaluation = {
        "scores": dimensions,
        "strengths": ["You submitted an attempt, but it needs much more development."],
        "improvements": [
            "Write meaningful sentences instead of random or incomplete text.",
            "Answer the actual task directly.",
            f"Write at least {min_words} words." if min_words else "Write a longer response with clear ideas.",
            "Use basic punctuation and complete sentence structure.",
        ],
        "rewrite_suggestions": [
            "Start with one clear sentence that answers the topic directly.",
            "Add 2 to 3 supporting sentences with real examples or reasons.",
            "Use full stops and capital letters correctly.",
            "Check that your words are meaningful and related to the task.",
        ],
        "rubric_cards": _rubric_cards(dimensions, level, task_type),
        "sentence_alerts": _sentence_alerts(sentences) or ["The answer does not yet contain enough valid sentence structure."],
        "metrics": {
            "word_count": word_count,
            "char_count": char_count,
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "min_words": min_words,
            "max_words": max_words or None,
            "length_status": "invalid_submission",
            "avg_sentence_length": round((word_count / max(1, len(sentences))), 2),
            "keyword_overlap": 0,
            "transition_hits": 0,
            "unique_ratio": 0.0,
            "long_word_ratio": 0.0,
            "level": level,
            "task_type": task_type,
            "integrity_flag": reason,
        },
        "length_message": (
            f"Minimum target: {min_words} words." if min_words
            else "Response is too short for accurate evaluation."
        ),
        "keyword_focus": [],
        "task_structure": TASK_TYPE_HINTS.get(task_type, TASK_TYPE_HINTS["essay"]),
        "error_patterns_found": [],
        "rubric_summary": f"Submission flagged before full scoring because {reason}.",
    }
    return overall_score, feedback, summary, evaluation


def evaluate_writing_submission(text: str, task=None, topic=None) -> tuple[float, str, str, dict]:
    clean = (text or "").strip()
    words = _tokenize(clean)
    lc_words = [w.lower() for w in words]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", clean) if s.strip()]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", clean) if p.strip()]
    word_count = len(words)
    char_count = len(clean)
    sentence_count = len(sentences)
    paragraph_count = len(paragraphs)
    min_words = int(getattr(task, "min_words", 0) or 0)
    max_words = int(getattr(task, "max_words", 0) or 0)
    level = (getattr(task, "level", None) or getattr(topic, "level", None) or "basic").strip().lower()
    task_type = (getattr(task, "task_type", None) or "essay").strip().lower()
    target = LEVEL_TARGETS.get(level, LEVEL_TARGETS["basic"])

    quality_flags = _basic_text_quality_flags(clean, words, sentences, min_words)

    if not clean:
        return _invalid_submission_response(
            clean, level, task_type, min_words, max_words, "no answer was provided."
        )

    if quality_flags["very_short"]:
        return _invalid_submission_response(
            clean, level, task_type, min_words, max_words, "the answer is far too short."
        )

    if quality_flags["nonsense_like"]:
        return _invalid_submission_response(
            clean, level, task_type, min_words, max_words, "the text does not look meaningful enough."
        )

    if quality_flags["too_short_for_real_eval"] and sentence_count <= 1:
        return _invalid_submission_response(
            clean, level, task_type, min_words, max_words, "there is not enough sentence development."
        )

    avg_sentence_len = word_count / max(sentence_count, 1)
    unique_ratio = len(set(lc_words)) / max(word_count, 1)
    long_words = [w for w in lc_words if len(w) >= 7]
    long_word_ratio = len(long_words) / max(word_count, 1)
    transition_hits = sum(1 for phrase in TRANSITION_WORDS if phrase in clean.lower())
    repeated_word_penalty = sum(count - 3 for _, count in Counter(lc_words).items() if count > 3) * 0.08
    grammar_matches = [message for pat, message in COMMON_ERROR_PATTERNS if re.search(pat, clean, re.I)]
    grammar_hits = len(grammar_matches)
    capitalization_penalty = 0.0 if not clean or clean[:1].isupper() else 0.8
    punctuation_penalty = 0.0 if clean.endswith((".", "!", "?")) else 0.8
    short_sentence_penalty = 0.5 if sentence_count and avg_sentence_len < target["avg_sentence_low"] else 0.0
    long_sentence_penalty = 0.6 if avg_sentence_len > target["avg_sentence_high"] else 0.0

    grammar_score = 7.2 - (grammar_hits * 0.75) - capitalization_penalty - punctuation_penalty - short_sentence_penalty - long_sentence_penalty
    if sentence_count >= 3:
        grammar_score += 0.8
    if paragraph_count >= target["min_paragraphs"]:
        grammar_score += 0.3
    if word_count < max(20, min_words // 2 if min_words else 20):
        grammar_score -= 2.0
    grammar_score = _clamp(grammar_score)

    vocab_score = 4.8 + (unique_ratio * 4.1) + min(1.4, long_word_ratio * 10.0) - repeated_word_penalty
    if word_count < 40:
        vocab_score -= 1.4
    if long_word_ratio >= target["long_word_ratio"]:
        vocab_score += 0.4
    if word_count < max(20, min_words // 2 if min_words else 20):
        vocab_score -= 1.8
    vocab_score = _clamp(vocab_score)

    coherence_score = 3.8
    if sentence_count >= 3:
        coherence_score += 1.8
    if paragraph_count >= target["min_paragraphs"]:
        coherence_score += 1.8
    if transition_hits:
        coherence_score += min(1.8, transition_hits * 0.45)
    if clean.endswith((".", "!", "?")):
        coherence_score += 0.5
    if word_count < 35:
        coherence_score -= 1.4
    if sentence_count <= 1:
        coherence_score -= 2.2
    coherence_score = _clamp(coherence_score)

    prompt_keywords = _keywords_from_prompt(
        getattr(task, "title", ""),
        getattr(task, "instructions", ""),
        getattr(topic, "title", ""),
        getattr(topic, "description", ""),
    )
    submission_keywords = {w for w in lc_words if len(w) >= 4 and w not in STOPWORDS}
    keyword_overlap = len(prompt_keywords & submission_keywords)
    keyword_target = max(2, min(6, len(prompt_keywords) // 3 or 2))
    keyword_score = min(3.0, (keyword_overlap / max(keyword_target, 1)) * 3.0)

    if min_words > 0 and word_count < min_words:
        length_ratio = word_count / max(min_words, 1)
        length_component = max(0.5, 4.0 * length_ratio)
        length_status = "below_min"
        length_message = f"Below target length. Add more ideas to reach at least {min_words} words."
    elif max_words > 0 and word_count > max_words:
        overflow = word_count - max_words
        length_component = max(1.5, 4.0 - min(2.5, overflow / max(max_words, 1) * 8.0))
        length_status = "above_max"
        length_message = f"Above the limit by {overflow} words. Trim repeated or extra lines."
    else:
        length_component = 4.0
        length_status = "within_range"
        if min_words and max_words:
            length_message = f"Good length control. Your answer stays inside {min_words}-{max_words} words."
        elif min_words:
            length_message = f"Good length control. You met the minimum target of {min_words} words."
        elif max_words:
            length_message = f"Good length control. You stayed within the {max_words}-word limit."
        else:
            length_message = "Length is acceptable for this task."

    task_response_score = 2.8 + keyword_score + (length_component * 0.9)
    if sentence_count >= 3:
        task_response_score += 0.7
    if paragraph_count >= target["min_paragraphs"]:
        task_response_score += 0.4
    if sentence_count <= 1:
        task_response_score -= 2.4
    if keyword_overlap == 0 and prompt_keywords:
        task_response_score -= 2.0
    task_response_score = _clamp(task_response_score)

    dimensions = {
        "grammar": _round1(grammar_score),
        "vocabulary": _round1(vocab_score),
        "coherence": _round1(coherence_score),
        "task_response": _round1(task_response_score),
    }
    overall_score = _round1(sum(dimensions.values()) / 4.0)

    strengths = []
    improvements = []
    if dimensions["grammar"] >= 7:
        strengths.append("Grammar is mostly controlled and easy to follow.")
    else:
        improvements.append("Check sentence grammar, capitalization, and end punctuation more carefully.")
    if dimensions["vocabulary"] >= 7:
        strengths.append("Vocabulary shows a good range with less repetition.")
    else:
        improvements.append("Use a wider range of words and avoid repeating the same vocabulary.")
    if dimensions["coherence"] >= 7:
        strengths.append("Ideas are organized clearly and connect well from one point to the next.")
    else:
        improvements.append("Organize the answer into clearer paragraphs and add linking words for smoother flow.")
    if dimensions["task_response"] >= 7:
        strengths.append("The answer responds well to the task and keeps a suitable length.")
    else:
        improvements.append("Focus more directly on the task and develop each point fully within the required length.")
    if not strengths:
        strengths.append("You attempted the full task and presented a base to improve from.")

    sentence_alerts = _sentence_alerts(sentences)
    rewrite_suggestions = _rewrite_suggestions(sentences, transition_hits, keyword_overlap)
    rubric_cards = _rubric_cards(dimensions, level, task_type)
    task_structure = TASK_TYPE_HINTS.get(task_type, TASK_TYPE_HINTS["essay"])

    feedback_parts = strengths + improvements + sentence_alerts[:2] + [length_message]
    feedback = " ".join(feedback_parts)
    if min_words and max_words:
        length_target = f"Target range: {min_words}-{max_words} words"
    elif min_words:
        length_target = f"Minimum target: {min_words} words"
    elif max_words:
        length_target = f"Maximum target: {max_words} words"
    else:
        length_target = "Flexible length"
    summary = f"{word_count} words, {sentence_count} sentences, {paragraph_count} paragraphs. {length_target}."

    evaluation = {
        "scores": dimensions,
        "strengths": strengths,
        "improvements": improvements,
        "rewrite_suggestions": rewrite_suggestions,
        "rubric_cards": rubric_cards,
        "sentence_alerts": sentence_alerts,
        "metrics": {
            "word_count": word_count,
            "char_count": char_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "min_words": min_words,
            "max_words": max_words or None,
            "length_status": length_status,
            "avg_sentence_length": round(avg_sentence_len, 2),
            "keyword_overlap": keyword_overlap,
            "transition_hits": transition_hits,
            "unique_ratio": round(unique_ratio, 3),
            "long_word_ratio": round(long_word_ratio, 3),
            "level": level,
            "task_type": task_type,
            "real_word_ratio": quality_flags["real_word_ratio"],
            "alpha_ratio": quality_flags["alpha_ratio"],
        },
        "length_message": length_message,
        "keyword_focus": sorted(list(prompt_keywords))[:12],
        "task_structure": task_structure,
        "error_patterns_found": grammar_matches,
        "rubric_summary": f"Scored using grammar, vocabulary, coherence, and task response for a {level} {task_type} task.",
    }
    return overall_score, feedback, summary, evaluation