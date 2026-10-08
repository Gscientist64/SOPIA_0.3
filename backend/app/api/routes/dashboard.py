import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.db.session import get_db
from app.models.assessment import AttemptStatus, ExamAttempt
from app.models.chat import Conversation, Message, MessageRole
from app.models.interview import InterviewSession, InterviewStatus
from app.models.learning import LearningSession, LearningStatus
from app.schemas.dashboard import RecentItem, UserDashboardOut

router = APIRouter()

_DEFAULT_RECOMMENDATIONS = [
    "Monitoring and Evaluation fundamentals",
    "Data collection and quality",
    "Report writing essentials",
]


@router.get("/me", response_model=UserDashboardOut)
def user_dashboard(current_user: CurrentUser, db: Session = Depends(get_db)):
    user_id = current_user.id

    conversation_count = (
        db.query(func.count(Conversation.id)).filter(Conversation.user_id == user_id).scalar() or 0
    )
    questions_asked = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == user_id, Message.role == MessageRole.USER)
        .scalar()
        or 0
    )
    learning_sessions = (
        db.query(func.count(LearningSession.id))
        .filter(LearningSession.user_id == user_id)
        .scalar()
        or 0
    )
    learning_completed = (
        db.query(func.count(LearningSession.id))
        .filter(LearningSession.user_id == user_id, LearningSession.status == LearningStatus.COMPLETED)
        .scalar()
        or 0
    )
    exams_completed = (
        db.query(func.count(ExamAttempt.id))
        .filter(
            ExamAttempt.user_id == user_id,
            ExamAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
        )
        .scalar()
        or 0
    )
    interviews_completed = (
        db.query(func.count(InterviewSession.id))
        .filter(InterviewSession.user_id == user_id, InterviewSession.status == InterviewStatus.COMPLETED)
        .scalar()
        or 0
    )

    # Aggregate weak topics from learning sessions and exam attempts.
    weak: list[str] = []
    for (raw,) in db.query(LearningSession.weak_areas).filter(LearningSession.user_id == user_id).all():
        weak.extend(_load_list(raw))
    for (raw,) in db.query(ExamAttempt.weak_topics).filter(ExamAttempt.user_id == user_id).all():
        weak.extend(_load_list(raw))
    weak_topics = list(dict.fromkeys([w for w in weak if w]))[:8]

    recent_conversations = [
        RecentItem(id=c.id, label=c.title, detail=c.mode, at=c.updated_at)
        for c in db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(5)
        .all()
    ]
    recent_learning = [
        RecentItem(id=s.id, label=s.topic_name, detail=s.status, at=s.created_at)
        for s in db.query(LearningSession)
        .filter(LearningSession.user_id == user_id)
        .order_by(LearningSession.created_at.desc())
        .limit(5)
        .all()
    ]
    attempts = [
        {
            "id": a.id,
            "status": a.status,
            "score": a.score,
            "maximum_score": a.maximum_score,
            "percentage": a.percentage,
            "at": a.submitted_at or a.started_at,
        }
        for a in db.query(ExamAttempt)
        .filter(ExamAttempt.user_id == user_id)
        .order_by(ExamAttempt.created_at.desc())
        .limit(5)
        .all()
    ]
    interviews = [
        {"id": s.id, "job_title": s.job_title, "status": s.status, "at": s.created_at}
        for s in db.query(InterviewSession)
        .filter(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.created_at.desc())
        .limit(5)
        .all()
    ]

    return UserDashboardOut(
        stats={
            "conversations": conversation_count,
            "questions_asked": questions_asked,
            "learning_sessions": learning_sessions,
            "learning_completed": learning_completed,
            "exams_completed": exams_completed,
            "interviews_completed": interviews_completed,
        },
        weak_topics=weak_topics,
        recommended_topics=weak_topics[:3] or _DEFAULT_RECOMMENDATIONS,
        recent_conversations=recent_conversations,
        recent_learning=recent_learning,
        exam_attempts=attempts,
        interview_sessions=interviews,
    )


def _load_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(item) for item in data]
    return []
