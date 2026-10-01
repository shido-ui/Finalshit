from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from .models import TaxonomyProposal
from .taxonomy import Taxonomy


class TaxonomyProposalCandidate(BaseModel):
    """Untrusted AI output before it is converted into a persisted proposal."""

    id: str
    parent_id: str | None = None
    name: str = Field(min_length=1, max_length=160)
    level: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=1000)


class TaxonomyProposalProvider(Protocol):
    name: str

    def propose(
        self,
        document_text: str,
        taxonomy: Taxonomy,
    ) -> list[TaxonomyProposalCandidate]: ...


@dataclass(frozen=True)
class TaxonomyProposalEngine:
    provider: TaxonomyProposalProvider
    taxonomy: Taxonomy

    def build_proposals(
        self,
        document_id: str,
        document_text: str,
    ) -> list[TaxonomyProposal]:
        candidates = self.provider.propose(document_text, self.taxonomy)
        proposals: list[TaxonomyProposal] = []
        candidate_ids = {candidate.id for candidate in candidates}
        accepted_ids: set[str] = set()
        valid_levels = Taxonomy.VALID_LEVELS

        # Resolve parent references in repeated passes so a child can safely
        # appear before its proposed parent in the model response.
        remaining = list(candidates)
        while remaining:
            progress = False
            next_remaining: list[TaxonomyProposalCandidate] = []

            for candidate in remaining:
                proposal_id = f"{document_id}-{candidate.id}"
                if candidate.level not in valid_levels or proposal_id in accepted_ids:
                    continue

                parent_id = candidate.parent_id
                if parent_id is not None:
                    if parent_id.startswith("new:"):
                        parent_candidate_id = parent_id.removeprefix("new:")
                        if parent_candidate_id not in candidate_ids:
                            continue
                        if f"{document_id}-{parent_candidate_id}" not in accepted_ids:
                            next_remaining.append(candidate)
                            continue
                    elif self.taxonomy.get(parent_id) is None:
                        continue

                proposals.append(
                    TaxonomyProposal(
                    id=proposal_id,
                    document_id=document_id,
                    parent_id=candidate.parent_id,
                    name=candidate.name.strip(),
                    level=candidate.level,
                    confidence=candidate.confidence,
                    evidence=candidate.evidence.strip(),
                    provider=self.provider.name,
                    )
                accepted_ids.add(proposal_id)
                progress = True

            if not progress:
                break
            remaining = next_remaining

        return proposals


class GeminiTaxonomyProposalProvider:
    """Gemini-backed taxonomy discovery.

    The API key is read only from the server environment. It is never accepted
    from an Android request or persisted in the database.
    """

    name = "gemini-taxonomy-v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_TAXONOMY_MODEL", "gemini-3-flash")
        self.timeout_seconds = timeout_seconds

    def propose(
        self,
        document_text: str,
        taxonomy: Taxonomy,
    ) -> list[TaxonomyProposalCandidate]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        existing = [
            {
                "id": node.id,
                "name": node.name,
                "level": node.level,
                "parent_id": node.parent_id,
            }
            for node in taxonomy.all()
        ]
        prompt = self._build_prompt(document_text, existing)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "parent_id": {"type": "STRING"},
                            "name": {"type": "STRING"},
                            "level": {
                                "type": "STRING",
                                "enum": ["subject", "chapter", "topic", "subtopic"],
                            },
                            "confidence": {"type": "NUMBER"},
                            "evidence": {"type": "STRING"},
                        },
                        "required": [
                            "id",
                            "name",
                            "level",
                            "confidence",
                            "evidence",
                        ],
                    },
                },
            },
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError("Gemini taxonomy request failed") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned invalid JSON") from exc

        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            decoded = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gemini returned an invalid taxonomy response") from exc

        if not isinstance(decoded, list):
            raise RuntimeError("Gemini taxonomy response must be an array")

        return [TaxonomyProposalCandidate.model_validate(item) for item in decoded]

    @staticmethod
    def _build_prompt(
        document_text: str,
        existing: list[dict[str, str | None]],
    ) -> str:
        # Keep the model grounded: existing canonical nodes are preferred, and
        # new nodes are proposals only. The resolver, not the model, controls IDs.
        existing_json = json.dumps(existing, ensure_ascii=False, separators=(",", ":"))
        clipped_text = document_text[:120_000]
        return f"""
You are FocusForge's controlled educational taxonomy analyzer.

Analyze the supplied educational document and identify taxonomy nodes that are
actually evidenced by the document but are missing from the existing taxonomy.

Rules:
1. Prefer existing canonical nodes; do not propose duplicates or renamed copies.
2. Only propose a new node when the document contains enough evidence that it
   represents a meaningful chapter, topic, or subtopic.
3. Never invent syllabus content merely to fill gaps.
4. New nodes must use IDs beginning with "new:" and stable slug-like identifiers.
5. A new node may use parent_id="new:<id>" to reference another new proposal.
6. Existing parents must use their exact canonical ID.
7. Use one of: subject, chapter, topic, subtopic.
8. Return only JSON matching the requested schema.
9. Confidence is your evidence confidence, not a claim of correctness.
10. Evidence must quote or precisely describe what in the document supports the proposal.

Existing canonical taxonomy:
{existing_json}

Document:
{clipped_text}
""".strip()


def default_taxonomy_proposal_provider() -> GeminiTaxonomyProposalProvider:
    return GeminiTaxonomyProposalProvider()
