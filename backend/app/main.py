from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s (env=%s, provider=%s, embedding_dim=%s)",
        settings.PROJECT_NAME,
        settings.ENVIRONMENT,
        settings.AI_PROVIDER,
        settings.EMBEDDING_DIM,
    )
    if not settings.is_production:
        logger.warning(
            "ENVIRONMENT=%s: production safety checks are disabled. Set "
            "ENVIRONMENT=production on a public deployment.",
            settings.ENVIRONMENT,
        )
    yield
    logger.info("SOPIA API shutting down")


_docs_enabled = settings.api_docs_enabled

app = FastAPI(
    title="SOPIA API",
    description="Standard Operating Procedure Intelligent Assistant API",
    version="0.2.0",
    lifespan=lifespan,
    # Interactive docs and the schema are hidden in production by default, so the
    # API surface is not advertised to anonymous visitors.
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Reject requests whose Host header is not one we serve, which blocks
# host-header poisoning and cache-poisoning attempts.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def read_root():
    payload = {"message": "Welcome to the SOPIA API", "api": settings.API_V1_PREFIX}
    if settings.api_docs_enabled:
        payload["docs"] = "/docs"
    return payload


@app.get("/health")
def health():
    """Liveness probe: the process is up. Deliberately dependency-free so a slow
    database or model never causes the platform to kill a healthy process."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness probe: the API can actually serve requests."""
    from sqlalchemy import text

    from app.db.session import SessionLocal

    db_ok = True
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - readiness must never raise
        logger.error("Readiness check failed: %s", exc)
        db_ok = False

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": "ready" if db_ok else "unavailable", "database": db_ok},
    )


