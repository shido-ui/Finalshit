from pathlib import Path

import pytest
import pymupdf

from app.knowledge.extractor import extract_document, reconstruct_question_candidates
from app.knowledge.models import DocumentRecord, ProcessingJob, ProcessingStatus
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore


def make_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (50, 60),
        "1. A particle moves with velocity v. What is its speed?\n"
        "(A) v\n(B) -v\n(C) |v|\n(D) 0\n"
        "2. What is Newton's second law?\n"
        "(A) F=ma\n(B) E=mc2\n(C) p=mv\n(D) W=Fd",
    )
    content = document.tobytes()
    document.close()
    return content


def make_empty_pdf() -> bytes:
    document = pymupdf.open()
    content = document.tobytes()
    document.close()
    return content


def test_question_reconstruction(tmp_path: Path):
    pdf_path = tmp_path / "focusforge-test.pdf"
    pdf_path.write_bytes(make_pdf())

    pages = extract_document(str(pdf_path))
    questions = reconstruct_question_candidates(pages)

    assert len(questions) == 2
    assert questions[0].number == "1"
    assert questions[1].number == "2"


def test_ingestion_is_provenanced_and_resumable(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")
    record = service.ingest_pdf("sample.pdf", make_pdf())

    assert record.status is ProcessingStatus.READY
    assert record.page_count == 1
    assert record.question_count == 2

    questions = service.extract_questions(record.id)
    assert len(questions) == 2
    assert questions[0].provenance[0].source_hash == record.sha256
    assert questions[0].provenance[0].page_number == 1


def test_pending_job_can_resume(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")
    content = make_pdf()

    digest = __import__("hashlib").sha256(content).hexdigest()
    document_id = digest[:24]
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(exist_ok=True)
    (documents_dir / f"{document_id}.pdf").write_bytes(content)

    store.save_document(
        DocumentRecord(
            id=document_id,
            filename="resume.pdf",
            sha256=digest,
            page_count=1,
            status=ProcessingStatus.QUEUED,
        )
    )
    job = ProcessingJob(
        id="resume-job",
        document_id=document_id,
        status=ProcessingStatus.QUEUED,
        updated_at=store.now(),
    )
    store.save_job(job)

    resumed = service.resume_pending()

    assert resumed[0].status is ProcessingStatus.READY
    assert store.pending_jobs() == []


def test_empty_pdf_is_rejected_and_not_persisted(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")

    with pytest.raises(ValueError, match="no pages"):
        service.ingest_pdf("empty.pdf", make_empty_pdf())

    assert list((tmp_path / "documents").glob("*.pdf")) == []


def test_missing_source_is_reported_as_a_consistent_failure(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")

    record = DocumentRecord(
        id="missing-source",
        filename="missing.pdf",
        sha256="a" * 64,
        page_count=1,
        status=ProcessingStatus.QUEUED,
    )
    store.save_document(record)
    store.save_job(
        ProcessingJob(
            id="missing-job",
            document_id=record.id,
            status=ProcessingStatus.QUEUED,
            updated_at=store.now(),
        )
    )

    result = service.resume_pending()

    assert result[0].status is ProcessingStatus.FAILED
    assert result[0].error == "Source PDF is missing"
    assert store.get_job("missing-job").status is ProcessingStatus.FAILED


def test_extract_questions_requires_source_file(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")
    record = DocumentRecord(
        id="missing-source",
        filename="missing.pdf",
        sha256="a" * 64,
        page_count=1,
        status=ProcessingStatus.READY,
    )
    store.save_document(record)

    with pytest.raises(FileNotFoundError):
        service.extract_questions(record.id)
