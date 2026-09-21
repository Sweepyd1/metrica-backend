from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from src.database.models import Group, GroupStudent, User


class GroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, tutor_id: int, name: str, description: Optional[str] = None) -> Group:
        group = Group(tutor_id=tutor_id, name=name, description=description)
        self.session.add(group)
        await self.session.flush()
        await self.session.commit()
        return group

    async def add_students(self, group_id: int, student_ids: List[int]) -> None:
        for student_id in student_ids:
            existing = await self.session.execute(
                select(GroupStudent).where(
                    GroupStudent.group_id == group_id,
                    GroupStudent.student_id == student_id
                )
            )
            if not existing.scalar_one_or_none():
                self.session.add(GroupStudent(group_id=group_id, student_id=student_id))
        await self.session.flush()
        await self.session.commit()

    async def remove_students(self, group_id: int, student_ids: List[int]) -> None:
        await self.session.execute(
            delete(GroupStudent).where(
                GroupStudent.group_id == group_id,
                GroupStudent.student_id.in_(student_ids)
            )
        )
        await self.session.flush()
        await self.session.commit()

    async def get_by_tutor(self, tutor_id: int) -> List[Group]:
        result = await self.session.execute(
            select(Group).where(Group.tutor_id == tutor_id).order_by(Group.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_id(self, group_id: int, tutor_id: int) -> Optional[Group]:
        result = await self.session.execute(
            select(Group)
            .where(Group.id == group_id, Group.tutor_id == tutor_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, group_id: int) -> None:
        await self.session.execute(
            delete(Group).where(Group.id == group_id)
        )
        await self.session.flush()
        await self.session.commit()

    async def count_students(self, group_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(GroupStudent).where(GroupStudent.group_id == group_id)
        )
        return result.scalar_one()

    async def get_students(self, group_id: int) -> List[User]:
        result = await self.session.execute(
            select(User)
            .join(GroupStudent, User.id == GroupStudent.student_id)
            .where(GroupStudent.group_id == group_id)
        )
        return result.scalars().all()
