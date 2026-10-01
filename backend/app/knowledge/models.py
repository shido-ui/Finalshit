from enum import Enum
from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"


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
    taxonomy_node_id: str | None = None
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: list[Provenance] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    id: str
    filename: str
    sha256: str
    page_count: int
    status: ProcessingStatus
    error: str | None = None
    question_count: int = 0
