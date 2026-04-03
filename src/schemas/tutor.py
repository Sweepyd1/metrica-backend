import datetime as dt
from typing import Optional, List

from pydantic import BaseModel, Field


class StudentAdd(BaseModel):
    email: str


class StudentOut(BaseModel):
    id: int  # ID связи tutor_student
    student_id: int
    full_name: str
    subject: Optional[str] = None
    class_info: Optional[str] = None  # student_inf из модели
    star_balance: int = 0
    last_submission_id: Optional[int] = None
    last_submission_status: Optional[str] = None  # "pending", "checked", "none"


class StarTransactionCreate(BaseModel):
    amount: int = Field(gt=0)
    reason: Optional[str] = None
    lesson_id: Optional[int] = None


class StarTransactionOut(BaseModel):
    id: int
    tutor_student_id: int
    student_id: int
    student_name: str
    lesson_id: Optional[int] = None
    lesson_topic: Optional[str] = None
    lesson_date: Optional[dt.date] = None
    delta: int
    balance_after: int
    transaction_type: str
    reason: Optional[str] = None
    created_at: dt.datetime


class TutorStudentStarsOut(BaseModel):
    tutor_student_id: int
    student_id: int
    student_name: str
    subject: Optional[str] = None
    class_info: Optional[str] = None
    star_balance: int
    transactions: List[StarTransactionOut] = Field(default_factory=list)


class LessonCreate(BaseModel):
    tutor_student_id: int
    date: dt.date
    time: dt.time
    topic: str
    meet_link: Optional[str] = None
    homework_deadline: Optional[dt.date] = None
    material_file_ids: List[int] = Field(default_factory=list)
    homework_task_file_ids: List[int] = Field(default_factory=list)


class LessonUpdate(LessonCreate):
    pass


class LessonOut(BaseModel):
    id: int
    tutor_student_id: int
    date: Optional[dt.date]
    time: Optional[dt.time]
    topic: Optional[str]
    meet_link: Optional[str]
    homework_done: bool
    homework_deadline: Optional[dt.date]


class TutorLessonAttachmentOut(BaseModel):
    id: int
    filename: Optional[str] = None
    file_url: Optional[str] = None
    type: Optional[str] = None


class TutorLessonSummary(BaseModel):
    id: int
    tutor_student_id: int
    student_id: int
    student_name: str
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    topic: Optional[str] = None
    meet_link: Optional[str] = None
    materials: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    homework_deadline: Optional[dt.date] = None
    homework_done: bool
    homework_status: str


class TutorLessonListOut(BaseModel):
    upcoming: List[TutorLessonSummary]
    past: List[TutorLessonSummary]


class TutorLessonDetail(TutorLessonSummary):
    submission_file: Optional[TutorLessonAttachmentOut] = None
    submission_comment: Optional[str] = None


class TutorLessonProgressItem(BaseModel):
    id: int
    sequence_number: int
    progress_status: str
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    topic: Optional[str] = None
    meet_link: Optional[str] = None
    materials: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    homework_deadline: Optional[dt.date] = None
    homework_done: bool
    homework_status: str
    submission_file: Optional[TutorLessonAttachmentOut] = None
    submission_comment: Optional[str] = None


class TutorLessonProgressTreeOut(BaseModel):
    tutor_student_id: int
    student_id: int
    student_name: str
    subject: Optional[str] = None
    class_info: Optional[str] = None
    total_lessons: int
    completed_lessons: int
    upcoming_lessons: int
    unscheduled_lessons: int
    items: List[TutorLessonProgressItem] = Field(default_factory=list)


class SubmissionOut(BaseModel):
    id: int
    student: str
    lesson_date: Optional[dt.date]
    lesson_topic: Optional[str]
    file_url: Optional[str]  # путь к файлу
    status: str  # "submitted" / "checked"
    comment: Optional[str] = None


class SubmissionCheck(BaseModel):
    comment: Optional[str] = None
