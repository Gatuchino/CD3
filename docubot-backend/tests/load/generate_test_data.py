"""
DocuBot — Generador de datos de prueba para validación con 5.000 documentos.
Crea: proyectos, documentos, versiones, chunks, embeddings mock y consultas RAG.

Uso:
    python generate_test_data.py --docs 5000 --chunks-per-doc 20 --tenant-id TEST-TENANT

Estrategia:
    - Genera documentos con contenido contractual sintético realista
    - Crea embeddings aleatorios de 3072 dimensiones (evitar costo real de API)
    - Inserta en PostgreSQL directamente para pruebas de volumen
    - Valida performance de búsqueda híbrida bajo carga
"""
import argparse
import asyncio
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import List
import numpy as np

# ── Contenido contractual sintético ────────────────────────────────────

DOCUMENT_TYPES = [
    "contract", "addendum", "specification", "rfi", "transmittal",
    "minutes", "correspondence", "report", "certificate", "drawing"
]

DISCIPLINES = [
    "civil", "mechanical", "electrical", "instrumentation",
    "piping", "structural", "process", "safety", "environmental"
]

CONTRACT_CLAUSES = [
    "El contratista deberá entregar la ingeniería básica en un plazo de 90 días corridos.",
    "Las multas por retraso serán del 0.1% del valor del contrato por día de atraso.",
    "El propietario dispondrá de 30 días para revisar y aprobar los documentos entregados.",
    "La garantía de fiel cumplimiento será equivalente al 10% del monto del contrato.",
    "El plazo total de ejecución de las obras es de 24 meses a partir de la orden de inicio.",
    "Los pagos se efectuarán dentro de los 30 días siguientes a la aprobación del estado de pago.",
    "El contratista deberá mantener vigente un seguro de responsabilidad civil por UF 50.000.",
    "Las adendas al contrato solo serán válidas si están suscritas por ambas partes.",
    "La recepción provisional se realizará una vez completados todos los hitos del contrato.",
    "El contratista es responsable de gestionar todos los permisos y licencias necesarios.",
    "La inspección fiscal tendrá acceso irrestricto a todas las áreas de trabajo.",
    "Los materiales deben cumplir con las normas chilenas NCh y ASTM correspondientes.",
    "El contratista deberá presentar un plan de gestión ambiental antes del inicio de obras.",
    "Se establece un fondo de retención del 5% sobre cada estado de pago.",
    "Los cambios en el alcance deberán tramitarse mediante órdenes de cambio aprobadas.",
]

PROJECT_NAMES = [
    "Planta Concentradora Norte 2024",
    "Ampliación Mina El Cobre Fase II",
    "Construcción Campamento Minero",
    "Línea de Alta Tensión 220kV",
    "Planta Desalinizadora Costa Norte",
    "Bodega de Ácido Sulfúrico",
    "Sistema de Transporte por Ductos",
    "Espesadores de Relave",
    "Central Fotovoltaica 50MW",
    "Túnel de Servicio Km 12-18",
]


def gen_uuid() -> str:
    return str(uuid.uuid4())


def gen_contract_text(num_clauses: int = 10) -> str:
    """Genera texto contractual sintético realista."""
    clauses = random.sample(CONTRACT_CLAUSES, min(num_clauses, len(CONTRACT_CLAUSES)))
    text_parts = []
    for i, clause in enumerate(clauses, 1):
        text_parts.append(f"Cláusula {i}.{random.randint(1, 5)}: {clause}")
        # Añadir sub-cláusulas ocasionales
        if random.random() > 0.6:
            sub = random.choice(CONTRACT_CLAUSES)
            text_parts.append(f"  {i}.{random.randint(1, 5)}.1: {sub}")
    return "\n\n".join(text_parts)


def gen_random_embedding(dim: int = 3072) -> List[float]:
    """Genera un embedding aleatorio normalizado (simula text-embedding-3-large)."""
    vec = np.random.randn(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)  # Normalizar para coseno
    return vec.tolist()


