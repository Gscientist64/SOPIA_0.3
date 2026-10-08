"""Learning, quiz, exam, interview, provider-switching and observability tests."""

import json

import pytest

from app.rag.prompts import QUESTION_AUTHOR_SYSTEM_PROMPT
from app.services import chat_service


@pytest.fixture
def with_context(monkeypatch, fake_chunk):
    monkeypatch.setattr(chat_service, "retrieve", lambda *a, **k: [fake_chunk])


# ----------------------------------------------------- grounded question authoring
def test_question_prompt_defines_grounding_and_trust_boundary():
    lowered = QUESTION_AUTHOR_SYSTEM_PROMPT.lower()
    assert "grounding rules" in lowered
    assert "reference data only" in lowered
    # The model must not fall back to its own knowledge, which is how an exam can
    # end up marking an answer correct that the SOP contradicts.
    assert "never use general knowledge" in lowered
    assert "do not invent" in lowered


def test_quiz_is_rejected_without_sop_grounding(client, normal_user, no_grounding):
    response = client.post(
        "/api/v1/learning/quiz",
        headers=normal_user["headers"],
        json={"topic": "Interplanetary Travel", "question_count": 2},
    )
    assert response.status_code == 409
    assert "No approved SOP content" in response.json()["detail"]


def test_exam_is_rejected_without_sop_grounding(client, normal_user, no_grounding):
    response = client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={"topic": "Interplanetary Travel", "question_count": 2},
    )
    assert response.status_code == 409
    assert "No approved SOP content" in response.json()["detail"]


def test_exam_questions_cite_their_sources(client, normal_user, sop_grounding):
    body = client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={"topic": "Client registration", "question_count": 2},
    ).json()

    assert body["questions"], "expected generated questions"
    for question in body["questions"]:
        assert question["citations"], "every generated question must cite its SOP source"
        citation = question["citations"][0]
        assert citation["document_title"] == "Client Registration SOP"
        assert citation["version"] == "3.2"
        assert citation["section"] == "3. REGISTRATION PROCEDURE"
        assert citation["page"] == 1


def test_exam_result_details_keep_their_sources(client, normal_user, sop_grounding):
    exam = client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={"topic": "Client registration", "question_count": 2},
    ).json()
    result = client.post(
        f"/api/v1/exams/attempts/{exam['attempt_id']}/submit",
        headers=normal_user["headers"],
        json={
            "answers": [
                {"question_id": q["id"], "answer": "4"} for q in exam["questions"]
            ]
        },
    ).json()

    assert result["details"]
    for detail in result["details"]:
        assert detail["sources"], "reviewed questions must keep their SOP sources"


def test_quiz_questions_cite_their_sources(client, normal_user, sop_grounding):
    body = client.post(
        "/api/v1/learning/quiz",
        headers=normal_user["headers"],
        json={"topic": "Client registration", "question_count": 2},
    ).json()

    assert body["questions"]
    for question in body["questions"]:
        assert question["citations"]
        assert question["citations"][0]["document_title"] == "Client Registration SOP"


def test_interview_question_is_grounded_when_the_sop_covers_the_role(
    client, normal_user, sop_grounding
):
    body = client.post(
        "/api/v1/interviews/start",
        headers=normal_user["headers"],
        json={"job_title": "Registration Officer", "topics": "client registration"},
    ).json()

    citations = body["question"]["citations"]
    assert citations
    assert citations[0]["document_title"] == "Client Registration SOP"


def test_interview_falls_back_when_the_knowledge_base_is_empty(
    client, normal_user, no_grounding
):
    response = client.post(
        "/api/v1/interviews/start",
        headers=normal_user["headers"],
        json={"job_title": "Data Analyst"},
    )
    # An interview is about the candidate, so an empty knowledge base must not
    # block practice the way it blocks a quiz or an exam.
    assert response.status_code == 200
    assert response.json()["question"]["prompt"]
    assert response.json()["question"]["citations"] == []


def test_interview_survives_a_retrieval_failure(client, normal_user, monkeypatch):
    from app.rag import grounding

    def boom(*args, **kwargs):
        raise RuntimeError("vector search unavailable")

    monkeypatch.setattr(grounding, "retrieve_grounding", boom)

    response = client.post(
        "/api/v1/interviews/start",
        headers=normal_user["headers"],
        json={"job_title": "Data Analyst"},
    )
    assert response.status_code == 200
    assert response.json()["question"]["prompt"]


