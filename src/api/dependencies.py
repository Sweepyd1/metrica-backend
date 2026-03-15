# src/api/dependencies.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.user import UserRepository
from core.service.auth import AuthService
from typing import AsyncIterator
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_manager import DatabaseManager
from core.service.auth import AuthService
from core.repositories.user import UserRepository
from core.repositories.tutor_student import TutorStudentRepository
from core.repositories.lesson import LessonRepository
from core.repositories.lesson_file import LessonFileRepository
from core.service.tutor import TutorService
from database.models import User, UserRole
from fastapi.security import OAuth2PasswordBearer


from database.db_manager import db_manager


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with db_manager.get_session() as session:
        yield session


async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
) -> AuthService:
    repo = UserRepository(db)
    return AuthService(repo)


async def get_current_user(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
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


async def get_tutor_service(db: AsyncSession = Depends(get_db_session)) -> TutorService:
    return TutorService(
        tutor_student_repo=TutorStudentRepository(db),
        lesson_repo=LessonRepository(db),
        lesson_file_repo=LessonFileRepository(db),
        user_repo=UserRepository(db),
    )
