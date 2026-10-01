from app.knowledge.models import TaxonomyProposalStatus
from app.knowledge.store import KnowledgeStore
from app.knowledge.taxonomy import DEFAULT_TAXONOMY
from app.knowledge.taxonomy_ai import (
    TaxonomyProposalCandidate,
    TaxonomyProposalEngine,
)


class FakeProvider:
    name = "fake-taxonomy-v1"

    def __init__(self, candidates):
        self.candidates = candidates

    def propose(self, document_text, taxonomy):
        assert "document content" in document_text
        assert taxonomy.get("physics") is not None
        return self.candidates


def test_ai_can_propose_topic_and_subtopic_under_existing_taxonomy():
    provider = FakeProvider(
        [
            TaxonomyProposalCandidate(
                id="new:rolling-motion",
                parent_id="physics.c05",
                name="Rolling Motion",
                level="topic",
                confidence=0.93,
                evidence="The document repeatedly derives rolling without slipping.",
            ),
            TaxonomyProposalCandidate(
                id="new:rolling-without-slipping",
                parent_id="new:rolling-motion",
                name="Rolling Without Slipping",
                level="subtopic",
                confidence=0.91,
                evidence="A worked example derives the no-slip condition.",
            ),
        ]
    )
    proposals = TaxonomyProposalEngine(provider, DEFAULT_TAXONOMY).build_proposals(
        "doc-1", "document content"
    )

    assert [item.name for item in proposals] == [
        "Rolling Motion",
        "Rolling Without Slipping",
    ]
    assert proposals[1].parent_id == "new:rolling-motion"


def test_ai_proposals_reject_unknown_existing_parents_and_bad_levels():
    provider = FakeProvider(
        [
            TaxonomyProposalCandidate(
                id="new:bad-parent",
                parent_id="does-not-exist",
                name="Invented Topic",
                level="topic",
                confidence=0.99,
                evidence="unsupported",
            ),
            TaxonomyProposalCandidate(
                id="new:bad-level",
                parent_id="physics.c05",
                name="Invalid",
                level="chapterish",
                confidence=0.99,
                evidence="unsupported",
            ),
        ]
    )
    proposals = TaxonomyProposalEngine(provider, DEFAULT_TAXONOMY).build_proposals(
        "doc-2", "document content"
    )
    assert proposals == []


def test_ai_proposal_parent_cycle_is_quarantined_by_resolver():
    provider = FakeProvider(
        [
            TaxonomyProposalCandidate(
                id="new:a",
                parent_id="new:b",
                name="A",
                level="topic",
                confidence=0.9,
                evidence="evidence",
            ),
            TaxonomyProposalCandidate(
                id="new:b",
                parent_id="new:a",
                name="B",
                level="subtopic",
                confidence=0.9,
                evidence="evidence",
            ),
        ]
    )
    proposals = TaxonomyProposalEngine(provider, DEFAULT_TAXONOMY).build_proposals(
        "doc-3", "document content"
    )
    assert proposals == []


def test_taxonomy_proposals_persist_with_pending_status(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    from app.knowledge.models import TaxonomyProposal

    proposal = TaxonomyProposal(
        id="doc-1-new-topic",
        document_id="doc-1",
        parent_id="physics.c05",
        name="Rolling Motion",
        level="topic",
        confidence=0.93,
        evidence="Worked examples",
        provider="fake-taxonomy-v1",
    )
    store.save_taxonomy_proposals([proposal])

    loaded = store.get_taxonomy_proposals("doc-1")
    assert loaded[0].status is TaxonomyProposalStatus.PENDING
    assert loaded[0].name == "Rolling Motion"
