import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from app.knowledge.models import (
    ClassificationStatus,
    ContentBlock,
    DocumentAsset,
    DocumentRecord,
    QuestionCandidate,
    Solution,
    LibraryItem,
    PracticeSession,
    MistakeRecord,
    WeaknessProfile,
    ReviewState,
    KnowledgeEdge,
    TaxonomyNode,
    TaxonomyProposal,
    TaxonomyProposalResolution,
)
from app.knowledge.classifier_ai import default_question_classifier
from app.knowledge.question_intelligence import default_question_intelligence
from app.knowledge.solution_engine import SolutionEngine, default_solution_provider
from app.knowledge.copilot import StudyCopilot, default_copilot_provider, CopilotCandidate
from app.knowledge.practice import PracticeResult, PracticeQuestion, PracticeService
from app.knowledge.intelligence import IntelligenceService
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.knowledge.taxonomy_ai import GeminiTaxonomyProposalProvider

app = FastAPI(title="FocusForge AI Gateway", version="0.1.0")


@app.middleware("http")
async def api_access_control(request: Request, call_next) -> Response:
    if request.url.path.startswith("/api/"):
        if API_TOKEN:
            supplied = request.headers.get("Authorization", "")
            if supplied != "Bearer " + API_TOKEN:
                return Response(status_code=401, content="Unauthorized")
        else:
            host = request.client.host if request.client else ""
            if host not in {"127.0.0.1", "::1", "localhost"}:
                return Response(status_code=403, content="Backend is localhost-only unless FOCUSFORGE_API_TOKEN is configured")
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    request_id = request.headers.get("X-Request-ID", "").strip()
    if not request_id or len(request_id) > 128 or any(ord(ch) < 32 or ord(ch) == 127 for ch in request_id):
        request_id = os.urandom(8).hex()
    response.headers["X-Request-ID"] = request_id
    return response

_configured_data_dir = os.getenv("FOCUSFORGE_DATA_DIR")
if _configured_data_dir:
    _data_dir = Path(_configured_data_dir).expanduser().resolve()
else:
    _data_dir = (Path(__file__).resolve().parents[2] / "data").resolve()
_data_dir.mkdir(parents=True, exist_ok=True)

_store = KnowledgeStore(_data_dir / "knowledge.db")
intelligence_service = IntelligenceService(_store)
practice_service = PracticeService(_store, intelligence=intelligence_service)

knowledge_service = KnowledgeService(
    store=_store,
    storage_dir=_data_dir / "documents",
    taxonomy_proposal_provider=GeminiTaxonomyProposalProvider(),
    classifier=default_question_classifier(),
    question_intelligence=default_question_intelligence(),
    solution_engine=SolutionEngine(default_solution_provider()),
)

MAX_PDF_BYTES = 50 * 1024 * 1024
API_TOKEN = os.getenv("FOCUSFORGE_API_TOKEN", "").strip()
study_copilot = StudyCopilot(default_copilot_provider())


class HealthResponse(BaseModel):
    status: str
    service: str



@app.post(
    "/api/v1/knowledge/questions/{question_id}/solution",
    response_model=Solution,
)
def generate_question_solution(question_id: str) -> Solution:
    try:
        return knowledge_service.generate_solution(question_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Document source is missing") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc) == "GEMINI_API_KEY is not configured":
            raise HTTPException(status_code=503, detail="Solution AI provider is not configured") from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/api/v1/knowledge/questions/{question_id}/solution",
    response_model=Solution,
)
def get_question_solution(question_id: str) -> Solution:
    solution = knowledge_service.get_solution(question_id)
    if solution is None:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution



class PracticeStartRequest(BaseModel):
    mode: str = Field(default="fast", max_length=16)
    limit: int = Field(default=10, ge=1, le=100)
    document_id: str | None = None
    taxonomy_node_id: str | None = None
    seed: int | None = None


class LibraryUpdateRequest(BaseModel):
    pinned: bool | None = None
    archived: bool | None = None
    fast_mode_enabled: bool | None = None


class AnswerUpdateRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)


class PracticeStartResponse(BaseModel):
    session: PracticeSession
    questions: list[PracticeQuestion]


class PracticeSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    page_start: int = Field(default=1, ge=1)
    page_end: int = Field(default=1, ge=1)


