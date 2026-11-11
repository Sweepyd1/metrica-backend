"""The student report endpoint must never expose another student's review."""
import unittest
from unittest.mock import AsyncMock
from datetime import date

from src.ai_checker.integration import get_student_ai_review_state
from src.database.models import AiHomeworkReview, AiReviewStatus


class StudentAiReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_unowned_lesson_stops_before_reading_report(self):
        session = AsyncMock()
        session.scalar.return_value = None
        with self.assertRaises(LookupError):
            await get_student_ai_review_state(session, 2, 42)
        self.assertEqual(session.scalar.await_count, 1)

    async def test_no_report_is_not_started(self):
        session = AsyncMock()
        session.scalar.side_effect = [42, None]
        state = await get_student_ai_review_state(session, 2, 42)
        self.assertEqual(state.status, "not_started")
        self.assertFalse(state.available)
        self.assertIsNone(state.result)

    async def test_saved_error_reason_is_returned(self):
        review = AiHomeworkReview(id=1, lesson_id=42, student_id=2, tutor_id=7,
            status=AiReviewStatus.COMPLETED, provider="test", model="test", usage_date=date.today(),
            result_json={"readable": True, "tasks": [{"task_label": "1", "transcription": "x=7",
                "is_correct": False, "errors": [{"location": "2", "student_wrote": "x=7",
                    "correct": "x=3", "explanation": "При переносе меняется знак",
                    "topic": "Уравнения", "severity": "conceptual"}]}]})
        session = AsyncMock()
        session.scalar.side_effect = [42, review]
        state = await get_student_ai_review_state(session, 2, 42)
        self.assertEqual(state.result.tasks[0].errors[0].explanation, "При переносе меняется знак")
        self.assertFalse(state.available)
