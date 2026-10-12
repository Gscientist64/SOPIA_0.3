"""A minimal in-memory fixed-window rate limiter.

Good enough for a single-process MVP. Swap for Redis if SOPIA is scaled out:
the counter lives in this process, so running several workers multiplies the
effective limit by the number of workers.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

_HITS: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(max_requests: int, window_seconds: int = 60):
    """Return a FastAPI dependency enforcing ``max_requests`` per window.

    Disabled entirely when ``RATE_LIMIT_ENABLED`` is false, which the test suite
    sets because it issues many requests from a single address in seconds.
    """

    def _dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}:{max_requests}:{window_seconds}"
        now = time.monotonic()
        bucket = _HITS[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )
        bucket.append(now)

    return _dependency


# ------------------------------------------------------------------ named limits
# AI-backed endpoints cost real CPU time on a CPU-only deployment and are the
# ones worth throttling per client. Ordinary reads are left unlimited.
AUTH_LIMIT = rate_limit(20, 60)
REGISTER_LIMIT = rate_limit(10, 60)
CHAT_LIMIT = rate_limit(30, 60)
# Quiz, exam and interview generation emit long JSON documents, so they are far
# more expensive per call than a chat turn.
GENERATION_LIMIT = rate_limit(12, 60)
UPLOAD_LIMIT = rate_limit(10, 60)
REPROCESS_LIMIT = rate_limit(3, 60)
