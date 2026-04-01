# schemas/group.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class StudentBasicOut(BaseModel):
    id: int
    full_name: str  # first_name + last_name

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    student_ids: List[int] = []  # ученики, которые будут добавлены при создании


class GroupOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    student_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class GroupDetailOut(GroupOut):
    students: List[StudentBasicOut]

    class Config:
        from_attributes = True


class GroupStudentsUpdate(BaseModel):
    student_ids: List[int]