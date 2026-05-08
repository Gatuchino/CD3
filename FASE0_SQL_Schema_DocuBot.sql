-- ============================================================
-- DocuBot — Aurenza IA — Módulo 02
-- Script SQL completo: Modelo de datos MVP
-- Base de datos: PostgreSQL 16 + pgvector + pg_trgm
-- Fecha: 2026-05-06
-- ============================================================

-- ------------------------------------------------------------
-- EXTENSIONES
-- ------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ------------------------------------------------------------
-- TABLA: tenants
-- Empresas clientes (multi-tenant SaaS)
-- ------------------------------------------------------------
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    country         VARCHAR(100) DEFAULT 'Chile',
    industry        VARCHAR(150),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: users
-- Usuarios por tenant con roles
-- Roles: admin_tenant | project_manager | contract_manager |
--        document_controller | viewer | auditor
-- ------------------------------------------------------------
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    email               VARCHAR(255) UNIQUE NOT NULL,
    role                VARCHAR(80) NOT NULL
                            CHECK (role IN (
                                'admin_tenant',
                                'project_manager',
                                'contract_manager',
                                'document_controller',
                                'viewer',
                                'auditor'
                            )),
    azure_b2c_subject   VARCHAR(255),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: projects
-- Proyectos documentales por tenant
-- ------------------------------------------------------------
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code            VARCHAR(100),
    name            VARCHAR(255) NOT NULL,
    client_name     VARCHAR(255),
    contract_name   VARCHAR(255),
    status          VARCHAR(50) DEFAULT 'active'
                        CHECK (status IN ('active', 'closed', 'archived')),
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: documents
-- Documentos por proyecto (cada documento puede tener N versiones)
-- current_version_id apunta a la revisión vigente
-- ------------------------------------------------------------
CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title               VARCHAR(500) NOT NULL,
    document_code       VARCHAR(150),
    document_type       VARCHAR(100)
                            CHECK (document_type IN (
                                'contract', 'addendum', 'rfi', 'transmittal',
                                'meeting_minutes', 'technical_specification',
                                'drawing', 'schedule', 'commercial_proposal',
                                'technical_proposal', 'purchase_order',
                                'change_order', 'claim', 'letter', 'report', 'other'
                            )),
    discipline          VARCHAR(100)
                            CHECK (discipline IN (
                                'contractual', 'commercial', 'engineering',
                                'construction', 'procurement', 'safety',
                                'environmental', 'quality', 'planning',
                                'operations', 'legal', 'other'
                            )),
    current_status      VARCHAR(80) DEFAULT 'active'
                            CHECK (current_status IN ('active', 'superseded', 'cancelled', 'archived')),
    current_version_id  UUID,   -- FK añadida después de document_versions
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: document_versions
-- Cada revisión de un documento
-- processing_status: uploaded | processing | processed | error
-- ------------------------------------------------------------
CREATE TABLE document_versions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_label       VARCHAR(80),
    revision_number     VARCHAR(80),
    file_name           VARCHAR(500) NOT NULL,
    file_type           VARCHAR(30) NOT NULL
                            CHECK (file_type IN ('pdf', 'docx', 'xlsx', 'png', 'jpg', 'jpeg', 'tiff')),
    blob_url            TEXT NOT NULL,
    blob_path           TEXT,
    processing_status   VARCHAR(80) DEFAULT 'uploaded'
                            CHECK (processing_status IN (
                                'uploaded', 'processing', 'processed',
                                'error', 'pending_review'
                            )),
    processing_error    TEXT,
    checksum_sha256     VARCHAR(128),
    file_size_bytes     BIGINT,
    page_count          INTEGER,
    uploaded_by         UUID REFERENCES users(id),
    uploaded_at         TIMESTAMP DEFAULT NOW(),
    processed_at        TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- FK diferida: documents.current_version_id → document_versions.id
ALTER TABLE documents
    ADD CONSTRAINT fk_current_version
    FOREIGN KEY (current_version_id)
    REFERENCES document_versions(id)
    DEFERRABLE INITIALLY DEFERRED;

