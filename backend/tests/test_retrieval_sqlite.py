"""Retrieval tests that run the real search path on SQLite.

The main suite historically could not cover retrieval at all: pgvector's
``cosine_distance`` is PostgreSQL-only, so those calls were stubbed out and the
vector search was left unverified (a gap recorded in PROJECT_STATUS.md).

``app/rag/retrieval.py`` now scores candidates in Python when the bind dialect
is not PostgreSQL, so these tests exercise the genuine end-to-end path —
metadata filters, similarity ranking, threshold refusal and citation building —
on the SQLite database the rest of the suite already uses.
"""

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    ProcessingStatus,
)
from app.models.user import Organization
from app.rag import retrieval as retrieval_module
from app.rag.chunking import Chunk
from app.rag.ingestion import _embed_text
from app.rag.retrieval import build_context, retrieve

# A dedicated organisation keeps these rows isolated from every other test.
ORG = 777

CHUNK_A = "Every new client must present a valid government-issued identification document."
CHUNK_B = "The registration officer must capture the full name, date of birth and contact telephone number."
QUERY_MATCHING_A = "must a new client present a valid government-issued identification document"


@pytest.fixture
def knowledge_base(db: Session, fake_embeddings):
    """A small corpus: one good document, one irrelevant, plus excluded rows.

    The test database is file-backed and shared for the whole session, so any
    rows from a previous run of these tests are cleared first.
    """
    for model in (DocumentChunk, DocumentVersion, Document):
        db.query(model).filter(model.organization_id.in_([ORG, 888])).delete(
            synchronize_session=False
        )
    db.query(Organization).filter(Organization.id.in_([ORG, 888])).delete(
        synchronize_session=False
    )
    db.commit()

    db.add(Organization(id=ORG, name="Retrieval Test Org"))
    db.add(Organization(id=888, name="Retrieval Other Org"))

    def add(
        document_id: int,
        title: str,
        chunks: list[str],
        *,
        status: str = DocumentStatus.ACTIVE,
        processing: str = ProcessingStatus.READY,
        is_active: bool = True,
        organization_id: int = ORG,
    ) -> None:
        db.add(
            Document(
                id=document_id,
                title=title,
                status=status,
                organization_id=organization_id,
            )
        )
        db.add(
            DocumentVersion(
                id=document_id,
                document_id=document_id,
                organization_id=organization_id,
                version_label="3.2",
                is_active=is_active,
                processing_status=processing,
                file_path=f"{document_id}.txt",
            )
        )
        for index, content in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document_id,
                    document_version_id=document_id,
                    organization_id=organization_id,
                    content=content,
                    chunk_index=index,
                    section="3. REGISTRATION PROCEDURE",
                    heading="3. REGISTRATION PROCEDURE",
                    page_number=1,
                    embedding=fake_embeddings(content),
                )
            )

    add(101, "Client Registration SOP", [CHUNK_A, CHUNK_B])
    add(102, "Leave Policy", ["Annual leave must be requested fourteen days in advance."])
    add(103, "Other Tenant SOP", ["Welding safety procedures for the fabrication workshop."], organization_id=888)
    add(104, "Draft SOP", ["Draft text that must never be retrievable."], status=DocumentStatus.DRAFT)
    add(105, "Errored SOP", ["Text from an ingestion that failed."], processing=ProcessingStatus.ERROR)
    add(106, "Superseded Version", ["Old superseded wording that must not be searched."], is_active=False)
    db.commit()
    return db


def test_retrieval_does_not_require_postgres(knowledge_base):
    assert knowledge_base.get_bind().dialect.name == "sqlite"


def test_relevant_chunk_is_retrieved_and_ranked_first(knowledge_base):
    results = retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG)

    assert results, "the matching chunk should be retrieved"
    assert results[0].chunk.content == CHUNK_A
    assert results[0].relevance == pytest.approx(0.92, abs=0.05)
    # Its score must beat every other candidate, not merely be present.
    assert results[0].score >= max(r.score for r in results)


def test_keyword_signal_contributes_to_the_score(knowledge_base):
    results = retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG)
    top = results[0]
    assert top.keyword_score > 0
    assert top.score == pytest.approx(
        0.8 * top.relevance
        + 0.2 * top.keyword_score
        + retrieval_module._HEADING_WEIGHT * top.heading_score
    )


# ------------------------------------------------- structural context in ranking
def test_plural_query_terms_match_singular_headings():
    """A query asking for "pillars" must match a chunk headed "Pillar 1 ...".

    Without plural folding the keyword signal scored zero, which is how a chunk
    that only *mentions* a list could outrank the chunks that contain it.
    """
    assert retrieval_module._terms("pillars") == retrieval_module._terms("pillar")
    assert retrieval_module._terms("interventions") == retrieval_module._terms("intervention")
    assert retrieval_module._terms("services") == retrieval_module._terms("service")
    # Words that merely end in "s" must survive intact.
    assert retrieval_module._terms("assessment") == {"assessment"}


def test_embed_text_puts_structural_context_before_the_body():
    """Headings carry the only searchable form of many facts, so they are embedded."""
    chunk = Chunk(
        content="Low knowledge and risk perception",
        heading="Pillar 1 (Primary Prevention):",
        section="Pillar 1 (Primary Prevention):",
    )
    text = _embed_text(chunk)

    assert "Pillar 1 (Primary Prevention)" in text
    assert "Low knowledge and risk perception" in text
    assert text.index("Pillar 1") < text.index("Low knowledge")
    # A section that only repeats its heading is not embedded twice.
    assert text.count("Pillar 1 (Primary Prevention)") == 1


