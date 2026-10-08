"""Diagnose Ollama connectivity from this Python environment."""

import json
import traceback

import requests

BASE = "http://localhost:11434"
LONG_TEXT = ("Client registration procedure. " * 45).strip()

print("LONG_TEXT length:", len(LONG_TEXT))


def attempt(label: str, method: str, url: str, **kw):
    try:
        resp = requests.request(method, url, timeout=120, **kw)
        print(f"[OK]   {label}: {resp.status_code}")
        return resp
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {label}: {type(exc).__name__}: {exc!r}")
        cause = exc.__cause__ or exc.__context__
        if cause:
            print(f"        cause: {type(cause).__name__}: {cause!r}")
        return None


attempt("GET /api/tags", "GET", f"{BASE}/api/tags")
attempt(
    "POST /api/embeddings (short)",
    "POST",
    f"{BASE}/api/embeddings",
    json={"model": "mxbai-embed-large", "prompt": "hello"},
)
attempt(
    "POST /api/embeddings (long)",
    "POST",
    f"{BASE}/api/embeddings",
    json={"model": "mxbai-embed-large", "prompt": LONG_TEXT},
)
for i in range(5):
    attempt(
        f"POST /api/embeddings (burst {i})",
        "POST",
        f"{BASE}/api/embeddings",
        json={"model": "mxbai-embed-large", "prompt": f"burst text number {i}"},
    )
attempt(
    "POST /api/chat",
    "POST",
    f"{BASE}/api/chat",
    json={
        "model": "llama3",
        "messages": [{"role": "user", "content": "Say OK"}],
        "stream": False,
    },
)
