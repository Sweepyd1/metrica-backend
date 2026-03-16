from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from src.database.models import TutorStudent
from src.core.repositories.base import BaseRepository


class TutorStudentRepository(BaseRepository[TutorStudent]):
    def __init__(self, session):
        super().__init__(TutorStudent, session)

    async def get_by_tutor(self, tutor_id: int):
        query = (
            select(TutorStudent)
            .where(TutorStudent.tutor_id == tutor_id)
            .options(selectinload(TutorStudent.student))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_tutor_and_student(self, tutor_id: int, student_id: int):
        query = select(TutorStudent).where(
            and_(
                TutorStudent.tutor_id == tutor_id, TutorStudent.student_id == student_id
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        tutor_id: int,
        student_id: int,
        subject: str = None,
        student_inf: str = None,
    ):
        link = TutorStudent(
            tutor_id=tutor_id,
            student_id=student_id,
            subject=subject,
            student_inf=student_inf,
        )
        self.session.add(link)
        await self.session.flush()
        await self.session.commit()  # фиксируем транзакцию

        # После коммита загружаем связь с уже подгруженным студентом
        result = await self.session.execute(
            select(TutorStudent)
            .where(TutorStudent.id == link.id)
            .options(selectinload(TutorStudent.student))
        )
        return result.scalar_one()
