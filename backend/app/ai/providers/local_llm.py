import json
from collections.abc import Iterator
from typing import Any

import requests

from app.ai.base import AIProvider, AIProviderError
from app.ai.parsing import normalise_questions, parse_json_array, parse_json_object
from app.core.config import settings
from app.rag.prompts import QUESTION_AUTHOR_SYSTEM_PROMPT, build_question_prompt


class LocalLLMProvider(AIProvider):
    """AI provider backed by a local Ollama runtime."""

    name = "local"

    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.embed_model = settings.OLLAMA_EMBED_MODEL
        self.keep_alive = settings.OLLAMA_KEEP_ALIVE
        self.num_thread = settings.OLLAMA_NUM_THREAD
        self._dim = settings.EMBEDDING_DIM

    def _options(self, temperature: float) -> dict[str, Any]:
        """Inference options shared by generate and stream."""
        options: dict[str, Any] = {"temperature": temperature}
        if self.num_thread > 0:
            options["num_thread"] = self.num_thread
        return options

    # ----------------------------------------------------------------- helpers
    @property
    def embedding_dim(self) -> int:
        return self._dim

    def _post(self, path: str, payload: dict[str, Any], stream: bool = False):
        try:
            resp = requests.post(
                f"{self.base_url}{path}", json=payload, stream=stream, timeout=300
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError as exc:
            raise AIProviderError(
                f"Local LLM (Ollama) is not reachable at {self.base_url}. "
                "Ensure Ollama is running (`ollama serve`)."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise AIProviderError("Ollama request timed out.") from exc
        except requests.exceptions.HTTPError as exc:
            detail = resp.text[:300] if resp is not None else str(exc)
            raise AIProviderError(f"Ollama returned an error: {detail}") from exc

    def health(self) -> bool:
        try:
            requests.get(f"{self.base_url}/api/tags", timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    # ---------------------------------------------------------------- generate
    def generate(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> str:
        user_content = f"{context}\n\n{prompt}" if context else prompt
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": self._options(temperature),
        }
        resp = self._post("/api/chat", payload)
        data = resp.json()
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AIProviderError("Malformed response received from Ollama.") from exc

    def stream(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> Iterator[str]:
        user_content = f"{context}\n\n{prompt}" if context else prompt
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": self._options(temperature),
        }
        resp = self._post("/api/chat", payload, stream=True)
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = chunk.get("message", {}).get("content")
            if piece:
                yield piece
            if chunk.get("done"):
                break

    # ------------------------------------------------------------------- embed
    def _validate(self, vector: list[float]) -> list[float]:
        if not vector:
            raise AIProviderError("Ollama returned an empty embedding.")
        if len(vector) != self._dim:
            raise AIProviderError(
                f"Embedding dimension mismatch: model '{self.embed_model}' returned "
                f"{len(vector)} values but EMBEDDING_DIM is {self._dim}. "
                "Update EMBEDDING_DIM and the vector column, then re-ingest documents."
            )
        return vector

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed several texts in one request.

        Uses ``/api/embed`` rather than the legacy ``/api/embeddings`` because it
        accepts a list of inputs and, with ``truncate``, clips any text that
        exceeds the model's context window instead of failing the request. A
        single over-long chunk would otherwise abort a whole document's
        ingestion.
        """
        if not texts:
            return []
        payload = {
            "model": self.embed_model,
            "input": texts,
            "truncate": True,
            "keep_alive": self.keep_alive,
        }
        data = self._post("/api/embed", payload).json()
        vectors = data.get("embeddings") or []
        if len(vectors) != len(texts):
            raise AIProviderError(
                f"Ollama returned {len(vectors)} embeddings for {len(texts)} inputs."
            )
        return [self._validate(vector) for vector in vectors]

    # ------------------------------------------------------------ evaluations
    def evaluate_answer(self, question: str, answer: str, context: str = "") -> dict[str, Any]:
        system = (
            "You are an expert examiner evaluating a candidate's answer. "
            "Respond ONLY with valid JSON using the keys: "
            "strengths (list of strings), weaknesses (list), missing_points (list), "
            "clarity (string), accuracy (string), relevance (string), "
            "suggested_answer (string), follow_up (string)."
        )
        prompt = f"Question:\n{question}\n\nCandidate answer:\n{answer}\n"
        if context:
            prompt += f"\nReference material:\n{context}\n"
        raw = self.generate(prompt=prompt, system_prompt=system)
        return parse_json_object(raw) or {"feedback": raw.strip()}

    def generate_questions(
        self,
        topic: str,
        count: int,
        difficulty: str = "medium",
        question_type: str = "mcq",
        context: str = "",
    ) -> list[dict[str, Any]]:
        prompt = build_question_prompt(topic, count, difficulty, question_type, context)
        raw = self.generate(
            prompt=prompt, system_prompt=QUESTION_AUTHOR_SYSTEM_PROMPT, temperature=0.5
        )
        return normalise_questions(parse_json_array(raw))

