from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.auth_identity import AuthIdentityRepository
from src.core.repositories.file import FileRepository
from src.core.repositories.group import GroupRepository
from src.core.repositories.lesson import LessonRepository
from src.core.repositories.lesson_file import LessonFileRepository
from src.core.repositories.parent_access import ParentAccessRepository
from src.core.repositories.parent_chat_message import ParentChatMessageRepository
from src.core.repositories.phone_auth_code import PhoneAuthCodeRepository
from src.core.repositories.star_transaction import StarTransactionRepository
from src.core.repositories.telegram_auth_session import TelegramAuthSessionRepository
from src.core.repositories.tutor_student import TutorStudentRepository
from src.core.repositories.user import UserRepository
from src.core.service.auth import AuthService
from src.core.service.parent import ParentService
from src.core.service.student import StudentService
from src.core.service.tutor import TutorService
from src.config import cfg
from src.database.db_manager import db_manager
from src.database.models import User, UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with db_manager.get_session() as session:
        yield session


async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
) -> AuthService:
    return AuthService(
        session=db,
        user_repo=UserRepository(db),
        identity_repo=AuthIdentityRepository(db),
        phone_code_repo=PhoneAuthCodeRepository(db),
        telegram_auth_session_repo=TelegramAuthSessionRepository(db),
    )


async def get_current_user(
    request: Request,
    token_from_bearer: str | None = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    token = request.cookies.get(cfg.auth.access_cookie_name)
    if not token:
        token = token_from_bearer
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user = await auth_service.get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    return user


async def get_current_tutor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.TUTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a tutor")
    return current_user


async def get_current_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a student"
        )
    return current_user


async def get_current_parent(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a parent"
        )
    return current_user


async def get_tutor_service(db: AsyncSession = Depends(get_db_session)) -> TutorService:
    return TutorService(
        tutor_student_repo=TutorStudentRepository(db),
        lesson_repo=LessonRepository(db),
        lesson_file_repo=LessonFileRepository(db),
        parent_access_repo=ParentAccessRepository(db),
        parent_chat_message_repo=ParentChatMessageRepository(db),
        star_transaction_repo=StarTransactionRepository(db),
        user_repo=UserRepository(db),
        session=db,
        group_repo=GroupRepository(db),
    )


async def get_student_service(
    db: AsyncSession = Depends(get_db_session),
) -> StudentService:
    return StudentService(
        lesson_repo=LessonRepository(db),
        lesson_file_repo=LessonFileRepository(db),
        file_repo=FileRepository(db),
    )


async def get_parent_service(
    db: AsyncSession = Depends(get_db_session),
) -> ParentService:
    return ParentService(
        parent_access_repo=ParentAccessRepository(db),
        parent_chat_message_repo=ParentChatMessageRepository(db),
        tutor_student_repo=TutorStudentRepository(db),
        lesson_repo=LessonRepository(db),
        user_repo=UserRepository(db),
    )
