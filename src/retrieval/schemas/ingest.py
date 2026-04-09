from typing import Any, Dict, Optional

from pydantic import BaseModel, HttpUrl, Field


class IngestRequest(BaseModel):
    url: HttpUrl
    doc_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    status: str
    doc_id: str
    title: str
    source_url: str
    chunks_count: int
    metadata: Dict[str, Any]