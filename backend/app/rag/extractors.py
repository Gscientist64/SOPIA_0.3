"""Text extraction that preserves structure.

Returns structured :class:`~app.rag.chunking.Block` objects (with page numbers
and detected headings) rather than a flat string, so downstream chunking can
keep section context.
"""

import logging
import re

from app.rag.chunking import Block, is_heading

logger = logging.getLogger(__name__)

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def extract_blocks(file_path: str, extension: str | None = None) -> tuple[list[Block], int]:
    """Return ``(blocks, page_count)`` for the given file."""
    ext = (extension or file_path.rsplit(".", 1)[-1]).lower()
    if ext == "pdf":
        return _extract_pdf(file_path)
    if ext == "docx":
        return _extract_docx(file_path)
    if ext in {"txt", "md", "markdown"}:
        return _extract_text_file(file_path, ext)
    raise ValueError(f"Unsupported file extension: {ext}")


def _paragraphs_from_lines(lines: list[str], page_number: int | None) -> list[Block]:
    """Turn raw lines into heading/paragraph blocks."""
    blocks: list[Block] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            text = " ".join(buffer).strip()
            if text:
                blocks.append(Block(text=text, page_number=page_number))
            buffer.clear()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if is_heading(stripped):
            flush()
            blocks.append(
                Block(text=stripped, page_number=page_number, is_heading=True, level=1)
            )
        else:
            buffer.append(stripped)
    flush()
    return blocks


def _extract_pdf(file_path: str) -> tuple[list[Block], int]:
    import pdfplumber

    blocks: list[Block] = []
    page_count = 0
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for index, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001 - keep going on a bad page
                logger.warning("Failed to extract text from page %s: %s", index, exc)
                continue
            blocks.extend(_paragraphs_from_lines(text.splitlines(), index))
    return blocks, page_count


def _extract_docx(file_path: str) -> tuple[list[Block], int]:
    import docx

    document = docx.Document(file_path)
    blocks: list[Block] = []
    for para in document.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        style = (para.style.name or "") if para.style else ""
        if style.lower().startswith("heading") or style.lower() == "title":
            blocks.append(Block(text=text, is_heading=True, level=1))
        else:
            blocks.append(Block(text=text))
    return blocks, 1


def _extract_text_file(file_path: str, ext: str) -> tuple[list[Block], int]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.read().splitlines()

    if ext in {"md", "markdown"}:
        blocks: list[Block] = []
        buffer: list[str] = []

        def flush() -> None:
            if buffer:
                text = " ".join(buffer).strip()
                if text:
                    blocks.append(Block(text=text))
                buffer.clear()

        for line in lines:
            match = _MD_HEADING.match(line.strip())
            if match:
                flush()
                blocks.append(Block(text=match.group(2).strip(), is_heading=True, level=len(match.group(1))))
            else:
                buffer.append(line.strip())
        flush()
        return blocks, 1

    return _paragraphs_from_lines(lines, None), 1
