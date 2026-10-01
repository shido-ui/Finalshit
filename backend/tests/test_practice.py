from app.knowledge.models import ClassificationStatus, QuestionCandidate
from app.knowledge.practice import PracticeService
from app.knowledge.store import KnowledgeStore


def make_question(question_id: str, answer: str) -> QuestionCandidate:
    return QuestionCandidate(
        id=question_id,
        document_id="doc",
        page_start=1,
        page_end=1,
        text=f"Question {question_id}",
        options={"A": "one", "B": "two"},
        answer=answer,
        classification_status=ClassificationStatus.CLASSIFIED,
    )


def test_fast_session_is_bounded_and_deterministic(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = PracticeService(store)
    questions = [make_question(f"q{i}", "A") for i in range(10)]

    session, public = service.create_session(questions, "fast", 5, seed=7)

    assert session.total == 5
    assert len(public) == 5
    assert [item.position for item in public] == [1, 2, 3, 4, 5]
    assert all(not hasattr(item, "answer") for item in public)


def test_quarantined_questions_are_excluded(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = PracticeService(store)
    questions = [
        make_question("good", "A"),
        make_question("bad", "A").model_copy(
            update={"classification_status": ClassificationStatus.QUARANTINED}
        ),
    ]

    session, public = service.create_session(questions, "test", 10, seed=1)

    assert session.question_ids == ["good"]
    assert [item.id for item in public] == ["good"]


def test_submission_scores_only_ground_truth_answers(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = PracticeService(store)
    questions = [make_question("q1", "A"), make_question("q2", "B")]
    session, _ = service.create_session(questions, "test", 2, seed=0)

    result = service.submit(session.id, {"q1": "A", "q2": "A"})

    assert result.correct == 1
    assert result.total == 2
    assert result.answered == 2
    assert result.percentage == 50.0
    assert result.question_results == {"q1": True, "q2": False}


def test_session_cannot_be_submitted_twice(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = PracticeService(store)
    session, _ = service.create_session([make_question("q1", "A")], "fast", 1, seed=0)
    service.submit(session.id, {"q1": "A"})

    try:
        service.submit(session.id, {"q1": "A"})
    except ValueError as exc:
        assert "already submitted" in str(exc)
    else:
        raise AssertionError("expected duplicate submission to fail")
