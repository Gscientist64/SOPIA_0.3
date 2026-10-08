# SOPIA — Project Status

_Last updated: 2026-10-08_

## Completed

### P0 audit blockers (all fixed and verified)
- **Embedding dimension mismatch resolved.** Verified that Ollama's
  `mxbai-embed-large` returns **1024** dims (not 384). Added a single
  `EmbeddingService` (`app/rag/embeddings.py`) that owns embedding generation,
  reports the dimension, and fails loudly on provider/dimension errors. The
  `document_chunks.embedding` column is now `Vector(1024)`.
- **Authentication is enforced.** `app/core/security.py` provides
  `get_current_user` plus `require_roles` factories. Every non-public route now
  requires a valid JWT; `require_admin` / `require_super_admin` guard document
  management and admin endpoints.
- **RBAC implemented and tested.** `SUPER_ADMIN`, `CONTENT_ADMIN`, `USER`.
  Normal users cannot upload/delete SOPs, manage users, or read admin analytics.
- **Secret hygiene.** Added a root `.gitignore` (ignores `.env`, uploads, venvs).
  `.env.example` contains placeholders only. The repository is not a git repo, so
  no secret is in git history.
- **Tailwind v4 fixed.** Switched to `@tailwindcss/vite` + `@import "tailwindcss"`,
  removed the Tailwind v3 config. `npm run build` succeeds and styles render.

### Core SOP RAG pipeline (MVP)
- Section-aware chunking (`app/rag/chunking.py`) with configurable size/overlap
  that records `section`, `heading`, `page_number`, `chunk_index` — no longer a
  naive fixed-width split.
- Structure-preserving extraction (`app/rag/extractors.py`) for PDF (with page
  numbers), DOCX (heading styles), TXT and Markdown.
- Document **versioning**: `documents` → `document_versions` → `document_chunks`,
  with exactly one active version per document; retrieval uses only the active,
  ready, `Active` version.
- **Metadata-filtered hybrid retrieval** (org isolation, document/status/dept/type
  filters, cosine similarity + keyword-overlap reranking).
- **Structured citations** persisted in `citations` and returned by the API
  (document title, version, section, page, chunk id, relevance). The UI shows
  clickable "View source" cards backed by `GET /documents/chunks/{id}`.
- **Prompt hardening**: retrieved text is wrapped in `<retrieved_sop_context>` and
  explicitly declared reference-only data. Injection phrases inside documents are
  ignored as instructions (verified by test and by E2E).
- **Hallucination control**: answers from the SOP, says what is *not* specified,
  or returns the standard refusal when the SOP is silent.
- **Chat persistence**: `conversations`, `messages`, `citations` — new, continue,
  rename, search, delete, clear, retry, copy.
- **Streaming**: Server-Sent Events (`POST /chat/stream`) with graceful fallback
  and error events; the session used by the stream is opened independently.
- **Dashboards with real data**: `/dashboard/me` and `/admin/dashboard` — no
  hardcoded statistics anywhere.
- **Learning mode** (sessions, progress rows, tutor turns), **quizzes**, **exam
  mode** (timer, navigation, mark-for-review, auto-submit, scoring, explanations,
  weak topics), **interview mode** (conversational Q&A with structured feedback
  and a final summary).
- **Observability & security extras**: audit logs, AI provider logs, in-memory
  rate limiting on auth endpoints, CORS allow-list from settings, file-type and
  size validation, secure generated filenames.
