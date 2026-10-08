from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: int | None = None
    document_version_id: int | None = None
    chunk_id: int | None = None
    document_title: str | None = None
    version: str | None = None
    section: str | None = None
    heading: str | None = None
    page: int | None = None
    relevance: float | None = None
    snippet: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    mode: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    citations: list[CitationOut] = []


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    mode: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = []


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    mode: str = "SOP_MODE"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    mode: str = "SOP_MODE"
    conversation_id: int | None = None
    document_ids: list[int] | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    user_message: MessageOut
    assistant_message: MessageOut
