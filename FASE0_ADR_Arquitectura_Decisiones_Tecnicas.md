# DocuBot — Architecture Decision Records (ADR)
## Fase 0 — Decisiones Técnicas Críticas

**Proyecto:** DocuBot — Módulo 02 Aurenza IA  
**Empresa:** Aurenza Group  
**Fecha:** 2026-05-06  
**Estado:** Aprobado para MVP

---

## ADR-001 — Base de datos vectorial: pgvector vs Pinecone

**Decisión:** pgvector sobre PostgreSQL (Azure Database for PostgreSQL Flexible Server)

**Contexto:**  
DocuBot necesita almacenar y buscar embeddings de 3.072 dimensiones (text-embedding-3-large) para el motor RAG. Se evaluaron pgvector y Pinecone.

**Justificación:**
- pgvector permite un único motor de base de datos transaccional + vectorial, reduciendo la complejidad del MVP.
- Mejor trazabilidad transaccional: chunks, metadatos y vectores en el mismo motor.
- Integración nativa con Azure Database for PostgreSQL Flexible Server.
- Índice ivfflat con `lists = 100` cubre bien el volumen inicial (< 1M chunks).
- Menor costo operacional en etapa MVP.

**Criterio de revisión:**  
Evaluar migración a Pinecone cuando el proyecto supere 1 millón de chunks, tenga múltiples clientes concurrentes con alta demanda, o cuando la latencia de búsqueda vectorial supere los 500ms en P95.

**Stack resultante:** PostgreSQL 16 + pgvector (extensión vector) + extensiones uuid-ossp y pg_trgm

---

## ADR-002 — OCR: Azure Document Intelligence + fallback Tesseract

**Decisión:** Arquitectura híbrida Azure Document Intelligence como motor principal, Tesseract como fallback

**Contexto:**  
DocuBot debe procesar PDFs escaneados, imágenes (PNG, JPG, TIFF) y documentos con layout complejo (tablas, columnas, planos).

**Justificación:**
- Azure Document Intelligence ofrece extracción estructurada: texto por página, coordenadas, tablas, formularios.
- Calidad superior para documentos técnicos y contractuales complejos.
- Fallback a Tesseract cuando Azure Document Intelligence falle o el documento sea muy simple.
- Tesseract permite operación sin costo adicional en casos degradados.

**Criterio de activación del fallback:**
1. Azure Document Intelligence retorna error HTTP 4xx/5xx.
2. Tiempo de respuesta > 30 segundos.
3. Texto extraído < 50 caracteres en un documento con más de 1 página.

---

## ADR-003 — Búsqueda: híbrida vector + keyword + metadata

**Decisión:** Búsqueda híbrida obligatoria en el pipeline RAG

**Contexto:**  
Los documentos contractuales y técnicos contienen cláusulas numeradas, códigos de documentos, siglas técnicas (RFI-024, CT-2026-0045) y nombres propios que la búsqueda vectorial pura no captura bien.

**Estrategia definida:**
1. **Vector search** — similitud semántica con pgvector cosine distance.
2. **Keyword search** — búsqueda por términos exactos con pg_trgm (GIN index).
3. **Metadata filters** — filtros por project_id, document_type, revision, discipline, date range.
4. **Re-ranking** — combinar scores vectorial + keyword, priorizar revisiones más recientes.

**Política de revisión vigente:** Por defecto, el sistema consulta únicamente la revisión más reciente de cada documento (`revision_policy: latest_only`), salvo que el usuario indique explícitamente consultar todas las revisiones.

---

## ADR-004 — Formato de respuestas IA: JSON estructurado obligatorio

**Decisión:** Todas las respuestas del motor IA deben retornar JSON válido y estructurado

**Contexto:**  
Las respuestas deben ser procesables por el backend para guardar citas, calcular confianza y mostrar evidencia en el frontend.

**Estructura obligatoria para RAG:**
```json
{
  "answer": "string",
  "evidence": [{"document": "", "revision": "", "page": "", "paragraph": "", "quote": ""}],
  "interpretation": "string",
  "risks_or_warnings": ["string"],
  "confidence": 0.0,
  "requires_human_review": true
}
```

**Regla:** Si no hay evidencia suficiente, DocuBot responde `"No existe evidencia suficiente en los documentos revisados"` — nunca inventa información.

---

## ADR-005 — Revisión humana obligatoria en respuestas contractuales

**Decisión:** Todas las respuestas con impacto contractual deben marcarse como `requires_human_review: true`

**Contexto:**  
DocuBot opera en proyectos mineros y de construcción donde una interpretación incorrecta puede tener consecuencias contractuales, comerciales o legales.

**Criterios para marcar requires_human_review = true:**
- Confianza < 0.80.
- La respuesta menciona plazos, multas, penalidades, obligaciones o condiciones de pago.
- Existen contradicciones entre documentos del mismo proyecto.
- La consulta involucra términos: "plazo", "multa", "penalidad", "obligación", "vencimiento", "claim", "reclamo".
- No se encontraron citas suficientes para respaldar la respuesta.