@app.post(
    "/api/v1/knowledge/documents/{document_id}/copilot",
    response_model=CopilotCandidate,
)
def ask_copilot(document_id: str, request: CopilotRequest) -> CopilotCandidate:
    try:
        return knowledge_service.answer_copilot(
            document_id,
            request.question,
            request.page_start,
            request.page_end,
            study_copilot,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Document source is missing") from exc
    except ValueError as exc:
        if str(exc) == "GEMINI_API_KEY is not configured":
            raise HTTPException(status_code=503, detail="Study Copilot is not configured") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc) == "GEMINI_API_KEY is not configured":
            raise HTTPException(status_code=503, detail="Study Copilot is not configured") from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/library", response_model=list[LibraryItem])
def get_library(include_archived: bool = False) -> list[LibraryItem]:
    return knowledge_service.store.get_library_items(include_archived=include_archived)


@app.patch("/api/v1/library/{document_id}", response_model=LibraryItem)
def update_library_item(
    document_id: str,
    request: LibraryUpdateRequest,
) -> LibraryItem:
    document = knowledge_service.store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    current = knowledge_service.store.get_library_item(document_id)
    if current is None:
        now = knowledge_service.store.now()
        current = LibraryItem(
            id=f"library-{document_id}",
            document_id=document_id,
            title=document.filename,
            created_at=now,
            updated_at=now,
        )
    updated = current.model_copy(
        update={
            "pinned": current.pinned if request.pinned is None else request.pinned,
            "archived": current.archived if request.archived is None else request.archived,
            "fast_mode_enabled": (
                current.fast_mode_enabled if request.fast_mode_enabled is None else request.fast_mode_enabled
            ),
            "updated_at": knowledge_service.store.now(),
        }
    )
    knowledge_service.store.save_library_item(updated)
    return updated


