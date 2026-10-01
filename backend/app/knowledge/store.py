from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    ClassificationStatus,
    DocumentRecord,
    TaxonomyProposal,
    TaxonomyProposalStatus,
    ProcessingJob,
    ProcessingStatus,
    Provenance,
    QuestionCandidate,
)


class KnowledgeStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    question_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_start INTEGER NOT NULL,
                    page_end INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    number TEXT,
                    taxonomy_node_id TEXT,
                    classification_status TEXT NOT NULL DEFAULT 'unclassified',
                    classification_confidence REAL NOT NULL DEFAULT 0.0,
                    classification_reason TEXT,
                    provenance_json TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );


                CREATE TABLE IF NOT EXISTS taxonomy_proposals (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    parent_id TEXT,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_taxonomy_proposals_document
                    ON taxonomy_proposals(document_id);
                CREATE INDEX IF NOT EXISTS idx_taxonomy_proposals_status
                    ON taxonomy_proposals(status);
                CREATE INDEX IF NOT EXISTS idx_questions_document
                    ON questions(document_id);
                CREATE INDEX IF NOT EXISTS idx_questions_taxonomy
                    ON questions(taxonomy_node_id);
                CREATE INDEX IF NOT EXISTS idx_questions_page_start
                    ON questions(page_start);
                """
            )
            self._migrate_questions(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_questions_classification "
                "ON questions(classification_status)"
            )

    @staticmethod
    def _migrate_questions(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(questions)").fetchall()
        }
        migrations = {
            "classification_status": "TEXT NOT NULL DEFAULT 'unclassified'",
            "classification_reason": "TEXT",
        }
        for name, definition in migrations.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE questions ADD COLUMN {name} {definition}"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def save_document(self, document: DocumentRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents
                    (id, filename, sha256, page_count, status, error, question_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename,
                    sha256=excluded.sha256,
                    page_count=excluded.page_count,
                    status=excluded.status,
                    error=excluded.error,
                    question_count=excluded.question_count
                """,
                (
                    document.id,
                    document.filename,
                    document.sha256,
                    document.page_count,
                    document.status.value,
                    document.error,
                    document.question_count,
                ),
            )

    def get_document(self, document_id: str) -> DocumentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if row is None:
            return None
        return DocumentRecord(
            id=row["id"],
            filename=row["filename"],
            sha256=row["sha256"],
            page_count=row["page_count"],
            status=ProcessingStatus(row["status"]),
            error=row["error"],
            question_count=row["question_count"],
        )

    def save_job(self, job: ProcessingJob) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO processing_jobs (id, document_id, status, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (job.id, job.document_id, job.status.value, job.updated_at),
            )

    def get_job(self, job_id: str) -> ProcessingJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        return ProcessingJob(
            id=row["id"],
            document_id=row["document_id"],
            status=ProcessingStatus(row["status"]),
            updated_at=row["updated_at"],
        )

    def pending_jobs(self) -> list[ProcessingJob]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM processing_jobs
                WHERE status IN (?, ?)
                ORDER BY updated_at
                """,
                (ProcessingStatus.QUEUED.value, ProcessingStatus.EXTRACTING.value),
            ).fetchall()
        return [
            ProcessingJob(
                id=row["id"],
                document_id=row["document_id"],
                status=ProcessingStatus(row["status"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def replace_questions(self, document_id: str, questions: list[QuestionCandidate]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM questions WHERE document_id = ?", (document_id,))
            connection.executemany(
                """
                INSERT INTO questions (
                    id, document_id, page_start, page_end, text, number,
                    taxonomy_node_id, classification_status, classification_confidence,
                    classification_reason, provenance_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        question.id,
                        question.document_id,
                        question.page_start,
                        question.page_end,
                        question.text,
                        question.number,
                        question.taxonomy_node_id,
                        question.classification_status.value,
                        question.classification_confidence,
                        question.classification_reason,
                        json.dumps(
                            [item.model_dump(mode="json") for item in question.provenance],
                            separators=(",", ":"),
                        ),
                    )
                    for question in questions
                ],
            )

    def get_questions(
        self,
        document_id: str,
        taxonomy_node_ids: list[str] | None = None,
        page: int | None = None,
        classification_status: ClassificationStatus | None = None,
    ) -> list[QuestionCandidate]:
        clauses = ["document_id = ?"]
        params: list[object] = [document_id]

        if taxonomy_node_ids is not None:
            if not taxonomy_node_ids:
                return []
            placeholders = ",".join("?" for _ in taxonomy_node_ids)
            clauses.append(f"taxonomy_node_id IN ({placeholders})")
            params.extend(taxonomy_node_ids)
        if page is not None:
            clauses.append("page_start <= ? AND page_end >= ?")
            params.extend([page, page])
        if classification_status is not None:
            clauses.append("classification_status = ?")
            params.append(classification_status.value)

        query = f"""
            SELECT * FROM questions
            WHERE {" AND ".join(clauses)}
            ORDER BY page_start, id
        """
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            QuestionCandidate(
                id=row["id"],
                document_id=row["document_id"],
                page_start=row["page_start"],
                page_end=row["page_end"],
                text=row["text"],
                number=row["number"],
                taxonomy_node_id=row["taxonomy_node_id"],
                classification_status=ClassificationStatus(row["classification_status"]),
                classification_confidence=row["classification_confidence"],
                classification_reason=row["classification_reason"],
                provenance=[
                    Provenance.model_validate(item)
                    for item in json.loads(row["provenance_json"])
                ],
            )
            for row in rows
        ]

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()


    def save_taxonomy_proposals(
        self, proposals: list[TaxonomyProposal]
    ) -> None:
        if not proposals:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO taxonomy_proposals (
                    id, document_id, parent_id, name, level, confidence,
                    evidence, status, provider
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    parent_id=excluded.parent_id,
                    name=excluded.name,
                    level=excluded.level,
                    confidence=excluded.confidence,
                    evidence=excluded.evidence,
                    status=excluded.status,
                    provider=excluded.provider
                """,
                [
                    (
                        item.id,
                        item.document_id,
                        item.parent_id,
                        item.name,
                        item.level,
                        item.confidence,
                        item.evidence,
                        item.status.value,
                        item.provider,
                    )
                    for item in proposals
                ],
            )

    def get_taxonomy_proposals(
        self,
        document_id: str,
        status: TaxonomyProposalStatus | None = None,
    ) -> list[TaxonomyProposal]:
        clauses = ["document_id = ?"]
        params: list[object] = [document_id]
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM taxonomy_proposals
                WHERE {" AND ".join(clauses)}
                ORDER BY level, name, id
                """,
                params,
            ).fetchall()

        return [
            TaxonomyProposal(
                id=row["id"],
                document_id=row["document_id"],
                parent_id=row["parent_id"],
                name=row["name"],
                level=row["level"],
                confidence=row["confidence"],
                evidence=row["evidence"],
                status=TaxonomyProposalStatus(row["status"]),
                provider=row["provider"],
            )
            for row in rows
        ]
