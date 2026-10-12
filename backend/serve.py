"""Production launcher for the SOPIA API.

Runs pending database migrations, then starts Uvicorn bound to all interfaces
with no auto-reload. Use this on a server instead of ``run.py``, which is the
development launcher (reload enabled, bound to 127.0.0.1).

    python serve.py                      # migrations + API on 0.0.0.0:8000
    python serve.py --workers 2          # more request parallelism
    python serve.py --skip-migrations    # when migrations run in a separate step

Migrations run once, before any worker starts, so the schema is never migrated
concurrently by several workers.
"""

import argparse
import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)


def run_migrations() -> None:
    print("Running database migrations (alembic upgrade head)...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Database migration failed. Fix the migration error before starting the API."
        )
    print("Migrations up to date.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SOPIA API in production")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default all interfaces)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help=(
            "Uvicorn worker processes. AI calls are I/O-bound (waiting on Ollama), "
            "so a couple of workers is usually plenty and keeps database "
            "connections low. Note the rate limiter is per worker."
        ),
    )
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Do not run alembic (use when migrations are a separate deploy step)",
    )
    parser.add_argument(
        "--trusted-proxy",
        default="127.0.0.1",
        help=(
            "Comma-separated proxies whose X-Forwarded-For is trusted for the "
            "client IP. Required for per-client rate limiting behind nginx."
        ),
    )
    args = parser.parse_args()

    from app.core.config import settings

    if settings.is_production:
        print(f"ENVIRONMENT=production | provider={settings.AI_PROVIDER}", flush=True)
    else:
        print(
            f"WARNING: ENVIRONMENT={settings.ENVIRONMENT}. Production safety checks "
            "are disabled; set ENVIRONMENT=production on a public server.",
            flush=True,
        )

    if not args.skip_migrations:
        run_migrations()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=False,
        log_level=args.log_level,
        # Honour X-Forwarded-For / X-Forwarded-Proto from the reverse proxy, so
        # request.client.host is the real visitor rather than the proxy. Without
        # this, every client shares one rate-limit bucket.
        proxy_headers=True,
        forwarded_allow_ips=args.trusted_proxy,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
