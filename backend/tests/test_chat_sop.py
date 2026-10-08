"""SOP chat, citations, refusal behaviour, streaming and prompt hardening."""

import pytest

from app.rag.prompts import (
    SOP_NO_CONTEXT_ANSWER,
    SOP_SYSTEM_PROMPT,
    build_user_prompt,
    get_system_prompt,
)
from app.services import chat_service


@pytest.fixture
def no_context(monkeypatch):
    monkeypatch.setattr(chat_service, "retrieve", lambda *a, **k: [])


@pytest.fixture
def with_context(monkeypatch, fake_chunk):
    monkeypatch.setattr(chat_service, "retrieve", lambda *a, **k: [fake_chunk])


def ask(client, headers, message, mode="SOP_MODE", conversation_id=None):
    payload = {"message": message, "mode": mode}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return client.post("/api/v1/chat/", headers=headers, json=payload)


# ------------------------------------------------------------------- prompt hardening
def test_sop_prompt_defines_trust_boundary():
    lowered = SOP_SYSTEM_PROMPT.lower()
    assert "<retrieved_sop_context>" in lowered
    assert "not as instructions" in lowered or "never an instruction" in lowered
    assert "ignore previous instructions" in lowered


def test_context_is_delimited_in_user_prompt():
    prompt = build_user_prompt("What is the procedure?", "<retrieved_sop_context>x</retrieved_sop_context>")
    assert "<retrieved_sop_context>" in prompt
    assert "</retrieved_sop_context>" in prompt
    assert "<user_question>" in prompt


def test_system_prompt_instructs_refusal():
    lowered = get_system_prompt("SOP_MODE").lower()
    assert "couldn't find" in lowered


# ------------------------------------------------------------------------- refusal
def test_sop_mode_refuses_without_retrieved_context(client, normal_user, no_context):
    response = ask(client, normal_user["headers"], "What is the policy on interplanetary travel?")
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"]["content"] == SOP_NO_CONTEXT_ANSWER
    assert body["assistant_message"]["citations"] == []


# ------------------------------------------------------------------------ grounded
def test_sop_answer_is_grounded_and_cited(client, normal_user, with_context):
    response = ask(client, normal_user["headers"], "What must a client present?")
    assert response.status_code == 200
    message = response.json()["assistant_message"]

    assert message["citations"], "expected structured citations"
    citation = message["citations"][0]
    assert citation["document_title"] == "Client Registration SOP"
    assert citation["version"] == "3.2"
    assert citation["section"] == "3. REGISTRATION PROCEDURE"
    assert citation["page"] == 1
    assert citation["relevance"] == pytest.approx(0.82)


def test_citations_are_persisted(client, normal_user, with_context, db):
    from app.models.chat import Citation

    ask(client, normal_user["headers"], "What must a client present?")
    assert db.query(Citation).count() >= 1


def test_raw_context_is_not_returned_to_the_user(client, normal_user, with_context):
    body = ask(client, normal_user["headers"], "What must a client present?").json()
    assert "<retrieved_sop_context>" not in body["assistant_message"]["content"]


# -------------------------------------------------------------------- persistence
def test_conversation_is_created_and_titled(client, normal_user, with_context):
    body = ask(client, normal_user["headers"], "What must a client present?").json()
    conversation = client.get(
        f"/api/v1/conversations/{body['conversation_id']}", headers=normal_user["headers"]
    ).json()
    assert conversation["title"].startswith("What must a client present")
    assert len(conversation["messages"]) == 2
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]


def test_conversation_can_be_continued(client, normal_user, with_context):
    first = ask(client, normal_user["headers"], "First question?").json()
    second = ask(
        client,
        normal_user["headers"],
        "Second question?",
        conversation_id=first["conversation_id"],
    ).json()
    assert second["conversation_id"] == first["conversation_id"]

    conversation = client.get(
        f"/api/v1/conversations/{first['conversation_id']}", headers=normal_user["headers"]
    ).json()
    assert len(conversation["messages"]) == 4


