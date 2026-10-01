from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from .models import MistakeRecord, QuestionCandidate, ReviewState, WeaknessProfile
from .store import KnowledgeStore


class IntelligenceService:
    """Deterministic local intelligence layer.

    It records observable practice outcomes, derives weakness from those outcomes,
    and schedules question-level reviews without requiring an AI provider.
    """

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    @staticmethod
    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def record_outcome(
        self,
        question: QuestionCandidate,
        session_id: str,
        submitted_answer: str | None,
        correct: bool,
    ) -> None:
        now = self.store.now()

        if not correct:
            self.store.save_mistake(
                MistakeRecord(
                    id=f"mistake-{uuid4()}",
                    question_id=question.id,
                    session_id=session_id,
                    submitted_answer=submitted_answer,
                    expected_answer=question.answer,
                    taxonomy_node_id=question.taxonomy_node_id,
                    created_at=now,
                )
            )

        if question.taxonomy_node_id:
            current = self.store.get_weakness(question.taxonomy_node_id)
            attempts = (current.attempts if current else 0) + 1
            correct_count = (current.correct if current else 0) + int(correct)
            incorrect_count = attempts - correct_count
            accuracy = correct_count / attempts
            # Conservative mastery: accuracy is discounted until the node has
            # repeated evidence. Five consistent attempts reach full weight.
            evidence_weight = min(1.0, attempts / 5.0)
            mastery = round(accuracy * evidence_weight, 4)
            self.store.save_weakness(
                WeaknessProfile(
                    taxonomy_node_id=question.taxonomy_node_id,
                    attempts=attempts,
                    correct=correct_count,
                    incorrect=incorrect_count,
                    accuracy=round(accuracy, 4),
                    mastery=mastery,
                    last_attempt_at=now,
                )
            )

        self._update_review(question.id, correct, now)

    def _update_review(self, question_id: str, correct: bool, now: str) -> None:
        current = self.store.get_review_state(question_id)
        if current is None:
            repetitions = 0
            interval = 0
            ease = 2.5
        else:
            repetitions = current.repetitions
            interval = current.interval_days
            ease = current.ease_factor

        if correct:
            repetitions += 1
            if repetitions == 1:
                interval = 1
            elif repetitions == 2:
                interval = 3
            else:
                interval = max(1, round(max(1, interval) * ease))
            ease = min(4.0, ease + 0.05)
        else:
            repetitions = 0
            interval = 1
            ease = max(1.3, ease - 0.2)

        reviewed_at = self._parse(now)
        due_at = reviewed_at + timedelta(days=interval)
        self.store.save_review_state(
            ReviewState(
                question_id=question_id,
                repetitions=repetitions,
                interval_days=interval,
                ease_factor=round(ease, 2),
                due_at=due_at.isoformat(),
                last_reviewed_at=now,
                last_correct=correct,
            )
        )

    def adaptive_rank(
        self,
        questions: list[QuestionCandidate],
        now: str | None = None,
    ) -> list[QuestionCandidate]:
        now = now or self.store.now()
        due_ids = set(self.store.get_due_review_question_ids(now, limit=10000))
        ranked: list[tuple[float, str, QuestionCandidate]] = []

        for question in questions:
            weakness = (
                self.store.get_weakness(question.taxonomy_node_id)
                if question.taxonomy_node_id
                else None
            )
            mastery_gap = 1.0 - (weakness.mastery if weakness else 0.0)
            due_bonus = 2.0 if question.id in due_ids else 0.0
            difficulty_bonus = {
                "hard": 0.20,
                "medium": 0.10,
                "easy": 0.0,
            }.get((question.difficulty or "").casefold(), 0.05)
            score = due_bonus + (2.0 * mastery_gap) + difficulty_bonus
            ranked.append((score, question.id, question))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked]
