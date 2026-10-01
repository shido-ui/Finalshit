from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from .models import Provenance, QuestionCandidate, Solution, SolutionStatus


class SolutionCandidate(BaseModel):
    answer: str | None = None
    method: str = Field(min_length=1, max_length=4000)
    steps: list[str] = Field(min_length=1, max_length=100)
    final_answer: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_pages: list[int] = Field(default_factory=list)
    evidence: str = Field(min_length=1, max_length=2000)


class SolutionProvider(Protocol):
    name: str

    def generate(self, question: QuestionCandidate, source_pages: dict[int, str]) -> SolutionCandidate:
        ...


class GeminiSolutionProvider:
    name = "gemini-solution-v1"

    def __init__(self, model: str | None = None, timeout_seconds: int = 30) -> None:
        self.model = model or os.getenv("GEMINI_SOLUTION_MODEL", "gemini-3-flash")
        self.timeout_seconds = timeout_seconds

    def generate(self, question: QuestionCandidate, source_pages: dict[int, str]) -> SolutionCandidate:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        page_context = "\n\n".join(
            f"[PAGE {page}]\n{text[:12000]}" for page, text in sorted(source_pages.items())
        )
        prompt = f"""Generate a structured solution for this extracted educational question.

QUESTION:
{question.text[:16000]}

SOURCE PAGES:
{page_context[:60000]}

STRICT RULES:
1. Use only the supplied question and source pages as grounding.
2. Do not invent facts, answer keys, equations, diagrams, or source claims.
3. If the supplied material does not contain enough information to justify a solution, return low confidence and say what is missing.
4. Give concise, ordered reasoning steps.
5. The final_answer must directly answer the question.
6. For multiple-choice questions, answer must be the option label only when the source/question supports it; otherwise null.
7. evidence_pages must contain only supplied page numbers that materially support the solution.
8. Never claim a source page was consulted if it was not supplied.
9. Return JSON only matching the requested schema."""

        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "nullable": True},
                "method": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
                "final_answer": {"type": "string"},
                "confidence": {"type": "number"},
                "evidence_pages": {"type": "array", "items": {"type": "integer"}},
                "evidence": {"type": "string"},
            },
            "required": ["method", "steps", "final_answer", "confidence", "evidence_pages", "evidence"],
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
            return SolutionCandidate.model_validate(json.loads(text))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Solution AI provider failed: {exc}") from exc


@dataclass(frozen=True)
class SolutionValidation:
    valid: bool
    reason: str


class SolutionValidator:
    def validate(
        self,
        question: QuestionCandidate,
        candidate: SolutionCandidate,
        source_pages: dict[int, str],
    ) -> SolutionValidation:
        if not candidate.steps:
            return SolutionValidation(False, "Solution has no reasoning steps")
        if not candidate.final_answer.strip():
            return SolutionValidation(False, "Solution has no final answer")
        if any(page not in source_pages for page in candidate.evidence_pages):
            return SolutionValidation(False, "Solution cites a page outside supplied provenance")
        if candidate.confidence < 0.50:
            return SolutionValidation(False, "Solution confidence is below verification threshold")
        if question.options and candidate.answer is not None:
            label = candidate.answer.strip().upper()
            if label not in question.options:
                return SolutionValidation(False, f"Solution answer option {label!r} is not an extracted option")
        return SolutionValidation(True, "Structural and provenance validation passed")


class SolutionEngine:
    def __init__(
        self,
        provider: SolutionProvider,
        validator: SolutionValidator | None = None,
    ) -> None:
        self.provider = provider
        self.validator = validator or SolutionValidator()

    def generate(
        self,
        question: QuestionCandidate,
        source_pages: dict[int, str],
    ) -> Solution:
        candidate = self.provider.generate(question, source_pages)
        validation = self.validator.validate(question, candidate, source_pages)
        status = SolutionStatus.VERIFIED if validation.valid else SolutionStatus.REJECTED
        provenance = [
            Provenance(
                document_id=question.document_id,
                page_number=page,
                source_hash=item.source_hash,
                extractor=item.extractor,
            )
            for page in sorted(set(candidate.evidence_pages))
            for item in question.provenance
            if item.page_number == page
        ]
        return Solution(
            id=f"{question.id}-solution",
            question_id=question.id,
            document_id=question.document_id,
            answer=candidate.answer,
            method=candidate.method,
            steps=candidate.steps,
            final_answer=candidate.final_answer,
            confidence=candidate.confidence,
            status=status,
            provider=self.provider.name,
            validation_reason=validation.reason,
            provenance=provenance,
        )


def default_solution_provider() -> GeminiSolutionProvider:
    return GeminiSolutionProvider()
