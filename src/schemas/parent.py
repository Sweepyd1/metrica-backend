import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field


class ParentChildAdd(BaseModel):
    email: str


class ParentChildOut(BaseModel):
    id: int
    student_id: int
    full_name: str
    created_at: dt.datetime


class ParentLessonAttachmentOut(BaseModel):
    id: int
    filename: Optional[str] = None
    file_url: Optional[str] = None
    type: Optional[str] = None


class ParentLessonSummary(BaseModel):
    id: int
    tutor_student_id: int
    student_id: int
    star_rewards_enabled: bool = False
    student_name: str
    tutor_name: str
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    topic: Optional[str] = None
    meet_link: Optional[str] = None
    subject: Optional[str] = None
    class_info: Optional[str] = None
    materials: list[ParentLessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: list[ParentLessonAttachmentOut] = Field(default_factory=list)
    parent_message_files: list[ParentLessonAttachmentOut] = Field(default_factory=list)
    parent_comment: Optional[str] = None
    homework_deadline: Optional[dt.date] = None
    homework_deadline_missed: bool = False
    homework_status: str
    submission_file: Optional[ParentLessonAttachmentOut] = None
    submission_files: list[ParentLessonAttachmentOut] = Field(default_factory=list)
    checked_file: Optional[ParentLessonAttachmentOut] = None
    checked_files: list[ParentLessonAttachmentOut] = Field(default_factory=list)
    submission_comment: Optional[str] = None
    student_comment: Optional[str] = None
    submitted_at: Optional[dt.datetime] = None
    homework_grade: Optional[float] = None
    homework_stars: float = 0


class ParentLessonListOut(BaseModel):
    upcoming: list[ParentLessonSummary]
    past: list[ParentLessonSummary]


class ParentLessonDetail(ParentLessonSummary):
    pass
