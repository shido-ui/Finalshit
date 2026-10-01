import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from app.knowledge.models import (
    ClassificationStatus,
    DocumentRecord,
    QuestionCandidate,
    TaxonomyNode,
)
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.knowledge.taxonomy import DEFAULT_TAXONOMY

app = FastAPI(title="FocusForge AI Gateway", version="0.1.0")

_data_dir = Path(os.getenv("FOCUSFORGE_DATA_DIR", "data"))
knowledge_service = KnowledgeService(
    store=KnowledgeStore(_data_dir / "knowledge.db"),
    storage_dir=_data_dir / "documents",
)

MAX_PDF_BYTES = 50 * 1024 * 1024


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="focusforge-backend")


@app.get("/api/v1/bootstrap")
def bootstrap() -> dict[str, object]:
    return {
        "service": "focusforge-backend",
        "version": "0.1.0",
        "features": [
            "document-ingestion",
            "question-reconstruction",
            "question-indexing",
            "question-filtering",
            "taxonomy-classification",
            "classification-confidence",
            "classification-quarantine",
            "taxonomy",
            "provenance",
        ],
    }


@app.get("/api/v1/knowledge/taxonomy", response_model=list[TaxonomyNode])
def taxonomy() -> list[TaxonomyNode]:
    return [
        TaxonomyNode(
            id=node.id,
            name=node.name,
            level=node.level,
            parent_id=node.parent_id,
        )
        for node in DEFAULT_TAXONOMY.all()
    ]


@app.post("/api/v1/knowledge/documents", response_model=DocumentRecord)
async def ingest_document(
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
) -> DocumentRecord:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Expected a PDF request body")

    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > MAX_PDF_BYTES:
                raise HTTPException(status_code=413, detail="PDF exceeds 50 MiB limit")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from None

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds 50 MiB limit")
        chunks.append(chunk)

    content = b"".join(chunks)
    try:
        return knowledge_service.ingest_pdf(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/v1/knowledge/documents/{document_id}",
    response_model=DocumentRecord,
)
def get_document(document_id: str) -> DocumentRecord:
    document = knowledge_service.store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.get(
    "/api/v1/knowledge/documents/{document_id}/questions",
    response_model=list[QuestionCandidate],
)
def get_questions(
    document_id: str,
    taxonomy_node_id: str | None = Query(default=None, min_length=1),
    page: int | None = Query(default=None, ge=1),
    classification_status: ClassificationStatus | None = None,
) -> list[QuestionCandidate]:
    try:
        return knowledge_service.extract_questions(
            document_id,
            taxonomy_node_id=taxonomy_node_id,
            page=page,
            classification_status=classification_status,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Document source is missing") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
