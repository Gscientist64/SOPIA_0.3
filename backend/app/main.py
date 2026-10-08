from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
    yield
    logger.info("SOPIA API shutting down")


app = FastAPI(
    title="SOPIA API",
    description="Standard Operating Procedure Intelligent Assistant API",
    version="0.2.0",
    lifespan=lifespan,
)

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
    return {"message": "Welcome to the SOPIA API", "docs": "/docs", "api": settings.API_V1_PREFIX}


@app.get("/health")
def health():
    return {"status": "ok"}


