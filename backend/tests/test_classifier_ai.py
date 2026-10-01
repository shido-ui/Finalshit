import json
import pytest

from app.knowledge.classifier import KeywordTaxonomyClassifier
from app.knowledge.classifier_ai import (
    GeminiQuestionClassificationProvider,
    HybridQuestionClassifier,
    QuestionClassificationCandidate,
)
from app.knowledge.models import QuestionCandidate
from app.knowledge.taxonomy import Taxonomy, TaxonomyNode


def taxonomy() -> Taxonomy:
    return Taxonomy(
        [
            TaxonomyNode("physics", "Physics", "subject"),
            TaxonomyNode("physics.c05", "Rotational Motion", "chapter", "physics"),
            TaxonomyNode(
                "physics.c05.t02",
                "Torque and angular momentum",
                "topic",
                "physics.c05",
            ),
            TaxonomyNode(
                "physics.c05.t02.s01",
                "Angular momentum conservation",
                "subtopic",
                "physics.c05.t02",
            ),
            TaxonomyNode("chemistry", "Chemistry", "subject"),
        ]
    )


def question(text: str) -> QuestionCandidate:
    return QuestionCandidate(
        id="q1",
        document_id="doc",
        page_start=1,
        page_end=1,
        text=text,
    )


class FakeProvider:
    name = "fake-ai-v1"

    def __init__(self, result: QuestionClassificationCandidate | Exception):
        self.result = result

    def classify(self, question_text: str, taxonomy: Taxonomy):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_ai_result_must_reference_existing_taxonomy():
    classifier = HybridQuestionClassifier(
        provider=FakeProvider(
            QuestionClassificationCandidate(
                taxonomy_node_id="does-not-exist",
                confidence=0.99,
                evidence="invented",
            )
        ),
        fallback=KeywordTaxonomyClassifier({"physics": ("force", "velocity")}),
    )

    result = classifier.classify(question("A force changes the velocity of the body."), taxonomy())

    assert result.taxonomy_node_id == "physics"
    assert result.quarantined is False
    assert "fallback" in result.reason.lower()


def test_high_confidence_ai_classification_can_use_dynamic_subtopic():
    classifier = HybridQuestionClassifier(
        provider=FakeProvider(
            QuestionClassificationCandidate(
                taxonomy_node_id="physics.c05.t02.s01",
                confidence=0.94,
                evidence="The question explicitly asks about conservation of angular momentum.",
            )
        )
    )

    result = classifier.classify(
        question("Use conservation of angular momentum to find the final speed."),
        taxonomy(),
    )

    assert result.taxonomy_node_id == "physics.c05.t02.s01"
    assert result.confidence == pytest.approx(0.94)
    assert result.quarantined is False
    assert "AI evidence" in result.reason


def test_low_confidence_ai_result_uses_strong_deterministic_fallback():
    classifier = HybridQuestionClassifier(
        provider=FakeProvider(
            QuestionClassificationCandidate(
                taxonomy_node_id="physics.c05",
                confidence=0.45,
                evidence="Weak evidence.",
            )
        ),
        fallback=KeywordTaxonomyClassifier(
            {"physics": ("force", "velocity")},
            minimum_confidence=0.80,
        ),
    )

    result = classifier.classify(
        question("Find the force and velocity."),
        taxonomy(),
    )

    assert result.taxonomy_node_id == "physics"
    assert result.quarantined is False
    assert "fallback" in result.reason.lower()


def test_unavailable_ai_without_strong_fallback_is_quarantined():
    classifier = HybridQuestionClassifier(
        provider=FakeProvider(RuntimeError("provider unavailable")),
        fallback=KeywordTaxonomyClassifier({"physics": ("force",)}),
    )

    result = classifier.classify(question("Solve this problem."), taxonomy())

    assert result.taxonomy_node_id is None
    assert result.quarantined is True
    assert result.confidence == 0.0
    assert "unavailable" in result.reason.lower()


def test_ai_null_classification_is_quarantined_when_fallback_is_weak():
    classifier = HybridQuestionClassifier(
        provider=FakeProvider(
            QuestionClassificationCandidate(
                taxonomy_node_id=None,
                confidence=0.31,
                evidence="The question does not provide enough topic-specific evidence.",
            )
        ),
        fallback=KeywordTaxonomyClassifier({"physics": ("force",)}),
    )

    result = classifier.classify(question("Solve this problem."), taxonomy())

    assert result.taxonomy_node_id is None
    assert result.quarantined is True
    assert result.confidence == pytest.approx(0.31)


def test_gemini_provider_parses_structured_response(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "taxonomy_node_id": "physics.c05.t02.s01",
                                                "confidence": 0.91,
                                                "evidence": "Angular momentum is explicitly conserved.",
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode()

    response = FakeResponse()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return response

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.knowledge.classifier_ai.urllib.request.urlopen",
        fake_urlopen,
    )

    provider = GeminiQuestionClassificationProvider(timeout_seconds=7.0)
    result = provider.classify(
        "A question about conservation of angular momentum.",
        taxonomy(),
    )

    assert result.taxonomy_node_id == "physics.c05.t02.s01"
    assert result.confidence == pytest.approx(0.91)
    assert captured["timeout"] == 7.0
    assert captured["request"].headers["X-goog-api-key"] == "test-key"
    body = json.loads(captured["request"].data.decode())
    prompt = body["contents"][0]["parts"][0]["text"]
    assert "physics.c05.t02.s01" in prompt
    assert "Never invent" in prompt


def test_gemini_provider_requires_server_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiQuestionClassificationProvider()

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        provider.classify("Question", taxonomy())