@app.post("/api/v1/practice/sessions", response_model=PracticeStartResponse)
def start_practice(request: PracticeStartRequest) -> PracticeStartResponse:
    if request.document_id is not None:
        document = knowledge_service.store.get_document(request.document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        library_item = knowledge_service.store.get_library_item(request.document_id)
        if library_item is not None and library_item.archived:
            raise HTTPException(status_code=409, detail="Archived documents are excluded from practice")
        if request.mode == "fast" and library_item is not None and not library_item.fast_mode_enabled:
            raise HTTPException(status_code=409, detail="Fast Mode is disabled for this document")
        questions = knowledge_service.store.get_questions(request.document_id)
    else:
        library = [
            item for item in knowledge_service.store.get_library_items()
            if not item.archived and (request.mode != "fast" or item.fast_mode_enabled)
        ]
        questions = [
            question
            for item in library
            for question in knowledge_service.store.get_questions(item.document_id)
        ]

    if request.taxonomy_node_id is not None:
        try:
            node_ids = knowledge_service.taxonomy.descendant_ids(
                request.taxonomy_node_id, include_self=True
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Unknown taxonomy node") from exc
        questions = [
            question for question in questions
            if question.taxonomy_node_id in node_ids
        ]

    try:
        session, public_questions = practice_service.create_session(
            questions, request.mode, request.limit, request.seed
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PracticeStartResponse(session=session, questions=public_questions)


@app.get("/api/v1/knowledge/jobs/{job_id}", response_model=ProcessingJob)
def get_processing_job(job_id: str) -> ProcessingJob:
    job = knowledge_service.store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return job


@app.patch("/api/v1/knowledge/questions/{question_id}/answer", response_model=QuestionCandidate)
def set_question_answer(question_id: str, request: AnswerUpdateRequest) -> QuestionCandidate:
    question = knowledge_service.store.get_question(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    updated = question.model_copy(update={"answer": request.answer.strip()})
    knowledge_service.store.save_question(updated)
    return updated


@app.get("/api/v1/practice/sessions/{session_id}", response_model=PracticeStartResponse)
def get_practice_session(session_id: str) -> PracticeStartResponse:
    try:
        session, questions = practice_service.resume_session(session_id)
        return PracticeStartResponse(session=session, questions=questions)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Practice session not found") from exc


@app.post("/api/v1/practice/sessions/{session_id}/submit", response_model=PracticeResult)
def submit_practice(session_id: str, request: PracticeSubmitRequest) -> PracticeResult:
    try:
        return practice_service.submit(session_id, request.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Practice session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/intelligence/mistakes", response_model=list[MistakeRecord])
def get_mistakes(
    question_id: str | None = Query(default=None, min_length=1),
    taxonomy_node_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MistakeRecord]:
    return intelligence_service.store.get_mistakes(
        question_id=question_id,
        taxonomy_node_id=taxonomy_node_id,
        limit=limit,
    )


@app.get("/api/v1/intelligence/weaknesses", response_model=list[WeaknessProfile])
def get_weaknesses(limit: int = Query(default=100, ge=1, le=500)) -> list[WeaknessProfile]:
    return intelligence_service.store.get_weaknesses(limit=limit)


@app.get("/api/v1/intelligence/reviews/due", response_model=list[str])
def get_due_reviews(limit: int = Query(default=100, ge=1, le=500)) -> list[str]:
    return intelligence_service.store.get_due_review_question_ids(
        intelligence_service.store.now(),
        limit=limit,
    )


@app.get("/api/v1/intelligence/reviews/{question_id}", response_model=ReviewState)
def get_review_state(question_id: str) -> ReviewState:
    state = intelligence_service.store.get_review_state(question_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Review state not found")
    return state


@app.get("/api/v1/intelligence/graph/edges", response_model=list[KnowledgeEdge])
def get_knowledge_edges(
    node_id: str | None = Query(default=None, min_length=1),
    relation: str | None = Query(default=None, min_length=1),
) -> list[KnowledgeEdge]:
    return intelligence_service.store.get_knowledge_edges(node_id=node_id, relation=relation)


@app.post("/api/v1/intelligence/graph/edges", response_model=KnowledgeEdge)
def save_knowledge_edge(edge: KnowledgeEdge) -> KnowledgeEdge:
    node_ids = {node.id for node in knowledge_service.taxonomy.all()}
    if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
        raise HTTPException(status_code=400, detail="Knowledge graph edge references an unknown taxonomy node")
    intelligence_service.store.save_knowledge_edge(edge)
    return edge


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
            "rich-content-block-extraction",
            "content-block-persistence",
            "provenance",
            "structured-solutions",
            "grounded-solution-generation",
            "solution-validation",
            "solution-provenance",
            "local-library",
            "fast-mode",
            "question-bank",
            "practice-sessions",
            "practice-scoring",
            "mistake-intelligence",
            "weakness-model",
            "adaptive-practice",
            "spaced-repetition",
            "knowledge-graph-foundation",
            "grounded-study-copilot",
            "copilot-source-citations",
            "device-owner-lock-task-hard-mode",
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
    background_tasks: BackgroundTasks,
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
        record = knowledge_service.ingest_pdf(filename, content, process=False)
        job = knowledge_service.store.pending_jobs()
        matching = next((item for item in job if item.document_id == record.id), None)
        if matching is None:
            raise HTTPException(status_code=500, detail="Ingestion job was not created")
        background_tasks.add_task(knowledge_service.process_document, matching.id)
        return record
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
    "/api/v1/knowledge/documents/{document_id}/content-blocks",
    response_model=list[ContentBlock],
)
def get_content_blocks(
    document_id: str,
    page: int | None = Query(default=None, ge=1),
    kind: str | None = Query(default=None, min_length=1, max_length=32),
) -> list[ContentBlock]:
    if knowledge_service.store.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return knowledge_service.extract_content_blocks(document_id, page=page, kind=kind)


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


@app.get("/api/v1/knowledge/questions/{question_id}/assets", response_model=list[DocumentAsset])
def get_question_assets(question_id: str) -> list[DocumentAsset]:
    question = knowledge_service.store.get_question(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return knowledge_service.store.get_question_assets(question_id)


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


@app.delete("/api/v1/knowledge/documents/{document_id}", status_code=204)
def delete_document(document_id: str) -> Response:
    document = knowledge_service.store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    deleted = knowledge_service.store.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    source_path = knowledge_service.storage_dir / (document_id + ".pdf")
    source_path.unlink(missing_ok=True)
    asset_dir = knowledge_service.storage_dir / "assets" / document_id
    import shutil
    shutil.rmtree(asset_dir, ignore_errors=True)
    return Response(status_code=204)


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
