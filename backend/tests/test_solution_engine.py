import json

import pytest

from app.knowledge.models import Provenance, QuestionCandidate
from app.knowledge.solution_engine import (
    GeminiSolutionProvider,
    SolutionCandidate,
    SolutionEngine,
    SolutionValidator,
)


def question() -> QuestionCandidate:
    return QuestionCandidate(
        id="q1",
        document_id="doc",
        page_start=1,
        page_end=1,
        text="Which value is correct? (A) 1 (B) 2",
        options={"A": "1", "B": "2"},
        provenance=[],
    )


def candidate(**updates) -> SolutionCandidate:
    data = {
        "answer": "A",
        "method": "Direct evaluation",
        "steps": ["Evaluate the supplied expression."],
        "final_answer": "1",
        "confidence": 0.9,
        "evidence_pages": [1],
        "evidence": "Question is on page 1.",
    }
    data.update(updates)
    return SolutionCandidate(**data)


def test_validator_accepts_grounded_structured_solution():
    q = question().model_copy(
        update={
            "provenance": [
                Provenance(document_id="doc", page_number=1, source_hash="h", extractor="test")
            ]
        }
    )
    result = SolutionValidator().validate(q, candidate(), {1: "question"})
    assert result.valid is True


def test_validator_rejects_unknown_option():
    q = question()
    result = SolutionValidator().validate(q, candidate(answer="C"), {1: "question"})
    assert result.valid is False
    assert "not an extracted option" in result.reason


def test_validator_rejects_unprovenanced_page():
    result = SolutionValidator().validate(question(), candidate(evidence_pages=[2]), {1: "question"})
    assert result.valid is False


def test_validator_rejects_low_confidence():
    result = SolutionValidator().validate(question(), candidate(confidence=0.49), {1: "question"})
    assert result.valid is False


def test_validator_requires_source_evidence():
    result = SolutionValidator().validate(question(), candidate(evidence_pages=[]), {1: "question"})
    assert result.valid is False


def test_engine_marks_valid_solution_verified():
    q = question().model_copy(
        update={
            "provenance": [
                Provenance(document_id="doc", page_number=1, source_hash="hash", extractor="test")
            ]
        }
    )

    class FakeProvider:
        name = "fake-solution"

        def generate(self, question, source_pages):
            return candidate()

    solution = SolutionEngine(FakeProvider()).generate(q, {1: "source"})
    assert solution.status.value == "verified"
    assert solution.question_id == "q1"
    assert solution.provenance[0].page_number == 1


def test_engine_rejects_invalid_solution_without_dropping_result():
    class FakeProvider:
        name = "fake-solution"

        def generate(self, question, source_pages):
            return candidate(answer="Z")

    solution = SolutionEngine(FakeProvider()).generate(question(), {1: "source"})
    assert solution.status.value == "rejected"
    assert solution.validation_reason


def test_gemini_solution_provider_parses_structured_response(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": json.dumps({
                        "answer": "A",
                        "method": "Direct",
                        "steps": ["Use the supplied value."],
                        "final_answer": "1",
                        "confidence": 0.91,
                        "evidence_pages": [1],
                        "evidence": "Page 1 contains the question.",
                    })}]}
                }]
            }).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.knowledge.solution_engine.urllib.request.urlopen", fake_urlopen)

    result = GeminiSolutionProvider(timeout_seconds=7).generate(question(), {1: "source"})
    assert result.answer == "A"
    assert result.confidence == pytest.approx(0.91)
    assert captured["timeout"] == 7
    body = json.loads(captured["request"].data.decode())
    prompt = body["contents"][0]["parts"][0]["text"].lower()
    assert "do not invent" in prompt
    assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_requires_server_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiSolutionProvider().generate(question(), {1: "source"})

def test_store_round_trips_solution(tmp_path):
    from app.knowledge.models import DocumentRecord, ProcessingStatus
    from app.knowledge.store import KnowledgeStore

    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.save_document(
        DocumentRecord(
            id="doc",
            filename="x.pdf",
            sha256="hash",
            page_count=1,
            status=ProcessingStatus.READY,
        )
    )
    q = question().model_copy(
        update={
            "provenance": [
                Provenance(document_id="doc", page_number=1, source_hash="hash", extractor="test")
            ]
        }
    )
    store.replace_questions("doc", [q])
    solution = SolutionEngine(
        type("FakeProvider", (), {
            "name": "fake",
            "generate": lambda self, question, source_pages: candidate(),
        })()
    ).generate(q, {1: "source"})
    store.save_solution(solution)
    restored = store.get_solution("q1")
    assert restored is not None
    assert restored.final_answer == "1"
    assert restored.status.value == "verified"
    assert restored.provenance[0].source_hash == "hash"
