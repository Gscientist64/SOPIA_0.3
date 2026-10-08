from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import AdminUser, SuperAdminUser
from app.db.session import get_db
from app.models.assessment import AttemptStatus, ExamAttempt
from app.models.audit import AIProviderLog
from app.models.chat import Conversation, Message, MessageRole
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion, ProcessingStatus
from app.models.interview import InterviewSession, InterviewStatus
from app.models.learning import LearningSession
from app.models.user import RoleEnum, User
from app.schemas.auth import UserOut
from app.schemas.dashboard import AdminDashboardOut

router = APIRouter()


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


def _count(db: Session, model, *criteria) -> int:
    query = db.query(func.count(model.id))
    if criteria:
        query = query.filter(*criteria)
    return query.scalar() or 0


@router.get("/dashboard", response_model=AdminDashboardOut)
def admin_dashboard(admin: AdminUser, db: Session = Depends(get_db)):
    org_filter = admin.organization_id

    def org_scoped(model):
        return [] if org_filter is None else [model.organization_id == org_filter]

    totals = {
        "users": _count(db, User, *org_scoped(User)),
        "organizations": db.query(func.count(func.distinct(User.organization_id))).scalar() or 0,
        "conversations": _count(db, Conversation),
        "questions_asked": _count(db, Message, Message.role == MessageRole.USER),
        "learning_sessions": _count(db, LearningSession),
        "exams_completed": _count(
            db, ExamAttempt, ExamAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED])
        ),
        "interviews_completed": _count(
            db, InterviewSession, InterviewSession.status == InterviewStatus.COMPLETED
        ),
    }

    documents = {
        "total": _count(db, Document, *org_scoped(Document)),
        "active": _count(db, Document, Document.status == DocumentStatus.ACTIVE),
        "processing": _count(db, Document, Document.status == DocumentStatus.PROCESSING),
        "errored": _count(db, Document, Document.status == DocumentStatus.ERROR),
        "versions": _count(db, DocumentVersion),
        "failed_versions": _count(db, DocumentVersion, DocumentVersion.processing_status == ProcessingStatus.ERROR),
        "chunks": _count(db, DocumentChunk),
    }

    engagement = {
        "active_users": _count(db, User, User.is_active.is_(True)),
        "ai_calls": _count(db, AIProviderLog),
    }

    recent_documents = [
        {
            "id": d.id,
            "title": d.title,
            "status": d.status,
            "department": d.department,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in db.query(Document)
        .order_by(Document.created_at.desc())
        .limit(10)
        .all()
    ]

    return AdminDashboardOut(
        totals=totals, documents=documents, engagement=engagement, recent_documents=recent_documents
    )


@router.get("/users", response_model=list[UserOut])
def list_users(admin: SuperAdminUser, db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdate, admin: SuperAdminUser, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.role is not None:
        if payload.role not in {r.value for r in RoleEnum}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        if user.id == admin.id and payload.role != RoleEnum.SUPER_ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove your own super-admin role.",
            )
        user.role = payload.role
    if payload.is_active is not None:
        if user.id == admin.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate yourself."
            )
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user
