import pymupdf

from app.knowledge.extractor import extract_content_blocks
from app.knowledge.models import ContentBlock, DocumentRecord, ProcessingStatus
from app.knowledge.store import KnowledgeStore


def make_pdf(path):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (60, 60),
        "Chapter 1\n"
        "1. Find the velocity of the particle.\n"
        "(A) 10\n"
        "(B) 20\n"
        "(C) 30\n"
        "(D) 40\n"
        "The particle moves uniformly.",
    )
    document.save(path)
    document.close()


def test_extract_content_blocks_classifies_question_options_and_paragraph(tmp_path):
    path = tmp_path / "sample.pdf"
    make_pdf(path)

    blocks = extract_content_blocks(str(path))
    kinds = [block.kind for block in blocks]

    assert "question" in kinds
    assert "option" in kinds
    assert "paragraph" in kinds
    assert all(block.page_number == 1 for block in blocks)
    assert all(block.text for block in blocks)


def test_content_blocks_round_trip_and_filtering(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.save_document(
        DocumentRecord(
            id="doc",
            filename="sample.pdf",
            sha256="source-hash",
            page_count=1,
            status=ProcessingStatus.READY,
        )
    )
    block = ContentBlock(
        id="doc-p1-b1",
        document_id="doc",
        page_number=1,
        block_index=1,
        kind="question",
        text="1. Find the velocity.",
        x0=10,
        y0=20,
        x1=300,
        y1=50,
        asset_ids=[],
        source_hash="source-hash",
        extractor="test",
    )
    store.replace_content_blocks("doc", [block])

    restored = store.get_content_blocks("doc", kind="question")

    assert len(restored) == 1
    assert restored[0].id == block.id
    assert restored[0].source_hash == "source-hash"
    assert store.get_content_blocks("doc", kind="option") == []
