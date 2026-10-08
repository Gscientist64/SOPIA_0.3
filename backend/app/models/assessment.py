from sqlalchemy import (
    Boolean,
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


class QuestionType:
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    SCENARIO = "scenario"
    MIXED = "mixed"


class AttemptStatus:
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), index=True)
    topic_label = Column(String, index=True)
    prompt = Column(Text, nullable=False)
    question_type = Column(String, default=QuestionType.MCQ, nullable=False)
    correct_answer = Column(Text)
    explanation = Column(Text)
    difficulty = Column(String, default="medium")
    source = Column(String, default="generated")  # generated | manual
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    options = relationship(
        "QuestionOption", back_populates="question", cascade="all, delete-orphan"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    label = Column(String)
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)

    question = relationship("Question", back_populates="options")


class ExamSession(Base):
    """A reusable exam definition (configuration + generated questions)."""

    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    topic_label = Column(String)
    difficulty = Column(String, default="medium")
    question_count = Column(Integer, default=5)
    time_limit_minutes = Column(Integer, default=15)
    question_type = Column(String, default=QuestionType.MCQ)
    question_ids = Column(Text)  # JSON list of question ids
    created_by_id = Column(Integer, ForeignKey("users.id"))
    is_shared = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempts = relationship("ExamAttempt", back_populates="exam_session")


class ExamAttempt(Base):
    """A single user's attempt at an :class:`ExamSession`."""

    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default=AttemptStatus.IN_PROGRESS, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    score = Column(Integer, default=0)
    maximum_score = Column(Integer, default=0)
    percentage = Column(Integer)
    weak_topics = Column(Text)  # JSON list
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    exam_session = relationship("ExamSession", back_populates="attempts")
    answers = relationship(
        "ExamAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )


class ExamAnswer(Base):
    __tablename__ = "exam_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    score_awarded = Column(Integer, default=0)
    feedback = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempt = relationship("ExamAttempt", back_populates="answers")
    question = relationship("Question")
