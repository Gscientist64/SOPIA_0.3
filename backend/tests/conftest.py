"""Shared pytest fixtures.

Tests run fully hermetically: no Ollama, no PostgreSQL. The AI provider is
exercised through the *real* code path but with `requests.post` stubbed, and the
database is an in-memory SQLite instance.

Note: pgvector similarity search itself is PostgreSQL-specific, so it is covered
by `scripts/e2e_test.py` against a real Postgres+pgvector instance rather than
here.
"""

import json
import os
import sqlite3
from types import SimpleNamespace

import pytest

# Must be set before any `app.*` import.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["AI_PROVIDER"] = "local"
os.environ["EMBEDDING_DIM"] = "1024"
os.environ["GEMINI_API_KEY"] = ""

# SQLite cannot bind Python lists natively; pgvector passes vectors as lists.
sqlite3.register_adapter(list, lambda value: json.dumps(value))

import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.models  # noqa: F401,E402  (register all models)
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

EMBED_DIM = 1024

QUESTIONS_JSON = json.dumps(
    [
        {
            "prompt": "What is 2 + 2?",
            "question_type": "mcq",
            "options": ["3", "4", "5"],
            "correct_answer": "4",
            "explanation": "Basic arithmetic.",
            "topic": "Maths",
            "difficulty": "easy",
        },
        {
            "prompt": "The sky is blue.",
            "question_type": "true_false",
            "options": ["True", "False"],
            "correct_answer": "True",
            "explanation": "Rayleigh scattering.",
            "topic": "Science",
            "difficulty": "easy",
        },
    ]
)

FEEDBACK_JSON = json.dumps(
    {
        "strengths": ["Clear structure"],
        "weaknesses": ["Lacks metrics"],
        "missing_points": ["Quantified impact"],
        "clarity": "Good",
        "accuracy": "Reasonable",
        "relevance": "High",
        "suggested_answer": "Add measurable outcomes.",
        "follow_up": "Can you quantify that?",
    }
)

OUTLINE_JSON = json.dumps(
    {
        "intro": "Let's explore this topic together.",
        "sections": ["Introduction", "Key concepts", "Practice", "Summary"],
        "first_question": "What do you already know?",
    }
)

TUTOR_JSON = json.dumps(
    {"reply": "Great start. Let's go deeper.", "weak_areas": ["indicators"], "suggested_next": "Logic models"}
)

INTERVIEW_JSON = json.dumps(
    [
        {"prompt": "Tell me about yourself.", "question_type": "behavioral"},
        {"prompt": "Describe a challenging project.", "question_type": "behavioral"},
    ]
)


class FakeResponse:
    def __init__(self, payload=None, lines=None, status=200):
        self._payload = payload or {}
        self._lines = lines or []
        self.status_code = status
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def iter_lines(self):
        for line in self._lines:
            yield line

    def close(self):
        pass


def _chat_reply(system: str, user: str) -> str:
    lowered = f"{system}\n{user}".lower()
    if "assessment author" in lowered:
        return QUESTIONS_JSON
    if "examiner" in lowered:
        return FEEDBACK_JSON
    if "learning outline" in lowered:
        return OUTLINE_JSON
    if "continue tutoring" in lowered:
        return TUTOR_JSON
    if "interview questions" in lowered:
        return INTERVIEW_JSON
    return "Grounded answer based on the provided reference material. [1]"


