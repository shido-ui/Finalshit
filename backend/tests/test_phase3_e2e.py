import pymupdf

from app.knowledge.classifier import DEFAULT_CLASSIFIER
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore


def build_fixture_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (50, 50),
        "1. A particle has velocity v.\n"
        "(A) 10 m/s\n"
        "(B) 20 m/s\n"
        "(C) 30 m/s\n"
        "(D) 40 m/s",
    )
    page.draw_rect(pymupdf.Rect(50, 120, 150, 180))
    output = document.tobytes()
    document.close()
    return output


def test_phase3_ingestion_end_to_end_persists_all_core_artifacts(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    service = KnowledgeService(
        store=store,
        storage_dir=tmp_path / "storage",
        classifier=DEFAULT_CLASSIFIER,
        question_intelligence=None,
    )

    record = service.ingest_pdf("fixture.pdf", build_fixture_pdf())

    assert record.status.value == "ready"
    assert record.page_count == 1

    assets = store.get_document_assets(record.id)
    blocks = store.get_content_blocks(record.id)
    questions = store.get_questions(record.id)

    assert assets == []
    assert blocks
    assert any(block.kind == "question" for block in blocks)
    assert questions
    question = questions[0]
    assert question.document_id == record.id
    assert question.page_start == 1
    assert question.page_end == 1
    assert question.provenance
    assert all(item.source_hash == record.sha256 for item in question.provenance)

    restored = store.get_document(record.id)
    assert restored is not None
    assert restored.sha256 == record.sha256
