"""Chat orchestration: retrieval, prompting, generation and persistence."""

import logging
from collections.abc import Iterator
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProviderError
from app.ai.router import get_ai_provider
from app.models.chat import ChatMode, Conversation, Message, MessageRole
from app.models.user import User
from app.rag import citations as citation_utils
from app.rag.prompts import (
    SOP_NO_CONTEXT_ANSWER,
    build_user_prompt,
    get_system_prompt,
)
from app.rag.retrieval import RetrievedChunk, build_context, retrieve
from app.services.audit import log_ai_call

logger = logging.getLogger(__name__)


def ensure_conversation(
    db: Session,
    user: User,
    conversation_id: int | None,
    mode: str,
    title_hint: str,
) -> Conversation:
    if conversation_id is not None:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
            .first()
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        if conversation.mode != mode:
            conversation.mode = mode
            db.commit()
        return conversation

    title = (title_hint or "New conversation").strip()[:80] or "New conversation"
    conversation = Conversation(
        user_id=user.id, organization_id=user.organization_id, title=title, mode=mode
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _retrieve(
    db: Session,
    user: User | None,
    question: str,
    document_ids: list[int] | None,
    organization_id: int | None = None,
) -> list[RetrievedChunk]:
    return retrieve(
        question,
        db=db,
        user=user,
        document_ids=document_ids,
        organization_id=organization_id,
    )


def _messages_with_citations(db: Session, message: Message) -> Message:
    db.refresh(message)
    return message


def complete_chat(
    db: Session,
    user: User,
    conversation: Conversation,
    mode: str,
    question: str,
    document_ids: list[int] | None = None,
) -> tuple[Message, Message]:
    """Run a full (non-streaming) turn and persist both messages."""
    user_message = Message(
        conversation_id=conversation.id, role=MessageRole.USER, content=question, mode=mode
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    assistant_message = generate_assistant_message(
        db, user, conversation, mode, question, document_ids
    )
    return user_message, assistant_message


def generate_assistant_message(
    db: Session,
    user: User,
    conversation: Conversation,
    mode: str,
    question: str,
    document_ids: list[int] | None = None,
) -> Message:
    """Generate and persist only the assistant message for ``question``."""
    provider = get_ai_provider()
    results: list[RetrievedChunk] = []
    error: str | None = None

    if mode == ChatMode.SOP:
        results = _retrieve(db, user, question, document_ids)

    context = build_context(results) if mode == ChatMode.SOP else ""
    system_prompt = get_system_prompt(mode)
    user_prompt = build_user_prompt(question, context)

    if mode == ChatMode.SOP and not results:
        answer_text = SOP_NO_CONTEXT_ANSWER
    else:
        try:
            with log_ai_call(
                db,
                provider=provider.name,
                operation="generate",
                model=getattr(provider, "model", None),
                mode=mode,
                user_id=user.id,
            ):
                answer_text = provider.generate(
                    prompt=user_prompt, system_prompt=system_prompt
                )
        except AIProviderError as exc:
            logger.error("AI provider error: %s", exc)
            error = str(exc)
            answer_text = (
                "I'm sorry, the AI service is currently unavailable, so I can't produce an "
                "answer right now. Please try again shortly."
            )

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=answer_text,
        mode=mode,
        provider=provider.name,
        error=error,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    if mode == ChatMode.SOP and results and error is None:
        citation_utils.persist_citations(db, assistant_message.id, results)
        db.commit()
        db.refresh(assistant_message)

    conversation.updated_at = assistant_message.created_at
    db.commit()
    return assistant_message


def regenerate_last(
    db: Session,
    user: User,
    conversation: Conversation,
    message_id: int,
) -> Message:
    """Delete an assistant message and regenerate a fresh response for its question."""
    target = (
        db.query(Message)
        .filter(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.ASSISTANT,
        )
        .first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assistant message not found"
        )

    previous_user = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.USER,
            Message.id < target.id,
        )
        .order_by(Message.id.desc())
        .first()
    )
    if previous_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No user question to regenerate from"
        )

    question = previous_user.content
    mode = target.mode or conversation.mode
    db.delete(target)
    db.commit()
    return generate_assistant_message(db, user, conversation, mode, question)


def stream_chat(
    db: Session,
    conversation_id: int,
    organization_id: int | None,
    mode: str,
    question: str,
    document_ids: list[int] | None = None,
) -> Iterator[tuple[str, Any]]:
    """Yield ``(event, data)`` tuples for an SSE streamed turn.

    This runs against its own Session (opened by the caller) and only takes
    primitive identifiers, so the request-scoped ORM objects are never touched
    after the endpoint returns.

    Events: ``meta``, ``delta``, ``citations``, ``error``, ``done``.
    """
    user_message = Message(
        conversation_id=conversation_id, role=MessageRole.USER, content=question, mode=mode
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    provider = get_ai_provider()
    yield ("meta", {"conversation_id": conversation_id, "user_message_id": user_message.id})

    results: list[RetrievedChunk] = []
    if mode == ChatMode.SOP:
        results = _retrieve(db, None, question, document_ids, organization_id)

    context = build_context(results) if mode == ChatMode.SOP else ""
    system_prompt = get_system_prompt(mode)
    user_prompt = build_user_prompt(question, context)

    pieces: list[str] = []
    error: str | None = None

    try:
        if mode == ChatMode.SOP and not results:
            pieces.append(SOP_NO_CONTEXT_ANSWER)
            yield ("delta", SOP_NO_CONTEXT_ANSWER)
        else:
            for piece in provider.stream(prompt=user_prompt, system_prompt=system_prompt):
                pieces.append(piece)
                yield ("delta", piece)
    except AIProviderError as exc:
        logger.error("AI provider stream error: %s", exc)
        error = str(exc)
        fallback = (
            "I'm sorry, the AI service is currently unavailable, so I can't produce an "
            "answer right now. Please try again shortly."
        )
        pieces = [fallback]
        yield ("error", {"message": error})
        yield ("delta", fallback)
    except Exception as exc:  # noqa: BLE001 - never break the stream silently
        logger.exception("Unexpected streaming failure")
        error = str(exc)
        pieces = ["An unexpected error occurred while generating the response."]
        yield ("error", {"message": error})
        yield ("delta", pieces[0])

    answer_text = "".join(pieces)
    assistant_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=answer_text,
        mode=mode,
        provider=provider.name,
        error=error,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    citation_dicts: list[dict] = []
    if mode == ChatMode.SOP and results and error is None:
        citation_utils.persist_citations(db, assistant_message.id, results)
        db.commit()
        db.refresh(assistant_message)
        citation_dicts = citation_utils.citations_to_dicts(assistant_message.citations)

    db.query(Conversation).filter(Conversation.id == conversation_id).update(
        {"updated_at": assistant_message.created_at}
    )
    db.commit()

    if citation_dicts:
        yield ("citations", citation_dicts)
    yield (
        "done",
        {"assistant_message_id": assistant_message.id, "conversation_id": conversation_id},
    )
