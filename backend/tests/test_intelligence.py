from app.knowledge.intelligence import IntelligenceService
from app.knowledge.models import ClassificationStatus, DocumentRecord, ProcessingStatus, QuestionCandidate, KnowledgeEdge
from app.knowledge.practice import PracticeService
from app.knowledge.store import KnowledgeStore


def make_question(question_id: str, taxonomy: str = "physics.c01.t01", answer: str = "A"):
    return QuestionCandidate(
        id=question_id,
        document_id="doc",
        page_start=1,
        page_end=1,
        text=f"Question {question_id}",
        options={"A": "one", "B": "two"},
        answer=answer,
        taxonomy_node_id=taxonomy,
        classification_status=ClassificationStatus.CLASSIFIED,
    )


def persist_doc(store):
    store.save_document(
        DocumentRecord(
            id="doc",
            filename="practice.pdf",
            sha256="hash",
            page_count=1,
            status=ProcessingStatus.READY,
        )
    )


def test_incorrect_answer_creates_mistake_weakness_and_review(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    persist_doc(store)
    question = make_question("q1")
    store.replace_questions("doc", [question])

    service = PracticeService(store)
    session, _ = service.create_session([question], "test", 1, seed=1)
    result = service.submit(session.id, {"q1": "B"})

    assert result.correct == 0
    mistakes = store.get_mistakes(question_id="q1")
    assert len(mistakes) == 1
    weakness = store.get_weakness("physics.c01.t01")
    assert weakness is not None
    assert weakness.incorrect == 1
    assert weakness.mastery == 0.0
    review = store.get_review_state("q1")
    assert review is not None
    assert review.interval_days == 1
    assert review.last_correct is False


def test_repeated_correct_answers_increase_mastery_and_review_interval(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    persist_doc(store)
    question = make_question("q1")
    store.replace_questions("doc", [question])
    service = PracticeService(store)

    for _ in range(3):
        session, _ = service.create_session([question], "test", 1, seed=1)
        service.submit(session.id, {"q1": "A"})

    weakness = store.get_weakness("physics.c01.t01")
    assert weakness is not None
    assert weakness.correct == 3
    assert weakness.accuracy == 1.0
    assert weakness.mastery == 0.6
    review = store.get_review_state("q1")
    assert review is not None
    assert review.repetitions == 3
    assert review.interval_days >= 3


def test_adaptive_mode_prioritizes_weak_and_due_questions(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    persist_doc(store)
    weak = make_question("weak", "physics.c01.t01")
    strong = make_question("strong", "physics.c02.t01")
    store.replace_questions("doc", [weak, strong])
    service = PracticeService(store)

    for _ in range(2):
        session, _ = service.create_session([weak], "test", 1)
        service.submit(session.id, {"weak": "B"})

    session, public = service.create_session([strong, weak], "adaptive", 1)
    assert public[0].id == "weak"
    assert session.mode == "adaptive"


def test_knowledge_graph_edge_round_trip(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    edge = KnowledgeEdge(
        source_node_id="physics.c01",
        target_node_id="physics.c01.t01",
        relation="contains",
        confidence=1.0,
        source="canonical",
    )
    store.save_knowledge_edge(edge)
    edges = store.get_knowledge_edges(node_id="physics.c01")
    assert edges == [edge]
