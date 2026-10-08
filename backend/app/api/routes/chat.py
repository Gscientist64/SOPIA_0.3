import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.serializers import message_out
from app.core.security import CurrentUser
from app.db.session import SessionLocal, get_db
from app.models.chat import ChatMode
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_mode(mode: str) -> str:
    if mode not in ChatMode.ALL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mode '{mode}'. Valid modes: {', '.join(ChatMode.ALL)}",
        )
    if mode not in ChatMode.IMPLEMENTED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Mode '{mode}' is not available yet.",
        )
    return mode


@router.get("/modes")
def list_modes():
    """Report which interaction modes are usable, so the UI never advertises 400s."""
    labels = {
        ChatMode.SOP: "SOP Assistant",
        ChatMode.LEARNING: "Learning",
        ChatMode.EXAM: "Exam",
        ChatMode.INTERVIEW: "Interview",
        ChatMode.RESEARCH: "Research",
        ChatMode.COMPARE: "Compare",
    }
    return {
        "modes": [
            {"value": m, "label": labels[m], "available": m in ChatMode.IMPLEMENTED}
            for m in ChatMode.ALL
        ]
    }


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    mode = _validate_mode(request.mode)
    conversation = chat_service.ensure_conversation(
        db, current_user, request.conversation_id, mode, request.message
    )
    user_message, assistant_message = chat_service.complete_chat(
        db, current_user, conversation, mode, request.message, request.document_ids
    )
    return ChatResponse(
        conversation_id=conversation.id,
        user_message=message_out(user_message),
        assistant_message=message_out(assistant_message),
    )


@router.post("/stream")
def chat_stream(request: ChatRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    mode = _validate_mode(request.mode)
    conversation = chat_service.ensure_conversation(
        db, current_user, request.conversation_id, mode, request.message
    )
    conversation_id = conversation.id
    organization_id = current_user.organization_id

    def event_source():
        # A dedicated session is used because the request-scoped session is torn
        # down as soon as this endpoint returns, before the body is consumed.
        stream_db = SessionLocal()
        try:
            for event, data in chat_service.stream_chat(
                stream_db,
                conversation_id,
                organization_id,
                mode,
                request.message,
                request.document_ids,
            ):
                # Deltas are JSON-encoded: a raw newline inside a delta would
                # otherwise corrupt the SSE frame (data lines cannot span lines).
                if event == "delta":
                    payload = json.dumps({"text": data})
                else:
                    payload = data if isinstance(data, str) else json.dumps(data)
                yield f"event: {event}\ndata: {payload}\n\n"
            yield "event: end\ndata: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001 - report errors inside the stream
            logger.exception("Streaming chat failed")
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


