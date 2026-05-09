"""
DocuBot — Modelos SQLAlchemy para todas las tablas del sistema.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, BigInteger, Text, DateTime,
    Numeric, Date, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.session import Base


def gen_uuid():
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    country = Column(String(100), default="Chile")
    industry = Column(String(150))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="tenant")
    projects = relationship("Project", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(80), nullable=False)
    password_hash = Column(String(255))
    azure_b2c_subject = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(100))
    name = Column(String(255), nullable=False)
    client_name = Column(String(255))
    contract_name = Column(String(255))
    status = Column(String(50), default="active")
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="projects")
    documents = relationship("Document", back_populates="project")
    alerts = relationship("Alert", back_populates="project")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    document_code = Column(String(150))
    document_type = Column(String(100))
    discipline = Column(String(100))
    current_status = Column(String(80), default="active")
    current_version_id = Column(UUID(as_uuid=False), nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document",
                            foreign_keys="DocumentVersion.document_id")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_label = Column(String(80))
    revision_number = Column(String(80))
    file_name = Column(String(500), nullable=False)
    file_type = Column(String(30), nullable=False)
    blob_url = Column(Text, nullable=False)
    blob_path = Column(Text)
    processing_status = Column(String(80), default="uploaded")
    processing_error = Column(Text)
    checksum_sha256 = Column(String(128))
    file_size_bytes = Column(BigInteger)
    page_count = Column(Integer)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="versions", foreign_keys=[document_id])
    pages = relationship("DocumentPage", back_populates="version")
    chunks = relationship("DocumentChunk", back_populates="version")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_version_id", "page_number"),)

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    extracted_text = Column(Text)
    layout_metadata = Column(JSONB)
    ocr_confidence = Column(Numeric(5, 2))
    ocr_engine = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    version = relationship("DocumentVersion", back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_version_id", "chunk_index"),)

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(UUID(as_uuid=False), ForeignKey("document_pages.id"), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    section_title = Column(String(500))
    paragraph_number = Column(String(100))
    start_page = Column(Integer)
    end_page = Column(Integer)
    token_count = Column(Integer)
    source_reference = Column(JSONB)
    chunk_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    version = relationship("DocumentVersion", back_populates="chunks")
    embedding = relationship("ChunkEmbedding", back_populates="chunk", uselist=False)


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    chunk_id = Column(UUID(as_uuid=False), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    embedding = Column(Vector(1536))
    embedding_model = Column(String(100), default="text-embedding-3-small")
    created_at = Column(DateTime, default=datetime.utcnow)

    chunk = relationship("DocumentChunk", back_populates="embedding")


class DocumentClassification(Base):
    __tablename__ = "document_classifications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(120))
    discipline = Column(String(120))
    project_phase = Column(String(120))
    detected_metadata = Column(JSONB)
    confidence_score = Column(Numeric(5, 2))
    classification_reason = Column(Text)
    requires_human_validation = Column(Boolean, default=True)
    validated_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExtractedObligation(Base):
    __tablename__ = "extracted_obligations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id"), nullable=False)
    obligation_type = Column(String(120))
    obligation_text = Column(Text, nullable=False)
    responsible_party = Column(String(255))
    consequence = Column(Text)
    source_reference = Column(JSONB)
    confidence_score = Column(Numeric(5, 2))
    requires_human_validation = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExtractedDeadline(Base):
    __tablename__ = "extracted_deadlines"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id"), nullable=False)
    deadline_type = Column(String(120))
    description = Column(Text, nullable=False)
    due_date = Column(Date)
    relative_deadline = Column(String(255))
    responsible_party = Column(String(255))
    source_reference = Column(JSONB)
    confidence_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(100), nullable=False)
    severity = Column(String(50), default="medium")
    title = Column(String(500), nullable=False)
    description = Column(Text)
    due_date = Column(Date)
    status = Column(String(50), default="open")
    source_document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id"), nullable=True)
    source_reference = Column(JSONB)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="alerts")


class VersionDiff(Base):
    __tablename__ = "version_diffs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    previous_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id"), nullable=False)
    new_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id"), nullable=False)
    diff_type = Column(String(100))
    semantic_summary = Column(Text)
    critical_changes = Column(JSONB)
    obligations_changed = Column(JSONB)
    deadlines_changed = Column(JSONB)
    commercial_impacts = Column(JSONB)
    technical_impacts = Column(JSONB)
    risk_level = Column(String(50))
    requires_legal_review = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RagQuery(Base):
    __tablename__ = "rag_queries"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    interpretation = Column(Text)
    risks_warnings = Column(JSONB)
    confidence = Column(Numeric(5, 2))
    requires_human_review = Column(Boolean, default=True)
    model_name = Column(String(100))
    retrieval_k = Column(Integer, default=8)
    latency_ms = Column(Integer)
    filters_used = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    citations = relationship("RagCitation", back_populates="query")


class RagCitation(Base):
    __tablename__ = "rag_citations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    query_id = Column(UUID(as_uuid=False), ForeignKey("rag_queries.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(UUID(as_uuid=False), ForeignKey("document_versions.id"), nullable=False)
    chunk_id = Column(UUID(as_uuid=False), ForeignKey("document_chunks.id"), nullable=True)
    page_number = Column(Integer)
    paragraph_ref = Column(String(200))
    quoted_text = Column(Text)
    relevance_score = Column(Numeric(8, 5))
    source_reference = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    query = relationship("RagQuery", back_populates="citations")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action = Column(String(150), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(UUID(as_uuid=False))
    details = Column(JSONB)
    ip_address = Column(String(100))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