-- ------------------------------------------------------------
-- TABLA: document_pages
-- Páginas extraídas por versión con texto y layout
-- ------------------------------------------------------------
CREATE TABLE document_pages (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_version_id     UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    page_number             INTEGER NOT NULL,
    extracted_text          TEXT,
    layout_metadata         JSONB,      -- coordenadas, tablas, bloques detectados
    ocr_confidence          NUMERIC(5,2),
    ocr_engine              VARCHAR(50), -- 'azure_document_intelligence' | 'tesseract'
    created_at              TIMESTAMP DEFAULT NOW(),
    UNIQUE (document_version_id, page_number)
);

-- ------------------------------------------------------------
-- TABLA: document_chunks
-- Fragmentos semánticos por versión (resultado del chunking)
-- ------------------------------------------------------------
CREATE TABLE document_chunks (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_version_id     UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    page_id                 UUID REFERENCES document_pages(id),
    chunk_index             INTEGER NOT NULL,
    content                 TEXT NOT NULL,
    section_title           VARCHAR(500),
    paragraph_number        VARCHAR(100),
    start_page              INTEGER,
    end_page                INTEGER,
    token_count             INTEGER,
    source_reference        JSONB,  -- {document, revision, page_start, page_end, section, paragraph}
    metadata                JSONB,  -- tenant_id, project_id, document_type, discipline, checksum, etc.
    created_at              TIMESTAMP DEFAULT NOW(),
    UNIQUE (document_version_id, chunk_index)
);

