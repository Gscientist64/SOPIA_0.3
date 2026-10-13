"""Build the pre-seeded SQLite database shipped with the offline demo.

Embedding a document is CPU-bound, so doing it on first run would leave the user
staring at a spinner. This script performs the ingestion at build time and ships
a database that is already populated and queryable, so the demo works the moment
it is started.

Run it on a machine with Ollama available:

    python scripts/build_demo_db.py --output dist-offline/data/sopia-demo.db

It is idempotent: an existing database is rebuilt from scratch each run.
"""

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

DEMO_SOPS_DIR = Path(BACKEND_DIR).parent / "demo" / "sops"

DEMO_ORG_NAME = "Demo Organisation"
DEMO_ADMIN_EMAIL = "demo@sopia.local"
# Deliberately free of shell metacharacters: this password is echoed by a batch
# launcher, where characters such as ! are consumed by delayed expansion and the
# displayed value would silently differ from the real one.
DEMO_ADMIN_PASSWORD = "Sopia-Demo-2025"
DEMO_ADMIN_NAME = "SOPIA Demo Admin"

# Documents are described here rather than inferred from the filename so the
# metadata (department, type) is meaningful in the UI.
DEMO_DOCUMENTS = [
    ("01_client_registration_sop.txt", "Client Registration SOP", "Clinical Services", "Clinical"),
    ("02_data_quality_reporting_sop.txt", "Data Quality and Monthly Reporting SOP", "Monitoring and Evaluation", "Procedure"),
    ("03_incident_reporting_sop.txt", "Incident Reporting and Escalation SOP", "Operations", "Procedure"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the offline demo database")
    parser.add_argument("--output", required=True, help="Path of the SQLite file to create")
    parser.add_argument(
        "--url",
        default=None,
        help="Override the database URL (defaults to the --output SQLite path)",
    )
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
        print(f"Removed existing {output.name}")

    # The application must be pointed at this database *before* app modules import.
    database_url = args.url or f"sqlite:///{output.as_posix()}"
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("UPLOAD_DIR", str(output.parent / "uploads"))
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401 - register every model
    from app.core.security import get_password_hash
    from app.db.base import Base
    from app.models.document import Document, DocumentStatus, DocumentVersion, ProcessingStatus
    from app.models.user import Organization, RoleEnum, User
    from app.rag.ingestion import ingest_document_version

    print(f"Database : {database_url}")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    org = Organization(name=DEMO_ORG_NAME)
    db.add(org)
    db.commit()
    db.refresh(org)

    admin = User(
        email=DEMO_ADMIN_EMAIL,
        hashed_password=get_password_hash(DEMO_ADMIN_PASSWORD),
        full_name=DEMO_ADMIN_NAME,
        role=RoleEnum.SUPER_ADMIN.value,
        organization_id=org.id,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print(f"Organisation {org.id} and admin {DEMO_ADMIN_EMAIL} created")

    for index, (filename, title, department, doc_type) in enumerate(DEMO_DOCUMENTS, start=1):
        source = DEMO_SOPS_DIR / filename
        if not source.is_file():
            print(f"  MISSING: {source}", file=sys.stderr)
            return 1

        document = Document(
            title=title,
            description=f"Demonstration SOP ({filename}).",
            category="Demo",
            department=department,
            doc_type=doc_type,
            status=DocumentStatus.PROCESSING,
            organization_id=org.id,
            uploaded_by_id=admin.id,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        version = DocumentVersion(
            document_id=document.id,
            organization_id=org.id,
            version_label="1.0",
            is_active=True,
            processing_status=ProcessingStatus.PENDING,
            file_path=str(source),
            original_filename=filename,
            file_size=source.stat().st_size,
            created_by_id=admin.id,
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        document.active_version_id = version.id
        db.commit()

        print(f"  [{index}/{len(DEMO_DOCUMENTS)}] ingesting {title} ...", flush=True)
        ingest_document_version(db, version)
        db.refresh(version)
        db.refresh(document)
        print(
            f"      status={version.processing_status} "
            f"chunks={version.chunk_count} pages={version.page_count}"
        )
        if version.processing_status != ProcessingStatus.READY:
            print(f"      ERROR: {version.processing_error}", file=sys.stderr)
            return 1

    total = sum(
        db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id).count()
        for d in db.query(Document).all()
    )
    print(f"\nDemo database ready: {output}")
    print(f"  documents: {db.query(Document).count()}  versions: {total}")
    print(f"  sign in as {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
