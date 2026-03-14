from fastapi import HTTPException
from core.repositories.author import AuthorRepository
from core.services.file_service import FileService
from schemas.author import AuthorCreate, AuthorUpdate

class AuthorService:
    def __init__(self, repo: AuthorRepository, file_service: FileService):
        self.repo = repo
        self.file_service = file_service

    async def create_author(self, author_data: AuthorCreate, photo_file=None):
        photo_url = None
        if photo_file:
            photo_url = await self.file_service.save_cover(photo_file)  # используем как обложку
        
        return await self.repo.create(
            full_name=author_data.full_name,
            bio=author_data.bio,
            photo_url=photo_url
        )

    async def update_author(self, author_id: int, author_data: AuthorUpdate, photo_file=None):
        author = await self.repo.get(author_id)
        if not author:
            return None
        
        update_data = author_data.dict(exclude_unset=True)
        
        if photo_file:
            # Если было старое фото, удаляем (опционально)
            if author.photo_url:
                self.file_service.delete_file(author.photo_url)
            update_data['photo_url'] = await self.file_service.save_cover(photo_file)
        
        return await self.repo.update(author_id, **update_data)

    async def delete_author(self, author_id: int):
        author = await self.repo.get(author_id)
        if not author:
            return False
        
        # Удаляем фото автора
        if author.photo_url:
            self.file_service.delete_file(author.photo_url)
        
        # Также нужно решить, что делать с треками автора. По условию диплома, возможно, запретим удаление, если есть треки.
        # Для простоты пока разрешим, но треки останутся без автора? Лучше запретить.
        # Добавим проверку
        if author.tracks:
            raise HTTPException(status_code=400, detail="Нельзя удалить автора, у которого есть треки")
        
        return await self.repo.delete(author_id)