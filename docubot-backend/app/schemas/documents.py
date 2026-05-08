"""
DocuBot — Schemas Pydantic para documentos y versiones.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


VALID_DOCUMENT_TYPES = [
    "contract", "addendum", "rfi", "transmittal", "meeting_minutes",
    "technical_specification", "drawing", "schedule", "commercial_proposal",
    "technical_proposal", "purchase_order", "change_order", "claim",
    "letter", "report", "other"
]

VALID_DISCIPLINES = [
    "contractual", "commercial", "engineering", "construction", "procurement",
    "safety", "environmental", "quality", "planning", "operations", "legal", "other"
]


class DocumentUploadResponse(BaseModel):
    document_id: str
    document_version_id: str
    file_name: str
    checksum_sha256: str
    blob_path: str
    processing_status: str
    message: str


class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version_label: Optional[str]
    revision_number: Optional[str]
    file_name: str
    file_type: str
    processing_status: str
    page_count: Optional[int]
    uploaded_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    title: str
    document_code: Optional[str]
    document_type: Optional[str]
    discipline: Optional[str]
    current_status: str
    current_version_id: Optional[str]
    created_at: datetime
    versions: List[DocumentVersionResponse] = []

    class Config:
        from_attributes = True


class DocumentListItem(BaseModel):
    id: str
    title: str
    document_code: Optional[str]
    document_type: Optional[str]
    discipline: Optional[str]
    current_status: str
    revision_number: Optional[str]
    processing_status: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProcessingStatusResponse(BaseModel):
    document_version_id: str
    processing_status: str
    steps: List[str] = [
        "file_validation",
        "ocr",
        "text_extraction",
        "classification",
        "chunking",
        "embeddings",
        "obligation_extraction",
        "alert_generation",
    ]
    current_step: Optional[str] = None
    error: Optional[str] = None
