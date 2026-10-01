from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import DocumentRecord, ProcessingJob, ProcessingStatus


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
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
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

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()
