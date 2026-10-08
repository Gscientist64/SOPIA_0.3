from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents: [core, app, backend, <project root>]
BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    PROJECT_NAME: str = "SOPIA"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # --- Database ---
    DATABASE_URL: str = "postgresql://sopia:sopiapass@localhost:5432/sopia"

    # --- Security ---
    SECRET_KEY: str = "change-me-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 25
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt,md"

    # --- Chunking ---
    CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 200

    # --- AI provider ---
    AI_PROVIDER: str = "local"

    # Local LLM (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_EMBED_MODEL: str = "mxbai-embed-large"
    # How long Ollama keeps a model resident in RAM after a request. A short
    # value frees memory (less system lag) at the cost of reloading next time.
    OLLAMA_KEEP_ALIVE: str = "2m"
    # Threads Ollama may use for CPU inference. 0 = let Ollama decide (all
    # physical cores). Lower it (e.g. 2) to keep the machine responsive.
    OLLAMA_NUM_THREAD: int = 0

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBED_MODEL: str = "text-embedding-004"

    # Embedding vector dimension. MUST match the active embedding model output.
    # mxbai-embed-large => 1024, text-embedding-004 => 768.
    EMBEDDING_DIM: int = 1024

    # --- Retrieval ---
    TOP_K: int = 5
    MIN_RELEVANCE: float = 0.55

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_extension_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()}


settings = Settings()


