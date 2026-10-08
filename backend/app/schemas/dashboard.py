from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RecentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    detail: str | None = None
    at: datetime | None = None


class UserDashboardOut(BaseModel):
    stats: dict[str, Any] = {}
    weak_topics: list[str] = []
    recommended_topics: list[str] = []
    recent_conversations: list[RecentItem] = []
    recent_learning: list[RecentItem] = []
    exam_attempts: list[dict[str, Any]] = []
    interview_sessions: list[dict[str, Any]] = []


class AdminDashboardOut(BaseModel):
    totals: dict[str, Any] = {}
    documents: dict[str, Any] = {}
    engagement: dict[str, Any] = {}
    recent_documents: list[dict[str, Any]] = []
