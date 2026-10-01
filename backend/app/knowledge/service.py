from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pymupdf

from .extractor import extract_document, reconstruct_question_candidates
from .models import (
    DocumentRecord,
    ProcessingJob,
    ProcessingStatus,
    Provenance,
    QuestionCandidate,
)
from .store import KnowledgeStore


class KnowledgeService:
    def __init__(self, store: KnowledgeStore, storage_dir: str | Path) -> None:
        self.store = store
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def ingest_pdf(self, filename: str, content: bytes) -> DocumentRecord:
        if not content:
            raise ValueError("PDF content is empty")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF documents are supported in this phase")

        digest = hashlib.sha256(content).hexdigest()
        document_id = digest[:24]
        source_path = self.storage_dir / f"{document_id}.pdf"
        source_path.write_bytes(content)

        try:
            with pymupdf.open(stream=content, filetype="pdf") as document:
                page_count = len(document)
        except Exception as exc:
            source_path.unlink(missing_ok=True)
            raise ValueError("The uploaded file is not a readable PDF") from exc

        record = DocumentRecord(
            id=document_id,
            filename=filename,
            sha256=digest,
            page_count=page_count,
            status=ProcessingStatus.QUEUED,
        )
        self.store.save_document(record)

        job = ProcessingJob(
            id=str(uuid.uuid4()),
            document_id=document_id,
            status=ProcessingStatus.QUEUED,
            updated_at=self.store.now(),
        )
        self.store.save_job(job)
        return self.process_document(job.id)

    def process_document(self, job_id: str) -> DocumentRecord:
        job = self.store.get_job(job_id)
        if job is None:
            raise KeyError(job_id)

        record = self.store.get_document(job.document_id)
        if record is None:
            raise KeyError(job.document_id)

        source_path = self.storage_dir / f"{record.id}.pdf"
        if not source_path.is_file():
            failed = record.model_copy(
                update={"status": ProcessingStatus.FAILED, "error": "Source PDF is missing"}
            )
            self.store.save_document(failed)
            self.store.save_job(
                job.model_copy(
                    update={
                        "status": ProcessingStatus.FAILED,
                        "updated_at": self.store.now(),
                    }
                )
            )
            return failed

        running_job = job.model_copy(
            update={"status": ProcessingStatus.EXTRACTING, "updated_at": self.store.now()}
        )
        self.store.save_job(running_job)
        running = record.model_copy(update={"status": ProcessingStatus.EXTRACTING, "error": None})
        self.store.save_document(running)

        try:
            pages = extract_document(str(source_path))
            questions = reconstruct_question_candidates(pages)
            ready = running.model_copy(
                update={
                    "status": ProcessingStatus.READY,
                    "question_count": len(questions),
                }
            )
            self.store.save_document(ready)
            self.store.save_job(
                running_job.model_copy(
                    update={
                        "status": ProcessingStatus.READY,
                        "updated_at": self.store.now(),
                    }
                )
            )
            return ready
        except Exception as exc:
            failed = running.model_copy(
                update={"status": ProcessingStatus.FAILED, "error": str(exc)}
            )
            self.store.save_document(failed)
            self.store.save_job(
                running_job.model_copy(
                    update={
                        "status": ProcessingStatus.FAILED,
                        "updated_at": self.store.now(),
                    }
                )
            )
            raise

    def resume_pending(self) -> list[DocumentRecord]:
        return [self.process_document(job.id) for job in self.store.pending_jobs()]

    def extract_questions(self, document_id: str) -> list[QuestionCandidate]:
        document = self.store.get_document(document_id)
        if document is None:
            raise KeyError(document_id)

        source_path = self.storage_dir / f"{document_id}.pdf"
        pages = extract_document(str(source_path))
        extracted = reconstruct_question_candidates(pages)

        return [
            QuestionCandidate(
                id=f"{document_id}-{index + 1}",
                document_id=document_id,
                page_start=item.page_start,
                page_end=item.page_end,
                text=item.text,
                number=item.number,
                provenance=[
                    Provenance(
                        document_id=document_id,
                        page_number=page,
                        source_hash=document.sha256,
                        extractor="pymupdf-text-v1",
                    )
                    for page in range(item.page_start, item.page_end + 1)
                ],
            )
            for index, item in enumerate(extracted)
        ]
