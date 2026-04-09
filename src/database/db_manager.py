from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import cfg
from src.database.models import Base


class DatabaseManager:
    def __init__(self, database_url):
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=20,  # базовых соединений
            max_overflow=10,  # доп. при пике
            pool_pre_ping=True,
        )
        self.AsyncSession = sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=AsyncSession
        )

    @asynccontextmanager
    async def get_session(
        self, existing_session: AsyncSession = None
    ) -> AsyncIterator[AsyncSession]:
        """
        Provides an asynchronous context manager for managing SQLAlchemy sessions.

        This function allows you to either:
        - Create a new session and manage its lifecycle automatically.
        - Use an existing session without managing its lifecycle (useful for nested calls).

        Args:
            existing_session (Optional[AsyncSession]): An existing session to reuse.
                If provided, the function will yield this session without creating a new one
                or managing its lifecycle. If not provided, a new session will be created
                and managed automatically.

        Yields:
            AsyncIterator[AsyncSession]: An asynchronous session that can be used to execute queries.

        Example:
            # Using a new session (automatically managed)
            async with db_manager.get_session() as session:
                result = await session.execute(select(User).where(User.id == 1))
                user = result.scalars().first()
                print(user)

            # Using an existing session (lifecycle managed externally)
            async with db_manager.get_session() as outer_session:
                await some_function(outer_session)

            async def some_function(session: AsyncSession):
                async with db_manager.get_session(existing_session=session) as inner_session:
                    result = await inner_session.execute(select(User).where(User.id == 1))
                    user = result.scalars().first()
                    print(user)
        """
        if existing_session is None:
            async with self.AsyncSession() as session:
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()
        else:
            yield existing_session

db_manager = DatabaseManager(cfg.database.async_url)
