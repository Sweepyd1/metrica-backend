"""M-06: adding a student must use the same email normalization as signup."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from src.core.service.tutor import TutorService
from src.database.models import UserRole


class StudentLookupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.student = SimpleNamespace(id=5, role=UserRole.STUDENT)
        self.service = TutorService.__new__(TutorService)
        self.service.user_repo = SimpleNamespace(get_by_email=AsyncMock(return_value=self.student))
        self.service.tutor_student_repo = SimpleNamespace(
            get_by_tutor_and_student=AsyncMock(return_value=None),
            create=AsyncMock(return_value=SimpleNamespace(id=8)),
        )

    async def test_mixed_case_and_whitespace_find_registered_email(self):
        await self.service.add_student(1, "  Invited.Student@Yandex.RU  ")
        self.service.user_repo.get_by_email.assert_awaited_once_with("invited.student@yandex.ru")
        self.service.tutor_student_repo.create.assert_awaited_once_with(
            tutor_id=1, student_id=5, subject=None, student_inf=None)

    async def test_invited_student_already_linked_is_not_duplicated(self):
        self.service.tutor_student_repo.get_by_tutor_and_student.return_value = SimpleNamespace(id=8)
        with self.assertRaises(HTTPException) as caught:
            await self.service.add_student(1, "Invited.Student@Yandex.RU")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, "Ученик уже добавлен")
        self.service.tutor_student_repo.create.assert_not_awaited()

    async def test_missing_student_still_returns_404(self):
        self.service.user_repo.get_by_email.return_value = None
        with self.assertRaises(HTTPException) as caught:
            await self.service.add_student(1, "missing@yandex.ru")
        self.assertEqual(caught.exception.status_code, 404)
        self.service.tutor_student_repo.create.assert_not_awaited()

    async def test_other_role_is_not_added_as_student(self):
        self.student.role = UserRole.TUTOR
        with self.assertRaises(HTTPException) as caught:
            await self.service.add_student(1, "tutor@yandex.ru")
        self.assertEqual(caught.exception.status_code, 404)
        self.service.tutor_student_repo.create.assert_not_awaited()
