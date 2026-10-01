import sqlite3

import pymupdf

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


def make_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (50, 60),
        "1. Find the force and velocity of the particle.\n"
        "(A) 1\n(B) 2\n(C) 3\n(D) 4\n"
        "2. What is the reaction rate?\n"
        "(A) 1\n(B) 2\n(C) 3\n(D) 4",
    )
    content = document.tobytes()
    document.close()
    return content


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


def test_existing_question_schema_migrates_before_new_index(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE questions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                page_start INTEGER NOT NULL,
                page_end INTEGER NOT NULL,
                text TEXT NOT NULL,
                number TEXT,
                taxonomy_node_id TEXT,
                classification_confidence REAL NOT NULL DEFAULT 0.0,
                provenance_json TEXT NOT NULL
            )
            """
        )

    store = KnowledgeStore(database)
    columns = {
        row["name"]
        for row in store._connect().execute("PRAGMA table_info(questions)").fetchall()
    }

    assert "classification_status" in columns
    assert "classification_reason" in columns
    assert store._connect().execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name='idx_questions_classification'"
    ).fetchone() is not None
