from pydantic import BaseModel, Field

class CopilotCandidate(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    citations: list[int] = Field(default_factory=list, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=2000)
