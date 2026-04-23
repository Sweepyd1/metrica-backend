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
    PARENT = "parent"


class ParentAccessStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ParentChatSenderRole(str, PyEnum):
    PARENT = "parent"
    TUTOR = "tutor"


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


class AuthProvider(str, PyEnum):
    PASSWORD = "password"
    PHONE = "phone"
    VK = "vk"
    YANDEX = "yandex"
    TELEGRAM = "telegram"


# --- Tables ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), unique=True)
    password: Mapped[Optional[str]] = mapped_column(String(200))
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
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
    auth_identities: Mapped[List["AuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    parent_accesses: Mapped[List["ParentAccess"]] = relationship(
        foreign_keys="[ParentAccess.parent_id]",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    reviewed_parent_accesses: Mapped[List["ParentAccess"]] = relationship(
        foreign_keys="[ParentAccess.reviewed_by]",
        back_populates="reviewer",
    )


class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_auth_identity_provider_user_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[AuthProvider] = mapped_column(
        SAEnum(AuthProvider, name="auth_provider", create_constraint=True),
        nullable=False,
    )
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[Optional[str]] = mapped_column(String(200))
    provider_phone: Mapped[Optional[str]] = mapped_column(String(32))
    is_verified: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )
    last_login_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="auth_identities")


class PhoneAuthCode(Base):
    __tablename__ = "phone_auth_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    resend_available_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )


class TelegramAuthSession(Base):
    __tablename__ = "telegram_auth_sessions"
    __table_args__ = (
        UniqueConstraint(
            "session_token", name="uq_telegram_auth_sessions_session_token"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmation_code: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=False),
        nullable=False,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(64))
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64))
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_first_name: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_last_name: Mapped[Optional[str]] = mapped_column(String(255))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
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
    parent_accesses: Mapped[List["ParentAccess"]] = relationship(
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


class ParentAccess(Base):
    __tablename__ = "parent_access"
    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "tutor_student_id",
            name="uq_parent_access_parent_tutor_student",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tutor_student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tutor_student.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ParentAccessStatus] = mapped_column(
        SAEnum(
            ParentAccessStatus,
            name="parent_access_status",
            create_constraint=True,
        ),
        nullable=False,
        default=ParentAccessStatus.PENDING,
        server_default=ParentAccessStatus.PENDING.name,
    )
    request_message: Mapped[Optional[str]] = mapped_column(Text)
    review_comment: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    parent: Mapped["User"] = relationship(
        foreign_keys=[parent_id], back_populates="parent_accesses"
    )
    tutor_student: Mapped["TutorStudent"] = relationship(
        back_populates="parent_accesses"
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        foreign_keys=[reviewed_by], back_populates="reviewed_parent_accesses"
    )
    messages: Mapped[List["ParentChatMessage"]] = relationship(
        back_populates="parent_access",
        cascade="all, delete-orphan",
    )


class ParentChatMessage(Base):
    __tablename__ = "parent_chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_access_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parent_access.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_role: Mapped[ParentChatSenderRole] = mapped_column(
        SAEnum(
            ParentChatSenderRole,
            name="parent_chat_sender_role",
            create_constraint=True,
        ),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), default=datetime.now
    )

    parent_access: Mapped["ParentAccess"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])


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
