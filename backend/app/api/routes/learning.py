import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProviderError
from app.ai.parsing import parse_json_array, parse_json_object
from app.ai.router import get_ai_provider
from app.core.security import CurrentUser
from app.db.session import get_db
from app.models.assessment import Question, QuestionOption
from app.models.learning import LearningProgress, LearningSession, LearningStatus
from app.rag.prompts import LEARNING_SYSTEM_PROMPT
from app.schemas.learning import (
    LearningSessionOut,
    LearningStartRequest,
    LearningTurnRequest,
    LearningTurnResponse,
    QuizOut,
    QuizQuestion,
    QuizRequest,
    QuizResultOut,
    QuizSubmitRequest,
)
from app.services.audit import log_ai_call

logger = logging.getLogger(__name__)
router = APIRouter()


def _outline(db, provider, topic: str) -> dict:
    prompt = (
        f"Create a short learning outline for the topic: {topic}.\n"
        'Respond ONLY as JSON: {"intro": "2-3 sentence friendly introduction", '
        '"sections": ["section 1 title", "section 2 title", ...], '
        '"first_question": "one short comprehension question"}.\n'
        "Use 4 to 6 sections."
    )
    try:
        with log_ai_call(db, provider.name, "outline", mode="LEARNING_MODE"):
            raw = provider.generate(prompt=prompt, system_prompt=LEARNING_SYSTEM_PROMPT)
        data = parse_json_object(raw)
        if not data.get("sections"):
            raise ValueError
        return data
    except (AIProviderError, ValueError):
        return {
            "intro": f"Let's learn about {topic}. We'll go step by step.",
            "sections": [
                "Introduction",
                "Key concepts",
                "Practical examples",
                "Common mistakes",
                "Summary",
            ],
            "first_question": f"What do you already know about {topic}?",
        }


def _session_out(session: LearningSession) -> LearningSessionOut:
    return LearningSessionOut.model_validate(session)


@router.post("/sessions/start", response_model=LearningTurnResponse)
def start_session(payload: LearningStartRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    provider = get_ai_provider()
    outline = _outline(db, provider, payload.topic)
    sections = outline.get("sections") or []

    session = LearningSession(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        topic_name=payload.topic,
        status=LearningStatus.ACTIVE,
        current_section=sections[0] if sections else None,
        total_sections=len(sections),
        completed_sections=0,
        weak_areas=json.dumps([]),
    )
    db.add(session)
    db.flush()
    for index, title in enumerate(sections):
        db.add(
            LearningProgress(
                session_id=session.id,
                section_index=index,
                section_title=title,
                status="in_progress" if index == 0 else "pending",
            )
        )
    db.commit()
    db.refresh(session)

    reply = (
        f"{outline.get('intro', '')}\n\n"
        + "Here is how we'll cover **"
        + payload.topic
        + "**:\n"
        + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sections))
        + f"\n\nLet's begin with **{sections[0] if sections else payload.topic}**.\n\n"
        + (outline.get("first_question") or "Does that sound good to you?")
    )
    return LearningTurnResponse(session=_session_out(session), reply=reply)


