# SOPIA — Offline Demonstration

A self-contained demonstration of SOPIA that runs with **no internet connection,
no PostgreSQL and no Python installation**. Everything it needs is in this folder.

---

## 1. What to hand over

Give the recipient the whole `dist-offline` folder (≈3.2 GB). Copy it to a USB
drive or transfer it directly — nothing is downloaded at run time.

```
dist-offline/
  Start SOPIA Demo.cmd      <- double-click this
  Stop SOPIA Demo.cmd
  OFFLINE_DEMO.md           <- this file
  app/                      the SOPIA API (bundled executable, no Python needed)
  frontend/                 the user interface
  data/sopia-demo.db        pre-loaded SOPs, already indexed
  data/uploads/
  ollama/OllamaSetup.exe    local AI runtime (installed on first run)
  ollama/models/            qwen2.5:1.5b + mxbai-embed-large (~1.6 GB)
```

## 2. Requirements on the demonstration machine

| | Minimum | Notes |
|---|---|---|
| OS | Windows 10/11 64-bit | |
| RAM | 4 GB | 8 GB recommended |
| Disk | 4 GB free | |
| CPU | 2 cores | 4+ makes answers noticeably faster |
| Internet | **not required** | Only needed if you want to send logs out |

No administrator rights are needed: the AI runtime installs per-user.

## 3. Running it

1. Copy the folder to the machine (e.g. `C:\SOPIA`). Keep it in a path without
   special characters.
2. Double-click **`Start SOPIA Demo.cmd`**.
   - **First run only:** it silently installs the local AI runtime (about 1 minute).
   - It then starts the AI model, starts SOPIA, and opens your browser.
3. Sign in:

   | | |
   |---|---|
   | **Email** | `demo@sopia.local` |
   | **Password** | `Sopia-Demo-2025` |

4. Ask something the bundled SOPs cover, for example:

   - *"What must a new client present during registration?"*
   - *"How soon must registration records be verified by a supervisor?"*
   - *"What percentage of records must be verified each month?"*

   You will get an answer **with clickable citations** back to the exact SOP
   section it came from.

5. Ask something the SOPs do **not** cover, e.g. *"What is the annual leave
   entitlement?"* SOPIA will refuse rather than guess — this is the behaviour the
   product is built around.

**The first answer takes 10–30 seconds** while the model loads into memory.
Later answers are faster. This is normal for CPU-only inference.

Closing the launcher window stops SOPIA. Run `Stop SOPIA Demo.cmd` to also stop
the AI runtime and release its memory.

## 4. What is pre-loaded

Three original, fictional SOPs (no third-party documents), already chunked and
indexed:

| Document | Department |
|---|---|
| Client Registration SOP | Clinical Services |
| Data Quality and Monthly Reporting SOP | Monitoring and Evaluation |
| Incident Reporting and Escalation SOP | Operations |

**Use your own documents instead:** sign in as the demo admin, open **Knowledge
Base → Upload a new SOP** and add a PDF, DOCX, TXT or Markdown file. Indexing
happens immediately and the document becomes searchable. Note that a large PDF
takes a while on CPU.

To start over from a clean slate, restore `data/sopia-demo.db` from your original
copy of the folder.

## 5. Demonstration script (suggested)

1. **Sign in** — note the role-aware navigation (Administration appears for admins).
2. **Knowledge Base** — show the three indexed SOPs and that each has an *Active*
   version with chunks indexed.
3. **Chat** — ask a covered question and expand **Sources** on the answer. Click a
   source to show the exact underlying text.
4. **Chat** — ask an uncovered question and show the refusal. This is the point of
   the product: it will not invent an organisational policy.
5. **Learn** — start a learning session on a topic; it produces a structured
   outline and tutors you.
6. **Exams** — generate a mock exam. Questions are drawn from your SOPs and each
   question shows the SOP it came from.
7. **Interviews** — run a short practice interview and show the structured
   feedback.
8. **Dashboard / Progress** — show that statistics come from real usage, not
   hard-coded numbers.

## 6. Known limitations

1. **Answer selection is not perfect.** When two SOPs use similar wording
   (for example both discuss "verification" of "records"), retrieval can return
   the less specific clause, and the answer will be grounded in that instead. The
   citation is always shown so the reader can check. Asking a more specific
   question, or raising `TOP_K`, improves this.
2. **CPU-only inference is slow.** Roughly 5–20 seconds per answer with
   `qwen2.5:1.5b`.
3. **Large uploads block.** Indexing runs inside the upload request; a 400-page
   PDF can take tens of minutes. Use small documents for a live demonstration.
4. **One request at a time.** The local runtime is configured for a single
   parallel request, so simultaneous users queue.
5. **Research and Compare modes are not implemented** and are shown as
   unavailable in the interface.
6. **No password reset in the UI.** The demo account password is fixed.

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "the AI runtime did not start within 2 minutes" | Run `%LOCALAPPDATA%\Programs\Ollama\ollama.exe serve` in a separate window to see the error. |
| "the SOPIA API did not become ready" | Port 8000 is already in use — stop the other copy with `Stop SOPIA Demo.cmd`. |
| Windows SmartScreen warns about the executable | Expected: the binaries are not code-signed. Choose *More info → Run anyway*. |
| Antivirus quarantines `sopia-api.exe` | A common false positive for bundled executables. Allow the folder, or rebuild the executable on the target machine. |
| Answers are slow | Normal on CPU. Closing other applications frees memory and cores. |
| Answer says it "couldn't find this in the available SOPs" | Expected when the question is outside the indexed documents. Check the wording or upload a relevant SOP. |
| Browser shows a blank page | Open `http://localhost:8000` manually; confirm the launcher reported `[ok] SOPIA is running`. |

## 8. If the recipient has internet

The same folder works unchanged. Nothing contacts the internet: the AI model,
the database and the interface are all local. You can verify this by watching
`http://localhost:8000/ready`, which reports database readiness only.

## 9. Rebuilding this bundle

For maintainers:

```bash
# 1. Build the frontend
cd frontend && npm ci && npm run build

# 2. Build the pre-indexed demo database (needs Ollama running)
cd ../backend
venv/Scripts/python.exe scripts/build_demo_db.py --output ../dist-offline/data/sopia-demo.db

# 3. Freeze the API
venv/Scripts/python.exe -m PyInstaller --noconfirm --clean sopia-demo.spec

# 4. Assemble: app/ frontend/ data/ ollama/ + the two .cmd files
```

| "port 11434 is already in use by another program (process NNNN)" | A leftover AI runtime or another program holds the runtime port. The launcher names the holding process: `tasklist /fi "pid eq NNNN"`. Run `taskkill /f /im ollama.exe`, then start the demo again. |
| Launcher sat on "starting up..." then failed | Usually the same cause as above. The launcher now detects an unresponsive runtime and restarts it automatically; if the port is held by something else it reports the owning process instead of waiting. |
