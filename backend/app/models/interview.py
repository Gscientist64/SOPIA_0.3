from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class InterviewStatus:
    ACTIVE = "active"
    COMPLETED = "completed"


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    job_title = Column(String, nullable=False)
    industry = Column(String)
    experience_level = Column(String)
    interview_type = Column(String, default="mixed")
    topics = Column(Text)
    status = Column(String, default=InterviewStatus.ACTIVE, nullable=False, index=True)
    summary = Column(Text)  # JSON: strengths/weaknesses/recommendations
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    questions = relationship(
        "InterviewQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.order_index",
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=False)
    question_type = Column(String, default="behavioral")
    # JSON list of the SOP excerpts this question was generated from.
    sources = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="questions")
    answer = relationship(
        "InterviewAnswer", back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_id = Column(
        Integer, ForeignKey("interview_questions.id"), nullable=False, unique=True, index=True
    )
    user_answer = Column(Text, nullable=False)
    feedback = Column(Text)  # JSON structured feedback
    score = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    question = relationship("InterviewQuestion", back_populates="answer")
