import json
from types import SimpleNamespace

import pytest

from app.knowledge.models import QuestionCandidate
from app.knowledge.question_intelligence import (
    GeminiQuestionIntelligenceProvider,
    HeuristicQuestionIntelligenceProvider,
    HybridQuestionIntelligence,
    QuestionIntelligenceCandidate,
)


def question(text: str) -> QuestionCandidate:
    return QuestionCandidate(
        id="q1",
        document_id="doc",
        page_start=1,
        page_end=1,
        text=text,
    )


def test_heuristic_extracts_explicit_options_and_visual_markers():
    result = HeuristicQuestionIntelligenceProvider().analyze(
        "1. Which value is correct?\n"
        "(A) 10\n(B) 20\n(C) 30\n(D) 40\n"
        "Refer to the diagram shown below."
    )

    assert result.options == {"A": "10", "B": "20", "C": "30", "D": "40"}
    assert result.has_diagram is True
    assert result.has_table is False
    assert result.confidence >= 0.75


def test_hybrid_provider_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    analyzer = HybridQuestionIntelligence(
        provider=GeminiQuestionIntelligenceProvider(),
    )

    result = analyzer.analyze(
        question("1. Choose the correct option.\n(A) 1\n(B) 2\n(C) 3\n(D) 4")
    )

    assert result.options == {"A": "1", "B": "2", "C": "3", "D": "4"}
    assert result.intelligence_provider == "heuristic-question-intelligence-v1"
    assert result.intelligence_confidence >= 0.75
    assert result.intelligence_reason


def test_candidate_validation_removes_unsupported_option_keys():
    candidate = QuestionIntelligenceCandidate(
        options={"A": "one", "X": "ignore"},
        confidence=0.9,
        evidence="Options are explicitly present.",
    )
    assert candidate.options["X"] == "ignore"

    analyzer = HybridQuestionIntelligence(
        provider=SimpleNamespace(
            name="fake",
            analyze=lambda _: candidate,
        )
    )
    result = analyzer.analyze(question("Question"))
    assert result.options == {"A": "one"}


def test_gemini_provider_parses_structured_metadata(monkeypatch):
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
                                                "options": {
                                                    "A": "10",
                                                    "B": "20",
                                                    "C": "30",
                                                    "D": "40",
                                                },
                                                "answer": "C",
                                                "solution": "Explicit solution text.",
                                                "has_diagram": True,
                                                "has_table": False,
                                                "exam": "JEE Main",
                                                "exam_year": 2026,
                                                "difficulty": "medium",
                                                "confidence": 0.93,
                                                "evidence": "Options, answer, exam, and year are explicitly present.",
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.knowledge.question_intelligence.urllib.request.urlopen",
        fake_urlopen,
    )

    provider = GeminiQuestionIntelligenceProvider(timeout_seconds=8)
    result = provider.analyze("JEE Main 2026 question with options.")

    assert result.answer == "C"
    assert result.exam == "JEE Main"
    assert result.exam_year == 2026
    assert result.difficulty == "medium"
    assert result.has_diagram is True
    assert result.confidence == pytest.approx(0.93)
    assert captured["timeout"] == 8
    body = json.loads(captured["request"].data.decode())
    assert "never solve" in body["contents"][0]["parts"][0]["text"].lower()


def test_store_round_trips_structured_intelligence(tmp_path):
    from app.knowledge.store import KnowledgeStore

    store = KnowledgeStore(tmp_path / "knowledge.db")
    from app.knowledge.models import DocumentRecord, ProcessingStatus

    store.save_document(
        DocumentRecord(
            id="doc",
            filename="x.pdf",
            sha256="hash",
            page_count=1,
            status=ProcessingStatus.READY,
        )
    )
    item = question("Question?")
    item = item.model_copy(
        update={
            "options": {"A": "1", "B": "2"},
            "answer": "A",
            "solution": "x",
            "has_diagram": True,
            "has_table": True,
            "exam": "JEE Main",
            "exam_year": 2026,
            "difficulty": "hard",
            "intelligence_confidence": 0.91,
            "intelligence_reason": "explicit metadata",
            "intelligence_provider": "fake",
        }
    )
    store.replace_questions("doc", [item])
    restored = store.get_questions("doc")[0]

    assert restored.options == {"A": "1", "B": "2"}
    assert restored.answer == "A"
    assert restored.solution == "x"
    assert restored.has_diagram is True
    assert restored.has_table is True
    assert restored.exam == "JEE Main"
    assert restored.exam_year == 2026
    assert restored.difficulty == "hard"
    assert restored.intelligence_confidence == pytest.approx(0.91)
    assert restored.intelligence_provider == "fake"