async def generate_test_data(
    num_docs: int,
    chunks_per_doc: int,
    tenant_id: str,
    db_url: str,
    dry_run: bool = False,
):
    """
    Genera y opcionalmente inserta datos de prueba en PostgreSQL.
    En dry_run=True, solo calcula y reporta sin insertar.
    """
    print(f"\n{'='*60}")
    print(f"DocuBot — Generador de datos de prueba")
    print(f"{'='*60}")
    print(f"Documentos a generar: {num_docs:,}")
    print(f"Chunks por documento: {chunks_per_doc}")
    print(f"Total chunks: {num_docs * chunks_per_doc:,}")
    print(f"Total embeddings: {num_docs * chunks_per_doc:,}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Dry run: {dry_run}")
    print()

    # Estimaciones de storage
    embedding_size_bytes = 3072 * 4  # float32
    chunk_text_avg = 500  # bytes promedio por chunk
    total_embedding_mb = (num_docs * chunks_per_doc * embedding_size_bytes) / (1024 * 1024)
    total_text_mb = (num_docs * chunks_per_doc * chunk_text_avg) / (1024 * 1024)

    print(f"📊 Estimaciones de almacenamiento:")
    print(f"  Embeddings: {total_embedding_mb:.1f} MB")
    print(f"  Texto de chunks: {total_text_mb:.1f} MB")
    print(f"  Total estimado: {total_embedding_mb + total_text_mb:.1f} MB")
    print()

    if dry_run:
        print("✓ Dry run completado. Para insertar datos usa --no-dry-run")
        return

    try:
        import asyncpg
    except ImportError:
        print("✗ asyncpg no instalado. Instala con: pip install asyncpg")
        return

    print("Conectando a PostgreSQL...")
    conn = await asyncpg.connect(db_url)
    print("✓ Conexión establecida")

    t_start = time.time()

    # Crear 5 proyectos de prueba
    project_ids = []
    print(f"\nCreando proyectos de prueba...")
    for i in range(5):
        pid = gen_uuid()
        project_ids.append(pid)
        if not dry_run:
            await conn.execute("""
                INSERT INTO projects (id, tenant_id, code, name, client_name, status, created_at)
                VALUES ($1, $2, $3, $4, $5, 'active', NOW())
                ON CONFLICT DO NOTHING
            """, pid, tenant_id,
                f"TEST-{i+1:03d}",
                random.choice(PROJECT_NAMES) + f" (Test {i+1})",
                "Cliente Test Locust"
            )

    print(f"✓ {len(project_ids)} proyectos creados")

    # Generar documentos en batches de 100
    BATCH_SIZE = 100
    docs_created = 0
    chunks_created = 0
    embeddings_created = 0

    print(f"\nGenerando {num_docs:,} documentos...")

    for batch_start in range(0, num_docs, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, num_docs)
        batch_size = batch_end - batch_start

        # Batch de documentos
        doc_rows = []
        version_rows = []
        chunk_rows = []
        embedding_rows = []

        for _ in range(batch_size):
            doc_id = gen_uuid()
            version_id = gen_uuid()
            project_id = random.choice(project_ids)
            doc_type = random.choice(DOCUMENT_TYPES)
            discipline = random.choice(DISCIPLINES)
            file_name = f"{doc_type}_{gen_uuid()[:8]}.pdf"

            doc_rows.append((
                doc_id, project_id,
                f"Documento {doc_type.title()} - {discipline.upper()}",
                doc_type, discipline,
                version_id,
            ))

            version_rows.append((
                version_id, doc_id,
                f"Rev.{random.randint(0, 5)}",
                "Original",
                file_name, "pdf",
                f"https://stdocubot.blob.core.windows.net/documents/{tenant_id}/{version_id}/{file_name}",
                "processed",
                random.randint(1, 50),
            ))

            # Chunks para esta versión
            for chunk_idx in range(chunks_per_doc):
                chunk_id = gen_uuid()
                content = gen_contract_text(num_clauses=random.randint(3, 8))
                chunk_rows.append((
                    chunk_id, version_id, chunk_idx,
                    content,
                    f"Sección {chunk_idx + 1}.{random.randint(1, 5)}",
                    str(random.randint(1, 50)),
                    random.randint(1, 40),
                ))
                embedding_rows.append((
                    gen_uuid(), chunk_id,
                    gen_random_embedding(),
                    "text-embedding-3-large",
                ))

        # Insertar batch en PostgreSQL
        if not dry_run:
            async with conn.transaction():
                await conn.executemany("""
                    INSERT INTO documents (id, project_id, title, document_type, discipline, current_version_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """, doc_rows)

                await conn.executemany("""
                    INSERT INTO document_versions (id, document_id, revision_number, version_label,
                        file_name, file_type, blob_url, processing_status, page_count, uploaded_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """, version_rows)

                await conn.executemany("""
                    INSERT INTO document_chunks (id, document_version_id, chunk_index, content,
                        section_title, paragraph_number, start_page, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT DO NOTHING
                """, chunk_rows)

                # Embeddings en batch separado (columna vector pgvector)
                for emb_id, chunk_id, vector, model in embedding_rows:
                    await conn.execute("""
                        INSERT INTO chunk_embeddings (id, chunk_id, embedding, embedding_model, created_at)
                        VALUES ($1, $2, $3::vector, $4, NOW())
                        ON CONFLICT DO NOTHING
                    """, emb_id, chunk_id, str(vector), model)

        docs_created += batch_size
        chunks_created += batch_size * chunks_per_doc
        embeddings_created += batch_size * chunks_per_doc

        elapsed = time.time() - t_start
        rate = docs_created / elapsed
        eta = (num_docs - docs_created) / rate if rate > 0 else 0

        print(
            f"  [{docs_created:,}/{num_docs:,}] docs | "
            f"{chunks_created:,} chunks | "
            f"{rate:.1f} docs/s | ETA: {eta:.0f}s",
            end="\r"
        )

    total_time = time.time() - t_start
    print(f"\n\n{'='*60}")
    print(f"✓ Generación completada en {total_time:.1f}s")
    print(f"  Documentos: {docs_created:,}")
    print(f"  Chunks: {chunks_created:,}")
    print(f"  Embeddings: {embeddings_created:,}")
    print(f"  Velocidad promedio: {docs_created/total_time:.1f} docs/s")
    print(f"{'='*60}\n")

    await conn.close()


