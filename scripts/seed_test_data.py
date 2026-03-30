import sys
from pathlib import Path
from datetime import date, datetime, time, timedelta

from passlib.context import CryptContext
from sqlalchemy import delete, text

# Allow running the script directly from the project root on Windows/Python.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db_manager import db_manager
from database.models import (
    File,
    Lesson,
    LessonFile,
    LessonFileKind,
    SubmissionStatus,
    TutorStudent,
    User,
    UserRole,
)


pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


async def reseed() -> None:
    async with db_manager.get_session() as session:
        # Remove only the fixed demo rows so the script can be re-run safely.
        await session.execute(
            delete(LessonFile).where(LessonFile.id.in_([1, 2, 3, 4, 5]))
        )
        await session.execute(delete(Lesson).where(Lesson.id.in_([1, 2, 3])))
        await session.execute(delete(File).where(File.id.in_([1, 2, 3, 4, 5])))
        await session.execute(delete(TutorStudent).where(TutorStudent.id == 1))
        await session.execute(delete(User).where(User.id.in_([1, 2])))
        await session.commit()

        tutor = User(
            id=1,
            email="tutor@example.com",
            password=pwd_context.hash("test1234"),
            first_name="Ivan",
            last_name="Tutor",
            role=UserRole.TUTOR,
        )
        student = User(
            id=2,
            email="student@example.com",
            password=pwd_context.hash("test1234"),
            first_name="Anna",
            last_name="Student",
            role=UserRole.STUDENT,
        )
        session.add_all([tutor, student])
        await session.flush()

        link = TutorStudent(
            id=1,
            tutor_id=tutor.id,
            student_id=student.id,
            subject="Mathematics",
            student_inf="7 grade, demo student for API testing",
        )
        session.add(link)
        await session.flush()

        today = date.today()
        now = datetime.now().time().replace(second=0, microsecond=0)

        upcoming_lesson = Lesson(
            id=1,
            tutor_student_id=link.id,
            l_date=today + timedelta(days=2),
            l_time=time(hour=18, minute=0),
            topic="Fractions and proportions",
            meet_link="https://meet.google.com/demo-upcoming-lesson",
            homework_done=False,
            homework_deadline=today + timedelta(days=4),
        )
        checked_lesson = Lesson(
            id=2,
            tutor_student_id=link.id,
            l_date=today - timedelta(days=3),
            l_time=time(hour=16, minute=30),
            topic="Linear equations",
            meet_link="https://meet.google.com/demo-checked-lesson",
            homework_done=True,
            homework_deadline=today - timedelta(days=1),
        )
        submitted_lesson = Lesson(
            id=3,
            tutor_student_id=link.id,
            l_date=today - timedelta(days=1),
            l_time=now,
            topic="Percentages",
            meet_link="https://meet.google.com/demo-submitted-lesson",
            homework_done=True,
            homework_deadline=today + timedelta(days=1),
        )
        session.add_all([upcoming_lesson, checked_lesson, submitted_lesson])
        await session.flush()

        files = [
            File(
                id=1,
                path="uploads/material_fractions.pdf",
                filename="material_fractions.pdf",
                type="application/pdf",
                uploaded_by=tutor.id,
            ),
            File(
                id=2,
                path="uploads/homework_linear.jpg",
                filename="homework_linear.jpg",
                type="image/jpeg",
                uploaded_by=tutor.id,
            ),
            File(
                id=3,
                path="uploads/submission_linear.pdf",
                filename="submission_linear.pdf",
                type="application/pdf",
                uploaded_by=student.id,
            ),
            File(
                id=4,
                path="uploads/material_percentages.pdf",
                filename="material_percentages.pdf",
                type="application/pdf",
                uploaded_by=tutor.id,
            ),
            File(
                id=5,
                path="uploads/submission_percentages.jpg",
                filename="submission_percentages.jpg",
                type="image/jpeg",
                uploaded_by=student.id,
            ),
        ]
        session.add_all(files)
        await session.flush()

        lesson_files = [
            LessonFile(
                id=1,
                lesson_id=upcoming_lesson.id,
                file_id=1,
                kind=LessonFileKind.MATERIAL,
            ),
            LessonFile(
                id=2,
                lesson_id=checked_lesson.id,
                file_id=2,
                kind=LessonFileKind.HOMEWORK_TASK,
            ),
            LessonFile(
                id=3,
                lesson_id=checked_lesson.id,
                file_id=3,
                kind=LessonFileKind.SUBMISSION,
                status=SubmissionStatus.CHECKED,
                comment="Good work. Recheck task 3 for sign mistakes.",
            ),
            LessonFile(
                id=4,
                lesson_id=submitted_lesson.id,
                file_id=4,
                kind=LessonFileKind.MATERIAL,
            ),
            LessonFile(
                id=5,
                lesson_id=submitted_lesson.id,
                file_id=5,
                kind=LessonFileKind.SUBMISSION,
                status=SubmissionStatus.SUBMITTED,
                comment=None,
            ),
        ]
        session.add_all(lesson_files)
        await session.commit()

        # Sync PostgreSQL sequences after inserting explicit ids.
        for table_name in ["users", "tutor_student", "lesson", "file", "lesson_file"]:
            await session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), true)"
                )
            )
        await session.commit()

    print("Seed completed.")
    print("Tutor: tutor@example.com / test1234")
    print("Student (id=2): student@example.com / test1234")


if __name__ == "__main__":
    import asyncio

    asyncio.run(reseed())
