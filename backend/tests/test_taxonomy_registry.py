import pytest

from app.knowledge.models import (
    DocumentRecord,
    ProcessingStatus,
    QuestionCandidate,
    TaxonomyProposal,
    TaxonomyProposalStatus,
)
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore


def document(store: KnowledgeStore, document_id: str = "doc-1") -> DocumentRecord:
    record = DocumentRecord(
        id=document_id,
        filename="source.pdf",
        sha256="a" * 64,
        page_count=1,
        status=ProcessingStatus.READY,
    )
    store.save_document(record)
    return record


def proposal(
    document_id: str,
    proposal_id: str,
    *,
    parent_id: str | None,
    name: str,
    level: str = "topic",
) -> TaxonomyProposal:
    return TaxonomyProposal(
        id=proposal_id,
        document_id=document_id,
        parent_id=parent_id,
        name=name,
        level=level,
        confidence=0.94,
        evidence="The source explicitly covers this concept.",
        provider="fake-taxonomy-v1",
    )


def test_store_seeds_default_taxonomy_and_persists_ai_nodes(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    nodes = store.get_taxonomy_nodes()

    assert any(node.id == "physics" for node in nodes)
    assert any(node.id == "physics.c05.t03" for node in nodes)

    ai_node = proposal(
        "doc-1",
        "doc-1-new-rolling",
        parent_id="physics.c05",
        name="Rolling Motion",
    )
    document(store)
    store.save_taxonomy_proposals([ai_node])

    service = KnowledgeService(store, tmp_path / "documents")
    service.approve_taxonomy_proposal(ai_node.id)

    loaded = store.get_taxonomy_proposal(ai_node.id)
    assert loaded is not None
    assert loaded.status is TaxonomyProposalStatus.APPROVED
    assert loaded.resolved_node_id is not None
    assert any(node.id == loaded.resolved_node_id for node in store.get_taxonomy_nodes())


def test_approval_deduplicates_against_existing_canonical_node(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    document(store)
    item = proposal(
        "doc-1",
        "doc-1-existing-electric-field",
        parent_id="physics.c11",
        name="Electric Field",
    )
    store.save_taxonomy_proposals([item])

    service = KnowledgeService(store, tmp_path / "documents")
    resolution = service.approve_taxonomy_proposal(item.id)

    assert resolution.created is False
    assert resolution.resolved_node_id == "physics.c11.t02"
    assert store.get_taxonomy_proposal(item.id).resolved_node_id == "physics.c11.t02"


def test_child_proposal_requires_approved_new_parent(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    document(store)

    parent = proposal(
        "doc-1",
        "doc-1-new-rolling",
        parent_id="physics.c05",
        name="Rolling Motion",
    )
    child = proposal(
        "doc-1",
        "doc-1-new-rolling-no-slip",
        parent_id="new:rolling",
        name="Rolling Without Slipping",
        level="subtopic",
    )
    store.save_taxonomy_proposals([parent, child])

    service = KnowledgeService(store, tmp_path / "documents")

    with pytest.raises(ValueError, match="must be approved first"):
        service.approve_taxonomy_proposal(child.id)

    service.approve_taxonomy_proposal(parent.id)
    child_resolution = service.approve_taxonomy_proposal(child.id)

    assert child_resolution.created is True
    assert store.get_taxonomy_proposal(child.id).resolved_node_id == child_resolution.resolved_node_id
    assert any(
        node.id == child_resolution.resolved_node_id
        and node.parent_id == store.get_taxonomy_proposal(parent.id).resolved_node_id
        for node in store.get_taxonomy_nodes()
    )


def test_approved_node_is_used_for_question_reclassification(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    document(store)
    question = QuestionCandidate(
        id="doc-1-1",
        document_id="doc-1",
        page_start=1,
        page_end=1,
        text="A rolling motion without slipping has angular velocity.",
    )
    store.replace_questions("doc-1", [question])

    item = proposal(
        "doc-1",
        "doc-1-new-rolling",
        parent_id="physics.c05",
        name="Rolling Motion",
    )
    store.save_taxonomy_proposals([item])

    service = KnowledgeService(store, tmp_path / "documents")
    resolution = service.approve_taxonomy_proposal(item.id)

    loaded_question = store.get_questions("doc-1")[0]
    assert loaded_question.taxonomy_node_id == resolution.resolved_node_id
    assert loaded_question.classification_status is ClassificationStatus.CLASSIFIED


def test_rejection_is_persistent_and_does_not_create_a_node(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    document(store)
    item = proposal(
        "doc-1",
        "doc-1-rejected",
        parent_id="physics.c05",
        name="Unsupported Topic",
    )
    store.save_taxonomy_proposals([item])

    service = KnowledgeService(store, tmp_path / "documents")
    resolution = service.reject_taxonomy_proposal(item.id, "Insufficient source evidence")

    assert resolution.status is TaxonomyProposalStatus.REJECTED
    loaded = store.get_taxonomy_proposal(item.id)
    assert loaded.resolution_reason == "Insufficient source evidence"
    assert not any(node.name == "Unsupported Topic" for node in store.get_taxonomy_nodes())
