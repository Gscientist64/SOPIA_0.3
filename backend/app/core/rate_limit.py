"""A minimal in-memory fixed-window rate limiter.

Good enough for a single-process MVP. Swap for Redis if SOPIA is scaled out.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_HITS: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(max_requests: int, window_seconds: int = 60):
    """Return a FastAPI dependency enforcing ``max_requests`` per window."""

    def _dependency(request: Request) -> None:
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
