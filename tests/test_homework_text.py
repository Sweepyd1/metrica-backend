"""M-03 regressions: text-only homework, updates and older clients."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from pydantic import ValidationError

from src.core.service.tutor import TutorService
from src.database.models import Lesson
from src.schemas.tutor import LessonCreate, LessonUpdate


class HomeworkTextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.lesson = Lesson(id=42, tutor_student_id=1, homework_text="Старое задание")
        self.service = TutorService.__new__(TutorService)
        self.service.tutor_student_repo = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(tutor_id=7)))
        self.service.lesson_repo = SimpleNamespace(
            create=AsyncMock(return_value=self.lesson),
            get_tutor_lesson=AsyncMock(return_value=self.lesson),
            save=AsyncMock(),
        )
        self.service.lesson_file_repo = SimpleNamespace(create=AsyncMock(), sync_lesson_files=AsyncMock())
        self.payload = dict(tutor_student_id=1, date="2026-11-12", time="12:00", topic="Дроби")

    async def test_create_text_only_homework(self):
        await self.service.create_lesson(7, LessonCreate(**self.payload, homework_text="  Решите: https://example.com/task\n№ 3  "))
        self.assertEqual(self.service.lesson_repo.create.call_args.kwargs["homework_text"], "Решите: https://example.com/task\n№ 3")
        self.service.lesson_file_repo.create.assert_not_awaited()

    async def test_update_and_clear_text(self):
        await self.service.update_lesson(7, 42, LessonUpdate(**self.payload, homework_text="Новое задание"))
        self.assertEqual(self.lesson.homework_text, "Новое задание")
        await self.service.update_lesson(7, 42, LessonUpdate(**self.payload, homework_text="  "))
        self.assertIsNone(self.lesson.homework_text)

    async def test_old_client_does_not_erase_text(self):
        await self.service.update_lesson(7, 42, LessonUpdate(**self.payload))
        self.assertEqual(self.lesson.homework_text, "Старое задание")

    async def test_null_explicitly_clears_text(self):
        await self.service.update_lesson(7, 42, LessonUpdate(**self.payload, homework_text=None))
        self.assertIsNone(self.lesson.homework_text)

    async def test_ownership_still_required(self):
        with self.assertRaises(HTTPException) as caught:
            await self.service.create_lesson(8, LessonCreate(**self.payload, homework_text="Задание"))
        self.assertEqual(caught.exception.status_code, 403)
        self.service.lesson_repo.create.assert_not_awaited()

    def test_text_length_is_bounded(self):
        with self.assertRaises(ValidationError):
            LessonCreate(**self.payload, homework_text="x" * 10001)


if __name__ == "__main__":
    unittest.main()
