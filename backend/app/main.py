import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.knowledge.models import (
    ClassificationStatus,
    DocumentAsset,
    DocumentRecord,
    QuestionCandidate,
    TaxonomyNode,
    TaxonomyProposal,
    TaxonomyProposalResolution,
)
from app.knowledge.classifier_ai import default_question_classifier
from app.knowledge.question_intelligence import default_question_intelligence
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.knowledge.taxonomy_ai import GeminiTaxonomyProposalProvider

app = FastAPI(title="FocusForge AI Gateway", version="0.1.0")

_data_dir = Path(os.getenv("FOCUSFORGE_DATA_DIR", "data"))
knowledge_service = KnowledgeService(
    store=KnowledgeStore(_data_dir / "knowledge.db"),
    storage_dir=_data_dir / "documents",
    taxonomy_proposal_provider=GeminiTaxonomyProposalProvider(),
    classifier=default_question_classifier(),
    question_intelligence=default_question_intelligence(),
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
            "jee-2026-paper-1-taxonomy",
            "hierarchical-taxonomy-filtering",
            "ai-taxonomy-discovery",
            "taxonomy-proposals",
            "taxonomy-registry",
            "taxonomy-proposal-resolution",
            "dynamic-taxonomy-classification",
            "ai-question-classification",
            "ai-classification-confidence",
            "ai-classification-fallback",
            "question-intelligence",
            "answer-option-extraction",
            "question-metadata-extraction",
            "visual-asset-extraction",
            "asset-persistence",
            "question-asset-association",
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
        for node in knowledge_service.taxonomy.all()
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




@app.post(
    "/api/v1/knowledge/documents/{document_id}/taxonomy/proposals",
    response_model=list[TaxonomyProposal],
)
def propose_document_taxonomy(document_id: str) -> list[TaxonomyProposal]:
    try:
        return knowledge_service.propose_taxonomy(document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Document source is missing") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc) == "GEMINI_API_KEY is not configured":
            raise HTTPException(status_code=503, detail="Taxonomy AI provider is not configured") from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/api/v1/knowledge/documents/{document_id}/taxonomy/proposals",
    response_model=list[TaxonomyProposal],
)
def get_document_taxonomy_proposals(document_id: str) -> list[TaxonomyProposal]:
    if knowledge_service.store.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return knowledge_service.store.get_taxonomy_proposals(document_id)


class TaxonomyRejectRequest(BaseModel):
    reason: str = Field(default="Rejected during taxonomy review", max_length=500)


@app.post(
    "/api/v1/knowledge/taxonomy/proposals/{proposal_id}/approve",
    response_model=TaxonomyProposalResolution,
)
def approve_taxonomy_proposal(proposal_id: str) -> TaxonomyProposalResolution:
    try:
        return knowledge_service.approve_taxonomy_proposal(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Taxonomy proposal not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/v1/knowledge/taxonomy/proposals/{proposal_id}/reject",
    response_model=TaxonomyProposalResolution,
)
def reject_taxonomy_proposal(
    proposal_id: str,
    request: TaxonomyRejectRequest | None = None,
) -> TaxonomyProposalResolution:
    try:
        return knowledge_service.reject_taxonomy_proposal(
            proposal_id,
            request.reason if request is not None else "Rejected during taxonomy review",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Taxonomy proposal not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get(
    "/api/v1/knowledge/documents/{document_id}/assets",
    response_model=list[DocumentAsset],
)
def get_document_assets(
    document_id: str,
    page: int | None = Query(default=None, ge=1),
) -> list[DocumentAsset]:
    if knowledge_service.store.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return knowledge_service.store.get_document_assets(document_id, page=page)


@app.get("/api/v1/knowledge/assets/{asset_id}")
def get_asset(asset_id: str) -> FileResponse:
    asset = knowledge_service.store.get_document_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    root = knowledge_service.storage_dir.resolve()
    path = (knowledge_service.storage_dir / asset.storage_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Invalid asset storage path") from exc
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Asset file is missing")
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=path.name,
    )


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
    include_descendants: bool = False,
) -> list[QuestionCandidate]:
    try:
        return knowledge_service.extract_questions(
            document_id,
            taxonomy_node_id=taxonomy_node_id,
            page=page,
            classification_status=classification_status,
            include_descendants=include_descendants,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Document source is missing") from exc
    except ValueError as exc:
        status_code = 400 if str(exc).startswith("Unknown taxonomy node:") else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
