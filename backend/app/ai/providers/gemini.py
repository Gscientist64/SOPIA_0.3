import json
from collections.abc import Iterator
from typing import Any

import requests

from app.ai.base import AIProvider, AIProviderError
from app.ai.parsing import normalise_questions, parse_json_array
from app.core.config import settings

# Known output dimension for Google's text-embedding-004 model.
GEMINI_EMBED_DIM = 768


def _strip_code_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


class GeminiProvider(AIProvider):
    """Optional AI provider backed by the Google Gemini API."""

    name = "gemini"

    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.embed_model = settings.GEMINI_EMBED_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def embedding_dim(self) -> int:
        return GEMINI_EMBED_DIM

    def _ensure_key(self) -> None:
        if not self.api_key:
            raise AIProviderError(
                "AI_PROVIDER is set to 'gemini' but GEMINI_API_KEY is not configured. "
                "Set GEMINI_API_KEY in your .env file or switch AI_PROVIDER back to 'local'."
            )

    def _payload(self, prompt: str, context: str, system_prompt: str, temperature: float) -> dict:
        full_text = f"{context}\n\n{prompt}" if context else prompt
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": full_text}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    def generate(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> str:
        self._ensure_key()
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        try:
            resp = requests.post(
                url, json=self._payload(prompt, context, system_prompt, temperature), timeout=120
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise AIProviderError(f"Gemini request failed: {exc}") from exc
        try:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("Could not parse response from Gemini.") from exc

    def stream(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> Iterator[str]:
        self._ensure_key()
        url = (
            f"{self.base_url}/models/{self.model}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )
        try:
            resp = requests.post(
                url,
                json=self._payload(prompt, context, system_prompt, temperature),
                stream=True,
                timeout=180,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise AIProviderError(f"Gemini stream failed: {exc}") from exc

        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8") if isinstance(line, bytes) else line
            if not text.startswith("data:"):
                continue
            data = text[len("data:") :].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                yield chunk["candidates"][0]["content"]["parts"][0]["text"]
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                continue

    def embed(self, text: str) -> list[float]:
        self._ensure_key()
        url = f"{self.base_url}/models/{self.embed_model}:embedContent?key={self.api_key}"
        payload = {"model": f"models/{self.embed_model}", "content": {"parts": [{"text": text}]}}
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]
        except (requests.exceptions.RequestException, KeyError) as exc:
            raise AIProviderError(f"Gemini embedding failed: {exc}") from exc

    def evaluate_answer(self, question: str, answer: str, context: str = "") -> dict[str, Any]:
        system = (
            "You are an expert examiner evaluating a candidate's answer. "
            "Respond ONLY with valid JSON using the keys: strengths, weaknesses, "
            "missing_points, clarity, accuracy, relevance, suggested_answer, follow_up."
        )
        prompt = f"Question:\n{question}\n\nCandidate answer:\n{answer}\n"
        if context:
            prompt += f"\nReference material:\n{context}\n"
        raw = self.generate(prompt=prompt, system_prompt=system)
        try:
            return json.loads(_strip_code_fence(raw))
        except json.JSONDecodeError:
            return {"feedback": raw.strip()}

    def generate_questions(
        self, topic: str, count: int, difficulty: str = "medium", question_type: str = "mcq"
    ) -> list[dict[str, Any]]:
        system = (
            "You are an assessment author. Respond ONLY with a valid JSON array, no prose. "
            "Each item must use exactly these keys: prompt, question_type, options (array), "
            "correct_answer, explanation, topic, difficulty.\n"
            'Example: [{"prompt": "What is 2 + 2?", "question_type": "mcq", '
            '"options": ["3", "4", "5"], "correct_answer": "4", '
            '"explanation": "Basic addition.", "topic": "Maths", "difficulty": "easy"}]'
        )
        prompt = f"Create {count} distinct {difficulty} {question_type} questions about: {topic}."
        raw = self.generate(prompt=prompt, system_prompt=system, temperature=0.5)
        return normalise_questions(parse_json_array(raw))