-- ------------------------------------------------------------
-- TABLA: chunk_embeddings
-- Vectores de embeddings por chunk (text-embedding-3-large = 3072 dims)
-- ------------------------------------------------------------
CREATE TABLE chunk_embeddings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id            UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    embedding           VECTOR(3072),
    embedding_model     VARCHAR(100) DEFAULT 'text-embedding-3-large',
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: document_classifications
-- Clasificación automática de documentos por IA
-- ------------------------------------------------------------
CREATE TABLE document_classifications (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_version_id     UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    document_type           VARCHAR(100),
    discipline              VARCHAR(100),
    project_phase           VARCHAR(80)
                                CHECK (project_phase IN (
                                    'tender', 'award', 'mobilization', 'execution',
                                    'commissioning', 'closeout', 'dispute', 'unknown'
                                )),
    detected_metadata       JSONB,  -- contract_name, owner, contractor, contract_number, etc.
    confidence_score        NUMERIC(5,2),
    classification_reason   TEXT,
    requires_human_validation BOOLEAN DEFAULT FALSE,
    validated_by            UUID REFERENCES users(id),
    validated_at            TIMESTAMP,
    created_at              TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: extracted_obligations
-- Obligaciones contractuales extraídas por IA
-- ------------------------------------------------------------
CREATE TABLE extracted_obligations (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_version_id     UUID NOT NULL REFERENCES document_versions(id),
    obligation_type         VARCHAR(120),
    obligation_text         TEXT NOT NULL,
    responsible_party       VARCHAR(255),
    consequence             TEXT,
    source_reference        JSONB,  -- {document, revision, page, paragraph, quote}
    confidence_score        NUMERIC(5,2),
    requires_human_validation BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: extracted_deadlines
-- Plazos y vencimientos extraídos por IA
-- ------------------------------------------------------------
CREATE TABLE extracted_deadlines (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_version_id     UUID NOT NULL REFERENCES document_versions(id),
    deadline_type           VARCHAR(120),
    description             TEXT NOT NULL,
    due_date                DATE,
    relative_deadline       VARCHAR(255),  -- "5 días hábiles desde adjudicación"
    responsible_party       VARCHAR(255),
    source_reference        JSONB,
    confidence_score        NUMERIC(5,2),
    created_at              TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: alerts
-- Alertas contractuales automáticas y manuales
-- ------------------------------------------------------------
CREATE TABLE alerts (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    alert_type                  VARCHAR(100) NOT NULL
                                    CHECK (alert_type IN (
                                        'deadline', 'rfi', 'obligation', 'document_review',
                                        'version_change', 'penalty', 'missing_document', 'claim_risk'
                                    )),
    severity                    VARCHAR(50) DEFAULT 'medium'
                                    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    title                       VARCHAR(500) NOT NULL,
    description                 TEXT,
    due_date                    DATE,
    status                      VARCHAR(50) DEFAULT 'open'
                                    CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
    source_document_version_id  UUID REFERENCES document_versions(id),
    source_reference            JSONB,
    assigned_to                 UUID REFERENCES users(id),
    created_at                  TIMESTAMP DEFAULT NOW(),
    resolved_at                 TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: version_diffs
-- Comparaciones semánticas entre revisiones de un documento
-- ------------------------------------------------------------
CREATE TABLE version_diffs (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id             UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    previous_version_id     UUID NOT NULL REFERENCES document_versions(id),
    new_version_id          UUID NOT NULL REFERENCES document_versions(id),
    diff_type               VARCHAR(100),
    semantic_summary        TEXT,
    critical_changes        JSONB,
    obligations_changed     JSONB,
    deadlines_changed       JSONB,
    commercial_impacts      JSONB,
    technical_impacts       JSONB,
    risk_level              VARCHAR(50)
                                CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    requires_legal_review   BOOLEAN DEFAULT FALSE,
    created_by              UUID REFERENCES users(id),
    created_at              TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: rag_queries
-- Consultas RAG realizadas por usuarios
-- ------------------------------------------------------------
CREATE TABLE rag_queries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    project_id      UUID REFERENCES projects(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    question        TEXT NOT NULL,
    answer          TEXT,
    interpretation  TEXT,
    risks_warnings  JSONB,
    confidence      NUMERIC(5,2),
    requires_human_review BOOLEAN DEFAULT TRUE,
    model_name      VARCHAR(100),
    retrieval_k     INTEGER DEFAULT 8,
    latency_ms      INTEGER,
    filters_used    JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: rag_citations
-- Citas documentales por consulta RAG
-- ------------------------------------------------------------
CREATE TABLE rag_citations (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id                UUID NOT NULL REFERENCES rag_queries(id) ON DELETE CASCADE,
    document_version_id     UUID NOT NULL REFERENCES document_versions(id),
    chunk_id                UUID REFERENCES document_chunks(id),
    page_number             INTEGER,
    paragraph_ref           VARCHAR(200),
    quoted_text             TEXT,
    relevance_score         NUMERIC(8,5),
    source_reference        JSONB,
    created_at              TIMESTAMP DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLA: audit_logs
-- Trazabilidad completa de todas las acciones del sistema
-- ------------------------------------------------------------
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(150) NOT NULL,
    entity_type     VARCHAR(100),
    entity_id       UUID,
    details         JSONB,
    ip_address      VARCHAR(100),
    user_agent      TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES
-- ============================================================

-- Projects
CREATE INDEX idx_projects_tenant_id        ON projects(tenant_id);
CREATE INDEX idx_projects_status           ON projects(status);

-- Documents
CREATE INDEX idx_documents_project_id      ON documents(project_id);
CREATE INDEX idx_documents_type            ON documents(document_type);
CREATE INDEX idx_documents_discipline      ON documents(discipline);
CREATE INDEX idx_documents_status          ON documents(current_status);

-- Document versions
CREATE INDEX idx_doc_versions_document_id  ON document_versions(document_id);
CREATE INDEX idx_doc_versions_status       ON document_versions(processing_status);
CREATE INDEX idx_doc_versions_checksum     ON document_versions(checksum_sha256);

-- Document pages
CREATE INDEX idx_doc_pages_version_id      ON document_pages(document_version_id);

-- Document chunks
CREATE INDEX idx_doc_chunks_version        ON document_chunks(document_version_id);
CREATE INDEX idx_doc_chunks_page           ON document_chunks(page_id);
-- Búsqueda full-text por contenido (trigram)
CREATE INDEX idx_doc_chunks_content_trgm
    ON document_chunks USING gin (content gin_trgm_ops);

-- Chunk embeddings — búsqueda vectorial cosine con ivfflat
CREATE INDEX idx_chunk_embeddings_vector
    ON chunk_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Alerts
CREATE INDEX idx_alerts_project_due        ON alerts(project_id, due_date);
CREATE INDEX idx_alerts_status             ON alerts(status);
CREATE INDEX idx_alerts_severity           ON alerts(severity);
CREATE INDEX idx_alerts_type               ON alerts(alert_type);

-- RAG queries
CREATE INDEX idx_rag_queries_project_user  ON rag_queries(project_id, user_id);
CREATE INDEX idx_rag_queries_tenant        ON rag_queries(tenant_id);
CREATE INDEX idx_rag_queries_created       ON rag_queries(created_at);

-- Audit logs
CREATE INDEX idx_audit_tenant_user         ON audit_logs(tenant_id, user_id);
CREATE INDEX idx_audit_entity              ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created             ON audit_logs(created_at);

-- Users
CREATE INDEX idx_users_tenant_id           ON users(tenant_id);
CREATE INDEX idx_users_email               ON users(email);

-- ============================================================
-- QUERY DE BÚSQUEDA VECTORIAL RAG
-- Recuperar top-K chunks por similitud cosine + filtro proyecto
-- ============================================================

-- Ejemplo de uso:
-- $1 = query_embedding::vector
-- $2 = project_id::uuid
-- $3 = document_type filter (opcional, NULL para ignorar)
-- $4 = top_k (default 8)

/*
SELECT
    dc.id                               AS chunk_id,
    dc.content,
    dc.section_title,
    dc.paragraph_number,
    dc.start_page,
    dc.source_reference,
    dc.metadata,
    dv.revision_number,
    dv.version_label,
    d.title                             AS document_title,
    d.document_type,
    1 - (ce.embedding <=> $1::vector)   AS similarity
FROM chunk_embeddings ce
JOIN document_chunks dc       ON dc.id = ce.chunk_id
JOIN document_versions dv     ON dv.id = dc.document_version_id
JOIN documents d              ON d.id = dv.document_id
WHERE d.project_id = $2
  AND dv.processing_status = 'processed'
  AND ($3 IS NULL OR d.document_type = $3)
  AND dv.id = d.current_version_id   -- solo revisión vigente
ORDER BY ce.embedding <=> $1::vector
LIMIT $4;
*/

-- ============================================================
-- QUERY HÍBRIDA: vector + keyword
-- ============================================================

/*
WITH vector_results AS (
    SELECT
        dc.id AS chunk_id,
        dc.content,
        dc.source_reference,
        d.title AS document_title,
        dv.revision_number,
        1 - (ce.embedding <=> $1::vector) AS vector_score
    FROM chunk_embeddings ce
    JOIN document_chunks dc   ON dc.id = ce.chunk_id
    JOIN document_versions dv ON dv.id = dc.document_version_id
    JOIN documents d          ON d.id = dv.document_id
    WHERE d.project_id = $2
      AND dv.id = d.current_version_id
    ORDER BY ce.embedding <=> $1::vector
    LIMIT 20
),
keyword_results AS (
    SELECT
        dc.id AS chunk_id,
        similarity(dc.content, $3) AS keyword_score
    FROM document_chunks dc
    JOIN document_versions dv ON dv.id = dc.document_version_id
    JOIN documents d          ON d.id = dv.document_id
    WHERE d.project_id = $2
      AND dv.id = d.current_version_id
      AND dc.content % $3
    LIMIT 20
)
SELECT
    vr.chunk_id,
    vr.content,
    vr.source_reference,
    vr.document_title,
    vr.revision_number,
    vr.vector_score,
    COALESCE(kr.keyword_score, 0) AS keyword_score,
    (vr.vector_score * 0.7 + COALESCE(kr.keyword_score, 0) * 0.3) AS combined_score
FROM vector_results vr
LEFT JOIN keyword_results kr ON kr.chunk_id = vr.chunk_id
ORDER BY combined_score DESC
LIMIT $4;
*/
