# SOPIA — Project Status

_Last updated: 2026-10-13_

## Completed

### Login-free access, with roles that mean something
SOPIA previously demanded an account before showing anything, which is the wrong
first impression for a chat product. It now opens straight into the assistant,
and access is granted by role:

| Role | Chat | Interview | Learn / Exams / Progress | Knowledge base & admin |
|------|:---:|:---:|:---:|:---:|
| Guest (no account) | ✅ | ✅ | — | — |
| Registered user | ✅ | ✅ | ✅ | — |
| Admin | ✅ | ✅ | ✅ | ✅ |

- `RoleEnum.GUEST` plus `POST /auth/guest` issue a normal JWT for an anonymous
  visitor, so every existing organisation-scoped query keeps working unchanged.
- Guests are scoped to **one designated organisation** via
  `PUBLIC_ORGANIZATION_ID`; blank disables login-free access entirely.
- `require_member` / `MemberUser` gate learning, exams, progress and dashboards;
  document management is admin-only, but **opening the source behind a citation
  stays open to everyone** — that is the product's whole point.
- The frontend bootstraps a guest on first load, filters navigation by access,
  and guards member-only routes.
- The theme is pink throughout (129 class replacements across 13 files), with a
  matching favicon and `theme-color`.

### Greetings no longer trigger the compliance refusal
A "Hi" produced *"I couldn't find this in the available SOPs…"* — the correct
refusal for an unanswerable SOP question, and completely wrong for a greeting.
The root cause was ordering: `MIN_RELEVANCE=0.55` is permissive enough that a
short greeting retrieves unrelated chunks at ~0.60, so retrieval "succeeded" and
the refusal came from the model, not from the empty-context branch.

`app/rag/smalltalk.py` now recognises greetings, thanks, goodbyes and capability
questions **before retrieval runs**, and answers them directly. The rule is
deliberately conservative — every word must be a pleasantry and the message must
be ≤ 8 words — so *"Hi, what is the registration procedure?"* still goes to the
SOPs. Covered by five tests, including one that fails if retrieval is ever
reached for a greeting.

### Interview practice is progressive and shows a model answer
- Questions now carry a `difficulty` (migration `0004_interview_difficulty`) and
  escalate: warm-up → medium → challenging. The prompt asks the model to order
  them, and `_difficulty_for` provides a positional fallback so the progression
  holds even when a small model omits the label (verified both ways).
- Feedback always includes a **first-person model answer** — verified to be
  genuinely better than the input, not an echo: answering "I just do my job and
  report what I find" scored 1/5 and produced a concrete, role-specific answer.
- The feedback card leads with the score and what worked, gives the model answer
  a prominent panel, and tucks accuracy/clarity/relevance behind a collapsed
  "Show more detail" so the page reads calmly instead of as a wall of text.
- The summary previously listed `weak_areas` **verbatim as `recommended_topics`**,
  showing the same complaints twice. It now names the SOP documents behind the
  weakest answers, which is actually actionable.

### Retrieval can reach structural context
Loading two more SOPs exposed a fabrication bug that predated them. Asking "what
are the four pillars of PMTCT" returned four invented pillars: the excerpts that
list them were never retrieved, only a passage saying "it is built on four
pillars" was, so the model filled the gap.

Three independent causes, each measured:

- **Plurals never matched.** `_terms` had no folding, so the query term "pillars"
  did not match a chunk labelled "Pillar 1" — the keyword signal scored 0.
- **Headings were not embedded.** A chunk whose body reads "Low knowledge and
  risk perception" is only findable as "Pillar 1 (Primary Prevention)" through its
  heading. Ingestion now embeds heading + section + body; the four pillar chunks
  moved from outside the top 200 candidates to ranks 2, 6, 7 and 10.
- **Headings carried no weight in ranking.** Heading overlap now contributes to
  the blended score, and `TOP_K` moved 5 -> 8 so a list split across sibling
  chunks can fit at all.

Measured on the real corpus: the answer went from four invented pillars to three
correct, cited ones.

### Re-ingestion no longer destroys citation history
Re-embedding the corpus failed and took the knowledge base offline. Ingesting a
version deletes its chunks first, but citations hold a foreign key to the chunk
they quoted, so the delete raised a `ForeignKeyViolation`; the documents were left
in `Error` with `is_active` still true, and since retrieval requires
`processing_status == "ready"` the whole corpus silently vanished from search.

- Ingestion now detaches citations before deleting their chunks. A citation
  denormalises the title, version, section and page it shows, so the citation is
  preserved and only the "view source" deep link is lost for answers given before
  the re-ingest.
- `scripts/reembed.py` adds a **new version** instead of rewriting the existing
  one, copies the file, and activates the new version only after it ingests
  successfully. A failed run now costs nothing, and the knowledge base stays
  online for the whole job.

The corpus was re-embedded this way (documents 9-11, 3 328 chunks, ~63 min). All
111 existing citations still resolve to live chunks: 0 detached, 0 dangling.

