# SOPIA — Standard Operating Procedure Intelligent Assistant

SOPIA lets an organisation upload its SOPs, policies, manuals and training
material, index them into a searchable vector knowledge base, and then answer
questions **strictly from those documents** — with citations, and with an explicit
refusal when the documents do not contain the answer. On top of that it offers
learning, exam and interview practice modes.

---

## 1. Overview

- **SOP Assistant** — retrieval-augmented answers grounded in your documents,
  with structured citations (document, version, section, page).
- **Learning mode** — an interactive tutor with sessions and progress tracking.
- **Exam mode** — timed mock exams with scoring, explanations and weak topics.
- **Interview mode** — conversational practice interviews with structured feedback.

Every question SOPIA generates — quizzes, exams and interview questions — is
authored from the same retrieved SOP excerpts as the answers, and each question
records the document, version, section and page it came from. A topic the
knowledge base cannot support returns an explicit refusal instead of questions
invented from the model's general knowledge, which could otherwise contradict
your own procedures.
- **Research / Compare modes** — planned. The API reports them as unavailable, so
  the UI never offers a broken feature.

## 2. Architecture

```
frontend (React + TS + Vite + Tailwind v4)
        │  REST + Server-Sent Events
        ▼
backend (FastAPI)
  api/routes/    auth, documents, chat, conversations, learning,
                 exams, interviews, dashboard, admin, system
  services/      chat orchestration, document lifecycle, storage, audit
  rag/           extractors → chunking → embeddings → retrieval → citations
  ai/            AIProvider interface + router → local (Ollama) | gemini
  models/        SQLAlchemy models
  core/          config, security (JWT + RBAC), logging, rate limiting
        │
        ▼
PostgreSQL + pgvector     Ollama (local LLM + embeddings)  /  Gemini API
```

Design rules:

- The AI provider is **swappable by configuration**; nothing else knows which one runs.
- Retrieved document text is treated as **data, never instructions**.
- Retrieval is **organisation-scoped** and only ever searches the **active**,
  successfully processed version of **Active** documents.

## 3. Technology stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL + pgvector |
| AI | Ollama (`qwen2.5:1.5b` + `mxbai-embed-large`) or Google Gemini |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS v4, React Router, Axios |
| Auth | JWT (python-jose) + bcrypt, role-based access control |
| Tests | pytest (hermetic unit/integration) plus a live end-to-end script |

## 4. Requirements

- Python **3.10+** (3.11 tested)
- Node.js **18+** and npm
- **PostgreSQL 14+ with the `pgvector` extension** — Docker or managed (e.g. Neon)
- **Ollama** for local inference, or a Gemini API key

## 5. Environment variables

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key — generate a long random value |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `AI_PROVIDER` | `local` or `gemini` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` | Local model settings |
| `OLLAMA_KEEP_ALIVE` | How long Ollama keeps the model in RAM (`30s`, `2m`, `-1` = forever) |
| `OLLAMA_NUM_THREAD` | Threads for CPU inference (`0` = auto/all cores; e.g. `2` to keep the machine responsive) |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBED_MODEL` | Gemini settings |
| `EMBEDDING_DIM` | **Must match the embedding model output** (1024 for `mxbai-embed-large`, 768 for Gemini `text-embedding-004`) |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB`, `ALLOWED_EXTENSIONS` | Upload controls |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | Chunking controls |
| `TOP_K`, `MIN_RELEVANCE` | Retrieval controls |

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> `.env` is git-ignored. Never commit it.

## 6. PostgreSQL setup

Docker Compose starts Postgres **with pgvector**:

```bash
docker-compose up -d
```

This exposes Postgres on `localhost:5432` with `sopia` / `sopiapass` / `sopia`
(override via `.env`). To use a managed provider instead, set `DATABASE_URL` and
skip this step.

## 7. pgvector setup

The Compose image (`pgvector/pgvector:pg16`) already includes pgvector. The
migration runs `CREATE EXTENSION IF NOT EXISTS vector`, so no manual step is
needed. Verify with:

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

## 8. Ollama installation

Install from <https://ollama.com/download>, then:

```bash
ollama --version
ollama list
```

If the server is not already running in the background, start it:

```bash
ollama serve
```

> On Windows, `localhost` can resolve to IPv6 first. If requests fail, set
> `OLLAMA_BASE_URL=http://127.0.0.1:11434`.

## 9. Model installation

```bash
ollama pull qwen2.5:1.5b          # chat model (~1.0 GB) - recommended for 16 GB laptops
ollama pull mxbai-embed-large   # embedding model (~670 MB, 1024 dims)
```

