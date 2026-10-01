from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .taxonomy import DEFAULT_TAXONOMY

from .models import (
    ClassificationStatus,
    DocumentRecord,
    TaxonomyProposal,
    TaxonomyProposalStatus,
    TaxonomyNode,
    DocumentAsset,
    ContentBlock,
    ProcessingJob,
    ProcessingStatus,
    Provenance,
    QuestionCandidate,
    Solution,
    SolutionStatus,
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
                    options_json TEXT NOT NULL DEFAULT '{}',
                    answer TEXT,
                    solution TEXT,
                    has_diagram INTEGER NOT NULL DEFAULT 0,
                    has_table INTEGER NOT NULL DEFAULT 0,
                    exam TEXT,
                    exam_year INTEGER,
                    difficulty TEXT,
                    intelligence_confidence REAL NOT NULL DEFAULT 0.0,
                    intelligence_reason TEXT,
                    intelligence_provider TEXT,
                    taxonomy_node_id TEXT,
                    classification_status TEXT NOT NULL DEFAULT 'unclassified',
                    classification_confidence REAL NOT NULL DEFAULT 0.0,
                    classification_reason TEXT,
                    provenance_json TEXT NOT NULL,
                    asset_ids_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );


                CREATE TABLE IF NOT EXISTS content_blocks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    x0 REAL NOT NULL,
                    y0 REAL NOT NULL,
                    x1 REAL NOT NULL,
                    y1 REAL NOT NULL,
                    asset_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_hash TEXT NOT NULL,
                    extractor TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_content_blocks_document_page
                    ON content_blocks(document_id, page_number, block_index);
                CREATE INDEX IF NOT EXISTS idx_content_blocks_kind
                    ON content_blocks(document_id, kind);

                CREATE TABLE IF NOT EXISTS document_assets (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    asset_index INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    x0 REAL NOT NULL DEFAULT 0,
                    y0 REAL NOT NULL DEFAULT 0,
                    x1 REAL NOT NULL DEFAULT 0,
                    y1 REAL NOT NULL DEFAULT 0,
                    xref INTEGER NOT NULL,
                    source_hash TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_document_assets_document_page
                    ON document_assets(document_id, page_number);
                CREATE INDEX IF NOT EXISTS idx_document_assets_sha256
                    ON document_assets(sha256);

                CREATE TABLE IF NOT EXISTS taxonomy_nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    parent_id TEXT,
                    source TEXT NOT NULL,
                    document_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(parent_id) REFERENCES taxonomy_nodes(id),
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_taxonomy_nodes_parent
                    ON taxonomy_nodes(parent_id);
                CREATE INDEX IF NOT EXISTS idx_taxonomy_nodes_level
                    ON taxonomy_nodes(level);

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
                    resolved_node_id TEXT,
                    resolution_reason TEXT,
                    FOREIGN KEY(document_id) REFERENCES documents(id),
                    FOREIGN KEY(resolved_node_id) REFERENCES taxonomy_nodes(id)
                );

                CREATE INDEX IF NOT EXISTS idx_taxonomy_proposals_document
                    ON taxonomy_proposals(document_id);
                CREATE INDEX IF NOT EXISTS idx_taxonomy_proposals_status
                    ON taxonomy_proposals(status);
                CREATE INDEX IF NOT EXISTS idx_questions_document
                    ON questions(document_id);

                CREATE TABLE IF NOT EXISTS solutions (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    answer TEXT,
                    method TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    final_answer TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    validation_reason TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    FOREIGN KEY(question_id) REFERENCES questions(id),
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_solutions_question
                    ON solutions(question_id);
                CREATE INDEX IF NOT EXISTS idx_solutions_document
                    ON solutions(document_id);

                CREATE INDEX IF NOT EXISTS idx_questions_taxonomy
                    ON questions(taxonomy_node_id);
                CREATE INDEX IF NOT EXISTS idx_questions_page_start
                    ON questions(page_start);
                """
            )
            self._migrate_questions(connection)
            self._migrate_document_assets(connection)
            self._migrate_taxonomy_proposals(connection)
            self._seed_taxonomy(connection)
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
            "options_json": "TEXT NOT NULL DEFAULT '{}'",
            "answer": "TEXT",
            "solution": "TEXT",
            "has_diagram": "INTEGER NOT NULL DEFAULT 0",
            "has_table": "INTEGER NOT NULL DEFAULT 0",
            "exam": "TEXT",
            "exam_year": "INTEGER",
            "difficulty": "TEXT",
            "intelligence_confidence": "REAL NOT NULL DEFAULT 0.0",
            "intelligence_reason": "TEXT",
            "intelligence_provider": "TEXT",
            "classification_status": "TEXT NOT NULL DEFAULT 'unclassified'",
            "classification_reason": "TEXT",
            "asset_ids_json": "TEXT NOT NULL DEFAULT '[]'",
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

    @staticmethod
    def _migrate_taxonomy_proposals(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(taxonomy_proposals)").fetchall()
        }
        migrations = {
            "resolved_node_id": "TEXT",
            "resolution_reason": "TEXT",
        }
        for name, definition in migrations.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE taxonomy_proposals ADD COLUMN {name} {definition}"
                )

    @staticmethod
    def _seed_taxonomy(connection: sqlite3.Connection) -> None:
        if connection.execute("SELECT 1 FROM taxonomy_nodes LIMIT 1").fetchone():
            return
        now = datetime.now(timezone.utc).isoformat()
        connection.executemany(
            """
            INSERT INTO taxonomy_nodes
                (id, name, level, parent_id, source, document_id, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            [
                (node.id, node.name, node.level, node.parent_id, "canonical", now)
                for node in DEFAULT_TAXONOMY.all()
            ],
        )

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
                    options_json, answer, solution, has_diagram, has_table,
                    exam, exam_year, difficulty, intelligence_confidence,
                    intelligence_reason, intelligence_provider,
                    taxonomy_node_id, classification_status, classification_confidence,
                    classification_reason, provenance_json, asset_ids_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        question.id,
                        question.document_id,
                        question.page_start,
                        question.page_end,
                        question.text,
                        question.number,
                        json.dumps(question.options, ensure_ascii=False, separators=(",", ":")),
                        question.answer,
                        question.solution,
                        int(question.has_diagram),
                        int(question.has_table),
                        question.exam,
                        question.exam_year,
                        question.difficulty,
                        question.intelligence_confidence,
                        question.intelligence_reason,
                        question.intelligence_provider,
                        question.taxonomy_node_id,
                        question.classification_status.value,
                        question.classification_confidence,
                        question.classification_reason,
                        json.dumps(
                            [item.model_dump(mode="json") for item in question.provenance],
                            separators=(",", ":"),
                        ),
                        json.dumps(question.asset_ids, separators=(",", ":")),
                    )
                    for question in questions
                ],
            )


    def get_question(self, question_id: str) -> QuestionCandidate | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM questions WHERE id = ?",
                (question_id,),
            ).fetchone()
        if row is None:
            return None
        rows = self.get_questions(row["document_id"])
        return next((item for item in rows if item.id == question_id), None)

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
                options=json.loads(row["options_json"] or "{}"),
                answer=row["answer"],
                solution=row["solution"],
                has_diagram=bool(row["has_diagram"]),
                has_table=bool(row["has_table"]),
                exam=row["exam"],
                exam_year=row["exam_year"],
                difficulty=row["difficulty"],
                intelligence_confidence=row["intelligence_confidence"],
                intelligence_reason=row["intelligence_reason"],
                intelligence_provider=row["intelligence_provider"],
                taxonomy_node_id=row["taxonomy_node_id"],
                classification_status=ClassificationStatus(row["classification_status"]),
                classification_confidence=row["classification_confidence"],
                classification_reason=row["classification_reason"],
                asset_ids=json.loads(row["asset_ids_json"] or "[]"),
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


    def get_taxonomy_nodes(self) -> list[TaxonomyNode]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, level, parent_id
                FROM taxonomy_nodes
                ORDER BY level, parent_id, name, id
                """
            ).fetchall()
        return [
            TaxonomyNode(
                id=row["id"],
                name=row["name"],
                level=row["level"],
                parent_id=row["parent_id"],
            )
            for row in rows
        ]

    def replace_content_blocks(self, document_id: str, blocks: list[ContentBlock]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM content_blocks WHERE document_id = ?", (document_id,))
            connection.executemany(
                """
                INSERT INTO content_blocks (
                    id, document_id, page_number, block_index, kind, text,
                    x0, y0, x1, y1, asset_ids_json, source_hash, extractor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (b.id, b.document_id, b.page_number, b.block_index, b.kind, b.text,
                     b.x0, b.y0, b.x1, b.y1, json.dumps(b.asset_ids, separators=(",", ":")),
                     b.source_hash, b.extractor)
                    for b in blocks
                ],
            )

    def get_content_blocks(self, document_id: str, page: int | None = None,
                           kind: str | None = None) -> list[ContentBlock]:
        clauses = ["document_id = ?"]
        params: list[object] = [document_id]
        if page is not None:
            clauses.append("page_number = ?")
            params.append(page)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM content_blocks WHERE {' AND '.join(clauses)} "
                "ORDER BY page_number, block_index, id", params
            ).fetchall()
        return [
            ContentBlock(
                id=row["id"], document_id=row["document_id"], page_number=row["page_number"],
                block_index=row["block_index"], kind=row["kind"], text=row["text"],
                x0=row["x0"], y0=row["y0"], x1=row["x1"], y1=row["y1"],
                asset_ids=json.loads(row["asset_ids_json"] or "[]"),
                source_hash=row["source_hash"], extractor=row["extractor"],
            )
            for row in rows
        ]

    @staticmethod
    def _migrate_document_assets(connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(document_assets)").fetchall()
        }
        for name in ("x0", "y0", "x1", "y1"):
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE document_assets ADD COLUMN {name} REAL NOT NULL DEFAULT 0"
                )

    def replace_document_assets(self, document_id: str, assets: list[DocumentAsset]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM document_assets WHERE document_id = ?", (document_id,))
            connection.executemany(
                """
                INSERT INTO document_assets (
                    id, document_id, page_number, asset_index, kind, mime_type,
                    sha256, byte_size, width, height, x0, y0, x1, y1, xref, source_hash, storage_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.id, item.document_id, item.page_number, item.asset_index,
                        item.kind, item.mime_type, item.sha256, item.byte_size,
                        item.width, item.height, item.x0, item.y0, item.x1, item.y1,
                        item.xref, item.source_hash, item.storage_path,
                    )
                    for item in assets
                ],
            )

    def get_document_asset(self, asset_id: str) -> DocumentAsset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM document_assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentAsset(
            id=row["id"], document_id=row["document_id"], page_number=row["page_number"],
            asset_index=row["asset_index"], kind=row["kind"], mime_type=row["mime_type"],
            sha256=row["sha256"], byte_size=row["byte_size"], width=row["width"],
            height=row["height"], x0=row["x0"], y0=row["y0"], x1=row["x1"], y1=row["y1"],
            xref=row["xref"], source_hash=row["source_hash"],
            storage_path=row["storage_path"],
        )

    def get_document_assets(self, document_id: str, page: int | None = None) -> list[DocumentAsset]:
        clauses = ["document_id = ?"]
        params: list[object] = [document_id]
        if page is not None:
            clauses.append("page_number = ?")
            params.append(page)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM document_assets WHERE {' AND '.join(clauses)} ORDER BY page_number, asset_index, id",
                params,
            ).fetchall()
        return [
            DocumentAsset(
                id=row["id"], document_id=row["document_id"], page_number=row["page_number"],
                asset_index=row["asset_index"], kind=row["kind"], mime_type=row["mime_type"],
                sha256=row["sha256"], byte_size=row["byte_size"], width=row["width"],
                height=row["height"], x0=row["x0"], y0=row["y0"], x1=row["x1"], y1=row["y1"], xref=row["xref"], source_hash=row["source_hash"],
                storage_path=row["storage_path"],
            )
            for row in rows
        ]


    def save_solution(self, solution: Solution) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO solutions (
                    id, question_id, document_id, answer, method, steps_json,
                    final_answer, confidence, status, provider, validation_reason,
                    provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    question_id=excluded.question_id,
                    document_id=excluded.document_id,
                    answer=excluded.answer,
                    method=excluded.method,
                    steps_json=excluded.steps_json,
                    final_answer=excluded.final_answer,
                    confidence=excluded.confidence,
                    status=excluded.status,
                    provider=excluded.provider,
                    validation_reason=excluded.validation_reason,
                    provenance_json=excluded.provenance_json
                """,
                (
                    solution.id,
                    solution.question_id,
                    solution.document_id,
                    solution.answer,
                    solution.method,
                    json.dumps(solution.steps, ensure_ascii=False, separators=(",", ":")),
                    solution.final_answer,
                    solution.confidence,
                    solution.status.value,
                    solution.provider,
                    solution.validation_reason,
                    json.dumps(
                        [item.model_dump(mode="json") for item in solution.provenance],
                        separators=(",", ":"),
                    ),
                ),
            )

    def get_solution(self, question_id: str) -> Solution | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM solutions WHERE question_id = ? ORDER BY id DESC LIMIT 1",
                (question_id,),
            ).fetchone()
        if row is None:
            return None
        return Solution(
            id=row["id"],
            question_id=row["question_id"],
            document_id=row["document_id"],
            answer=row["answer"],
            method=row["method"],
            steps=json.loads(row["steps_json"]),
            final_answer=row["final_answer"],
            confidence=row["confidence"],
            status=SolutionStatus(row["status"]),
            provider=row["provider"],
            validation_reason=row["validation_reason"],
            provenance=[
                Provenance.model_validate(item)
                for item in json.loads(row["provenance_json"])
            ],
        )

    def save_taxonomy_node(
        self,
        node: TaxonomyNode,
        source: str,
        document_id: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO taxonomy_nodes
                    (id, name, level, parent_id, source, document_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.name,
                    node.level,
                    node.parent_id,
                    source,
                    document_id,
                    self.now(),
                ),
            )

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
                    evidence, status, provider, resolved_node_id, resolution_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    parent_id=excluded.parent_id,
                    name=excluded.name,
                    level=excluded.level,
                    confidence=excluded.confidence,
                    evidence=excluded.evidence,
                    provider=excluded.provider,
                    resolved_node_id=COALESCE(taxonomy_proposals.resolved_node_id, excluded.resolved_node_id),
                    resolution_reason=COALESCE(taxonomy_proposals.resolution_reason, excluded.resolution_reason),
                    status=CASE
                        WHEN taxonomy_proposals.status IN ('approved', 'rejected')
                        THEN taxonomy_proposals.status
                        ELSE excluded.status
                    END
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
                        item.resolved_node_id,
                        item.resolution_reason,
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
                resolved_node_id=row["resolved_node_id"],
                resolution_reason=row["resolution_reason"],
            )
            for row in rows
        ]

    def get_taxonomy_proposal(self, proposal_id: str) -> TaxonomyProposal | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM taxonomy_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return TaxonomyProposal(
            id=row["id"],
            document_id=row["document_id"],
            parent_id=row["parent_id"],
            name=row["name"],
            level=row["level"],
            confidence=row["confidence"],
            evidence=row["evidence"],
            status=TaxonomyProposalStatus(row["status"]),
            provider=row["provider"],
            resolved_node_id=row["resolved_node_id"],
            resolution_reason=row["resolution_reason"],
        )

    def resolve_taxonomy_proposal(
        self,
        proposal_id: str,
        status: TaxonomyProposalStatus,
        resolved_node_id: str | None,
        reason: str,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE taxonomy_proposals
                SET status = ?, resolved_node_id = ?, resolution_reason = ?
                WHERE id = ?
                """,
                (status.value, resolved_node_id, reason, proposal_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(proposal_id)
