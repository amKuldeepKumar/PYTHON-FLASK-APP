from decimal import Decimal

from app.extensions import db
from app.models.lms import Course, Level, Lesson, Chapter, Subsection

if Course.query.count() == 0:
    demo_courses = [
        {
            "title": "Spoken English Starter",
            "slug": "spoken-english-starter",
            "description": "Build confidence in daily spoken English.",
            "language_code": "en",
            "track_type": "speaking",
            "difficulty": "basic",
        },
        {
            "title": "Reading Practice Course",
            "slug": "reading-practice-course",
            "description": "Improve reading accuracy and comprehension.",
            "language_code": "en",
            "track_type": "reading",
            "difficulty": "intermediate",
        },
        {
            "title": "Writing Skills Course",
            "slug": "writing-skills-course",
            "description": "Practice structured writing with guided tasks.",
            "language_code": "en",
            "track_type": "writing",
            "difficulty": "intermediate",
        },
        {
            "title": "Listening Mastery Course",
            "slug": "listening-mastery-course",
            "description": "Train your listening with practical exercises.",
            "language_code": "en",
            "track_type": "listening",
            "difficulty": "basic",
        },
        {
            "title": "Interview Preparation",
            "slug": "interview-preparation",
            "description": "Prepare for HR and role-based interviews.",
            "language_code": "en",
            "track_type": "interview",
            "difficulty": "advanced",
        },
    ]

    for item in demo_courses:
        course = Course(
            title=item["title"],
            slug=item["slug"],
            description=item["description"],
            language_code=item["language_code"],
            track_type=item["track_type"],
            difficulty=item["difficulty"],
            max_level=1,
            access_type="free",
            allow_level_purchase=False,
            level_access_type="free",
            currency_code="INR",
            level_price=Decimal("0.00"),
            base_price=Decimal("0.00"),
            is_published=True,
            is_premium=False,
            status="published",
            workflow_status="published",
        )
        db.session.add(course)
        db.session.flush()

        level = Level(
            course_id=course.id,
            title="Level 1",
            description="Starter level",
            sort_order=1,
        )
        db.session.add(level)
        db.session.flush()

        lesson = Lesson(
            level_id=level.id,
            title="Lesson 1",
            slug=f"{course.slug}-lesson-1",
            lesson_type="guided",
            explanation_text="Welcome to this course.",
            explanation_tts_text="Welcome to this course.",
            estimated_minutes=10,
            is_published=True,
            sort_order=1,
            workflow_status="published",
        )
        db.session.add(lesson)
        db.session.flush()

        chapter = Chapter(
            lesson_id=lesson.id,
            title="Chapter 1",
            description="Introduction chapter",
            sort_order=1,
        )
        db.session.add(chapter)
        db.session.flush()

        subsection = Subsection(
            chapter_id=chapter.id,
            title="Subsection 1",
            sort_order=1,
        )
        db.session.add(subsection)

    db.session.commit()
    print("Demo public courses created successfully.")
else:
    print("Courses already exist:", Course.query.count())