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
    star_rewards_enabled: bool = False
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    tutor_name: str
    meet_link: Optional[str] = None
    materials: List[LessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: List[LessonAttachmentOut] = Field(default_factory=list)
    homework_deadline: Optional[dt.date] = None
    homework_deadline_missed: bool = False
    homework_status: str
    submission_file: Optional[LessonAttachmentOut] = None
    submission_files: List[LessonAttachmentOut] = Field(default_factory=list)
    checked_file: Optional[LessonAttachmentOut] = None
    checked_files: List[LessonAttachmentOut] = Field(default_factory=list)
    submission_comment: Optional[str] = None
    student_comment: Optional[str] = None
    submitted_at: Optional[dt.datetime] = None
    homework_grade: Optional[float] = None
    homework_stars: float = 0


class StudentLessonListOut(BaseModel):
    upcoming: List[StudentLessonSummary]
    past: List[StudentLessonSummary]


class StudentLessonDetail(StudentLessonSummary):
    pass


class HomeworkSubmissionOut(BaseModel):
    lesson_id: int
    star_rewards_enabled: bool = False
    homework_status: str
    homework_deadline_missed: bool = False
    submission_file: Optional[LessonAttachmentOut] = None
    submission_files: List[LessonAttachmentOut] = Field(default_factory=list)
    checked_file: Optional[LessonAttachmentOut] = None
    checked_files: List[LessonAttachmentOut] = Field(default_factory=list)
    submission_comment: Optional[str] = None
    student_comment: Optional[str] = None
    submitted_at: Optional[dt.datetime] = None
    homework_grade: Optional[float] = None
    homework_stars: float = 0
