import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProviderError
from app.ai.parsing import parse_json_array
from app.ai.router import get_ai_provider
from app.core.security import CurrentUser
from app.db.session import get_db
from app.models.interview import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
    InterviewStatus,
)
from app.rag.prompts import INTERVIEW_SYSTEM_PROMPT
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewQuestionOut,
    InterviewSessionOut,
    InterviewStartRequest,
    InterviewStartResponse,
)
from app.services.audit import log_ai_call

logger = logging.getLogger(__name__)
router = APIRouter()

_FALLBACK_QUESTIONS = [
    "Tell me about yourself and your background.",
    "Describe a challenging project you worked on and how you handled it.",
    "How do you prioritise when you have multiple competing deadlines?",
    "Tell me about a time you disagreed with a colleague. How did you resolve it?",
    "Where do you see yourself growing in this role over the next two years?",
]


def _generate_questions(provider, db, user, payload: InterviewStartRequest) -> list[dict]:
    prompt = (
        f"Create 5 realistic interview questions for a {payload.job_title} role.\n"
        f"Industry: {payload.industry or 'general'}\n"
        f"Experience level: {payload.experience_level or 'mid-level'}\n"
        f"Interview type: {payload.interview_type}\n"
        f"Focus topics: {payload.topics or 'general role fit'}\n"
        'Respond ONLY with a JSON array of objects with keys "prompt" and "question_type".'
    )
    try:
        with log_ai_call(db, provider.name, "interview_questions", mode="INTERVIEW_MODE", user_id=user.id):
            raw = provider.generate(prompt=prompt, system_prompt=INTERVIEW_SYSTEM_PROMPT)
        items = parse_json_array(raw)
        cleaned = [i for i in items if (i.get("prompt") or "").strip()]
        if cleaned:
            return cleaned[:5]
    except AIProviderError as exc:
        logger.warning("Interview question generation failed: %s", exc)
    return [{"prompt": q, "question_type": "behavioral"} for q in _FALLBACK_QUESTIONS]


@router.post("/start", response_model=InterviewStartResponse)
def start_interview(
    payload: InterviewStartRequest, current_user: CurrentUser, db: Session = Depends(get_db)
):
    provider = get_ai_provider()
    items = _generate_questions(provider, db, current_user, payload)

    session = InterviewSession(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        job_title=payload.job_title,
        industry=payload.industry,
        experience_level=payload.experience_level,
        interview_type=payload.interview_type,
        topics=payload.topics,
        status=InterviewStatus.ACTIVE,
    )
    db.add(session)
    db.flush()

    first: InterviewQuestion | None = None
    for index, item in enumerate(items):
        question = InterviewQuestion(
            session_id=session.id,
            order_index=index,
            prompt=(item.get("prompt") or "").strip(),
            question_type=item.get("question_type") or "behavioral",
        )
        db.add(question)
        db.flush()
        if first is None:
            first = question
    db.commit()
    db.refresh(session)
    db.refresh(first)

    return InterviewStartResponse(
        session_id=session.id,
        job_title=session.job_title,
        question=InterviewQuestionOut.model_validate(first),
    )


def _owned_session(db: Session, session_id: int, user) -> InterviewSession:
    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return session


@router.post("/{session_id}/answer", response_model=InterviewAnswerResponse)
def answer_question(
    session_id: int,
    payload: InterviewAnswerRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    session = _owned_session(db, session_id, current_user)
    question = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session.id)
        .order_by(InterviewQuestion.order_index)
        .all()
    )
    current = next((q for q in question if q.answer is None), None)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This interview is already complete."
        )

    provider = get_ai_provider()
    context = f"Role: {session.job_title}. Industry: {session.industry}. Level: {session.experience_level}."
    try:
        with log_ai_call(db, provider.name, "interview_evaluate", mode="INTERVIEW_MODE", user_id=current_user.id):
            feedback = provider.evaluate_answer(current.prompt, payload.answer, context=context)
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    score = feedback.get("score")
    if not isinstance(score, int):
        score = None

    db.add(
        InterviewAnswer(
            session_id=session.id,
            question_id=current.id,
            user_answer=payload.answer,
            feedback=json.dumps(feedback),
            score=score,
        )
    )
    db.commit()

    remaining = (
        db.query(InterviewQuestion)
        .filter(
            InterviewQuestion.session_id == session.id,
            InterviewQuestion.order_index > current.order_index,
        )
        .order_by(InterviewQuestion.order_index)
        .all()
    )
    next_question = next((q for q in remaining if q.answer is None), None)

    summary = None
    if next_question is None:
        session.status = InterviewStatus.COMPLETED
        summary = _summarise(session)
        session.summary = json.dumps(summary)
        db.commit()

    return InterviewAnswerResponse(
        session_id=session.id,
        feedback=feedback,
        score=score,
        next_question=InterviewQuestionOut.model_validate(next_question) if next_question else None,
        done=next_question is None,
        summary=summary,
    )


def _summarise(session: InterviewSession) -> dict:
    strengths: list[str] = []
    weaknesses: list[str] = []
    difficult: list[str] = []
    for question in session.questions:
        if question.answer is None:
            continue
        try:
            fb = json.loads(question.answer.feedback or "{}")
        except json.JSONDecodeError:
            fb = {}
        strengths.extend(fb.get("strengths", []) if isinstance(fb.get("strengths"), list) else [])
        weaknesses.extend(fb.get("weaknesses", []) if isinstance(fb.get("weaknesses"), list) else [])
        if not question.answer.score or question.answer.score < 3:
            difficult.append(question.prompt)
    return {
        "strengths": list(dict.fromkeys(strengths))[:6],
        "weak_areas": list(dict.fromkeys(weaknesses))[:6],
        "difficult_questions": difficult[:5],
        "recommended_topics": list(dict.fromkeys(weaknesses))[:5],
        "questions_answered": len([q for q in session.questions if q.answer is not None]),
    }


@router.post("/{session_id}/finish", response_model=InterviewSessionOut)
def finish_interview(session_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    session = _owned_session(db, session_id, current_user)
    summary = _summarise(session)
    session.summary = json.dumps(summary)
    session.status = InterviewStatus.COMPLETED
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}/summary")
def get_summary(session_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    session = _owned_session(db, session_id, current_user)
    if session.summary:
        try:
            return json.loads(session.summary)
        except json.JSONDecodeError:
            pass
    return _summarise(session)


@router.get("", response_model=list[InterviewSessionOut])
def list_interviews(current_user: CurrentUser, db: Session = Depends(get_db)):
    return (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
        .all()
    )


@router.get("/{session_id}", response_model=InterviewSessionOut)
def get_interview(session_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    return _owned_session(db, session_id, current_user)
