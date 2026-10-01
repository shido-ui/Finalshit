from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from .classifier import ClassificationResult, DEFAULT_CLASSIFIER, QuestionClassifier
from .models import QuestionCandidate
from .taxonomy import Taxonomy


class QuestionClassificationCandidate(BaseModel):
    """Untrusted structured output from an external AI provider."""

    taxonomy_node_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=1000)


class QuestionClassificationProvider(Protocol):
    name: str

    def classify(
        self,
        question_text: str,
        taxonomy: Taxonomy,
    ) -> QuestionClassificationCandidate: ...


@dataclass(frozen=True)
class GeminiQuestionClassificationProvider:
    """Gemini provider for selecting an existing controlled taxonomy node."""

    api_key: str | None = None
    model: str | None = None
    timeout_seconds: float = 20.0
    name: str = "gemini-question-classifier-v1"

    def __post_init__(self) -> None:
        if self.api_key is None:
            object.__setattr__(self, "api_key", os.getenv("GEMINI_API_KEY"))
        if self.model is None:
            object.__setattr__(
                self,
                "model",
                os.getenv("GEMINI_QUESTION_CLASSIFICATION_MODEL", "gemini-3-flash"),
            )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def classify(
        self,
        question_text: str,
        taxonomy: Taxonomy,
    ) -> QuestionClassificationCandidate:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        nodes = [
            {
                "id": node.id,
                "name": node.name,
                "level": node.level,
                "parent_id": node.parent_id,
            }
            for node in taxonomy.all()
        ]
        prompt = self._build_prompt(question_text, nodes)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "taxonomy_node_id": {"type": "STRING", "nullable": True},
                        "confidence": {"type": "NUMBER"},
                        "evidence": {"type": "STRING"},
                    },
                    "required": ["confidence", "evidence"],
                },
            },
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        request = urllib.request.Request(
            url,
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
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(
                        f"Gemini question classification request failed (HTTP {exc.code})"
                    ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == 2:
                    raise RuntimeError("Gemini question classification request failed") from exc
            time.sleep(0.5 * (2 ** attempt))
        else:
            raise RuntimeError("Gemini question classification request failed") from last_error

        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            decoded = json.loads(text)
            return QuestionClassificationCandidate.model_validate(decoded)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(
                "Gemini returned an invalid question classification response"
            ) from exc

    @staticmethod
    def _build_prompt(
        question_text: str,
        nodes: list[dict[str, str | None]],
    ) -> str:
        taxonomy_json = json.dumps(
            nodes,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return f"""
You are FocusForge's controlled JEE question classifier.

Classify the supplied question using ONLY the provided taxonomy registry.

Rules:
1. Return an exact taxonomy_node_id from the supplied registry, or null if
   there is not enough evidence.
2. Prefer the most specific supported node: subtopic over topic, topic over
   chapter, chapter over subject.
3. Never invent, modify, normalize, or guess a taxonomy ID.
4. The selected node must be directly supported by the question's content.
5. Do not classify from answer-option wording alone.
6. If two or more taxonomy branches are similarly plausible, return null and
   use a lower confidence.
7. Confidence measures evidence strength for the selected node.
8. Evidence must briefly explain the terms, concepts, or equations in the
   question that support the selection.
9. Return only JSON matching the requested schema.

Taxonomy registry:
{taxonomy_json}

Question:
{question_text[:12000]}
""".strip()


@dataclass(frozen=True)
class HybridQuestionClassifier:
    """AI-first classifier with a deterministic safety fallback.

    The fallback keeps document ingestion usable when Gemini is unavailable,
    while the AI result can use the full dynamic taxonomy when configured.
    """

    provider: QuestionClassificationProvider
    fallback: QuestionClassifier = DEFAULT_CLASSIFIER
    minimum_confidence: float = 0.80

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")

    def classify(
        self,
        question: QuestionCandidate,
        taxonomy: Taxonomy,
    ) -> ClassificationResult:
        try:
            candidate = self.provider.classify(question.text, taxonomy)
            node = (
                taxonomy.get(candidate.taxonomy_node_id)
                if candidate.taxonomy_node_id is not None
                else None
            )

            if candidate.taxonomy_node_id is not None and node is None:
                raise RuntimeError("AI returned an unknown taxonomy node")

            if node is not None and candidate.confidence >= self.minimum_confidence:
                return ClassificationResult(
                    taxonomy_node_id=node.id,
                    confidence=candidate.confidence,
                    reason=f"AI evidence: {candidate.evidence.strip()}",
                    quarantined=False,
                )

            ai_reason = (
                f"AI confidence {candidate.confidence:.2f} is below the "
                f"{self.minimum_confidence:.2f} threshold"
            )
            fallback_result = self.fallback.classify(question, taxonomy)
            if not fallback_result.quarantined:
                return ClassificationResult(
                    taxonomy_node_id=fallback_result.taxonomy_node_id,
                    confidence=fallback_result.confidence,
                    reason=f"Deterministic fallback after {ai_reason}",
                    quarantined=False,
                )
            return ClassificationResult(
                taxonomy_node_id=None,
                confidence=candidate.confidence,
                reason=f"{ai_reason}; {candidate.evidence.strip()}",
                quarantined=True,
            )
        except RuntimeError as exc:
            fallback_result = self.fallback.classify(question, taxonomy)
            if not fallback_result.quarantined:
                return ClassificationResult(
                    taxonomy_node_id=fallback_result.taxonomy_node_id,
                    confidence=fallback_result.confidence,
                    reason=f"Deterministic fallback: {exc}",
                    quarantined=False,
                )
            return ClassificationResult(
                taxonomy_node_id=None,
                confidence=0.0,
                reason=f"AI classifier unavailable; {fallback_result.reason}",
                quarantined=True,
            )


def default_question_classifier() -> HybridQuestionClassifier:
    return HybridQuestionClassifier(
        provider=GeminiQuestionClassificationProvider(),
        fallback=DEFAULT_CLASSIFIER,
    )
