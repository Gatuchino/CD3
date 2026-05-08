"""
DocuBot — Schemas Pydantic para proyectos.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    code: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    client_name: Optional[str] = None
    contract_name: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    tenant_id: str
    code: Optional[str]
    name: str
    client_name: Optional[str]
    contract_name: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    id: str
    code: Optional[str]
    name: str
    client_name: Optional[str]
    status: str
    document_count: int = 0
    open_alerts: int = 0
    created_at: datetime

    class Config:
        from_attributes = True