async def validate_rag_performance(db_url: str, project_id: str, num_queries: int = 100):
    """
    Valida la performance del motor RAG ejecutando N consultas y midiendo latencias.
    Reporta P50, P90, P99 y detecta consultas lentas.
    """
    import asyncpg
    conn = await asyncpg.connect(db_url)

    print(f"\n{'='*60}")
    print(f"Validación de performance RAG — {num_queries} consultas")
    print(f"{'='*60}\n")

    questions = random.sample(
        CONTRACT_CLAUSES * (num_queries // len(CONTRACT_CLAUSES) + 1),
        num_queries
    )

    latencies = []
    errors = 0

    for i, question in enumerate(questions):
        t0 = time.time()
        try:
            # Simular búsqueda híbrida directamente en DB
            query_vector = gen_random_embedding()
            vector_str = "[" + ",".join(map(str, query_vector[:10])) + "..." + "]"

            await conn.fetch("""
                SELECT dc.id, dc.content,
                    1 - (ce.embedding <=> $1::vector) AS cosine_score
                FROM document_chunks dc
                JOIN chunk_embeddings ce ON ce.chunk_id = dc.id
                JOIN document_versions dv ON dv.id = dc.document_version_id
                JOIN documents d ON d.id = dv.document_id
                WHERE d.project_id = $2
                ORDER BY ce.embedding <=> $1::vector
                LIMIT 8
            """, str(query_vector), project_id)

            latency_ms = int((time.time() - t0) * 1000)
            latencies.append(latency_ms)

        except Exception as e:
            errors += 1
            print(f"  Error en consulta {i}: {e}")

        if (i + 1) % 10 == 0:
            print(f"  Progreso: {i+1}/{num_queries} consultas", end="\r")

    await conn.close()

    if not latencies:
        print("✗ No se obtuvieron resultados")
        return

    latencies.sort()
    n = len(latencies)

    def pct(data, p):
        return data[int(len(data) * p / 100)]

    print(f"\nResultados de performance ({n} consultas exitosas, {errors} errores):")
    print(f"  P50:  {pct(latencies, 50)}ms")
    print(f"  P90:  {pct(latencies, 90)}ms")
    print(f"  P99:  {pct(latencies, 99)}ms")
    print(f"  Min:  {latencies[0]}ms")
    print(f"  Max:  {latencies[-1]}ms")
    print(f"  Avg:  {sum(latencies)//len(latencies)}ms")

    slow = [l for l in latencies if l > 5000]
    print(f"\n  Consultas >5s: {len(slow)} ({len(slow)/n*100:.1f}%)")

    if pct(latencies, 90) < 3000:
        print("  ✓ SLA P90 < 3s: CUMPLE")
    else:
        print(f"  ✗ SLA P90 < 3s: NO CUMPLE ({pct(latencies, 90)}ms)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocuBot — Generador de datos de prueba")
    parser.add_argument("--docs", type=int, default=5000, help="Número de documentos a generar")
    parser.add_argument("--chunks-per-doc", type=int, default=20, help="Chunks por documento")
    parser.add_argument("--tenant-id", default="test-tenant-locust", help="Tenant ID de prueba")
    parser.add_argument("--db-url", default="postgresql://docubot:docubot@localhost:5432/docubot_dev",
                        help="URL de conexión a PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Solo calcular sin insertar")
    parser.add_argument("--validate-only", action="store_true", help="Solo validar performance")
    parser.add_argument("--project-id", default=None, help="Project ID para validación RAG")
    args = parser.parse_args()

    if args.validate_only:
        asyncio.run(validate_rag_performance(
            args.db_url,
            args.project_id or "550e8400-e29b-41d4-a716-446655440000",
            num_queries=100,
        ))
    else:
        asyncio.run(generate_test_data(
            num_docs=args.docs,
            chunks_per_doc=args.chunks_per_doc,
            tenant_id=args.tenant_id,
            db_url=args.db_url,
            dry_run=args.dry_run,
        ))
