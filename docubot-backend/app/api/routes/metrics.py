"""
DocuBot — Endpoints de métricas de costos IA y observabilidad.
Solo accesibles para admin_tenant y admin_global.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from typing import Optional

from app.db.session import get_db
from app.db.models import RagQuery, AuditLog
from app.core.security import get_current_user, require_roles, CurrentUser
from app.core.metrics import get_tenant_daily_cost, MODEL_COSTS, DAILY_BUDGET_USD

router = APIRouter(prefix="/api/v1/metrics", tags=["Metrics"])


@router.get("/costs/today")
async def get_today_costs(
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "admin_global")
    ),
):
    """
    Retorna el resumen de costos IA del día actual para el tenant.
    Incluye % del presupuesto diario consumido.
    """
    return await get_tenant_daily_cost(current_user.tenant_id)


@router.get("/costs/history")
async def get_costs_history(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "admin_global")
    ),
):
    """
    Historial de uso RAG de los últimos N días con métricas de latencia y confianza.
    Proxy de costo estimado basado en tokens RAG registrados.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Agregados de consultas RAG por día
    result = await db.execute(
        select(
            func.date_trunc("day", RagQuery.created_at).label("day"),
            func.count().label("queries"),
            func.avg(RagQuery.latency_ms).label("avg_latency_ms"),
            func.avg(RagQuery.confidence).label("avg_confidence"),
            func.sum(
                # Estimación conservadora: 1000 tokens por consulta RAG promedio
                1000
            ).label("estimated_tokens"),
        )
        .where(
            RagQuery.tenant_id == current_user.tenant_id,
            RagQuery.created_at >= since,
        )
        .group_by(func.date_trunc("day", RagQuery.created_at))
        .order_by(func.date_trunc("day", RagQuery.created_at).desc())
    )
    rows = result.fetchall()

    # Costo estimado por día (gpt-4o promedio)
    cost_per_1k = MODEL_COSTS["gpt-4o"]["input"] + MODEL_COSTS["gpt-4o"]["output"] * 0.3
    daily_data = []
    for row in rows:
        estimated_cost = (row.estimated_tokens / 1000) * cost_per_1k
        daily_data.append({
            "day": row.day.date().isoformat() if row.day else None,
            "queries": row.queries,
            "avg_latency_ms": round(float(row.avg_latency_ms or 0)),
            "avg_confidence": round(float(row.avg_confidence or 0), 2),
            "estimated_tokens": int(row.estimated_tokens or 0),
            "estimated_cost_usd": round(estimated_cost, 4),
        })

    total_queries = sum(d["queries"] for d in daily_data)
    total_cost = sum(d["estimated_cost_usd"] for d in daily_data)

    return {
        "period_days": days,
        "since": since.date().isoformat(),
        "total_queries": total_queries,
        "total_estimated_cost_usd": round(total_cost, 4),
        "daily_budget_usd": DAILY_BUDGET_USD,
        "model_rates": MODEL_COSTS,
        "daily_breakdown": daily_data,
    }


@router.get("/performance/rag")
async def get_rag_performance(
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "admin_global")
    ),
):
    """
    Métricas de performance del motor RAG:
    - P50, P90, P99 de latencia
    - Distribución de confianza
    - Tasa de revisión humana requerida
    """
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            RagQuery.latency_ms,
            RagQuery.confidence,
            RagQuery.requires_human_review,
        )
        .where(
            RagQuery.tenant_id == current_user.tenant_id,
            RagQuery.created_at >= since,
            RagQuery.latency_ms.isnot(None),
        )
        .order_by(RagQuery.latency_ms)
    )
    rows = result.fetchall()

    if not rows:
        return {"period_days": days, "total_queries": 0}

    latencies = sorted([r.latency_ms for r in rows if r.latency_ms])
    confidences = [float(r.confidence or 0) for r in rows]
    human_reviews = sum(1 for r in rows if r.requires_human_review)
    n = len(latencies)

    def percentile(data: list, pct: float) -> int:
        if not data:
            return 0
        idx = int(len(data) * pct / 100)
        return data[min(idx, len(data) - 1)]

    # Distribución de confianza en buckets
    conf_distribution = {
        "high_0.8_1.0": sum(1 for c in confidences if c >= 0.8),
        "medium_0.6_0.8": sum(1 for c in confidences if 0.6 <= c < 0.8),
        "low_below_0.6": sum(1 for c in confidences if c < 0.6),
    }

    return {
        "period_days": days,
        "total_queries": n,
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p90": percentile(latencies, 90),
            "p99": percentile(latencies, 99),
            "min": latencies[0],
            "max": latencies[-1],
            "avg": round(sum(latencies) / n),
        },
        "confidence": {
            "avg": round(sum(confidences) / len(confidences), 3),
            "distribution": conf_distribution,
        },
        "human_review_rate_pct": round((human_reviews / n) * 100, 1),
        "human_review_count": human_reviews,
    }


@router.get("/system/health-detailed")
async def get_detailed_health(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "admin_global")
    ),
):
    """
    Health check extendido con métricas del sistema:
    - Conectividad DB
    - Estadísticas de documentos
    - Actividad reciente
    """
    # Test de conectividad DB
    db_ok = False
    try:
        await db.execute(select(func.now()))
        db_ok = True
    except Exception:
        pass

    # Documentos procesados en últimas 24h
    since_24h = datetime.utcnow() - timedelta(hours=24)
    recent_logs = await db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.created_at >= since_24h,
        )
    )

    # Consultas RAG en últimas 24h
    recent_rag = await db.scalar(
        select(func.count()).select_from(RagQuery).where(
            RagQuery.tenant_id == current_user.tenant_id,
            RagQuery.created_at >= since_24h,
        )
    )

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "last_24h": {
            "audit_events": recent_logs or 0,
            "rag_queries": recent_rag or 0,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
