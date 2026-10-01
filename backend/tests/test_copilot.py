import json

import pytest

from app.knowledge.copilot import (
    CopilotCandidate,
    GeminiStudyCopilotProvider,
    StudyCopilot,
)


def candidate(**updates):
    data = {
        "answer": "Use the definition in the source.",
        "citations": [1],
        "confidence": 0.9,
        "evidence": "Page 1 states the relevant definition.",
    }
    data.update(updates)
    return CopilotCandidate(**data)


def test_copilot_accepts_grounded_citations():
    class FakeProvider:
        name = "fake"
        def answer(self, question, source_pages):
            return candidate()

    result = StudyCopilot(FakeProvider()).answer("Explain this.", {1: "source"})
    assert result.confidence == pytest.approx(0.9)


def test_copilot_rejects_unknown_citation():
    class FakeProvider:
        name = "fake"
        def answer(self, question, source_pages):
            return candidate(citations=[2])

    with pytest.raises(ValueError, match="outside supplied provenance"):
        StudyCopilot(FakeProvider()).answer("Explain this.", {1: "source"})


def test_copilot_rejects_empty_sources():
    class FakeProvider:
        name = "fake"
        def answer(self, question, source_pages):
            return candidate()

    with pytest.raises(ValueError, match="No usable source"):
        StudyCopilot(FakeProvider()).answer("Explain this.", {1: ""})


def test_gemini_copilot_structured_response(monkeypatch):
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        def read(self):
            return json.dumps({"candidates": [{"content": {"parts": [{
                "text": json.dumps({
                    "answer": "Grounded answer",
                    "citations": [1],
                    "confidence": 0.88,
                    "evidence": "Page 1",
                })
            }]}}]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["request"] = request
        return FakeResponse()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.knowledge.copilot.urllib.request.urlopen",
        fake_urlopen,
    )
    result = GeminiStudyCopilotProvider(timeout_seconds=9).answer(
        "Explain this.", {1: "source"}
    )
    assert result.answer == "Grounded answer"
    assert captured["timeout"] == 9
    body = json.loads(captured["request"].data.decode())
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "only" in body["contents"][0]["parts"][0]["text"].lower()


def test_gemini_copilot_requires_server_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiStudyCopilotProvider().answer("Explain this.", {1: "source"})
