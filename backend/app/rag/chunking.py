"""Section-aware chunking.

Rather than blindly slicing every N characters, documents are reduced to a
sequence of :class:`Block` objects (paragraphs, headings, list items) that
carry page/section context. :func:`chunk_blocks` then groups those blocks into
retrieval-sized chunks that respect section boundaries and overlap slightly so
procedural steps are not split in a way that loses meaning.
"""

import re
from dataclasses import dataclass, field

from app.core.config import settings

# --- heading heuristics -------------------------------------------------------
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(\S.*)$")
_ALLCAPS_HEADING = re.compile(r"^[A-Z0-9][A-Z0-9 \-&/,'()]{3,79}$")
_ENDING_COLON = re.compile(r"^[A-Z][^.!?]{2,78}:$")

# Sentence / line boundaries used when a single block must be broken up.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?:;])\s+|\n+")


def _split_oversized(text: str, chunk_size: int) -> list[str]:
    """Break a block longer than ``chunk_size`` into embeddable pieces.

    Extraction can yield one "paragraph" holding an entire PDF page (a page with
    no blank lines), which would otherwise become a single chunk far larger than
    the embedding model's context window and fail the whole ingestion. Such text
    is split on sentence boundaries, falling back to a hard cut for runs that
    have no boundary at all (e.g. a table row).
    """
    if len(text) <= chunk_size:
        return [text]

    pieces: list[str] = []
    current = ""
    for part in _SENTENCE_BOUNDARY.split(text):
        part = part.strip()
        if not part:
            continue
        if len(part) > chunk_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(
                part[start : start + chunk_size]
                for start in range(0, len(part), chunk_size)
            )
            continue
        if current and len(current) + len(part) + 1 > chunk_size:
            pieces.append(current)
            current = part
        else:
            current = f"{current} {part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def is_heading(line: str) -> bool:
    text = line.strip()
    if not text or len(text) > 90:
        return False
    if _MD_HEADING.match(text):
        return True
    if _ALLCAPS_HEADING.match(text) and any(c.isalpha() for c in text):
        return True
    if _ENDING_COLON.match(text):
        return True
    if _NUMBERED_HEADING.match(text) and not text.endswith("."):
        return True
    return False


@dataclass
class Block:
    """A logical unit of text produced by extraction."""

    text: str
    page_number: int | None = None
    heading: str | None = None
    section: str | None = None
    level: int = 0  # heading depth; 0 == body text
    is_heading: bool = False


@dataclass
class Chunk:
    content: str
    section: str | None = None
    heading: str | None = None
    page_number: int | None = None
    chunk_index: int = 0


@dataclass
class _SectionState:
    section: str | None = None
    heading: str | None = None


def _flush(buffer: list[str], meta: dict, chunks: list[Chunk]) -> None:
    text = "\n".join(buffer).strip()
    if text:
        chunks.append(
            Chunk(
                content=text,
                section=meta.get("section"),
                heading=meta.get("heading"),
                page_number=meta.get("page_number"),
                chunk_index=len(chunks),
            )
        )


def chunk_blocks(
    blocks: list[Block],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Group blocks into overlapping, section-aware chunks."""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.CHUNK_OVERLAP
    overlap = max(0, min(overlap, chunk_size // 2))
    # Leave room for the carried-over overlap so a finished chunk never exceeds
    # chunk_size, which would push it past the embedding model's context window.
    piece_budget = max(1, chunk_size - overlap)

    chunks: list[Chunk] = []
    buffer: list[str] = []
    size = 0
    state = _SectionState()
    meta: dict = {"section": None, "heading": None, "page_number": None}

    def reset(with_overlap: bool = True) -> None:
        nonlocal buffer, size
        tail = ""
        if with_overlap and overlap and buffer:
            joined = "\n".join(buffer)
            tail = joined[-overlap:]
            if " " in tail:
                tail = tail.split(" ", 1)[-1]
        _flush(buffer, meta, chunks)
        buffer = [tail] if tail else []
        size = len(tail)

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        if block.is_heading:
            # A new section always starts a new chunk.
            if buffer:
                reset(with_overlap=False)
            state.heading = text
            state.section = text
            meta = {"section": state.section, "heading": state.heading, "page_number": block.page_number}
            continue

        # A single extracted block can be larger than a whole chunk (a page with
        # no blank lines); break it up so no chunk exceeds the embedding window.
        for piece in _split_oversized(text, piece_budget):
            if not buffer:
                meta = {
                    "section": block.section or state.section,
                    "heading": block.heading or state.heading,
                    "page_number": block.page_number,
                }

            if size + len(piece) > chunk_size and buffer:
                reset(with_overlap=True)
                meta = {
                    "section": block.section or state.section,
                    "heading": block.heading or state.heading,
                    "page_number": block.page_number,
                }

            buffer.append(piece)
            size += len(piece) + 1

    if buffer:
        _flush(buffer, meta, chunks)

    return chunks
