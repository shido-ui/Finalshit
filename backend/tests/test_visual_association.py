import base64
import pymupdf

from app.knowledge.extractor import extract_document_assets
from app.knowledge.models import DocumentAsset
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def make_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "1. What is the value?")
    page.insert_image(pymupdf.Rect(50, 70, 150, 170), stream=ONE_PIXEL_PNG)
    page.insert_text((50, 200), "(A) 1")
    doc.save(path)
    doc.close()


def test_asset_extraction_contains_placement_bbox(tmp_path):
    path = tmp_path / "sample.pdf"
    make_pdf(path)
    assets = extract_document_assets(str(path))
    assert len(assets) == 1
    assert assets[0].bbox[2] > assets[0].bbox[0]
    assert assets[0].bbox[3] > assets[0].bbox[1]


def test_asset_store_migrates_and_round_trips_geometry(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    from app.knowledge.models import DocumentRecord, ProcessingStatus
    store.save_document(DocumentRecord(
        id="doc", filename="x.pdf", sha256="h", page_count=1,
        status=ProcessingStatus.READY,
    ))
    asset = DocumentAsset(
        id="a", document_id="doc", page_number=1, asset_index=1,
        mime_type="image/png", sha256="ah", byte_size=10,
        width=1, height=1, x0=10, y0=20, x1=30, y1=40, xref=1,
        source_hash="h", storage_path="assets/doc/a.png",
    )
    store.replace_document_assets("doc", [asset])
    restored = store.get_document_asset("a")
    assert restored is not None
    assert (restored.x0, restored.y0, restored.x1, restored.y1) == (10, 20, 30, 40)
