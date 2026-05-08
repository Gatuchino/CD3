"""
DocuBot — Job de alertas programadas.

Revisa todos los proyectos activos y genera alertas por:
  1. Plazos vencidos sin alerta existente
  2. Plazos que vencen en 7, 14 o 30 días (según severidad)
  3. Alertas abiertas cuyo due_date ya pasó (escalación)
  4. Documentos con processing_status='error' por más de 24h

Puede ejecutarse:
  - Como script standalone: python -m app.workers.alert_scheduler
  - Como endpoint interno: POST /api/v1/internal/run-alert-job
  - Como Azure Function Timer (function_app.py lo invoca)
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import (
    Project, ExtractedDeadline, Alert, DocumentVersion, AuditLog
)

logger = logging.getLogger("alert_scheduler")

# Días de anticipación por severidad
ALERT_WINDOWS = {
    "critical": 7,
    "high":     14,
    "medium":   30,
}


async def run_alert_job() -> dict:
    """
    Punto de entrada principal del job.
    Retorna estadísticas de ejecución.
    """
    stats = {
        "started_at": datetime.utcnow().isoformat(),
        "alerts_created": 0,
        "alerts_escalated": 0,
        "processing_errors_flagged": 0,
        "projects_checked": 0,
        "errors": [],
    }

    async with AsyncSessionLocal() as db:
        try:
            # Obtener proyectos activos
            result = await db.execute(
                select(Project).where(Project.status == "active")
            )
            projects = result.scalars().all()
            stats["projects_checked"] = len(projects)

            for project in projects:
                try:
                    created = await _check_deadlines(db, project.id, project.tenant_id)
                    stats["alerts_created"] += created

                    escalated = await _escalate_overdue_alerts(db, project.id)
                    stats["alerts_escalated"] += escalated

                except Exception as e:
                    logger.error(f"Error en proyecto {project.id}: {e}")
                    stats["errors"].append(f"project:{project.id}: {str(e)[:200]}")

            # Revisar errores de procesamiento (todos los tenants)
            flagged = await _flag_processing_errors(db)
            stats["processing_errors_flagged"] = flagged

            # Registrar ejecución en auditoría
            db.add(AuditLog(
                tenant_id="system",
                action="alert_job_executed",
                entity_type="system",
                entity_id="alert_scheduler",
                details=stats,
            ))

            await db.commit()
            logger.info(f"Job completado: {stats}")

        except Exception as e:
            logger.error(f"Error crítico en alert job: {e}")
            stats["errors"].append(f"critical: {str(e)[:500]}")
            raise

    stats["finished_at"] = datetime.utcnow().isoformat()
    return stats


async def _check_deadlines(
    db: AsyncSession, project_id: str, tenant_id: str
) -> int:
    """
    Revisa plazos del proyecto y crea alertas para los que estén
    dentro de la ventana de anticipación y no tengan alerta activa.
    """
    today = date.today()
    alerts_created = 0

    # Plazos con fecha definida
    deadlines_result = await db.execute(
        select(ExtractedDeadline).where(
            and_(
                ExtractedDeadline.project_id == project_id,
                ExtractedDeadline.due_date.isnot(None),
                ExtractedDeadline.due_date >= today - timedelta(days=1),  # incluye vencidos recientes
            )
        )
    )
    deadlines = deadlines_result.scalars().all()

    for deadline in deadlines:
        days_remaining = (deadline.due_date - today).days

        # Determinar severidad según días restantes
        severity = _compute_severity(days_remaining)
        if severity is None:
            continue  # fuera de todas las ventanas

        # Verificar si ya existe alerta activa para este plazo
        existing = await db.execute(
            select(Alert).where(
                and_(
                    Alert.project_id == project_id,
                    Alert.source_document_version_id == deadline.document_version_id,
                    Alert.alert_type == "deadline_approaching",
                    Alert.status.in_(["open", "acknowledged"]),
                    Alert.due_date == deadline.due_date,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue  # ya existe, no duplicar

        # Generar título descriptivo
        if days_remaining < 0:
            title = f"[VENCIDO] {deadline.description[:200]}"
            severity = "critical"
        elif days_remaining == 0:
            title = f"[HOY] {deadline.description[:200]}"
            severity = "critical"
        else:
            title = f"Plazo en {days_remaining} días: {deadline.description[:180]}"

        db.add(Alert(
            id=str(uuid4()),
            project_id=project_id,
            alert_type="deadline_approaching",
            severity=severity,
            title=title,
            description=(
                f"Plazo contractual: {deadline.description}\n"
                f"Vencimiento: {deadline.due_date}\n"
                f"Responsable: {deadline.responsible_party or 'No definido'}\n"
                f"Referencia: {deadline.source_reference or ''}"
            ),
            due_date=deadline.due_date,
            status="open",
            source_document_version_id=deadline.document_version_id,
            source_reference={
                "deadline_id": str(deadline.id),
                "deadline_type": deadline.deadline_type,
                "source_reference": deadline.source_reference,
                "confidence_score": float(deadline.confidence_score or 0),
            },
        ))
        alerts_created += 1

    return alerts_created


def _compute_severity(days_remaining: int) -> str | None:
    """Determina la severidad de la alerta según días restantes."""
    if days_remaining < 0:
        return "critical"
    elif days_remaining <= ALERT_WINDOWS["critical"]:
        return "critical"
    elif days_remaining <= ALERT_WINDOWS["high"]:
        return "high"
    elif days_remaining <= ALERT_WINDOWS["medium"]:
        return "medium"
    return None  # no está dentro de ninguna ventana


async def _escalate_overdue_alerts(db: AsyncSession, project_id: str) -> int:
    """
    Escala a 'critical' alertas abiertas cuyo due_date ya venció.
    """
    today = date.today()

    result = await db.execute(
        update(Alert)
        .where(
            and_(
                Alert.project_id == project_id,
                Alert.status.in_(["open", "acknowledged"]),
                Alert.due_date < today,
                Alert.severity != "critical",
            )
        )
        .values(severity="critical", updated_at=datetime.utcnow())
        .returning(Alert.id)
    )
    escalated = len(result.fetchall())
    return escalated


async def _flag_processing_errors(db: AsyncSession) -> int:
    """
    Genera alertas para DocumentVersions que llevan >24h en estado 'error'
    sin alerta de procesamiento existente.
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)
    flagged = 0

    error_versions_result = await db.execute(
        select(DocumentVersion).where(
            and_(
                DocumentVersion.processing_status == "error",
                DocumentVersion.created_at < cutoff,
            )
        )
    )
    error_versions = error_versions_result.scalars().all()

    for version in error_versions:
        # Verificar que no haya alerta de procesamiento ya existente
        existing = await db.execute(
            select(Alert).where(
                and_(
                    Alert.source_document_version_id == version.id,
                    Alert.alert_type == "processing_error",
                    Alert.status.in_(["open", "acknowledged"]),
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Obtener project_id del documento
        from app.db.models import Document
        doc_result = await db.execute(
            select(Document).where(Document.id == version.document_id)
        )
        document = doc_result.scalar_one_or_none()
        if not document:
            continue

        db.add(Alert(
            id=str(uuid4()),
            project_id=document.project_id,
            alert_type="processing_error",
            severity="high",
            title=f"Error de procesamiento: {version.file_name}",
            description=(
                f"El documento '{version.file_name}' (revisión {version.revision_number or 'N/A'}) "
                f"lleva más de 24 horas en estado de error.\n"
                f"Error: {version.processing_error or 'No especificado'}"
            ),
            status="open",
            source_document_version_id=version.id,
            source_reference={
                "version_id": str(version.id),
                "file_name": version.file_name,
                "error": version.processing_error,
            },
        ))
        flagged += 1

    return flagged


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_alert_job())
    print(result)
