from pathlib import Path

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
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / f"{document_id}.pdf").write_bytes(content)

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