Verify the embedding dimension matches `EMBEDDING_DIM`:

```bash
curl -s http://127.0.0.1:11434/api/embeddings \
  -d '{"model":"mxbai-embed-large","prompt":"ping"}'   # 1024 numbers
```

`qwen2.5:3b` (~1.9 GB) or `llama3:latest` (~4.7 GB) reason better still if you have
RAM to spare — set `OLLAMA_MODEL` accordingly and re-run `scripts/check_model.py`.
Avoid sub-1B models: they are light but cannot follow the strict structured-output
instructions that quizzes and exams depend on.

## 10. Backend setup

```bash
cd backend
python -m venv venv
# Windows:      .\venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
```

## 11. Frontend setup

```bash
cd frontend
npm install
```

## 12. Database migrations

```bash
cd backend
alembic upgrade head
```

`0002_core_mvp` creates the full MVP schema: documents, versions, chunks,
conversations, messages, citations, learning, exams, interviews and audit tables.

## 13. Running the project

```bash
# Terminal 1 — backend
cd backend
python run.py                 # http://127.0.0.1:8000   (OpenAPI docs at /docs)

# Terminal 2 — frontend
cd frontend
npm run dev                   # http://localhost:5173

# Terminal 3 (only if Ollama is not already running)
ollama serve
```

### Create your first account

The **first account registered through the UI becomes `SUPER_ADMIN`**. To create
or promote an account from the command line:

```bash
cd backend
python scripts/create_admin.py --email admin@example.com --password 'Str0ngPass!'
python scripts/create_admin.py --email user@example.com  --password 'Str0ngPass!' --role USER
```

Then sign in at <http://localhost:5173/login>.

## 14. Running tests

```bash
cd backend
python -m pytest                    # 99 hermetic tests (no DB or Ollama needed)
python scripts/check_model.py       # 4 behaviour checks for the configured model
python scripts/e2e_test.py          # 37 live checks (needs DB + Ollama running)
```

pytest stubs the AI provider and uses SQLite, so it requires nothing external —
note that pgvector similarity search itself is PostgreSQL-specific and is
therefore covered by the end-to-end script rather than pytest.

## 15. Gemini configuration

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

Gemini is optional and never required. Selecting it without a key returns a clear
configuration error rather than failing obscurely.

> A consumer Gemini subscription does not automatically cover API usage.

> **Embedding note:** Gemini embeddings are 768-dimensional while the local model
> is 1024. Changing the *embedding* provider means updating `EMBEDDING_DIM`, the
> pgvector column, and re-ingesting documents.

## 16. Local LLM configuration

```bash
AI_PROVIDER=local
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_EMBED_MODEL=mxbai-embed-large
OLLAMA_KEEP_ALIVE=2m
OLLAMA_NUM_THREAD=0
EMBEDDING_DIM=1024
```

Switching providers is configuration-only — no code changes. Inspect the active
configuration at any time:

- `GET /api/v1/provider`
- `GET /api/v1/health` — database, provider availability and embedding dimension

## 17. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Ollama is not reachable at http://localhost:11434` | Ollama is not running — start `ollama serve`. If it persists, use `127.0.0.1` instead of `localhost`. |
| `Embedding dimension mismatch` on upload | `EMBEDDING_DIM` does not match the model output. Fix it, recreate the vector column, re-ingest. |
| Upload succeeds but status is `Error` | Open **Knowledge Base → Versions** to read the recorded `processing_error`. |
| SOPIA always says it cannot find an answer | Lower `MIN_RELEVANCE` (e.g. `0.35`), or confirm the document is `Active` with an active `ready` version. |
| Quiz/exam says *"No approved SOP content matches this topic"* | Deliberate: generated questions must be traceable to a source, so nothing is invented when retrieval finds no relevant SOP. Widen the topic wording, `MIN_RELEVANCE`, or upload a document covering it. |
| Answers are slow, or the machine lags | Use the lightweight model (`OLLAMA_MODEL=qwen2.5:1.5b`), cap inference with `OLLAMA_NUM_THREAD`, and use a short `OLLAMA_KEEP_ALIVE` so the model leaves RAM when idle. Note that deleting models frees disk, not RAM. |
| `Cannot reach the SOPIA API` in the UI | Backend is not running, or `VITE_API_URL` is wrong. |
| Tailwind classes have no effect | Ensure `@tailwindcss/vite` is in `vite.config.ts` and `index.css` starts with `@import "tailwindcss";`. |
| `docker-compose up` fails | Docker Desktop is not running. A managed Postgres with pgvector works too — just set `DATABASE_URL`. |
