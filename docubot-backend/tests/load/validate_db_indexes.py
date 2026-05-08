"""
DocuBot — Validación de índices de base de datos para 5.000+ documentos.
Verifica que todos los índices críticos existen y están optimizados para escala.
Analiza query plans y detecta sequential scans sobre tablas grandes.

Uso:
    python validate_db_indexes.py --db-url postgresql://user:pass@host:5432/docubot
"""
import asyncio
import argparse


REQUIRED_INDEXES = [
    # pgvector — crítico para RAG
    {
        "name": "idx_chunk_embeddings_vector",
        "table": "chunk_embeddings",
        "type": "ivfflat",
        "critical": True,
        "description": "Índice coseno para búsqueda vectorial RAG",
    },
    # Tenant isolation — todas las queries filtran por tenant_id
    {
        "name": "idx_projects_tenant",
        "table": "projects",
        "column": "tenant_id",
        "critical": True,
        "description": "Filtrado multi-tenant en proyectos",
    },
    {
        "name": "idx_audit_logs_tenant_created",
        "table": "audit_logs",
        "columns": ["tenant_id", "created_at"],
        "critical": True,
        "description": "Consultas de auditoría por tenant y fecha",
    },
    {
        "name": "idx_rag_queries_tenant_created",
        "table": "rag_queries",
        "columns": ["tenant_id", "created_at"],
        "critical": True,
        "description": "Historial RAG por tenant",
    },
    # Document retrieval
    {
        "name": "idx_documents_project",
        "table": "documents",
        "column": "project_id",
        "critical": True,
        "description": "Listado de documentos por proyecto",
    },
    {
        "name": "idx_doc_versions_document",
        "table": "document_versions",
        "column": "document_id",
        "critical": True,
        "description": "Versiones por documento",
    },
    {
        "name": "idx_doc_chunks_version",
        "table": "document_chunks",
        "column": "document_version_id",
        "critical": True,
        "description": "Chunks por versión",
    },
    # Text search con pg_trgm (búsqueda híbrida)
    {
        "name": "idx_doc_chunks_content_trgm",
        "table": "document_chunks",
        "column": "content",
        "type": "gin",
        "critical": True,
        "description": "Búsqueda de texto por trigrams (búsqueda híbrida)",
    },
    # Alertas
    {
        "name": "idx_alerts_project_status",
        "table": "alerts",
        "columns": ["project_id", "status"],
        "critical": False,
        "description": "Alertas abiertas por proyecto",
    },
    {
        "name": "idx_alerts_due_date",
        "table": "alerts",
        "column": "due_date",
        "critical": False,
        "description": "Alertas por fecha de vencimiento",
    },
]

# SQL para crear los índices faltantes
INDEX_CREATION_SQL = {
    "idx_chunk_embeddings_vector": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_embeddings_vector
        ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """,
    "idx_projects_tenant": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_tenant
        ON projects (tenant_id);
    """,
    "idx_audit_logs_tenant_created": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_tenant_created
        ON audit_logs (tenant_id, created_at DESC);
    """,
    "idx_rag_queries_tenant_created": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rag_queries_tenant_created
        ON rag_queries (tenant_id, created_at DESC);
    """,
    "idx_documents_project": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_project
        ON documents (project_id);
    """,
    "idx_doc_versions_document": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_doc_versions_document
        ON document_versions (document_id);
    """,
    "idx_doc_chunks_version": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_doc_chunks_version
        ON document_chunks (document_version_id);
    """,
    "idx_doc_chunks_content_trgm": """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_doc_chunks_content_trgm
        ON document_chunks USING gin (content gin_trgm_ops);
    """,
    "idx_alerts_project_status": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_project_status
        ON alerts (project_id, status);
    """,
    "idx_alerts_due_date": """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_due_date
        ON alerts (due_date) WHERE due_date IS NOT NULL;
    """,
}


