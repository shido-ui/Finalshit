from __future__ import annotations

import math
import random
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field

from .models import ClassificationStatus, QuestionCandidate
from .intelligence import IntelligenceService
from .store import KnowledgeStore


class PracticeMode(str):
    FAST = "fast"
    TEST = "test"
    ADAPTIVE = "adaptive"


class PracticeQuestion(BaseModel):
    id: str
    position: int
    text: str
    options: dict[str, str] = Field(default_factory=dict)
    taxonomy_node_id: str | None = None
    difficulty: str | None = None
    has_diagram: bool = False
    has_table: bool = False
    asset_ids: list[str] = Field(default_factory=list)


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


def _normalize_answer(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip().casefold())
    value = value.strip("[](){} ")
    return value


def _numeric_value(value: str) -> Decimal | None:
    normalized = _normalize_answer(value).replace(",", "")
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _answer_matches(submitted: str, expected: str, tolerance: Decimal = Decimal("0.000001")) -> bool:
    submitted_normalized = _normalize_answer(submitted)
    expected_normalized = _normalize_answer(expected)
    if submitted_normalized == expected_normalized:
        return True

    submitted_number = _numeric_value(submitted_normalized)
    expected_number = _numeric_value(expected_normalized)
    if submitted_number is not None and expected_number is not None:
        return abs(submitted_number - expected_number) <= tolerance

    def as_set(value: str) -> set[str]:
        return {
            _normalize_answer(part)
            for part in re.split(r"\s*[,;]\s*", value)
            if _normalize_answer(part)
        }

    submitted_set = as_set(submitted_normalized)
    expected_set = as_set(expected_normalized)
    return bool(submitted_set and expected_set and submitted_set == expected_set)


class PracticeService:
    def __init__(self, store: KnowledgeStore, intelligence: IntelligenceService | None = None) -> None:
        self.store = store
        self.intelligence = intelligence or IntelligenceService(store)

    def _select(
        self,
        questions: list[QuestionCandidate],
        limit: int,
        seed: int | None,
        mode: str,
    ) -> list[QuestionCandidate]:
        # A practice question without a known ground-truth answer cannot be graded
        # safely. Keep it out of the practice pool rather than treating it as wrong.
        eligible = [
            question
            for question in questions
            if question.classification_status is not ClassificationStatus.QUARANTINED
            and bool((question.answer or "").strip())
        ]
        if mode == PracticeMode.ADAPTIVE:
            return self.intelligence.adaptive_rank(eligible)[:limit]
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
        if mode not in {PracticeMode.FAST, PracticeMode.TEST, PracticeMode.ADAPTIVE}:
            raise ValueError("Unsupported practice mode")
        if limit < 1 or limit > 100:
            raise ValueError("Practice limit must be between 1 and 100")

        selected = self._select(questions, limit, seed, mode)
        if not selected:
            raise ValueError("No scorable questions are available")

        session = PracticeSession(
            id=f"practice-{uuid.uuid4()}",
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
                asset_ids=question.asset_ids,
            )
            for index, question in enumerate(selected, start=1)
        ]
        return session, public

    def resume_session(self, session_id: str) -> tuple[PracticeSession, list[PracticeQuestion]]:
        session = self.store.get_practice_session(session_id)
        if session is None:
            raise KeyError(session_id)
        questions: list[PracticeQuestion] = []
        for position, question_id in enumerate(session.question_ids, start=1):
            question = self.store.get_question(question_id)
            if question is None:
                continue
            questions.append(
                PracticeQuestion(
                    id=question.id,
                    position=position,
                    text=question.text,
                    options=question.options,
                    taxonomy_node_id=question.taxonomy_node_id,
                    difficulty=question.difficulty,
                    has_diagram=question.has_diagram,
                    has_table=question.has_table,
                    asset_ids=question.asset_ids,
                )
            )
        return session, questions


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

        question_map: dict[str, QuestionCandidate] = {}
        for question_id in session.question_ids:
            question = self.store.get_question(question_id)
            if question is not None:
                question_map[question_id] = question

        results: dict[str, bool] = {}
        for question_id, question in question_map.items():
            submitted = (answers.get(question_id) or "").strip()
            expected = (question.answer or "").strip()
            if not submitted or not expected:
                continue

            if _answer_matches(submitted, expected):
                results[question_id] = True
                continue

            expected_label = expected.upper()
            if expected_label in question.options:
                results[question_id] = _answer_matches(
                    submitted, question.options[expected_label]
                )
                continue

            submitted_label = submitted.upper()
            if submitted_label in question.options:
                results[question_id] = _answer_matches(
                    question.options[submitted_label], expected
                )
                continue

            results[question_id] = False

        # Only graded answers enter the weakness/spaced-repetition model.
        for question_id, correct in results.items():
            question = question_map[question_id]
            submitted = (answers.get(question_id) or "").strip()
            self.intelligence.record_outcome(
                question=question,
                session_id=session.id,
                submitted_answer=submitted,
                correct=correct,
            )

        correct = sum(results.values())
        answered = sum(
            1 for question_id in session.question_ids
            if answers.get(question_id, "").strip()
        )
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
