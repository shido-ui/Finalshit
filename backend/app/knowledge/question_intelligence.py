from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from .extractor import OPTION_LINE
from .models import QuestionCandidate


class QuestionIntelligenceCandidate(BaseModel):
    options: dict[str, str] = Field(default_factory=dict)
    answer: str | None = None
    solution: str | None = None
    has_diagram: bool = False
    has_table: bool = False
    exam: str | None = None
    exam_year: int | None = Field(default=None, ge=1900, le=2100)
    difficulty: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=1200)


class QuestionIntelligenceProvider(Protocol):
    name: str

    def analyze(self, question_text: str) -> QuestionIntelligenceCandidate: ...


def _validate_candidate(candidate: QuestionIntelligenceCandidate) -> QuestionIntelligenceCandidate:
    difficulty = candidate.difficulty.casefold().strip() if candidate.difficulty else None
    if difficulty not in {None, "easy", "medium", "hard"}:
        difficulty = None

    options = {
        key.upper(): value.strip()
        for key, value in candidate.options.items()
        if key.upper() in {"A", "B", "C", "D"} and value.strip()
    }
    answer = candidate.answer.strip() if candidate.answer else None
    if answer and len(answer) > 1000:
        answer = answer[:1000]

    return candidate.model_copy(
        update={
            "options": options,
            "answer": answer,
            "solution": candidate.solution.strip() if candidate.solution else None,
            "difficulty": difficulty,
            "exam": candidate.exam.strip() if candidate.exam else None,
            "evidence": candidate.evidence.strip(),
        }
    )


@dataclass(frozen=True)
class HeuristicQuestionIntelligenceProvider:
    name: str = "heuristic-question-intelligence-v1"

    def analyze(self, question_text: str) -> QuestionIntelligenceCandidate:
        options: dict[str, str] = {}
        lines = question_text.splitlines()
        option_pattern = re.compile(r"^\s*[(\[]?([A-Da-d])[)\].:]\s+(.+?)\s*$")
        for line in lines:
            match = option_pattern.match(line)
            if match:
                options[match.group(1).upper()] = match.group(2).strip()

        lower = question_text.casefold()
        has_table = bool(re.search(r"\b(table|tabular|rows?\s+and\s+columns?)\b", lower))
        has_diagram = bool(re.search(r"\b(figure|fig\.?|diagram|shown\s+below|shown\s+in)\b", lower))
        exam = None
        exam_year = None
        match = re.search(r"\b(JEE\s*(?:Main|Advanced)|NEET|BITSAT)\b(?:[^\n]{0,30})?(20\d{2})?", question_text, re.I)
        if match:
            exam = re.sub(r"\s+", " ", match.group(1)).strip()
            exam_year = int(match.group(2)) if match.group(2) else None

        return QuestionIntelligenceCandidate(
            options=options,
            has_diagram=has_diagram,
            has_table=has_table,
            confidence=0.75 if options else 0.55,
            evidence="Deterministic extraction of explicit question metadata",
        )


@dataclass(frozen=True)
class GeminiQuestionIntelligenceProvider:
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: float = 20.0
    name: str = "gemini-question-intelligence-v1"

    def __post_init__(self) -> None:
        if self.api_key is None:
            object.__setattr__(self, "api_key", os.getenv("GEMINI_API_KEY"))
        if self.model is None:
            object.__setattr__(
                self,
                "model",
                os.getenv("GEMINI_QUESTION_INTELLIGENCE_MODEL", "gemini-3-flash"),
            )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def analyze(self, question_text: str) -> QuestionIntelligenceCandidate:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        prompt = f"""
You are FocusForge's structured educational question analyzer.

Extract ONLY information supported by the supplied question text.

Rules:
1. Extract answer options only when explicitly present.
2. Extract an answer only when explicitly present; never solve the question.
3. Extract a solution only when an explicit solution/explanation is present;
   never invent one.
4. Detect diagrams/tables only from explicit textual evidence.
5. Extract exam and year only when explicitly stated.
6. Difficulty may be easy, medium, hard, or null. Use null when unsupported.
7. Confidence measures extraction evidence, not whether the question itself is correct.
8. Evidence must explain what text supports the extracted metadata.
9. Return only JSON matching the schema.

Question:
{question_text[:12000]}
""".strip()

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "options": {
                            "type": "OBJECT",
                            "additionalProperties": {"type": "STRING"},
                        },
                        "answer": {"type": "STRING", "nullable": True},
                        "solution": {"type": "STRING", "nullable": True},
                        "has_diagram": {"type": "BOOLEAN"},
                        "has_table": {"type": "BOOLEAN"},
                        "exam": {"type": "STRING", "nullable": True},
                        "exam_year": {"type": "INTEGER", "nullable": True},
                        "difficulty": {
                            "type": "STRING",
                            "enum": ["easy", "medium", "hard"],
                            "nullable": True,
                        },
                        "confidence": {"type": "NUMBER"},
                        "evidence": {"type": "STRING"},
                    },
                    "required": ["options", "confidence", "evidence"],
                },
            },
        }
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(
                        f"Gemini question intelligence request failed (HTTP {exc.code})"
                    ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == 2:
                    raise RuntimeError("Gemini question intelligence request failed") from exc
            time.sleep(0.5 * (2 ** attempt))
        else:
            raise RuntimeError("Gemini question intelligence request failed") from last_error
        try:
            body
        except NameError as exc:
            raise RuntimeError("Gemini question intelligence request failed") from exc

        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            return QuestionIntelligenceCandidate.model_validate(json.loads(text))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError("Gemini returned invalid question intelligence") from exc


@dataclass(frozen=True)
class HybridQuestionIntelligence:
    provider: QuestionIntelligenceProvider
    fallback: QuestionIntelligenceProvider = HeuristicQuestionIntelligenceProvider()

    def analyze(self, question: QuestionCandidate) -> QuestionCandidate:
        try:
            candidate = _validate_candidate(self.provider.analyze(question.text))
            provider_name = self.provider.name
        except RuntimeError:
            candidate = _validate_candidate(self.fallback.analyze(question.text))
            provider_name = self.fallback.name

        return question.model_copy(
            update={
                "options": candidate.options,
                "answer": candidate.answer,
                "solution": candidate.solution,
                "has_diagram": candidate.has_diagram,
                "has_table": candidate.has_table,
                "exam": candidate.exam,
                "exam_year": candidate.exam_year,
                "difficulty": candidate.difficulty,
                "intelligence_confidence": candidate.confidence,
                "intelligence_reason": candidate.evidence,
                "intelligence_provider": provider_name,
            }
        )


def default_question_intelligence() -> HybridQuestionIntelligence:
    return HybridQuestionIntelligence(provider=GeminiQuestionIntelligenceProvider())