@router.post("/sessions/turn", response_model=LearningTurnResponse)
def learning_turn(payload: LearningTurnRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    if payload.session_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == payload.session_id, LearningSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found")

    provider = get_ai_provider()
    prompt = (
        f"Topic: {session.topic_name}\n"
        f"Current section: {session.current_section or 'Introduction'}\n"
        f"Learner says: {payload.message}\n\n"
        "Continue tutoring. Respond ONLY as JSON: "
        '{"reply": "your tutor response", "weak_areas": ["..."], '
        '"suggested_next": "next thing to study"}'
    )
    try:
        with log_ai_call(db, provider.name, "learning_turn", mode="LEARNING_MODE", user_id=current_user.id):
            raw = provider.generate(prompt=prompt, system_prompt=LEARNING_SYSTEM_PROMPT)
        data = parse_json_object(raw)
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    reply = data.get("reply") or raw
    weak = data.get("weak_areas") or []
    session.questions_answered = (session.questions_answered or 0) + 1
    session.weak_areas = json.dumps(weak)
    db.commit()
    db.refresh(session)

    return LearningTurnResponse(
        session=_session_out(session),
        reply=reply,
        weak_areas=weak if isinstance(weak, list) else [],
        suggested_next=data.get("suggested_next"),
    )


@router.get("/sessions", response_model=list[LearningSessionOut])
def list_sessions(current_user: CurrentUser, db: Session = Depends(get_db)):
    return (
        db.query(LearningSession)
        .filter(LearningSession.user_id == current_user.id)
        .order_by(LearningSession.created_at.desc())
        .all()
    )


@router.get("/sessions/{session_id}", response_model=LearningSessionOut)
def get_session(session_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == session_id, LearningSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found")
    return session


@router.post("/sessions/{session_id}/complete", response_model=LearningSessionOut)
def complete_session(session_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == session_id, LearningSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found")
    session.status = LearningStatus.COMPLETED
    session.completed_sections = session.total_sections
    db.query(LearningProgress).filter(LearningProgress.session_id == session.id).update(
        {LearningProgress.status: "completed"}, synchronize_session=False
    )
    db.commit()
    db.refresh(session)
    return session


@router.post("/quiz", response_model=QuizOut)
def generate_quiz(payload: QuizRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    provider = get_ai_provider()
    try:
        with log_ai_call(db, provider.name, "quiz_generate", mode="LEARNING_MODE", user_id=current_user.id):
            items = provider.generate_questions(
                payload.topic, payload.question_count, payload.difficulty, payload.question_type
            )
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not items:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI could not generate quiz questions. Please try again.",
        )

    questions_out: list[QuizQuestion] = []
    for item in items[: payload.question_count]:
        prompt_text = (item.get("prompt") or "").strip()
        if not prompt_text:
            continue
        question = Question(
            organization_id=current_user.organization_id,
            topic_label=payload.topic,
            prompt=prompt_text,
            question_type=item.get("question_type") or payload.question_type,
            correct_answer=item.get("correct_answer"),
            explanation=item.get("explanation"),
            difficulty=item.get("difficulty") or payload.difficulty,
            source="generated",
            created_by_id=current_user.id,
        )
        db.add(question)
        db.flush()
        options = item.get("options") or []
        for idx, opt in enumerate(options):
            db.add(
                QuestionOption(
                    question_id=question.id,
                    label=chr(65 + idx),
                    text=str(opt),
                    is_correct=_same(opt, item.get("correct_answer")),
                )
            )
        questions_out.append(
            QuizQuestion(
                id=question.id,
                prompt=prompt_text,
                question_type=question.question_type,
                options=[str(o) for o in options],
                difficulty=question.difficulty,
            )
        )
    db.commit()
    return QuizOut(session_id=payload.session_id, topic=payload.topic, questions=questions_out)


def _normalise(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _same(a, b) -> bool:
    return bool(_normalise(a)) and _normalise(a) == _normalise(b)


@router.post("/quiz/submit", response_model=QuizResultOut)
def submit_quiz(payload: QuizSubmitRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    details: list[dict] = []
    weak: set[str] = set()
    score = 0

    for answer in payload.answers:
        question_id = answer.get("question_id")
        user_answer = answer.get("answer")
        question = db.query(Question).filter(Question.id == question_id).first()
        if question is None:
            continue
        correct = _same(user_answer, question.correct_answer)
        if not correct:
            option = (
                db.query(QuestionOption)
                .filter(QuestionOption.question_id == question.id, QuestionOption.is_correct.is_(True))
                .first()
            )
            if option is not None and _same(user_answer, option.label):
                correct = True
        if correct:
            score += 1
        else:
            weak.add(question.topic_label or payload.topic)
        details.append(
            {
                "question_id": question.id,
                "prompt": question.prompt,
                "your_answer": user_answer,
                "correct_answer": question.correct_answer,
                "is_correct": correct,
                "explanation": question.explanation,
            }
        )

    maximum = len(details) or 1
    percentage = round(score / maximum * 100)
    return QuizResultOut(
        score=score,
        maximum_score=maximum,
        percentage=percentage,
        weak_topics=sorted(t for t in weak if t),
        details=details,
    )
