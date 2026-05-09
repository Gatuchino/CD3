"""Crear schema inicial DocuBot — 14 tablas + pgvector

Revision ID: 0001
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensiones PostgreSQL ─────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── tenants ────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), server_default="Chile"),
        sa.Column("industry", sa.String(150)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )

    # ── users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("role", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("azure_b2c_subject", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── projects ───────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(100)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_name", sa.String(255)),
        sa.Column("contract_name", sa.String(255)),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # ── documents ──────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("document_code", sa.String(150)),
        sa.Column("document_type", sa.String(100)),
        sa.Column("discipline", sa.String(100)),
        sa.Column("current_status", sa.String(80), server_default="active"),
        sa.Column("current_version_id", UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])

    # ── document_versions ──────────────────────────────────────────────
    op.create_table(
        "document_versions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_id", UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_label", sa.String(50)),
        sa.Column("revision_number", sa.String(50)),
        sa.Column("blob_url", sa.String(1024)),
        sa.Column("file_name", sa.String(500)),
        sa.Column("file_size_bytes", sa.BigInteger),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("sha256_hash", sa.String(64)),
        sa.Column("processing_status", sa.String(80), server_default="pending"),
        sa.Column("processing_error", sa.Text),
        sa.Column("processing_started_at", sa.DateTime),
        sa.Column("processing_finished_at", sa.DateTime),
        sa.Column("page_count", sa.Integer),
        sa.Column("uploaded_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_docver_document_id", "document_versions", ["document_id"])
    op.create_index("ix_docver_processing_status", "document_versions", ["processing_status"])

    # FK circular documents → document_versions (current_version_id)
    op.create_foreign_key(
        "fk_documents_current_version",
        "documents", "document_versions",
        ["current_version_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── document_pages ─────────────────────────────────────────────────
    op.create_table(
        "document_pages",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_version_id", UUID(as_uuid=False), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("extracted_text", sa.Text),
        sa.Column("ocr_confidence", sa.Numeric(5, 4)),
        sa.Column("has_tables", sa.Boolean, server_default="false"),
        sa.Column("has_figures", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_docpages_version_id", "document_pages", ["document_version_id"])

    # ── document_chunks ────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_version_id", UUID(as_uuid=False), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("chunk_metadata", JSONB),
        sa.Column("token_count", sa.Integer),
        sa.Column("start_page", sa.Integer),
        sa.Column("end_page", sa.Integer),
        sa.Column("section_title", sa.String(500)),
        sa.Column("paragraph_number", sa.String(50)),
        sa.Column("chunk_type", sa.String(80)),
        sa.Column("source_reference", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_chunks_version_id", "document_chunks", ["document_version_id"])

    # Columna vector nativa (pgvector) — no soportada por DDL de SA, usar SQL directo
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(3072)")
    # Índices vectoriales e índices GIN se crean post-deploy para no bloquear startup.

    # ── obligations ────────────────────────────────────────────────────
    op.create_table(
        "obligations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_version_id", UUID(as_uuid=False), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("obligation_type", sa.String(100)),
        sa.Column("responsible_party", sa.String(255)),
        sa.Column("due_date", sa.Date),
        sa.Column("recurrence", sa.String(80)),
        sa.Column("clause_reference", sa.String(100)),
        sa.Column("status", sa.String(80), server_default="pending"),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("needs_human_validation", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_obligations_version_id", "obligations", ["document_version_id"])
    op.create_index("ix_obligations_due_date", "obligations", ["due_date"])
    op.create_index("ix_obligations_status", "obligations", ["status"])

    # ── alerts ─────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obligation_id", UUID(as_uuid=False), sa.ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_version_id", UUID(as_uuid=False), sa.ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("due_date", sa.Date),
        sa.Column("status", sa.String(80), server_default="open"),
        sa.Column("acknowledged_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_alerts_tenant_id", "alerts", ["tenant_id"])
    op.create_index("ix_alerts_project_id", "alerts", ["project_id"])
    op.create_index("ix_alerts_status_severity", "alerts", ["status", "severity"])
    op.create_index("ix_alerts_due_date", "alerts", ["due_date"])

    # ── rag_queries ────────────────────────────────────────────────────
    op.create_table(
        "rag_queries",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text),
        sa.Column("interpretation", sa.Text),
        sa.Column("risks_warnings", JSONB),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("requires_human_review", sa.Boolean, server_default="false"),
        sa.Column("model_name", sa.String(100)),
        sa.Column("retrieval_k", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("filters_used", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_ragq_tenant_id", "rag_queries", ["tenant_id"])
    op.create_index("ix_ragq_project_id", "rag_queries", ["project_id"])
    op.create_index("ix_ragq_created_at", "rag_queries", ["created_at"])

    # ── rag_citations ──────────────────────────────────────────────────
    op.create_table(
        "rag_citations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("query_id", UUID(as_uuid=False), sa.ForeignKey("rag_queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_version_id", UUID(as_uuid=False), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=False), nullable=True),
        sa.Column("page_number", sa.Integer),
        sa.Column("paragraph_ref", sa.String(200)),
        sa.Column("relevance_score", sa.Numeric(6, 5)),
        sa.Column("source_reference", JSONB),
    )
    op.create_index("ix_ragcit_query_id", "rag_citations", ["query_id"])

    # ── audit_logs ─────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", sa.String(255)),
        sa.Column("details", JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])

    # ── document_classifications ───────────────────────────────────────
    op.create_table(
        "document_classifications",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_version_id", UUID(as_uuid=False), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detected_type", sa.String(100)),
        sa.Column("detected_discipline", sa.String(100)),
        sa.Column("confidence_type", sa.Numeric(5, 4)),
        sa.Column("confidence_discipline", sa.Numeric(5, 4)),
        sa.Column("validated_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("validated_at", sa.DateTime),
        sa.Column("final_type", sa.String(100)),
        sa.Column("final_discipline", sa.String(100)),
        sa.Column("needs_human_validation", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_class_version_id", "document_classifications", ["document_version_id"])


def downgrade() -> None:
    op.drop_table("document_classifications")
    op.drop_table("audit_logs")
    op.drop_table("rag_citations")
    op.drop_table("rag_queries")
    op.drop_table("alerts")
    op.drop_table("obligations")
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_current_version")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