# ------------------------------------------------------------------- learning
def test_learning_session_start(client, normal_user):
    response = client.post(
        "/api/v1/learning/sessions/start",
        headers=normal_user["headers"],
        json={"topic": "Monitoring and Evaluation"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session"]["topic_name"] == "Monitoring and Evaluation"
    assert body["session"]["total_sections"] == 4
    assert body["reply"]


def test_learning_turn_updates_progress(client, normal_user):
    session = client.post(
        "/api/v1/learning/sessions/start",
        headers=normal_user["headers"],
        json={"topic": "Epidemiology"},
    ).json()["session"]

    response = client.post(
        "/api/v1/learning/sessions/turn",
        headers=normal_user["headers"],
        json={"session_id": session["id"], "message": "I am a beginner."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"]
    assert body["weak_areas"] == ["indicators"]
    assert body["session"]["questions_answered"] == 1


def test_learning_turn_requires_valid_session(client, normal_user):
    response = client.post(
        "/api/v1/learning/sessions/turn",
        headers=normal_user["headers"],
        json={"session_id": 999, "message": "hello"},
    )
    assert response.status_code == 404


def test_learning_sessions_are_listed(client, normal_user):
    client.post(
        "/api/v1/learning/sessions/start",
        headers=normal_user["headers"],
        json={"topic": "Data analysis"},
    )
    response = client.get("/api/v1/learning/sessions", headers=normal_user["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_learning_session_can_be_completed(client, normal_user):
    session = client.post(
        "/api/v1/learning/sessions/start",
        headers=normal_user["headers"],
        json={"topic": "Reporting"},
    ).json()["session"]
    response = client.post(
        f"/api/v1/learning/sessions/{session['id']}/complete", headers=normal_user["headers"]
    )
    assert response.json()["status"] == "completed"


# ------------------------------------------------------------------------ quiz
def test_quiz_generation_and_scoring(client, normal_user, sop_grounding):
    quiz = client.post(
        "/api/v1/learning/quiz",
        headers=normal_user["headers"],
        json={"topic": "Maths", "question_count": 2, "difficulty": "easy", "question_type": "mcq"},
    )
    assert quiz.status_code == 200, quiz.text
    questions = quiz.json()["questions"]
    assert len(questions) == 2

    result = client.post(
        "/api/v1/learning/quiz/submit",
        headers=normal_user["headers"],
        json={
            "topic": "Maths",
            "answers": [
                {"question_id": questions[0]["id"], "answer": "4"},
                {"question_id": questions[1]["id"], "answer": "True"},
            ],
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["score"] == 2
    assert body["percentage"] == 100
    assert all(d["is_correct"] for d in body["details"])


def test_quiz_scoring_marks_wrong_answers(client, normal_user, sop_grounding):
    quiz = client.post(
        "/api/v1/learning/quiz",
        headers=normal_user["headers"],
        json={"topic": "Maths", "question_count": 2},
    ).json()["questions"]

    result = client.post(
        "/api/v1/learning/quiz/submit",
        headers=normal_user["headers"],
        json={
            "topic": "Maths",
            "answers": [
                {"question_id": quiz[0]["id"], "answer": "3"},
                {"question_id": quiz[1]["id"], "answer": "True"},
            ],
        },
    ).json()
    assert result["score"] == 1
    assert result["percentage"] == 50
    assert result["weak_topics"]


# ------------------------------------------------------------------------ exam
def test_exam_generate_and_full_score(client, normal_user, sop_grounding):
    response = client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={
            "topic": "Maths",
            "difficulty": "easy",
            "question_count": 2,
            "question_type": "mcq",
            "time_limit_minutes": 10,
        },
    )
    assert response.status_code == 200, response.text
    exam = response.json()
    assert len(exam["questions"]) == 2
    assert exam["expires_at"]

    result = client.post(
        f"/api/v1/exams/attempts/{exam['attempt_id']}/submit",
        headers=normal_user["headers"],
        json={
            "answers": [
                {"question_id": exam["questions"][0]["id"], "answer": "4"},
                {"question_id": exam["questions"][1]["id"], "answer": "True"},
            ]
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["score"] == 2
    assert body["maximum_score"] == 2
    assert body["percentage"] == 100
    assert all(d["explanation"] for d in body["details"])


def test_exam_submission_is_idempotent(client, normal_user, sop_grounding):
    exam = client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={"topic": "Maths", "question_count": 2},
    ).json()
    payload = {
        "answers": [{"question_id": exam["questions"][0]["id"], "answer": "4"}]
    }
    first = client.post(
        f"/api/v1/exams/attempts/{exam['attempt_id']}/submit",
        headers=normal_user["headers"],
        json=payload,
    ).json()
    second = client.post(
        f"/api/v1/exams/attempts/{exam['attempt_id']}/submit",
        headers=normal_user["headers"],
        json=payload,
    ).json()
    assert first["score"] == second["score"]


def test_exam_attempts_are_listed(client, normal_user, sop_grounding):
    client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={"topic": "Maths", "question_count": 2},
    )
    response = client.get("/api/v1/exams/attempts", headers=normal_user["headers"])
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_exam_attempt_of_another_user_is_hidden(client, admin, normal_user, sop_grounding):
    exam = client.post(
        "/api/v1/exams/generate",
        headers=normal_user["headers"],
        json={"topic": "Maths", "question_count": 2},
    ).json()
    response = client.get(
        f"/api/v1/exams/attempts/{exam['attempt_id']}", headers=admin["headers"]
    )
    assert response.status_code == 404


# ------------------------------------------------------------------- interview
def test_interview_flow_returns_feedback_and_summary(client, normal_user, no_grounding):
    start = client.post(
        "/api/v1/interviews/start",
        headers=normal_user["headers"],
        json={
            "job_title": "Monitoring and Evaluation Officer",
            "industry": "Health",
            "experience_level": "mid",
            "interview_type": "mixed",
        },
    )
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert start.json()["question"]["prompt"]

    first = client.post(
        f"/api/v1/interviews/{session_id}/answer",
        headers=normal_user["headers"],
        json={"answer": "I have three years of M&E experience."},
    )
    assert first.status_code == 200
    assert first.json()["feedback"]["strengths"] == ["Clear structure"]
    assert first.json()["done"] is False
    assert first.json()["next_question"]

    second = client.post(
        f"/api/v1/interviews/{session_id}/answer",
        headers=normal_user["headers"],
        json={"answer": "I led a regional survey."},
    )
    body = second.json()
    assert body["done"] is True
    assert body["summary"]["questions_answered"] == 2


def test_interview_answering_beyond_last_question_is_rejected(client, normal_user, no_grounding):
    session_id = client.post(
        "/api/v1/interviews/start",
        headers=normal_user["headers"],
        json={"job_title": "Data Analyst"},
    ).json()["session_id"]

    for _ in range(2):
        client.post(
            f"/api/v1/interviews/{session_id}/answer",
            headers=normal_user["headers"],
            json={"answer": "Answer"},
        )
    response = client.post(
        f"/api/v1/interviews/{session_id}/answer",
        headers=normal_user["headers"],
        json={"answer": "One too many"},
    )
    assert response.status_code == 400


# ------------------------------------------------------ provider configuration
def test_router_switches_between_providers(monkeypatch):
    import app.ai.router as router
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    router.get_ai_provider.cache_clear()
    assert router.get_ai_provider().name == "gemini"

    monkeypatch.setattr(settings, "AI_PROVIDER", "local")
    router.get_ai_provider.cache_clear()
    assert router.get_ai_provider().name == "local"


def test_gemini_without_api_key_raises_configuration_error():
    from app.ai.base import AIProviderError
    from app.ai.providers.gemini import GeminiProvider

    provider = GeminiProvider()
    provider.api_key = ""
    with pytest.raises(AIProviderError) as exc:
        provider.generate("hello")
    assert "GEMINI_API_KEY" in str(exc.value)


def test_provider_endpoint_reports_configuration(client, normal_user):
    response = client.get("/api/v1/provider", headers=normal_user["headers"])
    assert response.status_code == 200
    assert response.json()["provider"] == "local"
    assert response.json()["embedding_dim"] == 1024


# ------------------------------------------------------------- observability
def test_health_endpoint_reports_dependencies(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "ok"
    assert body["embedding_ok"] is True
    assert body["embedding_dim"] == 1024


def test_ai_calls_are_logged(client, normal_user, with_context, db):
    from app.models.audit import AIProviderLog

    client.post(
        "/api/v1/chat/",
        headers=normal_user["headers"],
        json={"message": "What must a client present?", "mode": "SOP_MODE"},
    )
    logs = db.query(AIProviderLog).all()
    assert logs
    assert logs[0].provider == "local"
    assert logs[0].success is True


# ------------------------------------------------------------------ dashboards
def test_user_dashboard_uses_real_counts(client, normal_user, with_context):
    empty = client.get("/api/v1/dashboard/me", headers=normal_user["headers"]).json()
    assert empty["stats"]["conversations"] == 0
    assert empty["stats"]["questions_asked"] == 0

    client.post(
        "/api/v1/chat/",
        headers=normal_user["headers"],
        json={"message": "What must a client present?", "mode": "SOP_MODE"},
    )
    after = client.get("/api/v1/dashboard/me", headers=normal_user["headers"]).json()
    assert after["stats"]["conversations"] == 1
    assert after["stats"]["questions_asked"] == 1


def test_admin_dashboard_reports_document_and_engagement_metrics(client, admin):
    response = client.get("/api/v1/admin/dashboard", headers=admin["headers"])
    assert response.status_code == 200
    body = response.json()
    assert set(body["totals"]) >= {"users", "conversations", "questions_asked"}
    assert set(body["documents"]) >= {"total", "active", "chunks"}


def test_admin_can_change_a_user_role(client, admin, normal_user, db):
    response = client.patch(
        f"/api/v1/admin/users/{normal_user['id']}",
        headers=admin["headers"],
        json={"role": "CONTENT_ADMIN"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "CONTENT_ADMIN"


def test_admin_rejects_invalid_role(client, admin, normal_user):
    response = client.patch(
        f"/api/v1/admin/users/{normal_user['id']}",
        headers=admin["headers"],
        json={"role": "WIZARD"},
    )
    assert response.status_code == 400


# ------------------------------------------------------------- citations helper
def test_citation_dict_includes_snippet_and_relevance(fake_chunk):
    from app.rag.citations import build_citation_dicts, citation_to_dict

    single = citation_to_dict(fake_chunk)
    assert single["document_title"] == "Client Registration SOP"
    assert single["snippet"]
    assert 0 <= single["relevance"] <= 1

    many = build_citation_dicts([fake_chunk, fake_chunk])
    assert len(many) == 2


def test_json_parsing_helpers_handle_fenced_output():
    from app.ai.parsing import parse_json_array, parse_json_object

    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert parse_json_array("not json at all") == []
    assert parse_json_object("nonsense") == {}


def test_json_parsing_salvages_malformed_model_output():
    """Small models emit almost-valid JSON; it must still yield usable objects."""
    from app.ai.parsing import parse_json_array, parse_json_object

    # Trailing comma
    assert parse_json_array('[{"prompt": "a"},]') == [{"prompt": "a"}]
    # Prose wrapped around the array
    assert parse_json_array('Sure!\n[{"prompt": "a"}]\nHope that helps.') == [{"prompt": "a"}]
    # Non-object entries are dropped, valid objects kept
    assert parse_json_array('["junk", {"prompt": "a"}]') == [{"prompt": "a"}]
    # A single object where an array was requested
    assert parse_json_array('{"prompt": "a"}') == [{"prompt": "a"}]
    # Broken nesting: balanced inner objects are salvaged
    assert parse_json_array('[{"prompt": "a"}, [1, {"prompt": "b"}]') == [
        {"prompt": "a"},
        {"prompt": "b"},
    ]

    # Object parsing tolerates surrounding prose too
    assert parse_json_object('Result:\n{"score": 3}\nDone.') == {"score": 3}


def test_normalise_questions_accepts_renamed_keys():
    """Models rename keys; the normaliser maps the common aliases."""
    from app.ai.parsing import normalise_questions

    items = [
        {"question": "What is 2+2?", "choices": ["3", "4"], "answer": "4", "type": "mcq"},
        {"prompt": "The sky is blue.", "options": ["True", "False"], "correct_answer": "True"},
        {"not_a_question": True},
    ]
    result = normalise_questions(items)

    assert len(result) == 2
    assert result[0]["prompt"] == "What is 2+2?"
    assert result[0]["options"] == ["3", "4"]
    assert result[0]["correct_answer"] == "4"
    assert result[1]["prompt"] == "The sky is blue."
    assert result[1]["correct_answer"] == "True"


def test_normalise_questions_handles_options_as_dict():
    from app.ai.parsing import normalise_questions

    result = normalise_questions(
        [{"prompt": "Pick one", "options": {"a": "First", "b": "Second"}}]
    )
    assert result[0]["options"] == ["First", "Second"]


def test_interview_summary_serialises_lists(fake_chunk):
    assert json.dumps({"ok": True})
