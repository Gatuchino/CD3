"""
DocuBot — Motor RAG contractual con citas exactas.

Pipeline:
  1. Normalización de la pregunta
  2. Detección de intención y filtros
  3. Embedding de la pregunta
  4. Búsqueda híbrida (vector + keyword + metadata)
  5. Re-ranking
  6. Construcción de contexto con citas
  7. Generación de respuesta GPT-4o
  8. Validación y parseo de JSON
"""
import json
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Any, Tuple

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.demo_mode import IS_DEMO, demo_rag_response
from app.core.metrics import AIOperationTimer, record_token_usage, TokenUsageRecord, compute_cost
from app.services.embedding_service import embedding_service


# ─────────────────────────────────────────────────────────────
# Prompts del sistema
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres DocuBot, un asistente experto en administración contractual, \
gestión documental, minería, construcción y proyectos EPC/EPCM en Chile.

Tu función es responder consultas del usuario usando exclusivamente el contexto \
documental recuperado desde la base de conocimiento del proyecto. Actúas como un \
copiloto documental experto, no como un chatbot genérico.

REGLAS OBLIGATORIAS:
1. No inventes información. Nunca uses conocimiento externo no respaldado por los \
documentos entregados en el contexto.
2. Toda afirmación contractual relevante debe incluir una cita exacta con: documento, \
revisión, página, párrafo o sección, y cita textual.
3. Si los documentos no contienen evidencia suficiente, responde exactamente: \
"No existe evidencia suficiente en los documentos revisados para responder esta consulta."
4. Si existen contradicciones entre documentos, indícalo y prioriza en este orden:
   a. La versión documental más reciente.
   b. La adenda sobre el contrato base.
   c. El contrato sobre documentos operacionales.
5. Si una respuesta implica riesgo contractual, marca requires_human_review: true.
6. Destaca plazos, vencimientos, multas, penalidades, obligaciones y entregables críticos.
7. Responde en español profesional, claro y ejecutivo.
8. Si la confianza es menor a 0.70, siempre marca requires_human_review: true.

FORMATO DE RESPUESTA OBLIGATORIO — devuelve únicamente JSON válido:
{
  "answer": "Respuesta directa y ejecutiva.",
  "evidence": [
    {
      "document": "Nombre exacto del documento",
      "revision": "Rev.X",
      "page": "número de página",
      "paragraph": "Cláusula o sección",
      "quote": "Cita textual extraída del documento."
    }
  ],
  "interpretation": "Interpretación contractual basada en la evidencia.",
  "risks_or_warnings": ["Advertencia o riesgo identificado."],
  "confidence": 0.00,
  "requires_human_review": true
}"""

HUMAN_PROMPT_TEMPLATE = """Pregunta del usuario:
{question}

Proyecto:
{project_name}

Filtros aplicados:
- Tipos documentales: {document_types}
- Política de revisión: {revision_policy}

Contexto documental recuperado:
{retrieved_context}

