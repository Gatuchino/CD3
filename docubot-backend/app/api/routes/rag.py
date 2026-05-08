"""
DocuBot — Endpoints del motor RAG contractual (implementación completa).
Incluye validación anti-injection y rate limiting por tenant.
"""
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import Project, RagQuery, RagCitation, AuditLog
from app.schemas.rag import RagQueryRequest, RagQueryResponse, RagEvidence
from app.services.rag_service import rag_service
from app.core.security import get_current_user, CurrentUser
from app.core.input_validation import validate_rag_question, validate_uuid
from app.core.tenant_isolation import assert_same_tenant
from app.core.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(
    request: RagQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Consulta RAG sobre documentos del proyecto.
    Retorna respuesta ejecutiva con citas exactas, interpretación,
    advertencias y nivel de confianza.
    """
    # Rate limiting por tenant (20 req/min para RAG)
    await check_rate_limit(current_user.tenant_id, "/api/v1/rag/query")

    # Validar y sanitizar pregunta (anti prompt-injection)
    safe_question = validate_rag_question(request.question)
    validated_project_id = validate_uuid(request.project_id, "project_id")

    # Verificar acceso al proyecto con aislamiento tenant
    result = await db.execute(
        select(Project).where(
            Project.id == validated_project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    assert_same_tenant(project.tenant_id, current_user.tenant_id, "proyecto")

    # Extraer filtros
    filters = request.filters or {}
    document_types = (
        getattr(filters, "document_types", None)
        if hasattr(filters, "document_types")
        else (filters.get("document_types") if isinstance(filters, dict) else None)
    )
    revision_policy = (
        getattr(filters, "revision_policy", "latest_only")
        if hasattr(filters, "revision_policy")
        else (filters.get("revision_policy", "latest_only") if isinstance(filters, dict) else "latest_only")
    )

    # Ejecutar pipeline RAG con la pregunta sanitizada
    rag_result = await rag_service.query(
        db=db,
        project_id=validated_project_id,
        project_name=project.name,
        question=safe_question,
        top_k=min(request.top_k, 20),  # Cap máximo de chunks
        document_types=document_types,
        revision_policy=revision_policy,
        tenant_id=current_user.tenant_id,  # Para métricas de costo
    )

    # Guardar consulta en BD
    query_id = str(uuid4())
    rag_record = RagQuery(
        id=query_id,
        tenant_id=current_user.tenant_id,
        project_id=validated_project_id,
        user_id=current_user.user_id,
        question=safe_question,
        answer=rag_result.answer,
        interpretation=rag_result.interpretation,
        risks_warnings=rag_result.risks_or_warnings,
        confidence=rag_result.confidence,
        requires_human_review=rag_result.requires_human_review,
        model_name="gpt-4o",
        retrieval_k=request.top_k,
        latency_ms=rag_result.latency_ms,
        filters_used={"document_types": document_types, "revision_policy": revision_policy},
    )
    db.add(rag_record)
    await db.flush()

    # Guardar citas
    for chunk in rag_result.retrieved_chunks[:request.top_k]:
        citation = RagCitation(
            query_id=query_id,
            document_version_id=chunk.source_reference.get("document_version_id", chunk.chunk_id),
            chunk_id=chunk.chunk_id,
            page_number=chunk.start_page,
            paragraph_ref=chunk.paragraph_number or chunk.section_title,
            relevance_score=chunk.combined_score,
            source_reference=chunk.source_reference,
        )
        db.add(citation)

    # Auditoría
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="rag_query",
        entity_type="rag_query",
        entity_id=query_id,
        details={
            "project_id": validated_project_id,
            "chunks_retrieved": len(rag_result.retrieved_chunks),
            "confidence": float(rag_result.confidence),
            "requires_human_review": rag_result.requires_human_review,
        },
    ))

    await db.commit()

    return RagQueryResponse(
        query_id=query_id,
        answer=rag_result.answer,
        evidence=[RagEvidence(**ev) for ev in rag_result.evidence],
        interpretation=rag_result.interpretation,
        risks_or_warnings=rag_result.risks_or_warnings,
        confidence=rag_result.confidence,
        requires_human_review=rag_result.requires_human_review,
        latency_ms=rag_result.latency_ms,
        created_at=datetime.utcnow(),
    )
