from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InterviewStartRequest(BaseModel):
    job_title: str = Field(..., min_length=2, max_length=200)
    industry: str | None = None
    experience_level: str | None = None
    interview_type: str = "mixed"
    topics: str | None = None


class InterviewQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    prompt: str
    question_type: str


class InterviewStartResponse(BaseModel):
    session_id: int
    job_title: str
    question: InterviewQuestionOut


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=6000)


class InterviewAnswerResponse(BaseModel):
    session_id: int
    feedback: dict[str, Any] = {}
    score: int | None = None
    next_question: InterviewQuestionOut | None = None
    done: bool = False
    summary: dict[str, Any] | None = None


class InterviewSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_title: str
    industry: str | None = None
    experience_level: str | None = None
    interview_type: str
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
