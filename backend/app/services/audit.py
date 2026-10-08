"""Audit + AI provider logging helpers."""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.models.audit import AIProviderLog, AuditLog
from app.models.user import User


def log_audit(
    db: Session,
    action: str,
    user: User | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    row = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(row)
    db.commit()


@contextmanager
def log_ai_call(
    db: Session,
    provider: str,
    operation: str,
    model: str | None = None,
    mode: str | None = None,
    user_id: int | None = None,
) -> Iterator[dict]:
    """Time an AI provider call and persist a success/failure record."""
    started = time.perf_counter()
    outcome: dict = {"success": True, "error": None}
    try:
        yield outcome
    except Exception as exc:  # noqa: BLE001 - log then re-raise
        outcome["success"] = False
        outcome["error"] = str(exc)[:1000]
        raise
    finally:
        latency = int((time.perf_counter() - started) * 1000)
        if db is None:
            return
        try:
            db.add(
                AIProviderLog(
                    provider=provider,
                    model=model,
                    operation=operation,
                    mode=mode,
                    user_id=user_id,
                    latency_ms=latency,
                    success=outcome["success"],
                    error=outcome["error"],
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001 - logging must never break a request
            db.rollback()
