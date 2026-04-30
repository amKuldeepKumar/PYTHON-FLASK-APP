from __future__ import annotations


class GuardrailService:
    MIN_TRANSCRIPT_WORDS = 3
    MAX_REPEAT_WORD_RATIO = 0.72

    @staticmethod
    def normalize_transcript(transcript: str | None) -> str:
        text = (transcript or '').replace('\r', ' ').replace('\n', ' ')
        text = ' '.join(text.split())
        return text.strip()

    @classmethod
    def is_submittable(cls, transcript: str | None) -> bool:
        normalized = cls.normalize_transcript(transcript)
        return len(normalized.split()) >= cls.MIN_TRANSCRIPT_WORDS

    @classmethod
    def validate_transcript(cls, transcript: str | None) -> tuple[bool, str | None]:
        normalized = cls.normalize_transcript(transcript)
        words = normalized.split()
        if len(words) < cls.MIN_TRANSCRIPT_WORDS:
            return False, 'Please enter a longer transcript before submitting.'
        unique_ratio = (len(set(word.lower() for word in words)) / len(words)) if words else 0
        if words and (1 - unique_ratio) > cls.MAX_REPEAT_WORD_RATIO and len(words) >= 10:
            return False, 'Your answer has too many repeated words. Please speak naturally.'
        return True, None
