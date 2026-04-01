from datetime import date, time, datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Date,
    Time,
    Text,
    ForeignKey,
    UniqueConstraint,
    TIMESTAMP,
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


class LessonFileKind(str, PyEnum):
    MATERIAL = "material"
    HOMEWORK_TASK = "homework_task"
    SUBMISSION = "submission"


class SubmissionStatus(str, PyEnum):
    SUBMITTED = "submitted"
    CHECKED = "checked"


class StarTransactionType(str, PyEnum):
    ACCRUAL = "accrual"
    WRITE_OFF = "write_off"


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
    star_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )

    tutor: Mapped["User"] = relationship(
        foreign_keys=[tutor_id], back_populates="tutor_links"
    )
    student: Mapped["User"] = relationship(
        foreign_keys=[student_id], back_populates="student_links"
    )
    lessons: Mapped[List["Lesson"]] = relationship(
        back_populates="tutor_student", cascade="all, delete-orphan"
    )
    star_transactions: Mapped[List["StarTransaction"]] = relationship(
        back_populates="tutor_student", cascade="all, delete-orphan"
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
    topic: Mapped[Optional[str]] = mapped_column(String(100))
    meet_link: Mapped[Optional[str]] = mapped_column(String(1000))
    homework_done: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    homework_deadline: Mapped[Optional[date]] = mapped_column(Date)

    tutor_student: Mapped["TutorStudent"] = relationship(back_populates="lessons")
    lesson_files: Mapped[List["LessonFile"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )
    star_transactions: Mapped[List["StarTransaction"]] = relationship(
        back_populates="lesson"
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
        back_populates="file", cascade="all, delete-orphan"
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
    kind: Mapped[LessonFileKind] = mapped_column(
        SAEnum(LessonFileKind, name="lesson_file_kind", create_constraint=True),
        nullable=False,
    )
    status: Mapped[Optional[SubmissionStatus]] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status", create_constraint=True)
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)

    lesson: Mapped["Lesson"] = relationship(back_populates="lesson_files")
    file: Mapped["File"] = relationship(back_populates="lesson_links")


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


class StarTransaction(Base):
    __tablename__ = "star_transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tutor_student.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("lesson.id", ondelete="SET NULL")
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[StarTransactionType] = mapped_column(
        SAEnum(
            StarTransactionType,
            name="star_transaction_type",
            create_constraint=True,
        ),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    tutor_student: Mapped["TutorStudent"] = relationship(
        back_populates="star_transactions"
    )
    lesson: Mapped[Optional["Lesson"]] = relationship(back_populates="star_transactions")