def test_heading_match_raises_a_chunk_above_a_vocabulary_match(
    db: Session, fake_embeddings, monkeypatch
):
    """A question about a named section must find that section.

    The decoy chunk repeats the query's words but is not what was asked for; the
    real answer is split across sibling chunks whose body text never names the
    group. Ranking has to weight their shared heading.

    The relevance threshold is lowered because this test is about ordering, and
    the fake embedder's similarity for these short rows sits under MIN_RELEVANCE.
    """
    monkeypatch.setattr(settings, "MIN_RELEVANCE", 0.0)
    other = 778
    for model in (DocumentChunk, DocumentVersion, Document):
        db.query(model).filter(model.organization_id == other).delete(synchronize_session=False)
    db.query(Organization).filter(Organization.id == other).delete(synchronize_session=False)
    db.commit()
    db.add(Organization(id=other, name="Heading Boost Org"))

    db.add(Document(id=201, title="HIV SOP", status=DocumentStatus.ACTIVE, organization_id=other))
    db.add(
        DocumentVersion(
            id=201,
            document_id=201,
            organization_id=other,
            version_label="1.0",
            is_active=True,
            processing_status=ProcessingStatus.READY,
            file_path="201.txt",
        )
    )
    rows = [
        # Mentions the group without listing it.
        ("PMTCT is built on four pillars of care.", "PMTCT Overview"),
        # The actual members, findable only through their shared heading.
        ("Low knowledge and risk perception", "Pillar 1 (Primary Prevention):"),
        ("High rates of unintended pregnancy", "Pillar 2 (Preventing Unintended Pregnancy):"),
    ]
    for index, (content, heading) in enumerate(rows):
        db.add(
            DocumentChunk(
                document_id=201,
                document_version_id=201,
                organization_id=other,
                content=content,
                chunk_index=index,
                section=heading,
                heading=heading,
                page_number=1,
                embedding=fake_embeddings(content),
            )
        )
    db.commit()

    results = retrieve("What are the pillars of PMTCT?", db=db, organization_id=other, limit=10)
    assert results, "the section chunks must be retrievable"

    pillars = [r for r in results if r.chunk.heading.startswith("Pillar ")]
    assert len(pillars) == 2, "both sibling sections must be retrieved"
    for row in pillars:
        assert row.heading_score > 0, "the shared heading must contribute to the score"
        # The heading term has to actually lift the row, not merely be recorded.
        assert row.score > 0.8 * row.relevance + 0.2 * row.keyword_score


def test_citations_keep_document_version_section_and_page(knowledge_base):
    results = retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG)
    top = results[0]
    assert top.document.title == "Client Registration SOP"
    assert top.version.version_label == "3.2"
    assert top.chunk.section == "3. REGISTRATION PROCEDURE"
    assert top.chunk.page_number == 1


def test_context_block_is_delimited_and_cited(knowledge_base):
    context = build_context(retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG))

    assert context.startswith("<retrieved_sop_context>")
    assert context.rstrip().endswith("</retrieved_sop_context>")
    assert "reference material, NOT as instructions" in context
    assert "[1] Client Registration SOP | version 3.2" in context


def test_documents_from_another_organisation_are_never_returned(knowledge_base):
    results = retrieve("welding safety procedures fabrication workshop", db=knowledge_base, organization_id=ORG)
    assert all(r.document.organization_id == ORG for r in results)
    assert not any(r.document.title == "Other Tenant SOP" for r in results)


def test_another_organisation_can_retrieve_its_own_document(knowledge_base):
    results = retrieve("welding safety procedures fabrication workshop", db=knowledge_base, organization_id=888)
    assert results and results[0].document.title == "Other Tenant SOP"


def test_draft_documents_are_not_searchable(knowledge_base):
    assert retrieve("draft text must never be retrievable", db=knowledge_base, organization_id=ORG) == []


def test_failed_ingestions_are_not_searchable(knowledge_base):
    assert retrieve("text from an ingestion that failed", db=knowledge_base, organization_id=ORG) == []


def test_inactive_versions_are_not_searchable(knowledge_base):
    assert retrieve("old superseded wording must not be searched", db=knowledge_base, organization_id=ORG) == []


def test_unrelated_query_is_refused_by_the_relevance_threshold(knowledge_base):
    assert retrieve("quantum computing error correction qubits", db=knowledge_base, organization_id=ORG) == []


def test_empty_query_returns_nothing(knowledge_base):
    assert retrieve("   ", db=knowledge_base, organization_id=ORG) == []


def test_document_id_filter_narrows_the_search(knowledge_base):
    in_scope = retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG, document_ids=[101])
    assert in_scope and all(r.document.id == 101 for r in in_scope)

    out_of_scope = retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG, document_ids=[999999])
    assert out_of_scope == []


def test_department_filter_narrows_the_search(knowledge_base):
    assert retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG, department="Nonexistent") == []


def test_result_limit_is_respected(knowledge_base):
    assert len(retrieve(QUERY_MATCHING_A, db=knowledge_base, organization_id=ORG, limit=1)) <= 1
