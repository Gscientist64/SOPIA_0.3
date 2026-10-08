"""Convert ORM objects into API schemas where attribute names differ."""

from app.models.chat import Message
from app.rag.citations import citations_to_dicts
from app.schemas.chat import MessageOut


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        mode=message.mode,
        error=message.error,
        created_at=message.created_at,
        citations=citations_to_dicts(list(message.citations)),
    )
