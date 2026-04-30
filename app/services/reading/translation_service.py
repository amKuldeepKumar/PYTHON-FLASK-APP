from __future__ import annotations

from dataclasses import dataclass

from ...models.reading_prompt_config import ReadingPromptConfig
from ..translation_engine import translate_text
from .provider_adapter_service import ReadingProviderAdapterService
from .provider_registry_service import ReadingProviderRegistryService


@dataclass
class ReadingWordSupportResult:
    ok: bool
    message: str
    payload: dict | None = None
    provider_name: str | None = None


class ReadingTranslationService:
    SIMPLE_MEANING_MAP = {
        "world": "the earth and all the people and places on it",
        "war": "a period of fighting between countries or groups",
        "basic": "simple and at an easy starting level",
        "simple": "easy to understand or do",
        "clear": "easy to understand",
        "beginner": "a person who is just starting to learn",
        "friendly": "kind, easy, or comfortable to use",
        "reading": "the activity of looking at and understanding written words",
        "passage": "a short piece of written text",
        "learner": "a person who is learning something",
        "students": "people who are learning in a class or course",
        "topic": "the subject being discussed or studied",
        "important": "very necessary or valuable",
        "support": "help or assistance",
        "question": "something asked to get an answer",
        "answer": "a reply to a question",
        "history": "the study of past events",
        "public": "for all people or the community",
        "discussion": "talking about something together",
        "facts": "true pieces of information",
        "complex": "not simple; difficult to understand",
        "guided": "helped or directed step by step",
        "confidence": "a feeling of trust in yourself",
        "explanation": "a statement that makes something clear",
        "translation": "the meaning of a word in another language",
        "expectation": "what is believed or hoped will happen",
        "expectations": "beliefs or hopes about what should happen",
        "activity": "a task or exercise to do",
        "activities": "tasks or exercises to do",
        "range": "the limits or spread of something",
        "sentence": "a group of words that makes a complete idea",
        "sentences": "groups of words that make complete ideas",
        "vocabulary": "all the words used in a language or topic",
        "lesson": "a period of learning or teaching",
        "today": "the present day",
        "final": "the last part or ending",
        "organized": "arranged in a clear order",
        "organised": "arranged in a clear order",
        "generated": "created or produced",
    }

    SIMPLE_SYNONYM_MAP = {
        "world": ["globe", "earth"],
        "war": ["conflict", "battle"],
        "basic": ["simple", "elementary"],
        "simple": ["easy", "clear"],
        "clear": ["plain", "obvious"],
        "beginner": ["starter", "new learner"],
        "friendly": ["helpful", "easy"],
        "reading": ["study", "perusal"],
        "passage": ["text", "paragraph"],
        "learner": ["student", "pupil"],
        "students": ["learners", "pupils"],
        "topic": ["subject", "theme"],
        "important": ["essential", "key"],
        "support": ["help", "assistance"],
        "question": ["query", "prompt"],
        "answer": ["response", "reply"],
        "history": ["past", "record"],
        "public": ["open", "community"],
        "discussion": ["talk", "conversation"],
        "facts": ["details", "truths"],
        "complex": ["difficult", "complicated"],
        "guided": ["directed", "supported"],
        "confidence": ["belief", "assurance"],
        "explanation": ["clarification", "description"],
        "translation": ["meaning in another language", "converted word"],
        "expectation": ["standard", "requirement"],
        "expectations": ["standards", "requirements"],
        "activity": ["task", "exercise"],
        "activities": ["tasks", "exercises"],
        "range": ["scope", "span"],
        "sentence": ["line", "statement"],
        "sentences": ["lines", "statements"],
        "vocabulary": ["word bank", "word stock"],
        "lesson": ["class", "session"],
        "today": ["nowadays", "at present"],
        "final": ["last", "ending"],
        "organized": ["arranged", "structured"],
        "organised": ["arranged", "structured"],
        "generated": ["created", "produced"],
    }

    @classmethod
    def _local_synonym(cls, word: str) -> str:
        clean = (word or "").strip().lower()
        if not clean:
            return ""

        variants = [clean]
        if clean.endswith("ies") and len(clean) > 3:
            variants.append(clean[:-3] + "y")
        if clean.endswith("es") and len(clean) > 3:
            variants.append(clean[:-2])
        if clean.endswith("s") and len(clean) > 3:
            variants.append(clean[:-1])
        if clean.endswith("ing") and len(clean) > 5:
            variants.append(clean[:-3])
            if clean[:-3].endswith(clean[:-4:-1]):
                variants.append(clean[:-4])
        if clean.endswith("ed") and len(clean) > 4:
            variants.append(clean[:-2])
            if len(clean) > 5 and clean[-3] == clean[-4]:
                variants.append(clean[:-3])
        for variant in variants:
            values = cls.SIMPLE_SYNONYM_MAP.get(variant)
            if values:
                return ", ".join(values[:2])

        if len(clean) <= 2:
            return clean
        if clean.endswith("ly"):
            return f"in a {clean[:-2]} way"
        if clean.endswith("ness"):
            return f"state of being {clean[:-4]}"
        if clean.endswith("tion"):
            return f"process of {clean[:-4]}ing"
        if clean.endswith("ment"):
            return f"result of {clean[:-4]}ing"
        return clean

    @classmethod
    def _local_meaning(cls, word: str, sentence: str = "") -> str:
        clean = (word or "").strip().lower()
        if not clean:
            return ""

        variants = [clean]
        if clean.endswith("ies") and len(clean) > 3:
            variants.append(clean[:-3] + "y")
        if clean.endswith("es") and len(clean) > 3:
            variants.append(clean[:-2])
        if clean.endswith("s") and len(clean) > 3:
            variants.append(clean[:-1])
        if clean.endswith("ing") and len(clean) > 5:
            variants.append(clean[:-3])
        if clean.endswith("ed") and len(clean) > 4:
            variants.append(clean[:-2])

        for variant in variants:
            value = cls.SIMPLE_MEANING_MAP.get(variant)
            if value:
                return value

        if clean.endswith("ly"):
            return f"in a {clean[:-2]} way"
        if clean.endswith("ness"):
            return f"the state or quality of being {clean[:-4]}"
        if clean.endswith("tion"):
            stem = clean[:-4]
            return f"the act, process, or result related to {stem}"
        if clean.endswith("ment"):
            stem = clean[:-4]
            return f"a result or condition related to {stem}"

        if sentence.strip():
            return f"Meaning of '{word.strip()}': used here in the context of the sentence."
        return f"A simple meaning of '{word.strip()}'."

    @classmethod
    def translate_word(cls, word: str, sentence: str = "", target_language: str = "English", target_language_code: str = "en") -> ReadingWordSupportResult:
        prompt = ReadingPromptConfig.query.filter_by(task_type=ReadingPromptConfig.TASK_TRANSLATION, is_active=True).first()
        prompt_text = prompt.prompt_text if prompt else "Provide simple meaning, synonym, and translation."
        prompt_snapshot = (
            prompt_text
            + f"\n\nWord: {word.strip()}"
            + (f"\nSentence: {sentence.strip()}" if sentence.strip() else "")
            + f"\nTarget language: {target_language.strip() or 'English'} ({(target_language_code or 'en').strip()})"
            + "\nReturn JSON with keys: word, meaning, synonym, translation."
        )
        execution = ReadingProviderRegistryService.execute_task(
            provider_kind=ReadingProviderRegistryService.KIND_TRANSLATION,
            payload={"task": "translation", "word": word, "sentence": sentence, "target_language": target_language, "target_language_code": target_language_code, "prompt": prompt_snapshot},
        )
        if not execution.get("ok"):
            return ReadingWordSupportResult(ok=False, message=execution.get("message") or "Translation failed.")
        provider = execution.get("provider") or {}
        text = ((execution.get("response") or {}).get("text") or "").strip()
        parsed = ReadingProviderAdapterService.parse_text_or_json(text)
        if isinstance(parsed, dict):
            payload = parsed
        else:
            clean_text = str(parsed or "").strip()
            payload = {
                "word": word,
                "meaning": cls._local_meaning(word, sentence),
                "synonym": cls._local_synonym(word),
                "translation": clean_text or (word.strip() if (target_language_code or "en").strip().lower() == "en" else f"{word.strip()} ({target_language.strip()})"),
            }
        return ReadingWordSupportResult(ok=True, message=execution.get("message") or "Translation completed.", payload=payload, provider_name=provider.get("name"))


    @classmethod
    def enrich_payload(cls, payload: dict | None, *, word: str, sentence: str = "", target_language_code: str = "en") -> dict:
        base = dict(payload or {})
        meaning = str(base.get("meaning") or "").strip()
        if not meaning or meaning.strip() == sentence.strip():
            meaning = cls._local_meaning(word, sentence)
        synonym = str(base.get("synonym") or "").strip() or cls._local_synonym(word)

        translation = str(base.get("translation") or "").strip()
        if not translation:
            try:
                translation, _ = translate_text(
                    word.strip(),
                    target_language_code or "en",
                    source_lang="en",
                    context="reading-word-support",
                )
            except Exception:
                translation = word.strip() if (target_language_code or "en").strip().lower() == "en" else f"[{target_language_code}] {word.strip()}"

        return {
            "word": word.strip(),
            "meaning": meaning,
            "synonym": synonym or "Not available yet",
            "translation": translation or word.strip(),
        }
