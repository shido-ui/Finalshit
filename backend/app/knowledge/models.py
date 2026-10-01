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
    taxonomy_node_id: str | None = None
    classification_status: ClassificationStatus = ClassificationStatus.UNCLASSIFIED
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_reason: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


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
