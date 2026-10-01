from pydantic import BaseModel, Field

class CopilotCandidate(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    citations: list[int] = Field(default_factory=list, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=2000)


import json
import os
import urllib.error
import urllib.request
from typing import Protocol


class CopilotProvider(Protocol):
    name: str
    def answer(self, question: str, source_pages: dict[int, str]) -> CopilotCandidate: ...


class GeminiStudyCopilotProvider:
    name = "gemini-study-copilot-v1"

    def __init__(self, model: str | None = None, timeout_seconds: int = 30) -> None:
        self.model = model or os.getenv("GEMINI_COPILOT_MODEL", "gemini-3-flash")
        self.timeout_seconds = timeout_seconds

    def answer(self, question: str, source_pages: dict[int, str]) -> CopilotCandidate:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        context = "\n\n".join(
            f"[PAGE {page}]\n{text[:12000]}" for page, text in sorted(source_pages.items())
        )
        prompt = f"""Answer the supplied question using ONLY the supplied study-source pages.

QUESTION:
{question[:12000]}

SOURCE PAGES:
{context[:60000]}

RULES:
- Use only information supported by the supplied pages.
- Do not invent facts, equations, examples, citations, or page numbers.
- If the sources are insufficient, say so and lower confidence.
- citations may contain only supplied page numbers directly supporting the answer.
- Do not claim external sources were checked.
- Return JSON only."""

        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "citations": {"type": "array", "items": {"type": "integer"}},
                "confidence": {"type": "number"},
                "evidence": {"type": "string"},
            },
            "required": ["answer", "citations", "confidence", "evidence"],
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode())
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            return CopilotCandidate.model_validate(json.loads(text))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Study Copilot provider failed: {exc}") from exc


class StudyCopilot:
    def __init__(self, provider: CopilotProvider) -> None:
        self.provider = provider

    def answer(self, question: str, source_pages: dict[int, str]) -> CopilotCandidate:
        if not question.strip():
            raise ValueError("Copilot question is empty")
        if not source_pages or not any(text.strip() for text in source_pages.values()):
            raise ValueError("No usable source text is available")
        candidate = self.provider.answer(question, source_pages)
        if any(page not in source_pages for page in candidate.citations):
            raise ValueError("Copilot cited a page outside supplied provenance")
        if not candidate.answer.strip():
            raise ValueError("Copilot returned an empty answer")
        if not candidate.citations:
            raise ValueError("Copilot returned no source citations")
        return candidate


def default_copilot_provider() -> GeminiStudyCopilotProvider:
    return GeminiStudyCopilotProvider()
