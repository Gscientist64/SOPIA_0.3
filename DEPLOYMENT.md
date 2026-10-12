# Deploying SOPIA on a single VM

Target: **one Linux VM (or Windows VM) with no containers.** The API, the
frontend and Ollama all run on that host; PostgreSQL is either Neon/managed or a
local install with pgvector.

> Nothing here has been executed on a real server yet — it was written and
> syntax-checked against this repository. Treat the first deployment as a
> rehearsal and work through the verification checklist at the end.

## 1. What runs where

| Component | Host | Port |
|---|---|---|
| nginx (TLS, static SPA, reverse proxy) | VM, public | 80 / 443 |
| SOPIA API (Uvicorn via `serve.py`) | VM, localhost only | 8000 |
| Ollama (chat + embeddings) | VM, localhost only | 11434 |
| PostgreSQL + pgvector | Neon (managed) or VM | 5432 |

Only nginx is exposed. The API and Ollama stay bound to localhost.

## 2. Sizing

CPU-only inference is the constraint.

| | Minimum | Comfortable |
|---|---|---|
| vCPU | 2 | 4+ |
| RAM | 4 GB | 8–16 GB |
| Disk | 10 GB | 20 GB (models ≈ 1.7 GB, uploads grow) |

Reference point: on a 4-core laptop, `qwen2.5:1.5b` answers in 4–22 s, and
ingesting a 478-page PDF (2 469 chunks) took **46 minutes**. Plan capacity
accordingly — a single user is fine, a training cohort is not.

## 3. Install OS packages (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git nginx curl
# PostgreSQL with pgvector, only if you are not using a managed database:
sudo apt install -y postgresql postgresql-16-pgvector
```

Node.js 20+ is needed on the build machine for the frontend:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 4. Deploy the code

```bash
sudo mkdir -p /opt/sopia /var/lib/sopia/uploads /var/www/sopia
sudo chown -R "$USER" /opt/sopia /var/lib/sopia
git clone https://github.com/Gscientist64/SOPIA_0.3.git /opt/sopia
cd /opt/sopia
```

## 5. Python environment

```bash
cd /opt/sopia/backend
python3.11 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

## 6. Database

**Managed (recommended).** Create a Neon project with the `vector` extension
enabled and copy the pooled connection string. Keep `sslmode=require`.

**Local.** Then create the database and enable pgvector:

```bash
sudo -u postgres psql -c "CREATE DATABASE sopia;"
sudo -u postgres psql -d sopia -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -c "CREATE USER sopia WITH PASSWORD 'strong-password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sopia TO sopia;"
```

The application migration also runs `CREATE EXTENSION IF NOT EXISTS vector`, so
the extension is created automatically on first migrate.

> Self-hosting Postgres on the same CPU-only VM means migrations and queries
> compete with model inference for cores.

## 7. Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mxbai-embed-large   # embeddings, 1024 dims - required
ollama pull qwen2.5:1.5b        # chat
```

Keep it responsive during generation:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=2m"
Environment="OLLAMA_NUM_THREAD=3"
EOF
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

`OLLAMA_NUM_THREAD=3` on a 4-core box leaves a core for the API. Verify:

```bash
curl -s http://127.0.0.1:11434/api/version
curl -s http://127.0.0.1:11434/api/embeddings \
  -d '{"model":"mxbai-embed-large","prompt":"ping"}' | head -c 120
```

## 8. Configuration

```bash
cd /opt/sopia
cp .env.production.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into SECRET_KEY
nano .env
```

Set at minimum: `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `ALLOWED_HOSTS`,
`UPLOAD_DIR=/var/lib/sopia/uploads`.

The API **refuses to start** if `ENVIRONMENT=production` and `SECRET_KEY` is a
placeholder, `CORS_ORIGINS` only allows localhost, or `ALLOWED_HOSTS` is `*`.
That is intentional: a missing secret would otherwise let anyone forge an admin
token.

```bash
chmod 600 /opt/sopia/.env     # contains the signing key and database password
```

## 9. Migrations

```bash
cd /opt/sopia/backend
./venv/bin/python -m alembic upgrade head
./venv/bin/python -m alembic current   # expect a head revision
```

`serve.py` also runs this automatically before starting, so a forgotten manual
step is not fatal.

## 10. Run the API as a service

**Linux (systemd).** Edit `deploy/sopia-api.service` (User, paths) then:

```bash
sudo useradd --system --home /opt/sopia --shell /usr/sbin/nologin sopia
sudo chown -R sopia:sopia /opt/sopia /var/lib/sopia
sudo cp deploy/sopia-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sopia-api
sudo systemctl status sopia-api
curl -s http://127.0.0.1:8000/ready
```

