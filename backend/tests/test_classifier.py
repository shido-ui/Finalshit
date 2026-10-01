from app.knowledge.classifier import KeywordTaxonomyClassifier
from app.knowledge.models import ClassificationStatus, QuestionCandidate
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.knowledge.taxonomy import Taxonomy, TaxonomyNode


def taxonomy() -> Taxonomy:
    return Taxonomy([
        TaxonomyNode("physics", "Physics", "subject"),
        TaxonomyNode("chemistry", "Chemistry", "subject"),
        TaxonomyNode("mathematics", "Mathematics", "subject"),
    ])


def question(text: str) -> QuestionCandidate:
    return QuestionCandidate(
        id="q1",
        document_id="doc",
        page_start=1,
        page_end=1,
        text=text,
    )


def test_strong_subject_evidence_is_classified():
    classifier = KeywordTaxonomyClassifier(
        {"physics": ("force", "velocity")}, minimum_confidence=0.8
    )

    result = classifier.classify(question("Find the force and velocity."), taxonomy())

    assert result.taxonomy_node_id == "physics"
    assert result.quarantined is False
    assert result.confidence >= 0.8


def test_unknown_or_ambiguous_evidence_is_quarantined():
    classifier = KeywordTaxonomyClassifier(
        {
            "physics": ("force",),
            "chemistry": ("reaction",),
        },
        minimum_confidence=0.8,
    )

    unknown = classifier.classify(question("Solve this problem."), taxonomy())
    assert unknown.quarantined is True
    assert unknown.taxonomy_node_id is None

    ambiguous = classifier.classify(
        question("A force causes a reaction."), taxonomy()
    )
    assert ambiguous.quarantined is True
    assert ambiguous.taxonomy_node_id is None


def test_classifier_never_returns_unknown_taxonomy_ids():
    classifier = KeywordTaxonomyClassifier(
        {"does-not-exist": ("force",), "physics": ("velocity",)}
    )

    result = classifier.classify(question("velocity is measured here"), taxonomy())

    assert result.taxonomy_node_id == "physics"


def test_service_persists_classification_state(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")

    from tests.test_knowledge_engine import make_pdf

    record = service.ingest_pdf("sample.pdf", make_pdf())
    questions = store.get_questions(record.id)

    assert len(questions) == 2
    assert all(
        item.classification_status
        in {ClassificationStatus.CLASSIFIED, ClassificationStatus.QUARANTINED}
        for item in questions
    )
    assert all(0.0 <= item.classification_confidence <= 1.0 for item in questions)
    assert all(item.classification_reason for item in questions)