### Production deployment preparation
The application was ready but there was **no way to deploy it**: no Dockerfile or
process manager, no reverse-proxy config, a dev-only launcher, and — most
dangerously — a `SECRET_KEY` that silently fell back to the value published in
this repository, letting anyone forge an admin token.

- `ENVIRONMENT=production` now activates **start-up safety checks** in
  `app/core/config.py`; the API refuses to boot when `SECRET_KEY` is a
  placeholder or shorter than 32 characters, `CORS_ORIGINS` still points only at
  localhost, or `ALLOWED_HOSTS` is `*`.
- `ALLOWED_HOSTS` is enforced via `TrustedHostMiddleware`, and interactive API
  docs plus the OpenAPI schema are hidden in production.
- `GET /ready` reports database readiness (and returns 503 when the database is
  unreachable) so a platform can distinguish liveness from readiness.
- **Rate limiting extended from 2 endpoints to 15.** Chat, quiz/exam/interview
  generation, uploads, reprocessing and registration are now throttled per
  client, with `RATE_LIMIT_ENABLED` as a global kill switch (disabled in tests).
  Previously one user could saturate the CPU-only AI backend at will.
- `backend/serve.py` is the production launcher: it runs `alembic upgrade head`
  then starts Uvicorn on `0.0.0.0` with configurable workers, no reload, and
  trusted-proxy headers so per-client rate limiting sees the real visitor.
- Deployment artifacts: `.env.production.example`,
  `frontend/.env.production.example`, `deploy/sopia-api.service` (systemd),
  `deploy/windows/install-sopia-service.ps1` (NSSM), `deploy/nginx-sopia.conf`
  (TLS, SSE streaming with buffering disabled, 1-hour read timeout for slow
  ingestion) and a step-by-step **DEPLOYMENT.md** runbook.

Not yet verified against a real server — the runbook's verification checklist is
the first thing to work through on the target VM.

### Generated questions are grounded, cited and traceable
Quizzes, exams and interview questions were previously authored from the model's
own knowledge — an exam could ask about drug mechanisms absent from the SOPs and
mark a wrong statement as the correct answer. All generated content now goes
through one retrieval seam (`app/rag/grounding.py`), its prompts carry the same
trust boundary and "no outside knowledge" rules as SOP answering, and every
question stores the excerpts it came from (`Question.sources` /
`InterviewQuestion.sources`, migration `0003_question_sources`). Quiz and exam
requests return **409** when the knowledge base has nothing relevant instead of
inventing questions; interviews fall back to generic questions, because an
interview is about the candidate rather than the SOP.

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
- Chat page with streaming, citations, source modal, retry/copy/clear.
- **One left sidebar.** Conversation history (new chat, search, rename, delete) lives
  beside the Chat and Interviews links instead of in a second rail, and is shared
  through a `ConversationsProvider` so the layout and the transcript agree on which
  thread is open. It appears on Chat and Interviews and stays out of the way on the
  other pages.
- The chat mode selector was removed: the assistant always answers from the SOPs,
  and Learning, Exams and Interviews have their own pages, so the dropdown only
  invited confusion.
- Dashboard, Progress, Knowledge Base (with admin upload + version management),
  Learn, Exams, Interviews, Administration pages.

### Tests
- **119 pytest tests passing** (`cd backend && python -m pytest`).
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
- `backend/login.txt` holds the admin password in clear text. It is covered by
  `.gitignore` and must never be committed.
- Guest rows are never pruned. They are cheap, but a public deployment should add
  a periodic cleanup of expired guest accounts before real traffic arrives.
- Short greetings used to be answered from unrelated chunks because
  `MIN_RELEVANCE=0.55` lets ~0.60 noise through. Small talk is now handled before
  retrieval, but the underlying margin is still thin: a genuinely vague question
  can retrieve marginally relevant chunks and be answered instead of refused.
- pgvector similarity search is PostgreSQL-specific, so it is **not** covered by
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
- **Multi-part answers are limited by the model, not by retrieval.** Asking "what are
  the four pillars of PMTCT" now retrieves three of the four pillar chunks and the
  answer names them correctly; the fourth is missed because it ranks 10th, just
  outside `TOP_K=8`. Retrieval *does* surface all four at `TOP_K=10`, but the answer
  got **worse** there (2 of 4 correct) — extra chunks dilute `qwen2.5:1.5b`'s
  attention. `TOP_K=8` was chosen because it measured best, not because it is
  perfect. Fixing this properly needs a larger model or a reranker, and the
  number of items a question asks for should not be inferred from `TOP_K`.
- No approximate-nearest-neighbour index (ivfflat/HNSW) is created yet — fine for
  MVP document counts, worth adding for large knowledge bases.
- Exam/quiz generation depends on the model returning JSON; interview mode has a
  rule-based fallback, exam/quiz surface a clear error instead.

## Next Priority
1. Run the DEPLOYMENT.md checklist on the real VM and fix whatever it surfaces.
2. Move ingestion to a background worker and surface processing progress in the UI.
3. Add an embedding-based reranker and an HNSW index for scale.
4. Implement Research mode and Compare mode (SOP vs external information).
5. Add frontend component tests and CI (lint + pytest + build).