---

## ADR-006 — Arquitectura multi-tenant desde el día uno

**Decisión:** Diseño multi-tenant con aislamiento por tenant_id en todas las tablas y queries

**Contexto:**  
Aurenza IA es una plataforma SaaS B2B que sirve a múltiples empresas (tenants). Cada empresa debe tener aislamiento total de sus datos.

**Implementación:**
- Campo `tenant_id` en todas las tablas principales.
- Row-level security (RLS) en PostgreSQL activado por tenant_id.
- Middleware de autenticación valida tenant_id desde el JWT de Azure AD B2C.
- Azure Blob Storage: paths organizados por `/{tenant_id}/...`.
- Ningún query puede retornar datos de otro tenant.

---

## ADR-007 — Procesamiento asíncrono de documentos

**Decisión:** Pipeline de ingesta completamente asíncrono vía Azure Service Bus

**Contexto:**  
El procesamiento de un documento (OCR + chunking + embeddings) puede tomar entre 30 segundos y varios minutos según el tamaño y tipo del documento.

**Flujo:**
1. Upload del archivo → respuesta inmediata con `processing_status: "uploaded"`.
2. Tarea encolada en Azure Service Bus.
3. Workers procesan en background: OCR → parsing → clasificación → chunking → embeddings → extracción contractual.
4. Estado actualizado en PostgreSQL: `uploaded → processing → processed / error`.
5. Frontend hace polling o usa WebSocket para mostrar progreso en tiempo real.

---

## ADR-008 — Trazabilidad y auditoría completa

**Decisión:** Registrar toda acción en audit_logs, guardar prompts y respuestas completas en rag_queries/rag_citations

**Contexto:**  
Los proyectos mineros y de construcción requieren trazabilidad total para auditorías, disputas contractuales y revisiones legales.

**Qué se registra:**
- Cada consulta RAG: pregunta, respuesta, chunks usados, citas, confianza, usuario, proyecto, timestamp.
- Cada carga de documento: usuario, archivo, checksum, estado.
- Cada clasificación: resultado, confianza, si fue corregida manualmente.
- Cada descarga de documento: usuario, documento, timestamp.
- Cada acción administrativa: creación de proyecto, usuarios, cambios de roles.

---

## ADR-009 — Stack tecnológico definitivo

**Decisión:** Stack confirmado para MVP

| Capa | Tecnología |
|---|---|
| Backend API | Python 3.12 + FastAPI |
| Frontend | React 18 + TypeScript + Vite + shadcn/ui |
| Base de datos | PostgreSQL 16 + pgvector + pg_trgm |
| Almacenamiento archivos | Azure Blob Storage |
| OCR | Azure Document Intelligence + Tesseract fallback |
| LLM | Azure OpenAI GPT-4o |
| Embeddings | Azure OpenAI text-embedding-3-large (3072 dims) |
| Autenticación | Azure AD B2C + MSAL React |
| Cola asíncrona | Azure Service Bus |
| Secretos | Azure Key Vault |
| Monitoreo | Azure Application Insights + Azure Monitor |
| Errores frontend | Sentry |
| Trazas | OpenTelemetry |
| Contenerización | Docker + Azure Container Apps (producción) |

---

## ADR-010 — Límites operacionales del sistema

**Decisión:** Establecer límites de tamaño y volumen para MVP

| Parámetro | Límite MVP |
|---|---|
| Tamaño máximo por documento | 50 MB |
| Páginas máximas por documento | 1.000 páginas |
| Documentos por proyecto | 5.000 documentos |
| Proyectos simultáneos por tenant | 20 proyectos |
| Consultas RAG por minuto (por tenant) | 60 req/min |
| Top-K chunks por consulta | 8 (configurable hasta 20) |
| Timeout OCR Azure | 30 segundos |
| Timeout generación respuesta GPT-4o | 60 segundos |

---

## Resumen de decisiones

| ADR | Decisión principal |
|---|---|
| ADR-001 | pgvector para MVP, evaluar Pinecone al escalar |
| ADR-002 | Azure Document Intelligence + Tesseract fallback |
| ADR-003 | Búsqueda híbrida: vector + keyword + metadata |
| ADR-004 | Respuestas IA en JSON estructurado obligatorio |
| ADR-005 | requires_human_review obligatorio en respuestas contractuales |
| ADR-006 | Multi-tenant con RLS desde el día uno |
| ADR-007 | Ingesta asíncrona vía Azure Service Bus |
| ADR-008 | Auditoría y trazabilidad completa de todas las acciones |
| ADR-009 | Stack tecnológico confirmado FastAPI + React + Azure |
| ADR-010 | Límites operacionales definidos para MVP |
