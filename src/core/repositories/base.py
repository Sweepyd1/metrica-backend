from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Базовый репозиторий с общими методами CRUD"""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        """Создание записи с автоматическим commit"""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # отправляем в БД, но не коммитим
        await self.session.refresh(instance)  # обновляем объект (получаем id)
        await self.session.commit()
        return instance

    async def get(self, id: int) -> Optional[ModelType]:
        """Получение записи по ID"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Получение всех записей с пагинацией"""
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Обновление записи"""
        # Сначала получаем объект
        instance = await self.get(id)
        if not instance:
            return None

        # Обновляем поля
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """Удаление записи"""
        instance = await self.get(id)
        if not instance:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        await self.session.commit()
        return True