def test_rename_delete_and_clear_conversation(client, normal_user, with_context):
    body = ask(client, normal_user["headers"], "Hello?").json()
    cid = body["conversation_id"]

    renamed = client.patch(
        f"/api/v1/conversations/{cid}", headers=normal_user["headers"], json={"title": "Renamed"}
    )
    assert renamed.json()["title"] == "Renamed"

    cleared = client.post(f"/api/v1/conversations/{cid}/clear", headers=normal_user["headers"])
    assert cleared.status_code == 200
    assert (
        client.get(f"/api/v1/conversations/{cid}", headers=normal_user["headers"]).json()["messages"]
        == []
    )

    assert (
        client.delete(f"/api/v1/conversations/{cid}", headers=normal_user["headers"]).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/conversations/{cid}", headers=normal_user["headers"]).status_code
        == 404
    )


def test_conversation_search(client, normal_user, with_context):
    ask(client, normal_user["headers"], "Unique topic about malaria nets?")
    response = client.get(
        "/api/v1/conversations", headers=normal_user["headers"], params={"q": "malaria"}
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_retry_regenerates_assistant_message(client, normal_user, with_context):
    body = ask(client, normal_user["headers"], "What must a client present?").json()
    cid = body["conversation_id"]
    assistant_id = body["assistant_message"]["id"]

    response = client.post(
        f"/api/v1/conversations/{cid}/messages/{assistant_id}/retry",
        headers=normal_user["headers"],
    )
    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    assert response.json()["content"]

    # The old answer is replaced, so the turn still holds exactly two messages.
    messages = client.get(f"/api/v1/conversations/{cid}", headers=normal_user["headers"]).json()[
        "messages"
    ]
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_retry_rejects_non_assistant_message(client, normal_user, with_context):
    body = ask(client, normal_user["headers"], "What must a client present?").json()
    response = client.post(
        f"/api/v1/conversations/{body['conversation_id']}/messages/"
        f"{body['user_message']['id']}/retry",
        headers=normal_user["headers"],
    )
    assert response.status_code == 404


# --------------------------------------------------------------------- streaming
def test_streaming_emits_deltas_and_citations(client, normal_user, with_context):
    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        headers=normal_user["headers"],
        json={"message": "What must a client present?", "mode": "SOP_MODE"},
    ) as response:
        body = "".join(chunk for chunk in response.iter_text())

    assert "event: meta" in body
    assert "event: delta" in body
    assert "event: citations" in body
    assert "event: done" in body


def test_streaming_persists_messages(client, normal_user, with_context, db):
    from app.models.chat import Message

    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        headers=normal_user["headers"],
        json={"message": "Streamed question", "mode": "SOP_MODE"},
    ) as response:
        list(response.iter_text())

    assert db.query(Message).filter_by(content="Streamed question").count() == 1
    assert db.query(Message).filter_by(role="assistant").count() >= 1


# ------------------------------------------------------------------ mode handling
def test_modes_endpoint_reports_availability(client, normal_user):
    response = client.get("/api/v1/chat/modes", headers=normal_user["headers"])
    modes = {m["value"]: m["available"] for m in response.json()["modes"]}
    assert modes["SOP_MODE"] is True
    assert modes["LEARNING_MODE"] is True
    assert modes["EXAM_MODE"] is False


def test_unknown_mode_returns_400(client, normal_user):
    response = ask(client, normal_user["headers"], "hi", mode="NONSENSE")
    assert response.status_code == 400


def test_unimplemented_mode_returns_501(client, normal_user):
    response = ask(client, normal_user["headers"], "hi", mode="RESEARCH_MODE")
    assert response.status_code == 501


def test_learning_mode_does_not_require_sop_context(client, normal_user, no_context):
    response = ask(client, normal_user["headers"], "Teach me M&E", mode="LEARNING_MODE")
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"]
