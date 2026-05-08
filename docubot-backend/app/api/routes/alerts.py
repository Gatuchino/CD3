"""
DocuBot — Endpoints de alertas contractuales.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.db.session import get_db
from app.db.models import Alert, Project
from app.schemas.rag import AlertResponse, AlertsListResponse
from app.core.security import get_current_user, CurrentUser

router = APIRouter(prefix="/api/v1/projects", tags=["Alerts"])


@router.get("/{project_id}/alerts", response_model=AlertsListResponse)
async def list_alerts(
    project_id: str,
    status: Optional[str] = "open",
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista alertas contractuales del proyecto con filtros opcionales."""
    # Verificar acceso al proyecto
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    query = select(Alert).where(Alert.project_id == project_id)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)

    query = query.order_by(
        Alert.severity.desc(),
        Alert.due_date.asc(),
        Alert.created_at.desc(),
    )

    result = await db.execute(query)
    alerts = result.scalars().all()

    return AlertsListResponse(
        project_id=project_id,
        total=len(alerts),
        alerts=[
            AlertResponse(
                alert_id=a.id,
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                description=a.description,
                due_date=str(a.due_date) if a.due_date else None,
                status=a.status,
                source_reference=a.source_reference,
            )
            for a in alerts
        ],
    )


@router.patch("/{project_id}/alerts/{alert_id}/status")
async def update_alert_status(
    project_id: str,
    alert_id: str,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Actualiza el estado de una alerta (acknowledged | resolved | dismissed)."""
    valid_statuses = ["open", "acknowledged", "resolved", "dismissed"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Opciones: {valid_statuses}")

    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.project_id == project_id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")

    alert.status = new_status
    if new_status == "resolved":
        from datetime import datetime
        alert.resolved_at = datetime.utcnow()

    return {"alert_id": alert_id, "status": new_status}