**Windows VM (NSSM).** From an elevated PowerShell:

```powershell
.\deploy\windows\install-sopia-service.ps1 -ProjectRoot C:\sopia
```

To run it by hand instead:

```bash
cd /opt/sopia/backend
./venv/bin/python serve.py --host 0.0.0.0 --port 8000 --workers 2
```

## 11. Frontend

Build on the VM (or in CI) with the API URL baked in:

```bash
cd /opt/sopia/frontend
cp .env.production.example .env.production
nano .env.production          # VITE_API_URL=https://sopia.example.com/api/v1
npm ci
npm run build
sudo rsync -a --delete dist/ /var/www/sopia/
```

`VITE_API_URL` is compiled into the bundle — changing it requires a rebuild.
Omitting it makes the deployed site call `http://localhost:8000`, which fails for
every visitor.

## 12. nginx and TLS

```bash
sudo cp /opt/sopia/deploy/nginx-sopia.conf /etc/nginx/sites-available/sopia
sudo ln -s /etc/nginx/sites-available/sopia /etc/nginx/sites-enabled/sopia
sudo rm -f /etc/nginx/sites-enabled/default
sudo nano /etc/nginx/sites-available/sopia    # replace sopia.example.com and paths
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d sopia.example.com
```

The config proxies `/api/` and disables buffering for `/api/v1/chat/stream`;
without that, tokens arrive in one lump instead of streaming.

## 13. First run

```bash
cd /opt/sopia/backend
./venv/bin/python scripts/create_admin.py \
  --email admin@yourorg.com --password 'StrongPassw0rd!' --role SUPER_ADMIN
```

The first account registered through the UI also becomes `SUPER_ADMIN`.

## 14. Verification checklist

```bash
curl -fsS https://sopia.example.com/health          # {"status":"ok"}
curl -fsS https://sopia.example.com/ready           # database: true
curl -fsS https://sopia.example.com/api/v1/provider # provider + embedding dim
```

- [ ] `https://<domain>/` loads the login page over HTTPS
- [ ] Login succeeds; an admin sees **Administration**
- [ ] Upload a small TXT/MD SOP → status becomes **Active** with chunks indexed
- [ ] Ask a question → streamed answer **with citations**
- [ ] Click a source → real document text appears
- [ ] A topic outside the SOPs is refused (not answered from general knowledge)
- [ ] Quiz/exam refuses with 409 for an uncovered topic
- [ ] Browser console shows no CORS or 401 errors
- [ ] `/docs` returns 404 in production
- [ ] `systemctl status sopia-api` (or the Windows service) is healthy
- [ ] Reboot the VM → service, Ollama and nginx all come back automatically

## 15. Updating and rollback

```bash
cd /opt/sopia
git fetch --all && git log --oneline HEAD..origin/main    # review first
git pull
./backend/venv/bin/pip install -r backend/requirements.txt
sudo systemctl restart sopia-api        # runs migrations on start
cd frontend && npm ci && npm run build && sudo rsync -a --delete dist/ /var/www/sopia/
```

Rollback: `git checkout <previous-commit>`, restart the service. Database
migrations are **not** automatically reversible — check
`alembic downgrade <revision>` for the revision you are reverting, and back up
before upgrading.

## 16. Backups

- **Database:** use the provider's automated backups (Neon has point-in-time
  restore). Verify a restore once.
- **Uploads:** `/var/lib/sopia/uploads` holds the original SOP files and is *not*
  reconstructible from the database. Back it up:

```bash
sudo tar czf /var/backups/sopia-uploads-$(date +%F).tar.gz -C /var/lib/sopia uploads
```

- **Secrets:** store `.env` in a password manager. Losing `SECRET_KEY` logs
  everyone out (not data loss); leaking it means rotating immediately.

## 17. Known limitations at this deployment size

1. **Ingestion is synchronous.** Uploading a large PDF blocks that request for as
   long as embedding takes (up to ~46 min for a 478-page document). nginx is
   configured with a 1-hour read timeout so it does not 504, but the user watches
   a spinner and the worker thread is busy. Use `scripts/ingest_document.py` for
   bulk loading until the background worker lands.
2. **The rate limiter is per worker.** With `--workers 2` each client effectively
   gets double the configured limit. Move to Redis if you run many workers.
3. **No ANN index** (ivfflat/HNSW) on `document_chunks.embedding`, so search is
   exact. Fine to a few thousand chunks; add an index beyond that.
4. **One Ollama instance** with `OLLAMA_NUM_PARALLEL=1`, so AI requests queue.
   Adding workers does not increase AI throughput.
5. **No self-service password reset**; reset by re-running `create_admin.py`.
6. **Research and Compare modes** return `501` by design and are hidden in the UI.
