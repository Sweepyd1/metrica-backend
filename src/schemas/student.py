import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, Field


class LessonAttachmentOut(BaseModel):
    id: int
    filename: Optional[str] = None
    file_url: Optional[str] = None
    type: Optional[str] = None


class StudentLessonSummary(BaseModel):
    id: int
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    topic: Optional[str] = None
    tutor_name: str
    meet_link: Optional[str] = None
    materials: List[LessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: List[LessonAttachmentOut] = Field(default_factory=list)
    homework_deadline: Optional[dt.date] = None
    homework_status: str


class StudentLessonListOut(BaseModel):
    upcoming: List[StudentLessonSummary]
    past: List[StudentLessonSummary]


class StudentLessonDetail(StudentLessonSummary):
    submission_file: Optional[LessonAttachmentOut] = None
    submission_comment: Optional[str] = None


class HomeworkSubmissionOut(BaseModel):
    lesson_id: int
    homework_status: str
    submission_file: LessonAttachmentOut
    submission_comment: Optional[str] = None
