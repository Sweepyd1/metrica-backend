from sqlalchemy import and_, desc, select
from sqlalchemy.orm import selectinload

from src.core.repositories.base import BaseRepository
from src.database.models import StarTransaction, TutorStudent


class StarTransactionRepository(BaseRepository[StarTransaction]):
    def __init__(self, session):
        super().__init__(StarTransaction, session)

    async def create_pending(self, **kwargs) -> StarTransaction:
        transaction = StarTransaction(**kwargs)
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def get_by_tutor_student(
        self,
        tutor_id: int,
        tutor_student_id: int,
        *,
        limit: int | None = None,
    ):
        query = (
            select(StarTransaction)
            .join(TutorStudent, StarTransaction.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    TutorStudent.tutor_id == tutor_id,
                    TutorStudent.id == tutor_student_id,
                )
            )
            .options(selectinload(StarTransaction.lesson))
            .order_by(desc(StarTransaction.created_at), desc(StarTransaction.id))
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_for_tutor(self, tutor_id: int, transaction_id: int):
        query = (
            select(StarTransaction)
            .join(TutorStudent, StarTransaction.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    TutorStudent.tutor_id == tutor_id,
                    StarTransaction.id == transaction_id,
                )
            )
            .options(
                selectinload(StarTransaction.lesson),
                selectinload(StarTransaction.tutor_student).selectinload(
                    TutorStudent.student
                ),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
