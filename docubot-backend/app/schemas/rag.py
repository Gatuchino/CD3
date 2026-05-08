"""
DocuBot — Schemas Pydantic para consultas RAG.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class RagFilters(BaseModel):
    document_types: Optional[List[str]] = None
    disciplines: Optional[List[str]] = None
    revision_policy: str = "latest_only"   # "latest_only" | "all_revisions"
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class RagQueryRequest(BaseModel):
    project_id: str
    question: str = Field(..., min_length=5, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)
    filters: Optional[RagFilters] = None


class RagEvidence(BaseModel):
    document: str
    revision: Optional[str]
    page: Optional[str]
    paragraph: Optional[str]
    quote: str
    relevance_score: Optional[float] = None


class RagQueryResponse(BaseModel):
    query_id: str
    answer: str
    evidence: List[RagEvidence]
    interpretation: Optional[str]
    risks_or_warnings: List[str] = []
    confidence: float
    requires_human_review: bool
    latency_ms: Optional[int]
    created_at: datetime


class AlertResponse(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    title: str
    description: Optional[str]
    due_date: Optional[str]
    status: str
    source_reference: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class AlertsListResponse(BaseModel):
    project_id: str
    total: int
    alerts: List[AlertResponse]
