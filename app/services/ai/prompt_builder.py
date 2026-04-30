from __future__ import annotations

from typing import Any

from .rule_service import AIRuleService


class AIPromptBuilder:
    TEMPLATES = {
        'translation': (
            'Translate the source text from {source_language} to {target_language}. '
            'Return only the translated text and keep the meaning accurate.\n\n'
            'Source text:\n{source_text}'
        ),
        'speaking_evaluation': (
            'Evaluate the student speaking response using five dimensions: pronunciation, fluency, grammar, '
            'sentence making, and relevance. Give short strengths and improvement notes.\n\n'
            'Prompt topic: {prompt_text}\nTranscript:\n{transcript}\nDuration seconds: {duration_seconds}'
        ),
        'speaking_tts': (
            'Prepare the following text for text-to-speech playback. Keep pauses natural and preserve pronunciation hints.\n\n'
            'Voice name: {voice_name}\nText:\n{text}'
        ),
        'reading_passage': (
            'Generate a reading passage for the topic "{topic}". Level: {level}. Length mode: {length_mode}. '
            'Target words: {target_words}. Keep the passage classroom-ready and aligned to the learning goal.\n\n'
            'Topic description: {topic_description}'
        ),
        'reading_question': (
            'Generate reading questions from the passage below. Create {mcq_count} MCQ, {fill_blank_count} fill-in-the-blank, '
            'and {true_false_count} true/false questions. Include answers and explanations.\n\n'
            'Passage:\n{passage_content}'
        ),
        'writing_evaluation': (
            'Evaluate this writing response for grammar, vocabulary, coherence, and task response. '
            'Respect the target word range if provided and return balanced feedback.\n\n'
            'Task title: {task_title}\nInstructions: {task_instructions}\nSubmission:\n{submission_text}'
        ),
        'writing_plagiarism': (
            'Compare the student submission with the reference text and estimate overlap risk. '
            'Return overlap percentage, risk level, and short reasons.\n\n'
            'Submission:\n{submission_text}\n\nReference:\n{reference_text}'
        ),
        'listening_review': (
            'Review this listening item for clarity, caption accuracy, answerability, and lesson quality. '
            'Return whether it should be approved, rejected, or kept pending, with one concise reason.\n\n'
            'Topic: {topic_title}\nPrompt: {prompt_text}\nCaptions:\n{caption_text}'
        ),
    }

    @classmethod
    def build(cls, task_key: str, **context: Any) -> str:
        template = cls.TEMPLATES.get(task_key)
        if not template:
            ordered = '\n'.join(f'{key}: {value}' for key, value in sorted(context.items()))
            return f'Task: {task_key}\n{ordered}'.strip()
        safe_context = {key: ('' if value is None else value) for key, value in context.items()}
        try:
            built = template.format(**safe_context).strip()
            prefix = AIRuleService.prompt_prefix_for_task(task_key)
            return f"{prefix}\n\n{built}".strip() if prefix else built
        except KeyError:
            ordered = '\n'.join(f'{key}: {value}' for key, value in sorted(safe_context.items()))
            built = f'{template}\n\n{ordered}'.strip()
            prefix = AIRuleService.prompt_prefix_for_task(task_key)
            return f"{prefix}\n\n{built}".strip() if prefix else built

    @classmethod
    def preview_catalog(cls) -> list[dict[str, str]]:
        previews: list[dict[str, str]] = []
        sample_context = {
            'source_language': 'English',
            'target_language': 'Punjabi',
            'source_text': 'What is your name?',
            'prompt_text': 'Speak about your hometown.',
            'transcript': 'My hometown is peaceful and full of friendly people.',
            'duration_seconds': 42,
            'voice_name': 'Default voice',
            'text': 'Welcome to Fluencify. Your lesson is ready.',
            'topic': 'World War',
            'level': 'Advanced',
            'length_mode': 'Long',
            'target_words': 220,
            'topic_description': 'History topic for reading practice.',
            'mcq_count': 3,
            'fill_blank_count': 2,
            'true_false_count': 2,
            'passage_content': 'Sample passage content for preview.',
            'task_title': 'Discuss world peace',
            'task_instructions': 'Write 250 words about how countries can avoid war.',
            'submission_text': 'Countries should communicate and work together.',
            'reference_text': 'Countries should work together and communicate clearly.',
            'topic_title': 'Daily Routine',
            'caption_text': 'This is a sample caption block.',
        }
        for task_key in sorted(cls.TEMPLATES.keys()):
            previews.append({
                'task_key': task_key,
                'prompt': cls.build(task_key, **sample_context),
            })
        return previews
