"""Application configuration, including frozen (PyInstaller) path handling."""

import sys
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_dirs() -> tuple[Path, Path]:
    """Return ``(app_dir, bundle_dir)`` for source and frozen layouts.

    * ``app_dir`` — writable working directory: holds ``.env``, uploads and the
      demo database. Next to the executable when frozen, otherwise ``backend/``.
    * ``bundle_dir`` — read-only resources unpacked by PyInstaller (``_MEIPASS``),
      otherwise the same as ``app_dir``.

    ``__file__`` points inside the temporary extraction directory when frozen, so
    deriving paths from it would place uploads somewhere that vanishes on exit.
    """
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        return executable_dir, Path(getattr(sys, "_MEIPASS", executable_dir))
    backend_dir = Path(__file__).resolve().parents[2]
    return backend_dir, backend_dir


# backend/app/core/config.py -> parents: [core, app, backend, <project root>]
BASE_DIR, BUNDLE_DIR = _resolve_dirs()
PROJECT_ROOT = BASE_DIR.parent

# The sample values shipped in .env.example. Booting production with one of these
# would let anyone forge a JWT, so they are rejected outright.
INSECURE_SECRET_KEYS = {
    "",
    "change-me-in-env",
    "replace_with_a_long_random_secret",
}
MIN_PRODUCTION_SECRET_LENGTH = 32

_LOCALHOST_PREFIXES = ("http://localhost", "http://127.0.0.1", "http://[::1]")


def _is_localhost_origin(origin: str) -> bool:
    return origin.startswith(_LOCALHOST_PREFIXES)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    PROJECT_NAME: str = "SOPIA"
    API_V1_PREFIX: str = "/api/v1"
    # "production" activates the start-up safety checks below.
    ENVIRONMENT: str = "development"

    # --- Database ---
    DATABASE_URL: str = "postgresql://sopia:sopiapass@localhost:5432/sopia"

    # --- Security ---
    SECRET_KEY: str = "change-me-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Host names the API will answer for. "*" accepts any (fine behind a local
    # proxy); set the real domain(s) so Host-header attacks are rejected.
    ALLOWED_HOSTS: str = "*"
    # Interactive API docs. Left unset they follow the environment: available in
    # development, hidden in production unless explicitly re-enabled.
    ENABLE_API_DOCS: bool | None = None
    # Per-client rate limiting. Disabled in the test suite, which fires many
    # requests from one address in seconds.
    RATE_LIMIT_ENABLED: bool = True

    # --- Anonymous access ---
    # Organisation whose SOPs anonymous visitors may search. Anonymous use of
    # the assistant and interview practice is enabled only when this is set, so
    # a deployment cannot expose chat by accident. Guests are recorded as users
    # in this organisation, which means every organisation-scoped query already
    # limits them to these documents without any further filtering.
    PUBLIC_ORGANIZATION_ID: int | None = None

    # --- Uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 25
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt,md"

    # --- Frontend (optional) ---
    # Directory holding the built single-page app. When set, the API serves the
    # frontend itself, so the whole application is reachable on one URL and one
    # port. Used by the offline/demo build; in a normal server deployment nginx
    # serves the SPA instead. Auto-detects `frontend/dist` when left blank.
    FRONTEND_DIST: str = ""

    # --- Chunking ---
    CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 200

    # --- AI provider ---
    AI_PROVIDER: str = "local"

    # Local LLM (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # qwen2.5:1.5b is the recommended default: it fits a 16 GB laptop and was
    # verified against SOPIA's prompts. Step up to qwen2.5:3b or llama3 with more
    # RAM, then re-run scripts/check_model.py.
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
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
    # 8 measured better than 5 (a list split across sibling chunks lost items) and
    # better than 10 (extra chunks diluted a small model's attention on multi-part
    # answers). Retrieval is no longer the bottleneck for those questions.
    TOP_K: int = 8
    MIN_RELEVANCE: float = 0.55

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_extension_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()}

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}

    @property
    def anonymous_access_enabled(self) -> bool:
        """Anonymous use is opt-in: it needs a published organisation to scope to."""
        return self.PUBLIC_ORGANIZATION_ID is not None

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()] or ["*"]

    @property
    def api_docs_enabled(self) -> bool:
        if self.ENABLE_API_DOCS is not None:
            return self.ENABLE_API_DOCS
        return not self.is_production

    @property
    def frontend_dist(self) -> Path | None:
        """Resolved directory of the built SPA, or ``None`` when not present."""
        candidates: list[Path] = []
        if self.FRONTEND_DIST:
            configured = Path(self.FRONTEND_DIST)
            candidates.append(configured if configured.is_absolute() else BASE_DIR / configured)
        # Next to the executable (offline bundle), then the source tree.
        candidates.append(BASE_DIR / "frontend")
        candidates.append(PROJECT_ROOT / "frontend" / "dist")
        candidates.append(BUNDLE_DIR / "frontend")
        for candidate in candidates:
            if (candidate / "index.html").is_file():
                return candidate
        return None

    @model_validator(mode="after")
    def _refuse_unsafe_production(self) -> "Settings":
        """Fail fast rather than run production on development defaults.

        A missing .env would otherwise leave the JWT signing key at a value that
        is published in this repository, which lets anyone mint an admin token.
        """
        if not self.is_production:
            return self

        problems: list[str] = []
        if (
            self.SECRET_KEY in INSECURE_SECRET_KEYS
            or len(self.SECRET_KEY) < MIN_PRODUCTION_SECRET_LENGTH
        ):
            problems.append(
                "SECRET_KEY must be a long random value "
                '(python -c "import secrets; print(secrets.token_urlsafe(48))")'
            )
        if not self.cors_origin_list:
            problems.append("CORS_ORIGINS must list the deployed frontend origin(s)")
        elif all(_is_localhost_origin(origin) for origin in self.cors_origin_list):
            problems.append(
                "CORS_ORIGINS still only allows localhost, so the deployed frontend "
                "could not call this API"
            )
        if self.allowed_host_list == ["*"]:
            problems.append("ALLOWED_HOSTS must name the public host(s) of the API")
        if problems:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=production: " + "; ".join(problems)
            )
        return self


settings = Settings()


