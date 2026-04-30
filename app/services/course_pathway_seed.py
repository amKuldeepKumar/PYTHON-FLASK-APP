from __future__ import annotations

from dataclasses import dataclass

from ..extensions import db
from ..models.lms import Course
from ..models.speaking_topic import SpeakingTopic
from ..models.speaking_prompt import SpeakingPrompt
from ..models.writing_topic import WritingTopic
from ..models.writing_task import WritingTask
from .lms_service import LMSService


@dataclass
class PathwayCourseResult:
    course: Course
    created: bool


def _get_or_create_course(*, title: str, owner_admin_id: int | None, created_by_id: int | None, **kwargs) -> PathwayCourseResult:
    course = Course.query.filter(Course.title == title).first()
    if course:
        changed = False
        for key, value in kwargs.items():
            if hasattr(course, key) and getattr(course, key) != value:
                setattr(course, key, value)
                changed = True
        if changed:
            db.session.flush()
        return PathwayCourseResult(course=course, created=False)

    course = LMSService.create_course(title, owner_admin_id, created_by_id, **kwargs)
    return PathwayCourseResult(course=course, created=True)


def _ensure_speaking_topic(course: Course, *, code: str, title: str, description: str, level: str, prompts: list[dict], owner_admin_id: int | None = None, order: int = 0) -> None:
    topic = SpeakingTopic.query.filter_by(course_id=course.id, code=code).first()
    if not topic:
        topic = SpeakingTopic(
            owner_admin_id=owner_admin_id,
            course_id=course.id,
            course_level_number=1,
            code=code,
            title=title,
            description=description,
            level=level,
            language_code=course.language_code or 'en',
            display_order=order,
            is_active=True,
            is_published=True,
            access_type='free' if not course.is_premium else 'paid',
            price=float(course.current_price or 0),
            currency=course.currency_code or 'INR',
        )
        db.session.add(topic)
        db.session.flush()
    else:
        topic.title = title
        topic.description = description
        topic.level = level
        topic.display_order = order
        topic.is_active = True
        topic.is_published = True

    for idx, prompt_data in enumerate(prompts, start=1):
        prompt = SpeakingPrompt.query.filter_by(topic_id=topic.id, title=prompt_data['title']).first()
        if not prompt:
            prompt = SpeakingPrompt(topic_id=topic.id, owner_admin_id=owner_admin_id, title=prompt_data['title'])
            db.session.add(prompt)
        prompt.prompt_text = prompt_data['prompt_text']
        prompt.instruction_text = prompt_data.get('instruction_text')
        prompt.difficulty = prompt_data.get('difficulty', level)
        prompt.estimated_seconds = int(prompt_data.get('estimated_seconds', 75))
        prompt.target_duration_seconds = int(prompt_data.get('target_duration_seconds', prompt.estimated_seconds))
        prompt.min_duration_seconds = int(prompt_data.get('min_duration_seconds', max(20, int(prompt.estimated_seconds * 0.5))))
        prompt.max_duration_seconds = int(prompt_data.get('max_duration_seconds', max(prompt.estimated_seconds, int(prompt.estimated_seconds * 1.5))))
        prompt.display_order = idx
        prompt.is_active = True


def _ensure_writing_topic(course: Course, *, code: str, title: str, category: str, description: str, level: str, tasks: list[dict], order: int = 0) -> None:
    topic = WritingTopic.query.filter_by(course_id=course.id, code=code).first()
    if not topic:
        topic = WritingTopic(
            code=code,
            title=title,
            category=category,
            description=description,
            level=level,
            course_id=course.id,
            course_level_number=1,
            display_order=order,
            is_active=True,
            is_published=True,
        )
        db.session.add(topic)
        db.session.flush()
    else:
        topic.title = title
        topic.category = category
        topic.description = description
        topic.level = level
        topic.display_order = order
        topic.is_active = True
        topic.is_published = True

    for idx, task_data in enumerate(tasks, start=1):
        task = WritingTask.query.filter_by(topic_id=topic.id, title=task_data['title']).first()
        if not task:
            task = WritingTask(topic_id=topic.id, topic_title_snapshot=title, title=task_data['title'])
            db.session.add(task)
        task.topic_title_snapshot = title
        task.instructions = task_data['instructions']
        task.task_type = task_data.get('task_type', 'essay')
        task.level = task_data.get('level', level)
        task.min_words = int(task_data.get('min_words', 120))
        task.max_words = int(task_data.get('max_words', 250)) if task_data.get('max_words') else None
        task.language_code = course.language_code or 'en'
        task.course_id = course.id
        task.course_level_number = 1
        task.display_order = idx
        task.is_active = True
        task.is_published = True


