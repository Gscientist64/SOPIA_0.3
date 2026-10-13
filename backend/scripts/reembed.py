"""Re-embed existing documents in place, without breaking citation history.

Embedding text changed (headings are now embedded alongside the body), so
documents ingested before that change have to be embedded again for the
improvement to apply. Re-ingesting a version destroys the chunks that already
answered questions, and every one of those answers keeps a foreign key to the
chunk it quoted, so a destructive re-ingest either fails or orphans history.

This script therefore adds a **new version** of each document and activates it.
The old version stays intact, its chunks keep serving the citations that point at
them, and retrieval moves to the freshly embedded version.

Usage:
    python scripts/reembed.py --documents 9 10 11
    python scripts/reembed.py --documents 9 10 11 --dry-run
"""

import argparse
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from sqlalchemy import func  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.document import (  # noqa: E402
    Document,
    DocumentChunk,
    DocumentVersion,
    ProcessingStatus,
)
from app.rag.ingestion import ingest_document_version  # noqa: E402
from app.services.documents import set_active_version  # noqa: E402

POLL_SECONDS = 120


def _next_label(current: str | None) -> str:
    """Bump "1.0" to "1.1" so the new version is distinguishable in the UI."""
    try:
        major, _, minor = (current or "1.0").partition(".")
        return f"{int(major)}.{int(minor or 0) + 1}"
    except ValueError:
        return f"{current or '1.0'}-reembed"


def _monitor(version_id: int, interval: int) -> threading.Event:
    stop = threading.Event()

    def watch() -> None:
        started = time.perf_counter()
        while not stop.wait(interval):
            db = SessionLocal()
            try:
                stored = (
                    db.query(func.count(DocumentChunk.id))
                    .filter(DocumentChunk.document_version_id == version_id)
                    .scalar()
                    or 0
                )
            finally:
                db.close()
            print(
                f"        [{(time.perf_counter() - started) / 60:5.1f} min] chunks={stored}",
                flush=True,
            )

    threading.Thread(target=watch, daemon=True).start()
    return stop


def _reembed(db, document: Document) -> bool:
    current = (
        db.query(DocumentVersion).filter(DocumentVersion.id == document.active_version_id).first()
    )
    if current is None:
        print(f"  document {document.id}: no active version, skipping", file=sys.stderr)
        return False
    if not current.file_path or not Path(current.file_path).exists():
        print(f"  document {document.id}: source file missing, skipping", file=sys.stderr)
        return False

    # Copy rather than reference the old path, so removing an old version later
    # can never pull the file out from under the new one.
    source = Path(current.file_path)
    target = source.with_name(f"{uuid.uuid4().hex}{source.suffix}")
    shutil.copyfile(source, target)

    label = _next_label(current.version_label)
    version = DocumentVersion(
        document_id=document.id,
        organization_id=document.organization_id,
        version_label=label,
        is_active=False,
        processing_status=ProcessingStatus.PENDING,
        file_path=str(target),
        original_filename=current.original_filename,
        file_size=target.stat().st_size,
        created_by_id=current.created_by_id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    print(f"  document {document.id}: {document.title}")
    print(f"    new version {version.id} ({label}); current active version is {current.id}")
    stop = _monitor(version.id, POLL_SECONDS)
    started = time.perf_counter()
    try:
        ingest_document_version(db, version)
    finally:
        stop.set()

    db.refresh(version)
    elapsed = time.perf_counter() - started
    if version.processing_status != ProcessingStatus.READY:
        print(
            f"    FAILED after {elapsed / 60:.1f} min: {version.processing_error}",
            file=sys.stderr,
        )
        print("    the previous version is still active; nothing was lost", file=sys.stderr)
        return False

    set_active_version(db, document, version)
    print(
        f"    ready in {elapsed / 60:.1f} min: chunks={version.chunk_count} "
        f"(previous version {current.id} kept for citation history)"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-embed documents via a new version")
    parser.add_argument("--documents", type=int, nargs="+", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    failures = 0
    try:
        for document_id in args.documents:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document is None:
                print(f"document {document_id} not found", file=sys.stderr)
                failures += 1
                continue
            if args.dry_run:
                current = db.query(DocumentVersion).filter(
                    DocumentVersion.id == document.active_version_id
                ).first()
                print(
                    f"  would re-embed document {document_id} ({document.title}) "
                    f"from version {current.id if current else '-'}"
                )
                continue
            try:
                if not _reembed(db, document):
                    failures += 1
            except Exception as exc:  # noqa: BLE001 - one bad document must not stop the batch
                db.rollback()
                failures += 1
                print(f"  document {document_id} FAILED: {exc}", file=sys.stderr)
        return 1 if failures else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
