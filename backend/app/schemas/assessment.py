from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import CitationOut


class ExamGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    difficulty: str = "medium"
    question_count: int = Field(default=5, ge=1, le=30)
    question_type: str = "mcq"
    time_limit_minutes: int = Field(default=15, ge=1, le=240)


class ExamQuestionOut(BaseModel):
    id: int
    prompt: str
    question_type: str
    options: list[str] = []
    difficulty: str | None = None
    # The SOP excerpts this question was generated from.
    citations: list[CitationOut] = []


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_label: str | None = None
    difficulty: str
    question_count: int
    time_limit_minutes: int
    question_type: str
    created_at: datetime | None = None


class ExamStartResponse(BaseModel):
    attempt_id: int
    exam: ExamOut
    questions: list[ExamQuestionOut]
    expires_at: datetime | None = None


class ExamSubmitRequest(BaseModel):
    answers: list[dict[str, Any]] = []


class ExamResultOut(BaseModel):
    attempt_id: int
    score: int
    maximum_score: int
    percentage: int
    weak_topics: list[str] = []
    details: list[dict[str, Any]] = []


class ExamAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_session_id: int
    status: str
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    expires_at: datetime | None = None
    score: int = 0
    maximum_score: int = 0
    percentage: int | None = None
