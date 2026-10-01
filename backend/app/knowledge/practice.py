from __future__ import annotations

import random
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .models import ClassificationStatus, QuestionCandidate
from .store import KnowledgeStore


class PracticeMode(str):
    FAST = "fast"
    TEST = "test"


class PracticeQuestion(BaseModel):
    id: str
    position: int
    text: str
    options: dict[str, str] = Field(default_factory=dict)
    taxonomy_node_id: str | None = None
    difficulty: str | None = None
    has_diagram: bool = False
    has_table: bool = False


class PracticeSession(BaseModel):
    id: str
    mode: str
    question_ids: list[str]
    started_at: str
    submitted_at: str | None = None
    score: int | None = None
    total: int
    answered: int = 0


class PracticeResult(BaseModel):
    session_id: str
    score: int
    total: int
    answered: int
    correct: int
    percentage: float
    question_results: dict[str, bool]


@dataclass(frozen=True)
class PracticeSelection:
    questions: list[QuestionCandidate]
    mode: str


class PracticeService:
    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def _select(
        self,
        questions: list[QuestionCandidate],
        limit: int,
        seed: int | None,
    ) -> list[QuestionCandidate]:
        eligible = [
            question for question in questions
            if question.classification_status is not ClassificationStatus.QUARANTINED
        ]
        rng = random.Random(seed)
        rng.shuffle(eligible)
        return eligible[:limit]

    def create_session(
        self,
        questions: list[QuestionCandidate],
        mode: str,
        limit: int,
        seed: int | None = None,
    ) -> tuple[PracticeSession, list[PracticeQuestion]]:
        if mode not in {PracticeMode.FAST, PracticeMode.TEST}:
            raise ValueError("Unsupported practice mode")
        if limit < 1 or limit > 100:
            raise ValueError("Practice limit must be between 1 and 100")

        selected = self._select(questions, limit, seed)
        if not selected:
            raise ValueError("No eligible questions are available")

        session = PracticeSession(
            id=f"practice-{self.store.now().replace(':', '').replace('+', '-')}",
            mode=mode,
            question_ids=[question.id for question in selected],
            started_at=self.store.now(),
            total=len(selected),
        )
        self.store.save_practice_session(session)

        public = [
            PracticeQuestion(
                id=question.id,
                position=index,
                text=question.text,
                options=question.options,
                taxonomy_node_id=question.taxonomy_node_id,
                difficulty=question.difficulty,
                has_diagram=question.has_diagram,
                has_table=question.has_table,
            )
            for index, question in enumerate(selected, start=1)
        ]
        return session, public

    def submit(
        self,
        session_id: str,
        answers: dict[str, str],
    ) -> PracticeResult:
        session = self.store.get_practice_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.submitted_at is not None:
            raise ValueError("Practice session is already submitted")

        question_map = {}
        for question_id in session.question_ids:
            question = self.store.get_question(question_id)
            if question is not None:
                question_map[question_id] = question

        results: dict[str, bool] = {}
        for question_id, question in question_map.items():
            submitted = answers.get(question_id)
            expected = (question.answer or "").strip().upper()
            actual = (submitted or "").strip().upper()
            if expected and actual:
                results[question_id] = actual == expected

        correct = sum(results.values())
        answered = sum(1 for question_id in session.question_ids if answers.get(question_id, "").strip())
        total = len(session.question_ids)
        percentage = round((correct / total) * 100, 2) if total else 0.0
        completed = session.model_copy(
            update={
                "submitted_at": self.store.now(),
                "score": correct,
                "answered": answered,
            }
        )
        self.store.save_practice_session(completed)
        return PracticeResult(
            session_id=session.id,
            score=correct,
            total=total,
            answered=answered,
            correct=correct,
            percentage=percentage,
            question_results=results,
        )
