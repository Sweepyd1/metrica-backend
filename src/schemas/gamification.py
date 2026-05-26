import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def validate_half_star(
    value: float | None,
    *,
    max_value: float = 100,
) -> float | None:
    if value is None:
        return value

    normalized = round(value * 2) / 2

    if normalized < 0 or normalized > max_value:
        raise ValueError(f"Stars value must be between 0 and {max_value:g}")

    return normalized


class BonusTaskOut(BaseModel):
    id: int
    tutor_student_id: int
    title: str
    description: Optional[str] = None
    stars: float
    reward_title: Optional[str] = None
    due_date: Optional[dt.date] = None
    is_completed: bool
    created_at: dt.datetime
    completed_at: Optional[dt.datetime] = None


class BonusTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    stars: Optional[float] = Field(default=None, ge=0, le=100)
    reward_title: Optional[str] = Field(default=None, max_length=100)
    due_date: Optional[dt.date] = None

    @field_validator("stars")
    @classmethod
    def validate_stars(cls, value: float | None) -> float | None:
        return validate_half_star(value)


class BonusTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    stars: Optional[float] = Field(default=None, ge=0, le=100)
    reward_title: Optional[str] = Field(default=None, max_length=100)
    due_date: Optional[dt.date] = None
    is_completed: Optional[bool] = None

    @field_validator("stars")
    @classmethod
    def validate_stars(cls, value: float | None) -> float | None:
        return validate_half_star(value)


class GamificationSettingsUpdate(BaseModel):
    star_rewards_enabled: bool
    star_goal: Optional[float] = Field(default=None, gt=0, le=1000)
    star_reward_title: Optional[str] = Field(default=None, max_length=100)

    @field_validator("star_goal")
    @classmethod
    def validate_goal(cls, value: float | None) -> float | None:
        return validate_half_star(value, max_value=1000)


class GamificationOut(BaseModel):
    tutor_student_id: int
    student_id: int
    student_name: str
    tutor_name: Optional[str] = None
    star_rewards_enabled: bool
    star_goal: Optional[float] = None
    star_reward_title: Optional[str] = None
    homework_stars: float
    bonus_stars: float
    earned_stars: float
    bonus_tasks: list[BonusTaskOut]
