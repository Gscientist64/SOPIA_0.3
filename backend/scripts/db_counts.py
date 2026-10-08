"""Report row counts for existing tables (safe, read-only)."""

import os
import sys

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(ROOT, ".env")


def load_env() -> dict:
    env = {}
    with open(ENV_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def main() -> int:
    url = load_env()["DATABASE_URL"]
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    print("tables:", [r[0] for r in cur.fetchall()])
    cur.execute(
        "SELECT atttypmod FROM pg_attribute "
        "WHERE attrelid='document_chunks'::regclass AND attname='embedding'"
    )
    row = cur.fetchone()
    print("document_chunks.embedding typmod:", row[0] if row else None)
    for table in ("organizations", "users", "documents", "document_versions", "document_chunks"):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - fixed names
            print(f"{table}: {cur.fetchone()[0]}")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(f"{table}: (missing) {type(exc).__name__}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
