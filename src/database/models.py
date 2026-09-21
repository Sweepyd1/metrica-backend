from datetime import date, time, datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    Date,
    Time,
    Text,
    ForeignKey,
    UniqueConstraint,
    TIMESTAMP,
    JSON,
    func,
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Enums ---
class UserRole(str, PyEnum):
    TUTOR = "tutor"
    STUDENT = "student"
    PARENT = "parent"


class LessonFileKind(str, PyEnum):
    MATERIAL = "material"
    HOMEWORK_TASK = "homework_task"
    SUBMISSION = "submission"
    PARENT_MESSAGE = "parent_message"


class SubmissionStatus(str, PyEnum):
    SUBMITTED = "submitted"
    CHECKED = "checked"


class AiReviewStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Tables ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
    )

    # Relationships (опционально, можно оставить)
    tutor_links: Mapped[List["TutorStudent"]] = relationship(
        foreign_keys="[TutorStudent.tutor_id]",
        back_populates="tutor",
        cascade="all, delete-orphan",
    )
    student_links: Mapped[List["TutorStudent"]] = relationship(
        foreign_keys="[TutorStudent.student_id]",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    parent_links: Mapped[List["ParentStudent"]] = relationship(
        foreign_keys="[ParentStudent.parent_id]",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    child_parent_links: Mapped[List["ParentStudent"]] = relationship(
        foreign_keys="[ParentStudent.student_id]",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    uploaded_files: Mapped[List["File"]] = relationship(back_populates="uploader")
    groups: Mapped[List["Group"]] = relationship(
        secondary="group_student", back_populates="students"
    )


class TutorStudent(Base):
    __tablename__ = "tutor_student"
    __table_args__ = (
        UniqueConstraint("tutor_id", "student_id", name="uq_tutor_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[Optional[str]] = mapped_column(String(30))
    student_inf: Mapped[Optional[str]] = mapped_column(Text)
    star_rewards_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    parent_contact_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    star_goal: Mapped[Optional[float]] = mapped_column(Float)
    star_reward_title: Mapped[Optional[str]] = mapped_column(String(100))

    tutor: Mapped["User"] = relationship(
        foreign_keys=[tutor_id], back_populates="tutor_links"
    )
    student: Mapped["User"] = relationship(
        foreign_keys=[student_id], back_populates="student_links"
    )
    lessons: Mapped[List["Lesson"]] = relationship(
        back_populates="tutor_student", cascade="all, delete-orphan"
    )
    bonus_tasks: Mapped[List["BonusTask"]] = relationship(
        back_populates="tutor_student", cascade="all, delete-orphan"
    )


class ParentStudent(Base):
    __tablename__ = "parent_student"
    __table_args__ = (
        UniqueConstraint("parent_id", "student_id", name="uq_parent_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    parent: Mapped["User"] = relationship(
        foreign_keys=[parent_id], back_populates="parent_links"
    )
    student: Mapped["User"] = relationship(
        foreign_keys=[student_id], back_populates="child_parent_links"
    )


class Lesson(Base):
    __tablename__ = "lesson"
    # Убрали CHECK-констрейнт

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tutor_student.id", ondelete="CASCADE"), nullable=False
    )
    l_date: Mapped[Optional[date]] = mapped_column(Date)
    l_time: Mapped[Optional[time]] = mapped_column(Time)
    subject: Mapped[Optional[str]] = mapped_column(String(30))
    topic: Mapped[Optional[str]] = mapped_column(String(100))
    meet_link: Mapped[Optional[str]] = mapped_column(String(1000))
    homework_done: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    homework_deadline: Mapped[Optional[date]] = mapped_column(Date)
    parent_comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    tutor_student: Mapped["TutorStudent"] = relationship(back_populates="lessons")
    lesson_files: Mapped[List["LessonFile"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )


class File(Base):
    __tablename__ = "file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[Optional[str]] = mapped_column(Text)
    filename: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    uploader: Mapped[Optional["User"]] = relationship(back_populates="uploaded_files")
    lesson_links: Mapped[List["LessonFile"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        foreign_keys="[LessonFile.file_id]",
    )


class LessonFile(Base):
    __tablename__ = "lesson_file"
    __table_args__ = (
        UniqueConstraint("lesson_id", "file_id", name="uq_lesson_file"),
        # Все CHECK-констрейнты удалены
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lesson.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("file.id", ondelete="CASCADE"), nullable=False
    )
    checked_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("file.id", ondelete="SET NULL")
    )
    kind: Mapped[LessonFileKind] = mapped_column(
        SAEnum(LessonFileKind, name="lesson_file_kind", create_constraint=True),
        nullable=False,
    )
    status: Mapped[Optional[SubmissionStatus]] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status", create_constraint=True)
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)
    student_comment: Mapped[Optional[str]] = mapped_column(Text)
    grade: Mapped[Optional[float]] = mapped_column(Float)
    stars_awarded: Mapped[float] = mapped_column(
        Float, server_default="0", default=0
    )
    deadline_missed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="lesson_files")
    file: Mapped["File"] = relationship(
        foreign_keys=[file_id], back_populates="lesson_links"
    )
    checked_file: Mapped[Optional["File"]] = relationship(
        foreign_keys=[checked_file_id]
    )


class AiHomeworkReview(Base):
    __tablename__ = "ai_homework_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lesson.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tutor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AiReviewStatus] = mapped_column(
        SAEnum(AiReviewStatus, name="ai_review_status", create_constraint=True),
        nullable=False,
        default=AiReviewStatus.PENDING,
    )
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="school")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    reserved_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    lesson: Mapped["Lesson"] = relationship()
    tasks: Mapped[List["AiHomeworkTask"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class AiHomeworkTask(Base):
    __tablename__ = "ai_homework_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_homework_review.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    task_label: Mapped[str] = mapped_column(Text, nullable=False)
    transcription: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    task_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    topic_groups: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    review: Mapped["AiHomeworkReview"] = relationship(back_populates="tasks")


class AiProgressReportCache(Base):
    __tablename__ = "ai_progress_report_cache"
    __table_args__ = (
        UniqueConstraint("student_id", "up_to_homework_count", name="uq_ai_progress_student_upto"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    up_to_homework_count: Mapped[int] = mapped_column(Integer, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )


class BonusTask(Base):
    __tablename__ = "bonus_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tutor_student.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    stars: Mapped[float] = mapped_column(Float, nullable=False)
    reward_title: Mapped[Optional[str]] = mapped_column(String(100))
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    tutor_student: Mapped["TutorStudent"] = relationship(back_populates="bonus_tasks")

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    tutor: Mapped["User"] = relationship(foreign_keys=[tutor_id])
    students: Mapped[List["User"]] = relationship(
        secondary="group_student", back_populates="groups"
    )


class GroupStudent(Base):
    __tablename__ = "group_student"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", name="uq_group_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    group: Mapped["Group"] = relationship()
    student: Mapped["User"] = relationship()
