from pydantic import BaseModel
from datetime import date, time
from typing import Optional, List


class StudentAdd(BaseModel):
    email: str


class StudentOut(BaseModel):
    id: int  # ID связи tutor_student
    student_id: int
    full_name: str
    subject: Optional[str] = None
    class_info: Optional[str] = None  # student_inf из модели
    last_submission_id: Optional[int] = None
    last_submission_status: Optional[str] = None  # "pending", "checked", "none"


class LessonCreate(BaseModel):
    tutor_student_id: int
    date: date
    time: time
    topic: str
    meet_link: Optional[str] = None
    homework_deadline: Optional[date] = None
    material_file_ids: List[int] = []  # ID загруженных файлов-материалов
    homework_task_file_ids: List[int] = []  # ID файлов с заданием


class LessonOut(BaseModel):
    id: int
    tutor_student_id: int
    date: Optional[date]
    time: Optional[time]
    topic: Optional[str]
    meet_link: Optional[str]
    homework_done: bool
    homework_deadline: Optional[date]


class SubmissionOut(BaseModel):
    id: int
    student: str
    lesson_date: Optional[date]
    lesson_topic: Optional[str]
    file_url: Optional[str]  # путь к файлу
    status: str  # "submitted" / "checked"
    comment: Optional[str] = None


class SubmissionCheck(BaseModel):
    comment: Optional[str] = None
