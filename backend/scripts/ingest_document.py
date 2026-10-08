"""Ingest or re-ingest a document version from the command line.

Embedding a large PDF on CPU takes far longer than an HTTP request can wait, so
very large documents should be ingested with this script rather than through the
browser upload (which is synchronous).

Usage:
    python scripts/ingest_document.py --document-id 10
    python scripts/ingest_document.py --document-id 10 --version-id 10
    python scripts/ingest_document.py --list
"""

import argparse
import os
import sys
import threading
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from sqlalchemy import func  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.document import (  # noqa: E402
    Document,
    DocumentChunk,
    DocumentVersion,
)
from app.rag.ingestion import ingest_document_version  # noqa: E402

POLL_SECONDS = 60


def _list_documents(db) -> None:
    rows = (
        db.query(Document, DocumentVersion)
        .outerjoin(DocumentVersion, DocumentVersion.id == Document.active_version_id)
        .order_by(Document.id)
        .all()
    )
    print(f"{'doc':>4}  {'status':<11} {'ver':>4}  {'proc':<11} {'chunks':>7}  title")
    for document, version in rows:
        print(
            f"{document.id:>4}  {document.status:<11} "
            f"{(version.id if version else 0):>4}  "
            f"{(version.processing_status if version else '-'):<11} "
            f"{(version.chunk_count if version and version.chunk_count is not None else 0):>7}  "
            f"{document.title}"
        )


def _start_monitor(version_id: int, interval: int) -> threading.Event:
    """Print chunk progress in the background so a long run is not a black box."""
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
                status = (
                    db.query(DocumentVersion.processing_status)
                    .filter(DocumentVersion.id == version_id)
                    .scalar()
                )
            finally:
                db.close()
            minutes = (time.perf_counter() - started) / 60
            print(f"  [{minutes:5.1f} min] status={status} chunks_stored={stored}", flush=True)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return stop


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a SOPIA document version")
    parser.add_argument("--document-id", type=int)
    parser.add_argument("--version-id", type=int, help="Defaults to the active version")
    parser.add_argument("--list", action="store_true", help="List documents and versions")
    parser.add_argument(
        "--poll", type=int, default=POLL_SECONDS, help="Progress interval in seconds"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.list or args.document_id is None:
            _list_documents(db)
            return 0

        document = db.query(Document).filter(Document.id == args.document_id).first()
        if document is None:
            print(f"Document {args.document_id} not found", file=sys.stderr)
            return 1

        if args.version_id is not None:
            version = (
                db.query(DocumentVersion)
                .filter(
                    DocumentVersion.id == args.version_id,
                    DocumentVersion.document_id == document.id,
                )
                .first()
            )
        else:
            version = (
                db.query(DocumentVersion)
                .filter(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.is_active.is_(True),
                )
                .first()
            )
        if version is None:
            print("No matching version found", file=sys.stderr)
            return 1

        print(f"Document {document.id}: {document.title}")
        print(f"Version {version.id} ({version.version_label}) -> {version.file_path}")
        print("Ingesting; this can take many minutes for a large PDF...")

        stop = _start_monitor(version.id, args.poll)
        started = time.perf_counter()
        try:
            ingest_document_version(db, version)
        finally:
            stop.set()

        elapsed = time.perf_counter() - started
        db.refresh(version)
        print(
            f"\nFinished in {elapsed / 60:.1f} min: status={version.processing_status} "
            f"chunks={version.chunk_count} pages={version.page_count}"
        )
        if version.processing_error:
            print(f"processing_error: {version.processing_error}")
            return 1
        print(f"document status: {document.status}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
