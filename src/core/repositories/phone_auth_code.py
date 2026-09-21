from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.base import BaseRepository
from src.database.models import PhoneAuthCode


class PhoneAuthCodeRepository(BaseRepository[PhoneAuthCode]):
    def __init__(self, session: AsyncSession):
        super().__init__(PhoneAuthCode, session)

    async def get_latest_by_phone(self, phone: str) -> PhoneAuthCode | None:
        result = await self.session.execute(
            select(PhoneAuthCode)
            .where(PhoneAuthCode.phone == phone)
            .order_by(PhoneAuthCode.created_at.desc(), PhoneAuthCode.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_active_by_phone(self, phone: str) -> PhoneAuthCode | None:
        result = await self.session.execute(
            select(PhoneAuthCode)
            .where(
                PhoneAuthCode.phone == phone,
                PhoneAuthCode.used_at.is_(None),
            )
            .order_by(PhoneAuthCode.created_at.desc(), PhoneAuthCode.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
