from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="FocusForge AI Gateway", version="0.1.0")

class HealthResponse(BaseModel):
    status: str
    service: str

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="focusforge-backend")

@app.get("/api/v1/bootstrap")
def bootstrap() -> dict[str, object]:
    return {"service": "focusforge-backend", "version": "0.1.0", "features": ["document-ingestion", "solutions", "verification"]}
