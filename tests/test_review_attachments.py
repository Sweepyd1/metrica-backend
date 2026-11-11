"""M-14: reviewed copies must not be truncated to the source photo count."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from src.core.review_files import get_review_files
from src.core.service.tutor import TutorService
from src.database.models import LessonFileKind
from src.schemas.tutor import SubmissionCheck


class ReviewAttachmentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.lesson = SimpleNamespace(review_files=[], tutor_student=SimpleNamespace(star_rewards_enabled=False))
        self.submission = SimpleNamespace(id=1, lesson_id=10, kind=LessonFileKind.SUBMISSION, lesson=self.lesson)
        self.files = {file_id: SimpleNamespace(id=file_id, uploaded_by=7) for file_id in (20, 21, 22)}
        self.service = TutorService.__new__(TutorService)
        self.service.file_repo = SimpleNamespace(get_by_id=AsyncMock(side_effect=lambda file_id: self.files.get(file_id)))
        self.service.lesson_file_repo = SimpleNamespace(
            get_submission_for_tutor=AsyncMock(return_value=self.submission),
            get_submissions_for_lesson=AsyncMock(return_value=[self.submission]),
            save_many=AsyncMock(),
        )
        self.service._submission_to_schema = lambda sub: sub

    async def test_keeps_all_three_files_for_one_source(self):
        await self.service.check_submission(7, 1, SubmissionCheck(grade=4, checked_file_ids=[20, 21, 22]))
        self.assertEqual([file.id for file in self.lesson.review_files], [20, 21, 22])
        self.assertEqual(self.submission.checked_file_id, 20)  # Older clients retain their first-file link.
        self.service.lesson_file_repo.save_many.assert_awaited_once()

    async def test_rechecking_clears_all_previous_copies(self):
        self.lesson.review_files = [self.files[20]]
        await self.service.check_submission(7, 1, SubmissionCheck(grade=5, checked_file_ids=[]))
        self.assertEqual(self.lesson.review_files, [])
        self.assertIsNone(self.submission.checked_file_id)

    async def test_foreign_file_is_rejected_before_changing_review(self):
        self.lesson.review_files = [self.files[20]]
        self.files[21].uploaded_by = 8
        with self.assertRaises(HTTPException) as caught:
            await self.service.check_submission(7, 1, SubmissionCheck(grade=4, checked_file_ids=[21]))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.lesson.review_files, [self.files[20]])
        self.service.lesson_file_repo.save_many.assert_not_awaited()

    async def test_duplicate_ids_are_not_saved_twice(self):
        await self.service.check_submission(7, 1, SubmissionCheck(grade=4, checked_file_ids=[20, 20]))
        self.assertEqual([file.id for file in self.lesson.review_files], [20])

    def test_old_reviews_remain_readable_without_new_links(self):
        old = [SimpleNamespace(checked_file=self.files[20]), SimpleNamespace(checked_file=self.files[20])]
        self.assertEqual(get_review_files(self.lesson, old), [self.files[20]])

    def test_full_collection_is_used_by_serializers(self):
        self.lesson.review_files = [self.files[20], self.files[21]]
        self.assertEqual(get_review_files(self.lesson, []), [self.files[20], self.files[21]])
