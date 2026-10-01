from enum import Enum

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"


class ClassificationStatus(str, Enum):
    UNCLASSIFIED = "unclassified"
    CLASSIFIED = "classified"
    QUARANTINED = "quarantined"


class TaxonomyNode(BaseModel):
    id: str
    name: str
    level: str
    parent_id: str | None = None


class Provenance(BaseModel):
    document_id: str
    page_number: int
    source_hash: str
    extractor: str


class DocumentAsset(BaseModel):
    id: str
    document_id: str
    page_number: int
    asset_index: int
    kind: str = "image"
    mime_type: str
    sha256: str
    byte_size: int = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    xref: int = Field(ge=0)
    source_hash: str
    storage_path: str


class ContentBlock(BaseModel):
    id: str
    document_id: str
    page_number: int
    block_index: int
    kind: str
    text: str
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    asset_ids: list[str] = Field(default_factory=list)
    source_hash: str
    extractor: str


class QuestionCandidate(BaseModel):
    id: str
    document_id: str
    page_start: int
    page_end: int
    text: str
    number: str | None = None
    options: dict[str, str] = Field(default_factory=dict)
    answer: str | None = None
    solution: str | None = None
    has_diagram: bool = False
    has_table: bool = False
    exam: str | None = None
    exam_year: int | None = Field(default=None, ge=1900, le=2100)
    difficulty: str | None = None
    intelligence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    intelligence_reason: str | None = None
    intelligence_provider: str | None = None
    asset_ids: list[str] = Field(default_factory=list)
    taxonomy_node_id: str | None = None
    classification_status: ClassificationStatus = ClassificationStatus.UNCLASSIFIED
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_reason: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)



class SolutionStatus(str, Enum):
    GENERATED = "generated"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Solution(BaseModel):
    id: str
    question_id: str
    document_id: str
    answer: str | None = None
    method: str
    steps: list[str] = Field(default_factory=list)
    final_answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: SolutionStatus
    provider: str
    validation_reason: str
    provenance: list[Provenance] = Field(default_factory=list)



class PracticeSession(BaseModel):
    id: str
    mode: str
    question_ids: list[str] = Field(default_factory=list)
    started_at: str
    submitted_at: str | None = None
    score: int | None = None
    total: int = Field(ge=0)
    answered: int = Field(default=0, ge=0)


class LibraryItem(BaseModel):
    id: str
    document_id: str
    title: str
    pinned: bool = False
    archived: bool = False
    fast_mode_enabled: bool = True
    created_at: str
    updated_at: str


class DocumentRecord(BaseModel):
    id: str
    filename: str
    sha256: str
    page_count: int
    status: ProcessingStatus
    error: str | None = None
    question_count: int = 0


class ProcessingJob(BaseModel):
    id: str
    document_id: str
    status: ProcessingStatus
    updated_at: str


class TaxonomyProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaxonomyProposal(BaseModel):
    id: str
    document_id: str
    parent_id: str | None = None
    name: str
    level: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    status: TaxonomyProposalStatus = TaxonomyProposalStatus.PENDING
    provider: str
    resolved_node_id: str | None = None
    resolution_reason: str | None = None


class TaxonomyProposalResolution(BaseModel):
    proposal_id: str
    status: TaxonomyProposalStatus
    resolved_node_id: str | None = None
    created: bool = False
    reason: str
