from typing import Literal

from pydantic import BaseModel, Field


class MathError(BaseModel):
    location: str = Field(max_length=300)
    student_wrote: str = Field(max_length=500)
    correct: str = Field(max_length=500)
    explanation: str = Field(max_length=1000)
    topic: str = Field(max_length=200)
    severity: Literal["conceptual", "computational", "careless"]


class TaskReview(BaseModel):
    task_label: str = Field(max_length=200)
    transcription: str = Field(max_length=2500)
    is_correct: bool
    errors: list[MathError] = Field(default_factory=list, max_length=5)
    task_types: list[
        Literal[
            "word_problem",
            "equation",
            "inequality",
            "geometry",
            "function_graph",
            "expression",
            "other",
        ]
    ] = Field(default_factory=list)


class PracticeTask(BaseModel):
    topic: str = Field(max_length=200)
    question: str = Field(max_length=700)
    hint: str = Field(max_length=500)
    answer: str = Field(max_length=300)
    solution: str = Field(max_length=1000)


class AiHomeworkResult(BaseModel):
    readable: bool
    quality_note: str | None = Field(default=None, max_length=500)
    tasks: list[TaskReview] = Field(default_factory=list, max_length=3)
    summary: str = Field(default="", max_length=1500)
    error_topics: list[str] = Field(default_factory=list, max_length=5)
    practice: list[PracticeTask] = Field(default_factory=list, max_length=3)


class AiReviewStateOut(BaseModel):
    id: int | None = None
    lesson_id: int
    status: Literal["not_started", "pending", "running", "completed", "failed"]
    available: bool
    result: AiHomeworkResult | None = None
    error_message: str | None = None


class AiHomeworkHistoryItemOut(BaseModel):
    homework_number: int
    homework_label: str
    created_at: str


class AiErrorClusterOut(BaseModel):
    label: str = Field(max_length=200)
    description: str = Field(max_length=1000)
    homework_labels: list[str] = Field(default_factory=list)
    error_count: int


class AiProgressLlmOut(BaseModel):
    narrative: str = Field(max_length=2000)
    strengths: list[str] = Field(default_factory=list, max_length=5)
    focus_areas: list[str] = Field(default_factory=list, max_length=5)
    clusters: list[AiErrorClusterOut] = Field(default_factory=list)


class AiProgressReportOut(AiProgressLlmOut):
    homework_count: int
    threshold_reached: bool
