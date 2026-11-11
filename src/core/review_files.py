"""Review attachments with compatibility for older, per-submission links."""
from src.database.models import File, Lesson, LessonFile


def get_review_files(lesson: Lesson, submissions: list[LessonFile]) -> list[File]:
    files = lesson.review_files or [item.checked_file for item in submissions if item.checked_file]
    return list({file.id: file for file in files}.values())
