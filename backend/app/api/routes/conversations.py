from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.serializers import message_out
from app.core.security import CurrentUser
from app.db.session import get_db
from app.models.chat import ChatMode, Conversation, Message, MessageRole
from app.schemas.chat import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
)
from app.services import chat_service

router = APIRouter()


def _owned_conversation(db: Session, conversation_id: int, user) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    conversation = Conversation(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        title=payload.title or "New conversation",
        mode=payload.mode if payload.mode in ChatMode.ALL else ChatMode.SOP,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    current_user: CurrentUser, db: Session = Depends(get_db), q: str | None = None
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Conversation.title.ilike(like))
    return query.order_by(Conversation.updated_at.desc()).all()


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(conversation_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    conversation = _owned_conversation(db, conversation_id, current_user)
    return ConversationDetailOut(
        id=conversation.id,
        title=conversation.title,
        mode=conversation.mode,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[message_out(m) for m in conversation.messages],
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, conversation_id, current_user)
    conversation.title = payload.title
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    conversation = _owned_conversation(db, conversation_id, current_user)
    db.delete(conversation)
    db.commit()
    return None


@router.post("/{conversation_id}/clear", response_model=ConversationOut)
def clear_conversation(conversation_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    conversation = _owned_conversation(db, conversation_id, current_user)
    db.query(Message).filter(Message.conversation_id == conversation.id).delete(
        synchronize_session=False
    )
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post(
    "/{conversation_id}/messages/{message_id}/retry", response_model=MessageOut
)
def retry_message(
    conversation_id: int,
    message_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, conversation_id, current_user)
    message = chat_service.regenerate_last(db, current_user, conversation, message_id)
    return message_out(message)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    conversation = _owned_conversation(db, conversation_id, current_user)
    return [message_out(m) for m in conversation.messages if m.role != MessageRole.SYSTEM]