@pytest.fixture(autouse=True)
def stub_ollama(monkeypatch):
    """Replace Ollama HTTP calls with deterministic fakes."""

    def fake_post(url, stream=False, timeout=None, **kwargs):
        # NB: accept the request body via **kwargs — naming a parameter `json`
        # would shadow the `json` module used below.
        payload = kwargs.get("json") or {}
        if url.endswith("/api/embeddings"):
            dim = int(os.environ.get("EMBEDDING_DIM", EMBED_DIM))
            return FakeResponse({"embedding": [0.01 * ((i % 13) + 1) for i in range(dim)]})
        if url.endswith("/api/embed"):
            dim = int(os.environ.get("EMBEDDING_DIM", EMBED_DIM))
            inputs = payload.get("input") or []
            if isinstance(inputs, str):
                inputs = [inputs]
            return FakeResponse(
                {
                    "embeddings": [
                        [0.01 * ((i % 13) + 1) for i in range(dim)] for _ in inputs
                    ]
                }
            )
        if url.endswith("/api/tags"):
            return FakeResponse({"models": []})
        if url.endswith("/api/chat"):
            messages = payload.get("messages", [])
            system = next((m["content"] for m in messages if m.get("role") == "system"), "")
            user = next((m["content"] for m in messages if m.get("role") == "user"), "")
            reply = _chat_reply(system, user)
            if stream:
                lines = [
                    json.dumps({"message": {"content": reply[:10]}, "done": False}).encode(),
                    json.dumps({"message": {"content": reply[10:]}, "done": True}).encode(),
                ]
                return FakeResponse({}, lines=lines)
            return FakeResponse({"message": {"content": reply}})
        return FakeResponse({})

    monkeypatch.setattr(requests, "post", fake_post)

    def fake_get(url, **kwargs):
        if url.endswith("/api/tags"):
            return FakeResponse({"models": []})
        raise requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", fake_get)


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    # A file-backed SQLite database (not in-memory) so that separate sessions —
    # including the one the SSE streaming endpoint opens for itself — share it.
    db_path = tmp_path_factory.mktemp("sopia-test") / "test.db"
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db, engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # The streaming endpoint deliberately opens its own session; point it at the
    # test database.
    import app.api.routes.chat as chat_routes

    chat_routes.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client, email, password="Str0ngPass!2025", full_name="Test User"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client, db):
    """A super-admin account plus its headers."""
    from app.models.user import RoleEnum, User

    body = register(client, "admin@test.local")
    user = db.query(User).filter_by(id=body["user"]["id"]).one()
    user.role = RoleEnum.SUPER_ADMIN.value
    db.commit()
    return {"headers": auth_header(body["access_token"]), "id": user.id}


@pytest.fixture
def normal_user(client, db, admin):
    """A plain USER. Depends on ``admin`` so it is never the first registration."""
    from app.models.user import RoleEnum, User

    body = register(client, "user@test.local")
    user = db.query(User).filter_by(id=body["user"]["id"]).one()
    user.role = RoleEnum.USER.value
    db.commit()
    return {"headers": auth_header(body["access_token"]), "id": user.id}


@pytest.fixture
def fake_chunk():
    """A RetrievedChunk stand-in for chat/citation tests."""
    from app.rag.retrieval import RetrievedChunk

    document = SimpleNamespace(id=1, title="Client Registration SOP", doc_type="txt")
    version = SimpleNamespace(id=1, version_label="3.2")
    chunk = SimpleNamespace(
        id=1,
        content="Every new client must present a valid government-issued identification document.",
        section="3. REGISTRATION PROCEDURE",
        heading="3. REGISTRATION PROCEDURE",
        page_number=1,
        document_id=1,
    )
    return RetrievedChunk(
        chunk=chunk, document=document, version=version, relevance=0.82, distance=0.18
    )


@pytest.fixture
def sop_grounding(monkeypatch, fake_chunk):
    """Ground generated questions in a stand-in SOP chunk.

    ``app.rag.grounding`` is the single retrieval seam for generated content, and
    pgvector search cannot run on SQLite, so it is stubbed here.
    """
    from app.rag import grounding

    monkeypatch.setattr(grounding, "retrieve_grounding", lambda *a, **k: [fake_chunk])


@pytest.fixture
def no_grounding(monkeypatch):
    """Simulate a knowledge base with nothing relevant to the requested topic."""
    from app.rag import grounding

    monkeypatch.setattr(grounding, "retrieve_grounding", lambda *a, **k: [])
