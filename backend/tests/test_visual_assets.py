import base64
import hashlib

import pymupdf

from app.knowledge.extractor import asset_id, extract_document_assets
from app.knowledge.models import DocumentAsset, DocumentRecord, ProcessingStatus, QuestionCandidate
from app.knowledge.store import KnowledgeStore


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def make_pdf(path):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "1. Which value is correct?")
    page.insert_text((72, 96), "(A) 1")
    page.insert_text((72, 112), "(B) 2")
    page.insert_text((72, 128), "(C) 3")
    page.insert_text((72, 144), "(D) 4")
    page.insert_image(pymupdf.Rect(72, 170, 172, 270), stream=ONE_PIXEL_PNG)
    document.save(path)
    document.close()


def test_extract_embedded_image_with_deterministic_id(tmp_path):
    path = tmp_path / "sample.pdf"
    make_pdf(path)

    first = extract_document_assets(str(path))
    second = extract_document_assets(str(path))

    assert len(first) == 1
    assert len(first[0].data) > 0
    assert hashlib.sha256(first[0].data).hexdigest() == hashlib.sha256(second[0].data).hexdigest()
    assert first[0].width == 1
    assert first[0].height == 1
    assert asset_id("doc", first[0]) == asset_id("doc", second[0])


def test_store_round_trips_document_assets_and_question_links(tmp_path):
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

    asset = DocumentAsset(
        id="doc-p1-a1-hash",
        document_id="doc",
        page_number=1,
        asset_index=1,
        mime_type="image/png",
        sha256="asset-hash",
        byte_size=10,
        width=100,
        height=50,
        xref=7,
        source_hash="source-hash",
        storage_path="assets/doc/doc-p1-a1-hash.png",
    )
    store.replace_document_assets("doc", [asset])

    question = QuestionCandidate(
        id="q1",
        document_id="doc",
        page_start=1,
        page_end=1,
        text="1. Which value is correct?",
        asset_ids=[asset.id],
    )
    store.replace_questions("doc", [question])

    restored_asset = store.get_document_assets("doc")[0]
    restored_question = store.get_questions("doc")[0]

    assert restored_asset.id == asset.id
    assert restored_asset.source_hash == "source-hash"
    assert restored_question.asset_ids == [asset.id]


def test_asset_storage_metadata_points_inside_document_storage(tmp_path):
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
    asset = DocumentAsset(
        id="doc-p1-a1-hash",
        document_id="doc",
        page_number=1,
        asset_index=1,
        mime_type="image/png",
        sha256="asset-hash",
        byte_size=10,
        width=1,
        height=1,
        xref=1,
        source_hash="source-hash",
        storage_path="assets/doc/image.png",
    )
    store.replace_document_assets("doc", [asset])
    restored = store.get_document_asset(asset.id)

    assert restored is not None
    assert restored.storage_path == "assets/doc/image.png"
