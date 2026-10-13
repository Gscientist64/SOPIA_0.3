"""Ingest local SOP files straight into the knowledge base.

The browser upload runs ingestion inside the HTTP request, which times out long
before a CPU-only machine finishes embedding a large document. This script does
the same work offline: it copies each file into the upload store, creates the
document and its first active version, then ingests it.

Usage:
    python scripts/ingest_path.py --path ../sops --organization-id 1
    python scripts/ingest_path.py --path ../sops/PMTCT.txt --organization-id 1
    python scripts/ingest_path.py --path ../sops --organization-id 1 --dry-run
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

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.document import (  # noqa: E402
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    ProcessingStatus,
)
from app.models.user import RoleEnum, User  # noqa: E402
from app.rag.ingestion import ingest_document_version  # noqa: E402
from app.services.storage import _upload_root, validate_extension  # noqa: E402

POLL_SECONDS = 30


def _collect(path: Path) -> list[Path]:
    """Return the ingestable files under ``path``, sorted for a stable order."""
    if path.is_file():
        candidates = [path]
    else:
        candidates = sorted(p for p in path.rglob("*") if p.is_file())
    allowed = settings.allowed_extension_set
    return [p for p in candidates if p.suffix.lstrip(".").lower() in allowed]


def _pick_uploader(db, organization_id: int) -> User:
    """An admin in this organisation to attribute the upload to."""
    user = (
        db.query(User)
        .filter(
            User.organization_id == organization_id,
            User.role.in_([RoleEnum.SUPER_ADMIN, RoleEnum.CONTENT_ADMIN]),
        )
        .order_by(User.id)
        .first()
    )
    if user is None:
        raise SystemExit(
            f"No admin user exists in organisation {organization_id}; "
            "documents must have an uploader."
        )
    return user


def _find_existing(db, organization_id: int, original_filename: str) -> Document | None:
    """Skip files already ingested, so the script is safe to re-run."""
    return (
        db.query(Document)
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .filter(
            Document.organization_id == organization_id,
            DocumentVersion.original_filename == original_filename,
        )
        .first()
    )


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
            print(f"        [{(time.perf_counter() - started) / 60:5.1f} min] chunks={stored}", flush=True)

    threading.Thread(target=watch, daemon=True).start()
    return stop


def _ingest_file(db, uploader: User, source: Path) -> bool:
    ext = validate_extension(source.name)
    target_dir = _upload_root() / "documents"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}.{ext}"
    shutil.copyfile(source, target)
    size = target.stat().st_size

    document = Document(
        title=source.stem.replace("_", " "),
        description=f"Ingested from {source.name}",
        doc_type=ext,
        status=DocumentStatus.PROCESSING,
        organization_id=uploader.organization_id,
        uploaded_by_id=uploader.id,
    )
    db.add(document)
    db.flush()

    version = DocumentVersion(
        document_id=document.id,
        organization_id=uploader.organization_id,
        version_label="1.0",
        is_active=True,
        processing_status=ProcessingStatus.PENDING,
        file_path=str(target),
        original_filename=source.name,
        file_size=size,
        created_by_id=uploader.id,
    )
    db.add(version)
    db.flush()

    document.active_version_id = version.id
    db.commit()

    print(f"  document {document.id}: {document.title} ({size / 1024:.0f} KB)")
    stop = _monitor(version.id, POLL_SECONDS)
    started = time.perf_counter()
    try:
        ingest_document_version(db, version)
    finally:
        stop.set()

    db.refresh(version)
    db.refresh(document)
    elapsed = time.perf_counter() - started
    print(
        f"    -> {version.processing_status} in {elapsed / 60:.1f} min, "
        f"chunks={version.chunk_count}, pages={version.page_count}, doc_status={document.status}"
    )
    if version.processing_error:
        print(f"    processing_error: {version.processing_error}")
    return version.processing_status == ProcessingStatus.READY


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest local SOP files")
    parser.add_argument("--path", required=True, help="A file or a folder to ingest")
    parser.add_argument("--organization-id", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="Re-ingest files already present")
    parser.add_argument("--dry-run", action="store_true", help="List the files only")
    args = parser.parse_args()

    source = Path(args.path).resolve()
    if not source.exists():
        print(f"Path not found: {source}", file=sys.stderr)
        return 1

    files = _collect(source)
    if not files:
        print(f"No supported files found under {source}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Would ingest {len(files)} file(s) into organisation {args.organization_id}:")
        for path in files:
            print(f"  {path.name} ({path.stat().st_size / 1024:.0f} KB)")
        return 0

    db = SessionLocal()
    failures = 0
    try:
        uploader = _pick_uploader(db, args.organization_id)
        print(f"Uploader: {uploader.email} (organisation {uploader.organization_id})")
        print(f"Ingesting {len(files)} file(s) from {source}\n")

        for path in files:
            existing = None if args.force else _find_existing(db, args.organization_id, path.name)
            if existing is not None:
                print(f"  skipping {path.name}: already ingested as document {existing.id}")
                continue
            try:
                if not _ingest_file(db, uploader, path):
                    failures += 1
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the batch
                db.rollback()
                failures += 1
                print(f"    FAILED {path.name}: {exc}", file=sys.stderr)
            print()
        return 1 if failures else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
