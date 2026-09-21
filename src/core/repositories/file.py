from src.database.models import File
from src.core.repositories.base import BaseRepository


class FileRepository(BaseRepository[File]):
    def __init__(self, session):
        super().__init__(File, session)

    async def create(
        self, path: str, filename: str, type: str, uploaded_by: int
    ) -> File:
        file = File(path=path, filename=filename, type=type, uploaded_by=uploaded_by)
        self.session.add(file)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(file)
        return file

    async def get_by_id(self, file_id: int) -> File | None:
        return await self.session.get(File, file_id)
