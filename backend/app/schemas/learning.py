from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LearningStartRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)


class LearningTurnRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(..., min_length=1, max_length=4000)


class LearningSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_name: str
    status: str
    current_section: str | None = None
    total_sections: int = 0
    completed_sections: int = 0
    questions_answered: int = 0
    correct_answers: int = 0
    created_at: datetime | None = None


class LearningTurnResponse(BaseModel):
    session: LearningSessionOut
    reply: str
    weak_areas: list[str] = []
    suggested_next: str | None = None


class QuizRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    question_count: int = Field(default=5, ge=1, le=20)
    difficulty: str = "medium"
    question_type: str = "mcq"
    session_id: int | None = None


class QuizQuestion(BaseModel):
    id: int
    prompt: str
    question_type: str
    options: list[str] = []
    difficulty: str | None = None


class QuizOut(BaseModel):
    session_id: int | None = None
    topic: str
    questions: list[QuizQuestion]


class QuizSubmitRequest(BaseModel):
    topic: str
    answers: list[dict[str, Any]] = []


class QuizResultOut(BaseModel):
    score: int
    maximum_score: int
    percentage: int
    weak_topics: list[str] = []
    details: list[dict[str, Any]] = []
