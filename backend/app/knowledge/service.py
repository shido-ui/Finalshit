from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pymupdf

from .extractor import extract_document, reconstruct_question_candidates
from .models import DocumentRecord, ProcessingStatus, QuestionCandidate, Provenance
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
            status=ProcessingStatus.EXTRACTING,
        )
        self.store.save_document(record)

        try:
            pages = extract_document(str(source_path))
            questions = reconstruct_question_candidates(pages)
            record = record.model_copy(
                update={
                    "status": ProcessingStatus.READY,
                    "question_count": len(questions),
                }
            )
            self.store.save_document(record)
            return record
        except Exception as exc:
            record = record.model_copy(
                update={"status": ProcessingStatus.FAILED, "error": str(exc)}
            )
            self.store.save_document(record)
            raise

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
