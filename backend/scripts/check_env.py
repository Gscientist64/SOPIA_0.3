"""Diagnostic script: verify DB connectivity, pgvector, and Ollama models."""
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(ROOT, ".env")


def load_env() -> dict:
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def main() -> int:
    env = load_env()
    url = env.get("DATABASE_URL", "")
    print("DATABASE_URL set:", bool(url))
    try:
        import psycopg2

        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("select version()")
        print("server:", cur.fetchone()[0][:70])
        cur.execute("select extname from pg_extension where extname='vector'")
        print("vector extension:", cur.fetchall())
        cur.execute(
            "select tablename from pg_tables where schemaname='public' order by tablename"
        )
        print("tables:", [r[0] for r in cur.fetchall()])
        conn.close()
    except Exception as exc:  # noqa: BLE001
        print("DB ERROR:", type(exc).__name__, exc)

    try:
        r = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "mxbai-embed-large", "prompt": "ping"},
            timeout=30,
        )
        print("ollama embed status:", r.status_code, "dim:", len(r.json().get("embedding", [])))
    except Exception as exc:  # noqa: BLE001
        print("OLLAMA ERROR:", type(exc).__name__, exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
