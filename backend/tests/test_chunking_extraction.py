"""Extraction and section-aware chunking tests."""

from app.rag.chunking import Block, chunk_blocks
from app.rag.extractors import extract_blocks


def test_heading_detection_and_sections():
    blocks = [
        Block(text="CLIENT REGISTRATION SOP", is_heading=True),
        Block(text="Every new client must present identification."),
        Block(text="3. REGISTRATION PROCEDURE", is_heading=True),
        Block(text="Capture full name and date of birth."),
        Block(text="Record consent in the client file."),
    ]
    chunks = chunk_blocks(blocks, chunk_size=1000, overlap=0)

    # A heading opens a chunk rather than becoming one of its own, so the body
    # text under the first heading and the second section form two chunks.
    assert len(chunks) == 2
    assert chunks[0].heading == "CLIENT REGISTRATION SOP"
    assert "Every new client must present identification." in chunks[0].content
    assert chunks[1].section == "3. REGISTRATION PROCEDURE"
    assert "Capture full name" in chunks[1].content
    assert "Record consent" in chunks[1].content


def test_chunks_do_not_cross_section_boundaries():
    blocks = [
        Block(text="1. PURPOSE", is_heading=True),
        Block(text="Describe the procedure."),
        Block(text="2. SCOPE", is_heading=True),
        Block(text="Applies to all staff."),
    ]
    chunks = chunk_blocks(blocks, chunk_size=1000, overlap=0)
    assert len(chunks) == 2
    assert "Applies to all staff." not in chunks[0].content


def test_chunk_size_is_respected():
    blocks = [Block(text="Sentence number %d about procedures." % i) for i in range(60)]
    chunks = chunk_blocks(blocks, chunk_size=200, overlap=0)
    assert len(chunks) > 1
    # Allow a little slack for the final block appended after the threshold check.
    assert all(len(c.content) <= 260 for c in chunks)


def test_overlap_carries_context_forward():
    blocks = [Block(text=f"Paragraph {i} with some meaningful procedural content.") for i in range(30)]
    chunks = chunk_blocks(blocks, chunk_size=200, overlap=60)
    assert len(chunks) > 1
    first_tail = chunks[0].content[-40:].strip()
    assert first_tail[:15] in chunks[1].content


def test_chunk_indexes_are_sequential():
    blocks = [Block(text=f"Item {i}") for i in range(10)]
    chunks = chunk_blocks(blocks, chunk_size=40, overlap=0)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_empty_blocks_produce_no_chunks():
    assert chunk_blocks([Block(text="   "), Block(text="")], chunk_size=100, overlap=0) == []


def test_page_numbers_are_preserved():
    blocks = [
        Block(text="1. PROCEDURE", page_number=1, is_heading=True),
        Block(text="First step.", page_number=1),
        Block(text="Second step.", page_number=2),
    ]
    chunks = chunk_blocks(blocks, chunk_size=1000, overlap=0)
    # Small content stays in one chunk, which records the page it started on.
    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert all(c.page_number is not None for c in chunks)


def test_page_number_recorded_when_chunk_starts_on_a_new_page():
    blocks = [
        Block(text="x" * 150, page_number=1),
        Block(text="y" * 150, page_number=2),
    ]
    chunks = chunk_blocks(blocks, chunk_size=200, overlap=0)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2


def test_oversized_block_is_split_into_embeddable_chunks():
    # A PDF page with no blank lines is extracted as one enormous "paragraph".
    # It must be broken up, otherwise the embedding call exceeds the model's
    # context window and the entire document fails to ingest.
    page = " ".join(f"Sentence {i} describing the procedure in some detail." for i in range(200))
    assert len(page) > 4000

    chunks = chunk_blocks([Block(text=page, page_number=7)], chunk_size=1200, overlap=0)

    assert len(chunks) > 1
    assert all(len(c.content) <= 1200 for c in chunks)
    # No content is lost and the page number is carried onto every piece.
    assert all(c.page_number == 7 for c in chunks)
    joined = " ".join(c.content for c in chunks)
    for i in range(200):
        assert f"Sentence {i} " in joined


def test_oversized_unbroken_run_is_hard_split():
    # e.g. a table rendered as one long run with no sentence boundaries.
    chunks = chunk_blocks([Block(text="A" * 5000)], chunk_size=1000, overlap=0)
    assert len(chunks) >= 5
    assert all(len(c.content) <= 1000 for c in chunks)
    assert sum(len(c.content) for c in chunks) == 5000


# ------------------------------------------------------------------- extraction
def test_extract_markdown_headings(tmp_path):
    path = tmp_path / "sop.md"
    path.write_text("# Registration\n\nShow your ID.\n\n## Step 2\n\nCapture details.\n", encoding="utf-8")

    blocks, pages = extract_blocks(str(path))
    assert pages == 1
    assert any(b.is_heading and b.text == "Registration" for b in blocks)
    assert any(b.is_heading and b.text == "Step 2" for b in blocks)
    assert any("Show your ID." in b.text for b in blocks)


def test_extract_txt_detects_numbered_headings(tmp_path):
    path = tmp_path / "sop.txt"
    path.write_text(
        "CLIENT REGISTRATION SOP\n\nEvery client must present ID.\n\n4. MISSED APPOINTMENTS\n\nCall within two days.\n",
        encoding="utf-8",
    )
    blocks, _ = extract_blocks(str(path))
    headings = [b.text for b in blocks if b.is_heading]
    assert "CLIENT REGISTRATION SOP" in headings
    assert "4. MISSED APPOINTMENTS" in headings


def test_extract_unsupported_extension_raises(tmp_path):
    path = tmp_path / "file.xyz"
    path.write_text("data", encoding="utf-8")
    try:
        extract_blocks(str(path))
    except ValueError:
        return
    raise AssertionError("Expected ValueError for unsupported extension")
