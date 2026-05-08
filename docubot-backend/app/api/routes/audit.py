"""
DocuBot — Endpoints de auditoría y trazabilidad completa.
Proporciona acceso filtrado al audit trail de todas las acciones del sistema.
"""
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.db.session import get_db
from app.db.models import AuditLog, RagQuery, User
from app.core.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])

# Acciones que generan eventos de auditoría en el sistema
AUDITABLE_ACTIONS = [
    "document_uploaded",
    "document_processed",
    "document_classified",
    "obligations_extracted",
    "rag_query",
    "version_diff",
    "alert_status_changed",
    "classification_confirmed",
    "version_promoted",
    "project_created",
    "project_status_changed",
]


@router.get("/logs")
async def list_audit_logs(
    project_id: Optional[str] = Query(None, description="Filtrar por proyecto"),
    user_id: Optional[str] = Query(None, description="Filtrar por usuario"),
    action: Optional[str] = Query(None, description="Filtrar por tipo de acción"),
    entity_type: Optional[str] = Query(None, description="Filtrar por tipo de entidad"),
    date_from: Optional[date] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "contract_manager", "auditor")
    ),
):
    """
    Lista el log de auditoría del tenant con filtros opcionales.
    Incluye todas las acciones: cargas, consultas RAG, clasificaciones,
    cambios de estado, diffs semánticos y alertas.
    """
    filters = [AuditLog.tenant_id == current_user.tenant_id]

    if action:
        filters.append(AuditLog.action == action)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if date_from:
        filters.append(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    # Filtro por proyecto: buscar en details JSONB
    if project_id:
        filters.append(AuditLog.details["project_id"].astext == project_id)

    # Contar total
    count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(and_(*filters))
    )
    total = count_result.scalar()

    # Obtener registros paginados
    result = await db.execute(
        select(AuditLog)
        .where(and_(*filters))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": str(log.entity_id) if log.entity_id else None,
                "user_id": str(log.user_id) if log.user_id else None,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


@router.get("/logs/summary")
async def audit_summary(
    days: int = Query(default=30, ge=1, le=365, description="Ultimos N dias"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "auditor")
    ),
):
    """
    Resumen estadístico de actividad del tenant en los últimos N días.
    Agrupa por tipo de acción y muestra totales.
    """
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(AuditLog.action, func.count().label("count"))
        .where(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.created_at >= since,
        )
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
    )
    rows = result.fetchall()

    # Métricas de consultas RAG
    rag_result = await db.execute(
        select(
            func.count().label("total_queries"),
            func.avg(RagQuery.latency_ms).label("avg_latency_ms"),
            func.avg(RagQuery.confidence).label("avg_confidence"),
        ).where(
            RagQuery.tenant_id == current_user.tenant_id,
            RagQuery.created_at >= since,
        )
    )
    rag_stats = rag_result.fetchone()

    return {
        "period_days": days,
        "since": since.isoformat(),
        "actions_breakdown": [
            {"action": row.action, "count": row.count}
            for row in rows
        ],
        "total_events": sum(r.count for r in rows),
        "rag_stats": {
            "total_queries": int(rag_stats.total_queries or 0),
            "avg_latency_ms": round(float(rag_stats.avg_latency_ms or 0)),
            "avg_confidence": round(float(rag_stats.avg_confidence or 0), 2),
        },
    }


@router.get("/rag-history")
async def rag_query_history(
    project_id: Optional[str] = Query(None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista el historial de consultas RAG del usuario actual o del tenant."""
    filters = [RagQuery.tenant_id == current_user.tenant_id]

    # Usuarios sin rol admin ven solo sus propias consultas
    if current_user.role not in ("admin_tenant", "project_manager", "auditor"):
        filters.append(RagQuery.user_id == current_user.user_id)

    if project_id:
        filters.append(RagQuery.project_id == project_id)

    count_result = await db.execute(
        select(func.count()).select_from(RagQuery).where(and_(*filters))
    )
    total = count_result.scalar()

    result = await db.execute(
        select(RagQuery)
        .where(and_(*filters))
        .order_by(RagQuery.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    queries = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "queries": [
            {
                "id": q.id,
                "question": q.question,
                "answer": q.answer[:300] + "…" if q.answer and len(q.answer) > 300 else q.answer,
                "confidence": float(q.confidence or 0),
                "requires_human_review": q.requires_human_review,
                "latency_ms": q.latency_ms,
                "model_name": q.model_name,
                "filters_used": q.filters_used,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in queries
        ],
    }


@router.get("/rag-history/{query_id}")
async def get_rag_query_detail(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Detalle completo de una consulta RAG con sus citas."""
    from app.db.models import RagCitation
    result = await db.execute(
        select(RagQuery).where(
            RagQuery.id == query_id,
            RagQuery.tenant_id == current_user.tenant_id,
        )
    )
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(status_code=404, detail="Consulta no encontrada.")

    cit_result = await db.execute(
        select(RagCitation)
        .where(RagCitation.query_id == query_id)
        .order_by(RagCitation.relevance_score.desc())
    )
    citations = cit_result.scalars().all()

    return {
        "id": query.id,
        "question": query.question,
        "answer": query.answer,
        "interpretation": query.interpretation,
        "risks_warnings": query.risks_warnings,
        "confidence": float(query.confidence or 0),
        "requires_human_review": query.requires_human_review,
        "latency_ms": query.latency_ms,
        "model_name": query.model_name,
        "retrieval_k": query.retrieval_k,
        "filters_used": query.filters_used,
        "created_at": query.created_at.isoformat() if query.created_at else None,
        "citations": [
            {
                "document_version_id": c.document_version_id,
                "page_number": c.page_number,
                "paragraph_ref": c.paragraph_ref,
                "relevance_score": float(c.relevance_score or 0),
                "source_reference": c.source_reference,
            }
            for c in citations
        ],
    }


@router.get("/actions")
async def list_auditable_actions(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Retorna la lista de tipos de acciones auditables en el sistema."""
    return {"actions": AUDITABLE_ACTIONS}
