from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import TaxonomyNode, TaxonomyProposal
from .taxonomy import Taxonomy


@dataclass(frozen=True)
class TaxonomyResolution:
    node_id: str
    created: bool
    reason: str


class TaxonomyRegistry:
    """Persistence-backed taxonomy registry with conservative proposal resolution."""

    FUZZY_THRESHOLD = 0.93

    def __init__(self, store) -> None:
        self.store = store
        self.refresh()

    def refresh(self) -> Taxonomy:
        self.taxonomy = Taxonomy(self.store.get_taxonomy_nodes())
        return self.taxonomy

    @staticmethod
    def _normalize(value: str) -> str:
        value = unicodedata.normalize("NFKC", value).casefold()
        value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
        return " ".join(value.split())

    @classmethod
    def _similarity(cls, left: str, right: str) -> float:
        a = cls._normalize(left)
        b = cls._normalize(right)
        if a == b:
            return 1.0
        sequence = SequenceMatcher(None, a, b).ratio()
        left_tokens = set(a.split())
        right_tokens = set(b.split())
        overlap = (
            len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
            if left_tokens or right_tokens
            else 1.0
        )
        return max(sequence, overlap)

    def resolve_duplicate(self, proposal: TaxonomyProposal) -> tuple[str, str] | None:
        parent_id = proposal.parent_id
        candidates = [
            node
            for node in self.taxonomy.all()
            if node.level == proposal.level and node.parent_id == parent_id
        ]
        for node in candidates:
            if self._normalize(node.name) == self._normalize(proposal.name):
                return node.id, "exact canonical name match"
        for node in candidates:
            if self._similarity(node.name, proposal.name) >= self.FUZZY_THRESHOLD:
                return node.id, f"high-confidence lexical match to canonical node {node.id}"
        return None

    @staticmethod
    def _new_node_id(proposal: TaxonomyProposal, parent_id: str | None) -> str:
        key = "|".join(
            [proposal.level, parent_id or "", TaxonomyRegistry._normalize(proposal.name)]
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return f"ai.{proposal.level}.{digest}"

    def approve(self, proposal: TaxonomyProposal) -> TaxonomyResolution:
        if proposal.status.value != "pending":
            raise ValueError(f"Proposal {proposal.id} is already {proposal.status.value}")

        parent_id = proposal.parent_id
        if parent_id is not None:
            parent = self.taxonomy.get(parent_id)
            if parent is None:
                raise ValueError(
                    f"Proposal parent {parent_id!r} is not in the canonical taxonomy"
                )
            expected = {"chapter": "subject", "topic": "chapter", "subtopic": "topic"}[
                proposal.level
            ]
            if parent.level != expected:
                raise ValueError(
                    f"Proposal {proposal.id} at level {proposal.level!r} requires a "
                    f"{expected!r} parent"
                )

        duplicate = self.resolve_duplicate(proposal)
        if duplicate is not None:
            node_id, reason = duplicate
            return TaxonomyResolution(node_id=node_id, created=False, reason=reason)

        node_id = self._new_node_id(proposal, parent_id)
        node = TaxonomyNode(
            id=node_id,
            name=proposal.name.strip(),
            level=proposal.level,
            parent_id=parent_id,
        )
        self.store.save_taxonomy_node(
            node, source="ai-approved", document_id=proposal.document_id
        )
        self.refresh()
        return TaxonomyResolution(
            node_id=node_id,
            created=True,
            reason="approved AI proposal added to canonical registry",
        )
