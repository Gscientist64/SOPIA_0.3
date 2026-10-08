import json
import logging
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProviderError
from app.ai.router import get_ai_provider
from app.core.security import CurrentUser
from app.db.session import get_db
from app.models.assessment import (
    AttemptStatus,
    ExamAnswer,
    ExamAttempt,
    ExamSession,
    Question,
    QuestionOption,
    QuestionType,
)
from app.schemas.assessment import (
    ExamAttemptOut,
    ExamGenerateRequest,
    ExamOut,
    ExamQuestionOut,
    ExamResultOut,
    ExamStartResponse,
    ExamSubmitRequest,
)
from app.services.audit import log_ai_call

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalise(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _same(a, b) -> bool:
    return bool(_normalise(a)) and _normalise(a) == _normalise(b)


def _question_options(db: Session, question: Question) -> list[str]:
    return [o.text for o in question.options]


def _question_out(db: Session, question: Question) -> ExamQuestionOut:
    return ExamQuestionOut(
        id=question.id,
        prompt=question.prompt,
        question_type=question.question_type,
        options=_question_options(db, question),
        difficulty=question.difficulty,
    )


def _load_questions(db: Session, exam: ExamSession) -> list[Question]:
    ids = json.loads(exam.question_ids or "[]")
    if not ids:
        return []
    questions = db.query(Question).filter(Question.id.in_(ids)).all()
    order = {qid: i for i, qid in enumerate(ids)}
    return sorted(questions, key=lambda q: order.get(q.id, 0))


@router.post("/generate", response_model=ExamStartResponse)
def generate_exam(
    payload: ExamGenerateRequest, current_user: CurrentUser, db: Session = Depends(get_db)
):
    provider = get_ai_provider()
    try:
        with log_ai_call(db, provider.name, "exam_generate", mode="EXAM_MODE", user_id=current_user.id):
            items = provider.generate_questions(
                payload.topic, payload.question_count, payload.difficulty, payload.question_type
            )
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not items:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI could not generate exam questions. Please try again.",
        )

    questions: list[Question] = []
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
        questions.append(question)

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI returned no usable questions. Please try again.",
        )

    exam = ExamSession(
        organization_id=current_user.organization_id,
        topic_label=payload.topic,
        difficulty=payload.difficulty,
        question_count=len(questions),
        time_limit_minutes=payload.time_limit_minutes,
        question_type=payload.question_type,
        question_ids=json.dumps([q.id for q in questions]),
        created_by_id=current_user.id,
    )
    db.add(exam)
    db.flush()

    attempt = ExamAttempt(
        exam_session_id=exam.id,
        user_id=current_user.id,
        status=AttemptStatus.IN_PROGRESS,
        maximum_score=len(questions),
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=payload.time_limit_minutes),
    )
    db.add(attempt)
    db.commit()
    db.refresh(exam)
    db.refresh(attempt)

    return ExamStartResponse(
        attempt_id=attempt.id,
        exam=ExamOut.model_validate(exam),
        questions=[_question_out(db, q) for q in questions],
        expires_at=attempt.expires_at,
    )


@router.get("/attempts", response_model=list[ExamAttemptOut])
def list_attempts(current_user: CurrentUser, db: Session = Depends(get_db)):
    return (
        db.query(ExamAttempt)
        .filter(ExamAttempt.user_id == current_user.id)
        .order_by(ExamAttempt.created_at.desc())
        .all()
    )


def _owned_attempt(db: Session, attempt_id: int, user) -> ExamAttempt:
    attempt = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.id == attempt_id, ExamAttempt.user_id == user.id)
        .first()
    )
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")
    return attempt


@router.get("/attempts/{attempt_id}/result", response_model=ExamResultOut)
def get_result(attempt_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    attempt = _owned_attempt(db, attempt_id, current_user)
    return _build_result(db, attempt)


def _build_result(db: Session, attempt: ExamAttempt) -> ExamResultOut:
    details: list[dict] = []
    for answer in attempt.answers:
        question = answer.question
        details.append(
            {
                "question_id": question.id if question else None,
                "prompt": question.prompt if question else None,
                "your_answer": answer.user_answer,
                "correct_answer": question.correct_answer if question else None,
                "is_correct": bool(answer.is_correct),
                "explanation": question.explanation if question else None,
                "topic": question.topic_label if question else None,
            }
        )
    return ExamResultOut(
        attempt_id=attempt.id,
        score=attempt.score or 0,
        maximum_score=attempt.maximum_score or 0,
        percentage=attempt.percentage or 0,
        weak_topics=json.loads(attempt.weak_topics or "[]"),
        details=details,
    )


@router.get("/attempts/{attempt_id}", response_model=ExamResultOut)
def get_attempt(attempt_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    attempt = _owned_attempt(db, attempt_id, current_user)
    return _build_result(db, attempt)


@router.post("/attempts/{attempt_id}/submit", response_model=ExamResultOut)
def submit_exam(
    attempt_id: int,
    payload: ExamSubmitRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    attempt = _owned_attempt(db, attempt_id, current_user)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return _build_result(db, attempt)

    exam = attempt.exam_session
    questions = _load_questions(db, exam)
    answers_by_id = {a.get("question_id"): a.get("answer") for a in payload.answers}

    score = 0
    weak: set[str] = set()
    db.query(ExamAnswer).filter(ExamAnswer.attempt_id == attempt.id).delete(
        synchronize_session=False
    )

    for question in questions:
        user_answer = answers_by_id.get(question.id)
        is_correct = _same(user_answer, question.correct_answer)
        if not is_correct and question.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            option = (
                db.query(QuestionOption)
                .filter(
                    QuestionOption.question_id == question.id,
                    QuestionOption.is_correct.is_(True),
                )
                .first()
            )
            if option is not None and _same(user_answer, option.label):
                is_correct = True
        if is_correct:
            score += 1
        elif user_answer:
            weak.add(question.topic_label or "general")

        db.add(
            ExamAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                user_answer=str(user_answer) if user_answer is not None else None,
                is_correct=is_correct,
                score_awarded=1 if is_correct else 0,
                feedback=question.explanation,
            )
        )

    attempt.score = score
    attempt.maximum_score = len(questions)
    attempt.percentage = round(score / len(questions) * 100) if questions else 0
    attempt.weak_topics = json.dumps(sorted(weak))
    # Some drivers (e.g. SQLite) return naive datetimes; normalise before comparing.
    expires_at = attempt.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    attempt.status = (
        AttemptStatus.EXPIRED
        if expires_at is not None and datetime.now(UTC) > expires_at
        else AttemptStatus.SUBMITTED
    )
    attempt.submitted_at = datetime.now(UTC)
    db.commit()
    db.refresh(attempt)
    return _build_result(db, attempt)
