import datetime as dt
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, field_validator

from schemas.gamification import validate_half_star


class StudentAdd(BaseModel):
    email: str


class StudentOut(BaseModel):
    id: int  # ID связи tutor_student
    student_id: int
    email: EmailStr
    first_name: str
    last_name: Optional[str] = None
    full_name: str
    subject: Optional[str] = None
    class_info: Optional[str] = None  # student_inf из модели
    last_submission_id: Optional[int] = None
    last_submission_status: Optional[str] = None  # "pending", "checked", "none"
    star_rewards_enabled: bool = False
    parent_contact_enabled: bool = False
    star_goal: Optional[float] = None
    star_reward_title: Optional[str] = None
    earned_stars: float = 0


class TutorStudentUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)
    subject: Optional[str] = Field(default=None, max_length=30)
    class_info: Optional[str] = Field(default=None, max_length=500)
    parent_contact_enabled: Optional[bool] = None


class LessonCreate(BaseModel):
    tutor_student_id: int
    date: dt.date
    time: dt.time
    subject: Optional[str] = Field(default=None, max_length=30)
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
    subject: Optional[str] = None
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
    star_rewards_enabled: bool = False
    student_name: str
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    meet_link: Optional[str] = None
    materials: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    parent_message_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    parent_comment: Optional[str] = None
    homework_deadline: Optional[dt.date] = None
    homework_deadline_missed: bool = False
    homework_done: bool
    homework_status: str
    submission_file: Optional[TutorLessonAttachmentOut] = None
    submission_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    checked_file: Optional[TutorLessonAttachmentOut] = None
    checked_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    submission_comment: Optional[str] = None
    student_comment: Optional[str] = None
    submitted_at: Optional[dt.datetime] = None
    homework_grade: Optional[float] = None
    homework_stars: float = 0


class TutorLessonListOut(BaseModel):
    upcoming: List[TutorLessonSummary]
    past: List[TutorLessonSummary]


class TutorLessonDetail(TutorLessonSummary):
    pass


class ParentLessonMessageUpdate(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=2000)
    file_ids: List[int] = Field(default_factory=list)


class SubmissionOut(BaseModel):
    id: int
    student: str
    star_rewards_enabled: bool = False
    lesson_date: Optional[dt.date]
    lesson_topic: Optional[str]
    file_url: Optional[str]  # путь к файлу
    file_name: Optional[str] = None
    submission_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    checked_file_url: Optional[str] = None
    checked_file_name: Optional[str] = None
    checked_files: List[TutorLessonAttachmentOut] = Field(default_factory=list)
    status: str  # "submitted" / "checked"
    comment: Optional[str] = None
    student_comment: Optional[str] = None
    submitted_at: Optional[dt.datetime] = None
    homework_deadline: Optional[dt.date] = None
    homework_deadline_missed: bool = False
    grade: Optional[float] = None
    stars_awarded: float = 0


class SubmissionCheck(BaseModel):
    comment: Optional[str] = None
    grade: Optional[float] = None
    checked_file_id: Optional[int] = None
    checked_file_ids: List[int] = Field(default_factory=list)

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, value: float | None) -> float | None:
        value = validate_half_star(value)
        if value is not None and (value < 0.5 or value > 5):
            raise ValueError("Grade must be between 0.5 and 5")
        return value