Instrucciones adicionales:
- Responde solamente con base en el contexto entregado.
- Incluye citas exactas por cada afirmación relevante.
- Si la evidencia no es suficiente, indícalo explícitamente.
- Si hay adendas que modifican el contrato base, analiza y señala el cambio.
- Devuelve exclusivamente JSON válido sin texto adicional."""


# ─────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    document_title: str
    revision_number: str
    document_type: str
    start_page: int
    section_title: Optional[str]
    paragraph_number: Optional[str]
    source_reference: dict
    vector_score: float
    keyword_score: float = 0.0

    @property
    def combined_score(self) -> float:
        return self.vector_score * 0.7 + self.keyword_score * 0.3


@dataclass
class RagAnswer:
    answer: str
    evidence: List[dict]
    interpretation: Optional[str]
    risks_or_warnings: List[str]
    confidence: float
    requires_human_review: bool
    retrieved_chunks: List[RetrievedChunk]
    latency_ms: int


# ─────────────────────────────────────────────────────────────
# Servicio RAG
# ─────────────────────────────────────────────────────────────

class RagService:
    def __init__(self):
        self._llm = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def query(
        self,
        db: AsyncSession,
        project_id: str,
        project_name: str,
        question: str,
        top_k: int = 8,
        document_types: Optional[List[str]] = None,
        revision_policy: str = "latest_only",
        tenant_id: str = "unknown",
    ) -> RagAnswer:
        """Pipeline RAG completo con métricas de tokens y costos."""
        t0 = time.time()

        # 1. Normalizar pregunta
        normalized = self._normalize_question(question)

        # 2. Embedding de la pregunta
        query_vector = await embedding_service.embed(normalized)

        # 3. Búsqueda híbrida
        chunks = await self._hybrid_search(
            db=db,
            project_id=project_id,
            query_vector=query_vector,
            query_text=normalized,
            top_k=top_k,
            document_types=document_types,
            revision_policy=revision_policy,
        )

        # 4. Re-ranking
        chunks = sorted(chunks, key=lambda c: c.combined_score, reverse=True)[:top_k]

        # 5. Construir contexto con citas
        context = self._build_context(chunks)

        # 6. Generar respuesta con GPT-4o + capturar tokens para métricas
        async with AIOperationTimer("rag_query", tenant_id, "gpt-4o", {"project_id": project_id}) as timer:
            raw_answer, usage = await self._generate_answer_with_usage(
                question=normalized,
                project_name=project_name,
                context=context,
                document_types=document_types,
                revision_policy=revision_policy,
            )
            if usage:
                timer.set_tokens(
                    prompt=usage.get("prompt_tokens", 0),
                    completion=usage.get("completion_tokens", 0),
                )

        # 7. Parsear JSON de respuesta
        parsed = self._parse_answer(raw_answer)

        latency_ms = int((time.time() - t0) * 1000)
        return RagAnswer(
            answer=parsed.get("answer", ""),
            evidence=parsed.get("evidence", []),
            interpretation=parsed.get("interpretation"),
            risks_or_warnings=parsed.get("risks_or_warnings", []),
            confidence=float(parsed.get("confidence", 0.0)),
            requires_human_review=bool(parsed.get("requires_human_review", True)),
            retrieved_chunks=chunks,
            latency_ms=latency_ms,
        )

    # ──────────────────────────────────────────────────────────
    # Búsqueda híbrida
    # ──────────────────────────────────────────────────────────

    async def _hybrid_search(
        self,
        db: AsyncSession,
        project_id: str,
        query_vector: List[float],
        query_text: str,
        top_k: int,
        document_types: Optional[List[str]],
        revision_policy: str,
    ) -> List[RetrievedChunk]:
        """
        Búsqueda híbrida: vector (cosine pgvector) + keyword (pg_trgm).
        Filtra por proyecto y opcionalmente por tipo documental y revisión vigente.
        """
        # Convertir vector a string para pgvector
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        # Condición de revisión: solo versión vigente o todas
        revision_condition = (
            "AND d.current_version_id = dv.id"
            if revision_policy == "latest_only"
            else ""
        )

        # Condición de tipo documental
        doc_type_condition = ""
        if document_types:
            types_str = ", ".join(f"'{t}'" for t in document_types)
            doc_type_condition = f"AND d.document_type IN ({types_str})"

        # ── Query vectorial ───────────────────────────────────
        vector_sql = text(f"""
            SELECT
                dc.id::text                              AS chunk_id,
                dc.content,
                dc.section_title,
                dc.paragraph_number,
                dc.start_page,
                dc.source_reference,
                d.title                                  AS document_title,
                dv.revision_number,
                d.document_type,
                1 - (ce.embedding <=> :query_vec::vector) AS vector_score
            FROM chunk_embeddings ce
            JOIN document_chunks dc       ON dc.id = ce.chunk_id
            JOIN document_versions dv     ON dv.id = dc.document_version_id
            JOIN documents d              ON d.id  = dv.document_id
            WHERE d.project_id = :project_id
              AND dv.processing_status = 'processed'
              {revision_condition}
              {doc_type_condition}
            ORDER BY ce.embedding <=> :query_vec::vector
            LIMIT :limit
        """)

        vresult = await db.execute(
            vector_sql,
            {"query_vec": vector_str, "project_id": project_id, "limit": top_k * 2},
        )
        vector_rows = {row.chunk_id: row for row in vresult.fetchall()}

        # ── Query keyword (trigram) ───────────────────────────
        keyword_sql = text(f"""
            SELECT
                dc.id::text                         AS chunk_id,
                similarity(dc.content, :query_text) AS keyword_score
            FROM document_chunks dc
            JOIN document_versions dv ON dv.id = dc.document_version_id
            JOIN documents d          ON d.id  = dv.document_id
            WHERE d.project_id = :project_id
              AND dv.processing_status = 'processed'
              AND dc.content % :query_text
              {revision_condition}
              {doc_type_condition}
            ORDER BY keyword_score DESC
            LIMIT :limit
        """)

        kresult = await db.execute(
            keyword_sql,
            {"query_text": query_text, "project_id": project_id, "limit": top_k * 2},
        )
        keyword_scores = {row.chunk_id: float(row.keyword_score) for row in kresult.fetchall()}

        # ── Combinar resultados ───────────────────────────────
        chunks: List[RetrievedChunk] = []
        for chunk_id, row in vector_rows.items():
            src = row.source_reference or {}
            chunks.append(RetrievedChunk(
                chunk_id=chunk_id,
                content=row.content,
                document_title=row.document_title or src.get("document", ""),
                revision_number=row.revision_number or src.get("revision", ""),
                document_type=row.document_type or "",
                start_page=row.start_page or 1,
                section_title=row.section_title,
                paragraph_number=row.paragraph_number,
                source_reference=src,
                vector_score=float(row.vector_score),
                keyword_score=keyword_scores.get(chunk_id, 0.0),
            ))

        # Añadir resultados keyword que no estaban en vector search
        for chunk_id, kscore in keyword_scores.items():
            if chunk_id not in vector_rows:
                # Recuperar datos básicos del chunk
                extra_sql = text("""
                    SELECT dc.id::text, dc.content, dc.section_title, dc.paragraph_number,
                           dc.start_page, dc.source_reference,
                           d.title, dv.revision_number, d.document_type
                    FROM document_chunks dc
                    JOIN document_versions dv ON dv.id = dc.document_version_id
                    JOIN documents d          ON d.id  = dv.document_id
                    WHERE dc.id::text = :chunk_id
                """)
                er = await db.execute(extra_sql, {"chunk_id": chunk_id})
                erow = er.fetchone()
                if erow:
                    src = erow.source_reference or {}
                    chunks.append(RetrievedChunk(
                        chunk_id=chunk_id,
                        content=erow.content,
                        document_title=erow.title or "",
                        revision_number=erow.revision_number or "",
                        document_type=erow.document_type or "",
                        start_page=erow.start_page or 1,
                        section_title=erow.section_title,
                        paragraph_number=erow.paragraph_number,
                        source_reference=src,
                        vector_score=0.0,
                        keyword_score=kscore,
                    ))

        return chunks

    # ──────────────────────────────────────────────────────────
    # Construcción de contexto
    # ──────────────────────────────────────────────────────────

    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """Construye el contexto textual con referencias documentales."""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            ref = f"[Fuente {i}] {chunk.document_title}"
            if chunk.revision_number:
                ref += f" — {chunk.revision_number}"
            if chunk.start_page:
                ref += f" — Pág. {chunk.start_page}"
            if chunk.paragraph_number:
                ref += f" — {chunk.paragraph_number}"
            elif chunk.section_title:
                ref += f" — {chunk.section_title}"
            parts.append(f"{ref}\n{chunk.content}")
        return "\n\n---\n\n".join(parts)

    # ──────────────────────────────────────────────────────────
    # Generación con GPT-4o
    # ──────────────────────────────────────────────────────────

    async def _generate_answer(
        self,
        question: str,
        project_name: str,
        context: str,
        document_types: Optional[List[str]],
        revision_policy: str,
    ) -> str:
        """Llama a OpenAI GPT-4o (compatibilidad hacia atrás)."""
        text, _ = await self._generate_answer_with_usage(
            question, project_name, context, document_types, revision_policy
        )
        return text

    async def _generate_answer_with_usage(
        self,
        question: str,
        project_name: str,
        context: str,
        document_types: Optional[List[str]],
        revision_policy: str,
    ) -> Tuple[str, Optional[dict]]:
        if IS_DEMO:
            import json
            resp = demo_rag_response(question)
            usage = {"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000}
            return json.dumps(resp), usage
        """
        Llama a OpenAI GPT-4o y retorna (respuesta_texto, token_usage).
        token_usage = {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        """
        import asyncio
        loop = asyncio.get_event_loop()

        human_prompt = HUMAN_PROMPT_TEMPLATE.format(
            question=question,
            project_name=project_name,
            document_types=", ".join(document_types) if document_types else "todos",
            revision_policy="solo revisión vigente" if revision_policy == "latest_only" else "todas las revisiones",
            retrieved_context=context if context else "No se recuperaron documentos relevantes.",
        )

        def _call():
            response = self._llm.chat.completions.create(
                model=settings.OPENAI_MODEL_GPT4O,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": human_prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
                timeout=settings.GPT_TIMEOUT_SECONDS,
            )
            text = response.choices[0].message.content
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return text, usage

        return await loop.run_in_executor(None, _call)