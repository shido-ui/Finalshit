from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from .models import QuestionCandidate
from .taxonomy import Taxonomy


@dataclass(frozen=True)
class ClassificationResult:
    taxonomy_node_id: str | None
    confidence: float
    reason: str
    quarantined: bool


class QuestionClassifier(Protocol):
    def classify(
        self, question: QuestionCandidate, taxonomy: Taxonomy
    ) -> ClassificationResult: ...


class KeywordTaxonomyClassifier:
    """Deterministic baseline until an external AI provider is configured.

    It never invents taxonomy IDs. Ambiguous or weak matches are quarantined.
    """

    def __init__(
        self,
        subject_keywords: dict[str, tuple[str, ...]],
        minimum_confidence: float = 0.80,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self.subject_keywords = subject_keywords
        self.minimum_confidence = minimum_confidence

    def classify(
        self, question: QuestionCandidate, taxonomy: Taxonomy
    ) -> ClassificationResult:
        text = question.text.casefold()
        scores: list[tuple[str, int]] = []

        for node_id, keywords in self.subject_keywords.items():
            if taxonomy.get(node_id) is None:
                continue
            score = sum(text.count(keyword.casefold()) for keyword in keywords)
            if score:
                scores.append((node_id, score))

        if scores:
            scores.sort(key=lambda item: (-item[1], item[0]))
            winner, winner_score = scores[0]
            runner_up_score = scores[1][1] if len(scores) > 1 else 0

            if len(scores) > 1 and winner_score == runner_up_score:
                return ClassificationResult(None, 0.0, "Classification evidence is ambiguous", True)

            confidence = min(0.99, 0.60 + 0.10 * winner_score)
            if confidence >= self.minimum_confidence:
                return ClassificationResult(
                    winner, confidence, "Controlled keyword evidence", False
                )

        # Once the canonical registry contains chapter/topic/subtopic nodes,
        # use their names as additional deterministic evidence. This makes
        # approved AI-created nodes usable by the classifier without allowing
        # the model to invent IDs or bypass the confidence gate.
        text_tokens = set(re.findall(r"[\w]+", text))
        node_matches: list[tuple[str, float]] = []
        for node in taxonomy.all():
            if node.level == "subject":
                continue
            normalized_name = node.name.casefold()
            name_tokens = [
                token for token in re.findall(r"[\w]+", normalized_name)
                if len(token) >= 4
            ]
            if not name_tokens:
                continue
            matched = sum(token in text_tokens for token in name_tokens)
            phrase = " ".join(name_tokens) in " ".join(re.findall(r"[\w]+", text))
            ratio = matched / len(name_tokens)
            if phrase or (matched >= 2 and ratio >= 0.5):
                score = 3.0 if phrase else matched + ratio
                node_matches.append((node.id, score))

        if not node_matches:
            return ClassificationResult(None, 0.0, "No controlled-taxonomy evidence", True)

        node_matches.sort(key=lambda item: (-item[1], item[0]))
        winner, winner_score = node_matches[0]
        runner_up_score = node_matches[1][1] if len(node_matches) > 1 else 0.0
        if len(node_matches) > 1 and winner_score == runner_up_score:
            return ClassificationResult(None, 0.0, "Classification evidence is ambiguous", True)

        confidence = min(0.99, 0.72 + 0.08 * winner_score)
        if confidence < self.minimum_confidence:
            return ClassificationResult(
                None,
                confidence,
                "Classification confidence below quarantine threshold",
                True,
            )
        return ClassificationResult(
            winner,
            confidence,
            "Controlled taxonomy-name evidence",
            False,
        )


DEFAULT_CLASSIFIER = KeywordTaxonomyClassifier(
    {
        "physics": (
            "force", "velocity", "acceleration", "momentum", "energy",
            "electric", "magnetic", "current", "wave", "optics",
        ),
        "chemistry": (
            "atom", "molecule", "molar", "reaction", "oxidation",
            "reduction", "organic", "inorganic", "equilibrium", "acid",
        ),
        "mathematics": (
            "equation", "integral", "derivative", "matrix", "vector",
            "probability", "permutation", "combination", "geometry", "limit",
        ),
    }
)