async def validate_indexes(db_url: str, auto_fix: bool = False):
    """Verifica índices y opcionalmente los crea si faltan."""
    try:
        import asyncpg
    except ImportError:
        print("✗ asyncpg no instalado. Instala con: pip install asyncpg")
        return

    print(f"\n{'='*60}")
    print("DocuBot — Validación de índices de base de datos")
    print(f"{'='*60}\n")

    conn = await asyncpg.connect(db_url)

    # Obtener todos los índices existentes
    existing = await conn.fetch("""
        SELECT
            i.relname AS index_name,
            t.relname AS table_name,
            am.amname AS index_type,
            ix.indisunique AS is_unique,
            pg_size_pretty(pg_relation_size(i.oid)) AS size
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_am am ON am.oid = i.relam
        WHERE t.relkind = 'r'
        ORDER BY t.relname, i.relname
    """)

    existing_names = {row["index_name"] for row in existing}

    # Obtener tamaños de tablas críticas
    table_stats = await conn.fetch("""
        SELECT
            relname AS table_name,
            n_live_tup AS row_count,
            pg_size_pretty(pg_total_relation_size(oid)) AS total_size
        FROM pg_stat_user_tables
        WHERE relname IN (
            'chunk_embeddings', 'document_chunks', 'documents',
            'document_versions', 'audit_logs', 'rag_queries',
            'projects', 'alerts'
        )
        ORDER BY n_live_tup DESC
    """)

    print("Estadísticas de tablas:")
    for row in table_stats:
        print(f"  {row['table_name']:30s} {row['row_count']:>10,} filas   {row['total_size']}")

    print(f"\nVerificación de índices ({len(REQUIRED_INDEXES)} requeridos):\n")
    missing = []
    present = []

    for idx in REQUIRED_INDEXES:
        exists = idx["name"] in existing_names
        critical_mark = "🔴" if idx["critical"] else "🟡"
        status = "✓ EXISTE" if exists else f"✗ FALTA"
        print(f"  {critical_mark} {status:12s} {idx['name']}")
        print(f"              → {idx['description']}")

        if exists:
            # Buscar tamaño del índice
            idx_info = next((r for r in existing if r["index_name"] == idx["name"]), None)
            if idx_info:
                print(f"              Tipo: {idx_info['index_type']} | Tamaño: {idx_info['size']}")
            present.append(idx["name"])
        else:
            missing.append(idx)
        print()

    print(f"{'─'*50}")
    print(f"Índices presentes: {len(present)}/{len(REQUIRED_INDEXES)}")
    critical_missing = [i for i in missing if i["critical"]]
    print(f"Críticos faltantes: {len(critical_missing)}")

    if missing:
        print(f"\n{'─'*50}")
        print(f"SQL para crear índices faltantes:\n")
        for idx in missing:
            sql = INDEX_CREATION_SQL.get(idx["name"], "-- SQL no disponible")
            print(f"-- {idx['description']}")
            print(sql)

        if auto_fix:
            print(f"\nCreando {len(missing)} índices faltantes...")
            for idx in missing:
                sql = INDEX_CREATION_SQL.get(idx["name"])
                if sql:
                    try:
                        await conn.execute(sql)
                        print(f"  ✓ Creado: {idx['name']}")
                    except Exception as e:
                        print(f"  ✗ Error en {idx['name']}: {e}")

    # Verificar query plan de búsqueda vectorial
    print(f"\n{'─'*50}")
    print("Análisis de query plan (búsqueda vectorial):\n")
    try:
        plan = await conn.fetch("""
            EXPLAIN (FORMAT TEXT, ANALYZE FALSE)
            SELECT dc.id, 1 - (ce.embedding <=> '[0.1,0.2,0.3]'::vector) AS score
            FROM document_chunks dc
            JOIN chunk_embeddings ce ON ce.chunk_id = dc.id
            ORDER BY ce.embedding <=> '[0.1,0.2,0.3]'::vector
            LIMIT 8
        """)
        for row in plan[:5]:
            print(f"  {row[0]}")

        plan_text = " ".join(str(row[0]) for row in plan)
        if "Seq Scan" in plan_text and "chunk_embeddings" in plan_text:
            print("\n  ⚠ ALERTA: Se detecta Seq Scan en chunk_embeddings.")
            print("    Crear el índice ivfflat mejorará significativamente la performance.")
        else:
            print("\n  ✓ Query plan usa índice vectorial correctamente.")
    except Exception as e:
        print(f"  No se pudo analizar query plan: {e}")

    await conn.close()
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocuBot — Validación de índices DB")
    parser.add_argument("--db-url", required=True, help="URL de conexión PostgreSQL")
    parser.add_argument("--auto-fix", action="store_true",
                        help="Crear automáticamente índices faltantes")
    args = parser.parse_args()
    asyncio.run(validate_indexes(args.db_url, auto_fix=args.auto_fix))
