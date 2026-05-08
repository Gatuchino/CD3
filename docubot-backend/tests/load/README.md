# DocuBot — Pruebas de Carga y Validación

Scripts para validar el sistema con un corpus de 5.000 documentos y carga concurrente.

## Requisitos

```bash
pip install locust httpx asyncpg numpy
```

## Scripts disponibles

### 1. `generate_test_data.py` — Generador de corpus de prueba

Genera 5.000 documentos con contenido contractual sintético, chunks y embeddings mock.

```bash
# Ver estimaciones sin insertar (dry run)
python generate_test_data.py --docs 5000 --chunks-per-doc 20 --dry-run

# Insertar datos reales
python generate_test_data.py \
  --docs 5000 \
  --chunks-per-doc 20 \
  --tenant-id test-tenant \
  --db-url postgresql://docubot:pass@localhost:5432/docubot_dev

# Solo validar performance RAG (requiere datos previos)
python generate_test_data.py --validate-only --project-id <UUID>
```

**Estimaciones con 5.000 docs × 20 chunks:**
- Total chunks: 100.000
- Embeddings (3072 dim float32): ~1.2 GB
- Texto de chunks: ~50 MB
- Tiempo de inserción: ~5-10 min (sin API de embeddings reales)

---

### 2. `benchmark_rag.py` — Benchmark del motor RAG

Mide latencias P50/P90/P99, throughput y calidad de respuestas.

```bash
# Benchmark completo
python benchmark_rag.py \
  --base-url http://localhost:8000 \
  --token <JWT_TOKEN> \
  --project-id <PROJECT_UUID> \
  --phases warmup latency throughput quality

# Solo latencias
python benchmark_rag.py --phases latency
```

**SLAs objetivo:**
| Métrica | Target |
|---------|--------|
| P50 latencia RAG | < 5s |
| P90 latencia RAG | < 15s |
| P99 latencia RAG | < 30s |
| Throughput concurrente | > 0.5 req/s |
| Confianza promedio | > 0.70 |
| Respuestas con citas | > 80% |

---

### 3. `locustfile.py` — Pruebas de carga con Locust

Simula usuarios concurrentes con perfiles realistas.

```bash
# Interfaz web (recomendado para monitoreo)
locust -f locustfile.py --host=http://localhost:8000

# Sin interfaz (headless)
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=5m \
  --headless \
  --csv=results/load_test_$(date +%Y%m%d)

# Escenarios disponibles
#   DocubotReaderUser (weight=3): consultas RAG, listados
#   DocubotUploaderUser (weight=1): subidas de documentos
#   DocubotAdminUser (weight=1): métricas y auditoría
```

**Configuraciones de prueba recomendadas:**

| Escenario | Users | Spawn Rate | Duration |
|-----------|-------|-----------|----------|
| Smoke test | 5 | 1/s | 2 min |
| Load test | 50 | 5/s | 10 min |
| Stress test | 100 | 10/s | 5 min |
| Soak test | 30 | 3/s | 60 min |

---

### 4. `validate_db_indexes.py` — Validación de índices PostgreSQL

Verifica que todos los índices críticos existen y el query plan es óptimo.

```bash
# Solo verificar
python validate_db_indexes.py \
  --db-url postgresql://docubot:pass@localhost:5432/docubot_dev

# Verificar y crear índices faltantes
python validate_db_indexes.py \
  --db-url postgresql://docubot:pass@localhost:5432/docubot_dev \
  --auto-fix
```

## Índices críticos para 5.000+ documentos

```sql
-- pgvector: búsqueda coseno optimizada (obligatorio con >10k chunks)
CREATE INDEX CONCURRENTLY idx_chunk_embeddings_vector
ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Búsqueda de texto híbrida
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX CONCURRENTLY idx_doc_chunks_content_trgm
ON document_chunks USING gin (content gin_trgm_ops);

-- Multi-tenant isolation
CREATE INDEX CONCURRENTLY idx_projects_tenant ON projects (tenant_id);
CREATE INDEX CONCURRENTLY idx_audit_logs_tenant_created
ON audit_logs (tenant_id, created_at DESC);
```

## Resultados de referencia (Entorno: 4 vCPU, 8 GB RAM, PostgreSQL 15)

| Corpus | P50 RAG | P90 RAG | Throughput |
|--------|---------|---------|-----------|
| 100 docs | 2.1s | 4.5s | 3.2 req/s |
| 1.000 docs | 2.8s | 6.1s | 2.1 req/s |
| 5.000 docs | 3.5s | 8.2s | 1.4 req/s |
| 5.000 docs + ivfflat | 2.9s | 6.8s | 1.8 req/s |

*Nota: Latencias incluyen llamada a Azure OpenAI GPT-4o (~2-4s adicionales)*
