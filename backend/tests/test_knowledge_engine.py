from pathlib import Path

import pytest
import pymupdf

from app.knowledge.extractor import extract_document, reconstruct_question_candidates
from app.knowledge.models import DocumentRecord, ProcessingJob, ProcessingStatus, Provenance, QuestionCandidate
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.knowledge.taxonomy import Taxonomy, TaxonomyNode


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


def test_indexed_questions_survive_service_reload_and_filter(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")
    record = service.ingest_pdf("sample.pdf", make_pdf())

    indexed = store.get_questions(record.id)
    assert len(indexed) == 2

    classified = indexed[0].model_copy(
        update={"taxonomy_node_id": "physics", "classification_confidence": 0.95}
    )
    store.replace_questions(record.id, [classified, indexed[1]])

    reloaded_store = KnowledgeStore(tmp_path / "knowledge.db")
    reloaded_service = KnowledgeService(
        store=reloaded_store, storage_dir=tmp_path / "documents"
    )

    assert len(reloaded_service.extract_questions(record.id)) == 2
    physics = reloaded_service.extract_questions(
        record.id, taxonomy_node_id="physics"
    )
    assert len(physics) == 1
    assert physics[0].id == classified.id
    assert physics[0].classification_confidence == 0.95

    page_matches = reloaded_service.extract_questions(record.id, page=1)
    assert len(page_matches) == 2


def test_replace_questions_is_atomic_per_document(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.save_document(
        DocumentRecord(
            id="doc",
            filename="doc.pdf",
            sha256="a" * 64,
            page_count=1,
            status=ProcessingStatus.READY,
        )
    )
    question = QuestionCandidate(
        id="doc-1",
        document_id="doc",
        page_start=1,
        page_end=1,
        text="What is force?",
        provenance=[
            Provenance(
                document_id="doc",
                page_number=1,
                source_hash="a" * 64,
                extractor="test",
            )
        ],
    )

    store.replace_questions("doc", [question])
    assert len(store.get_questions("doc")) == 1

    store.replace_questions("doc", [])
    assert store.get_questions("doc") == []


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


def test_empty_content_is_rejected_and_not_persisted(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")

    with pytest.raises(ValueError, match="empty"):
        service.ingest_pdf("empty.pdf", b"")

    assert list((tmp_path / "documents").glob("*.pdf")) == []


def test_invalid_pdf_is_rejected_and_cleaned_up(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(store=store, storage_dir=tmp_path / "documents")

    with pytest.raises(ValueError, match="readable PDF"):
        service.ingest_pdf("broken.pdf", b"not a PDF")

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


def test_tampered_source_is_rejected(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    documents_dir = tmp_path / "documents"
    service = KnowledgeService(store=store, storage_dir=documents_dir)
    record = service.ingest_pdf("sample.pdf", make_pdf())

    source_path = documents_dir / f"{record.id}.pdf"
    source_path.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="hash does not match"):
        service.extract_questions(record.id)

    job = ProcessingJob(
        id="tampered-job",
        document_id=record.id,
        status=ProcessingStatus.QUEUED,
        updated_at=store.now(),
    )
    store.save_job(job)
    pending = service.resume_pending()

    assert pending[-1].status is ProcessingStatus.FAILED
    assert "hash does not match" in pending[-1].error


def test_taxonomy_rejects_invalid_graphs():
    with pytest.raises(ValueError, match="Duplicate"):
        Taxonomy([
            TaxonomyNode("physics", "Physics", "subject"),
            TaxonomyNode("physics", "Physics again", "subject"),
        ])

    with pytest.raises(ValueError, match="missing parent"):
        Taxonomy([
            TaxonomyNode("mechanics", "Mechanics", "chapter", "physics"),
        ])

    with pytest.raises(ValueError, match="cycle"):
        Taxonomy([
            TaxonomyNode("a", "A", "subject", "b"),
            TaxonomyNode("b", "B", "chapter", "a"),
        ])