def ensure_special_english_pathways(owner_admin_id: int | None, created_by_id: int | None) -> list[PathwayCourseResult]:
    results: list[PathwayCourseResult] = []

    spoken = _get_or_create_course(
        title='Spoken English',
        owner_admin_id=owner_admin_id,
        created_by_id=created_by_id,
        slug='spoken-english',
        description='Daily conversation practice course with Q&A speaking prompts, routine situations, and model-answer guidance for real fluency growth.',
        language_code='en',
        track_type='speaking',
        difficulty='basic',
        max_level=1,
        access_type='free',
        is_published=True,
        is_premium=False,
        lesson_title='Daily Conversation Flow',
        lesson_type='speaking',
        explanation_text='Practice short everyday speaking answers. Focus on confidence, natural speed, and useful daily phrases.',
        badge_title='Spoken English',
        badge_subtitle='Daily Practice',
        badge_template='gradient',
        badge_animation='glow',
    )
    _ensure_speaking_topic(spoken.course, code='spoken-daily-conversation', title='Daily Conversation Topics', description='Practice everyday questions for self-introduction, routine, shopping, travel, and social situations.', level='basic', order=1, owner_admin_id=owner_admin_id, prompts=[
        {'title': 'Morning Routine', 'prompt_text': 'Describe your daily morning routine in simple English.', 'instruction_text': 'Answer for 45-60 seconds. Mention time, actions, and small habits. Model direction: I wake up at..., then I..., after that I...', 'estimated_seconds': 60},
        {'title': 'At the Market', 'prompt_text': 'How would you buy vegetables at a local market in English?', 'instruction_text': 'Speak naturally. Include greeting, asking price, quantity, and closing politely.', 'estimated_seconds': 75},
        {'title': 'Meeting a New Friend', 'prompt_text': 'Introduce yourself to a new friend and continue the conversation.', 'instruction_text': 'Include your name, city, interests, and one follow-up question.', 'estimated_seconds': 75},
    ])
    _ensure_speaking_topic(spoken.course, code='spoken-functional-qa', title='Functional Q&A Practice', description='Quick-answer speaking prompts for common daily English use.', level='basic', order=2, owner_admin_id=owner_admin_id, prompts=[
        {'title': 'Ask for Directions', 'prompt_text': 'Ask someone for directions to the railway station.', 'instruction_text': 'Use polite English and at least two follow-up questions.', 'estimated_seconds': 60},
        {'title': 'Phone Call Practice', 'prompt_text': 'Make a short phone call to ask about a class timing.', 'instruction_text': 'Start politely, ask clearly, and close the call well.', 'estimated_seconds': 60},
    ])
    results.append(spoken)

    interview = _get_or_create_course(
        title='Interview Preparation',
        owner_admin_id=owner_admin_id,
        created_by_id=created_by_id,
        slug='interview-preparation',
        description='Job-focused English course with HR questions, self-introduction practice, and mock interview speaking sessions.',
        language_code='en',
        track_type='speaking',
        difficulty='intermediate',
        max_level=1,
        access_type='free',
        is_published=True,
        is_premium=False,
        lesson_title='Mock Interview Practice',
        lesson_type='interview',
        explanation_text='Train for real interviews with clear HR-style answers, structure, confidence, and relevance.',
        badge_title='Interview Prep',
        badge_subtitle='Job Ready',
        badge_template='glass',
        badge_animation='pulse',
    )
    _ensure_speaking_topic(interview.course, code='interview-self-intro', title='Self Introduction', description='Build a strong tell-me-about-yourself answer.', level='intermediate', order=1, owner_admin_id=owner_admin_id, prompts=[
        {'title': 'Tell Me About Yourself', 'prompt_text': 'Give a professional self introduction for a job interview.', 'instruction_text': 'Structure: present role or study, strengths, experience, goals. Keep it clear and confident.', 'estimated_seconds': 90},
        {'title': 'Why Should We Hire You?', 'prompt_text': 'Answer: Why should we hire you for this role?', 'instruction_text': 'Mention strengths, value, and fit for the job.', 'estimated_seconds': 90},
    ])
    _ensure_speaking_topic(interview.course, code='interview-hr-answers', title='HR Answer Practice', description='Practice common HR interview questions with focused job-ready English.', level='intermediate', order=2, owner_admin_id=owner_admin_id, prompts=[
        {'title': 'Strengths and Weaknesses', 'prompt_text': 'Talk about one strength and one weakness professionally.', 'instruction_text': 'Be honest, balanced, and solution-oriented.', 'estimated_seconds': 90},
        {'title': 'Career Goal', 'prompt_text': 'Where do you see yourself in five years?', 'instruction_text': 'Answer with ambition and realistic growth steps.', 'estimated_seconds': 75},
        {'title': 'Handle Pressure', 'prompt_text': 'Describe how you handle pressure at work or study.', 'instruction_text': 'Use one example and show calm problem solving.', 'estimated_seconds': 75},
    ])
    results.append(interview)

    advanced = _get_or_create_course(
        title='English Super Advanced',
        owner_admin_id=owner_admin_id,
        created_by_id=created_by_id,
        slug='english-super-advanced',
        description='Premium advanced English pathway with debate-style prompts, advanced vocabulary use, and formal writing tasks for high-level learners.',
        language_code='en',
        track_type='writing',
        difficulty='advanced',
        max_level=1,
        access_type='paid',
        base_price='1999',
        sale_price='1499',
        is_published=True,
        is_premium=True,
        lesson_title='Formal Writing Mastery',
        lesson_type='writing',
        explanation_text='Use high-level language, argument structure, nuance, and polished formal writing.',
        badge_title='Premium Advanced',
        badge_subtitle='Debate + Writing',
        badge_template='gold',
        badge_animation='shimmer',
    )
    _ensure_writing_topic(advanced.course, code='esa-debate-topics', title='Debate Topics', category='Debate', description='Write structured high-level responses to debate-style issues.', level='advanced', order=1, tasks=[
        {'title': 'Technology and Privacy', 'instructions': 'Write a balanced formal response on whether technological convenience justifies the loss of personal privacy. Include a clear position, counterargument, and conclusion.', 'task_type': 'essay', 'min_words': 220, 'max_words': 320},
        {'title': 'Globalisation Debate', 'instructions': 'Write an advanced argument on whether globalisation benefits developing countries more than it harms them.', 'task_type': 'essay', 'min_words': 220, 'max_words': 320},
    ])
    _ensure_writing_topic(advanced.course, code='esa-advanced-vocabulary', title='Advanced Vocabulary in Context', category='Vocabulary', description='Apply sophisticated vocabulary naturally in controlled formal writing.', level='advanced', order=2, tasks=[
        {'title': 'Precision Vocabulary Paragraph', 'instructions': 'Write a formal paragraph using nuanced academic vocabulary naturally and clearly. Avoid forced wording and maintain coherence.', 'task_type': 'paragraph', 'min_words': 150, 'max_words': 220},
    ])
    _ensure_writing_topic(advanced.course, code='esa-formal-writing', title='Formal Writing', category='Formal Writing', description='High-level formal writing tasks for advanced learners and exam-style practice.', level='advanced', order=3, tasks=[
        {'title': 'Policy Recommendation Letter', 'instructions': 'Write a formal recommendation letter proposing one education reform and defending it with clear evidence and tone control.', 'task_type': 'letter', 'min_words': 200, 'max_words': 280},
    ])
    results.append(advanced)

    db.session.commit()
    return results