- **Local inference tuned for a laptop.** Default chat model is `qwen2.5:1.5b`
  (~1.0 GB rather than llama3's 4.7 GB) with `OLLAMA_KEEP_ALIVE=2m`, so the model
  is released from RAM shortly after use instead of being pinned for 5 minutes,
  plus `OLLAMA_NUM_THREAD` to cap how many CPU cores inference may take.
  Verified against SOPIA's real prompts (`scripts/check_model.py`): grounded
  answering, refusal when unspecified, injection resistance and question-JSON
  generation all pass (4/4) at 4–22s per call on a 4-core laptop.
- **Ingestion survived real PDFs.** Three defects that made large documents fail
  outright are fixed: (1) a single extracted block could become a chunk far
  larger than the embedding model's context window — oversized blocks are now
  split, and a finished chunk never exceeds `CHUNK_SIZE`; (2) embeddings now use
  Ollama's `/api/embed` with `truncate`, so an over-long input is clipped instead
  of aborting the document, and chunks are embedded in batches; (3) ingestion
  commits in batches, because a multi-minute transaction over one connection was
  being closed by Neon and left the version stuck in `processing`. `_mark_error`
  now rolls back first, so a failure is always recorded.
- **Tolerant JSON parsing** (`app/ai/parsing.py`). Model output that is almost-JSON
  (trailing commas, surrounding prose, or one broken object) is salvaged
  object-by-object, and question keys are normalised across common aliases
  (`question`→`prompt`, `choices`→`options`, `answer`→`correct_answer`). Without
  this, a 3B model would silently break quiz and exam generation.

### Frontend
- Register / login / logout, protected routes, role-aware navigation, 401 handling.
- Chat page with streaming, citations, source modal, conversation sidebar,
  retry/copy/clear, and a mode selector that disables unimplemented modes.
- Dashboard, Progress, Knowledge Base (with admin upload + version management),
  Learn, Exams, Interviews, Administration pages.

### Tests
- **90 pytest tests passing** (`cd backend && python -m pytest`).
- **37/37 end-to-end checks passing** (`python scripts/e2e_test.py`) against real
  Postgres + pgvector + Ollama: auth, RBAC, upload→chunk→embed, grounded answers,
  citations, refusal, injection resistance, streaming, conversations, learning,
  quiz, exam, interview, dashboards.
- **4/4 model behaviour checks** (`python scripts/check_model.py`) — run this after
  changing `OLLAMA_MODEL` to confirm the new model still answers, refuses and
  produces valid question JSON.

## In Progress
- Research mode and Compare mode: system prompts exist; endpoints intentionally
  return `501` so the UI never advertises a broken mode.
- Reranking: keyword rerank is live; an embedding-based reranker is not yet added.

## Blocked
- None.

## Known Issues & Limitations
- **The database password previously present in `.env` must be rotated** in the
  database provider. Removing a file does not invalidate an exposed credential.
- `backend/login.txt` holds the admin password in clear text and is **not**
  covered by `.gitignore`. Delete it or add it to `.gitignore` before initialising
  a git repository..- pgvector similarity search is PostgreSQL-specific, so it is **not** covered by
  pytest (which uses SQLite). It is covered by `scripts/e2e_test.py` instead.
- Document ingestion is synchronous inside the upload request. Embedding is the
  bottleneck on CPU: a 478-page PDF (~2 500 chunks) needs roughly **75 minutes**
  on a 4-core laptop, so an HTTP request will time out long before it finishes.
  A background worker with progress reporting is the top priority for large
  corpora; until then, ingest very large PDFs from a script, not the browser.
- Local generation runs on CPU (no usable GPU present): roughly **4–22s per call
  with `qwen2.5:1.5b`** (higher figures are JSON/quiz generation, which emits more
  tokens) and 30–90s with `llama3`. Streaming keeps the UI responsive. Run
  `python scripts/check_model.py` after switching models.
- `MIN_RELEVANCE=0.55` is deliberately strict (precision over recall). Lower it
  if legitimate questions are being refused.
- No approximate-nearest-neighbour index (ivfflat/HNSW) is created yet — fine for
  MVP document counts, worth adding for large knowledge bases.
- Exam/quiz generation depends on the model returning JSON; interview mode has a
  rule-based fallback, exam/quiz surface a clear error instead.

## Next Priority
1. Rotate the exposed database credential, and delete or ignore `login.txt`.
2. Move ingestion to a background worker and surface processing progress in the UI.
3. Add an embedding-based reranker and an HNSW index for scale.
4. Implement Research mode and Compare mode (SOP vs external information).
5. Add frontend component tests and CI (lint + pytest + build).

