"""
DocuBot — Endpoints de control de versiones y diff semantico.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import (
    Document, DocumentVersion, DocumentPage, Project, VersionDiff, Alert,
)
from app.services.diff_service import diff_service
from app.core.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["Versions"])


# ─────────────────────────────────────────────────────────────
# Listar versiones de un documento
# ─────────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/versions")
async def list_versions(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista todas las versiones de un documento ordenadas por fecha de carga."""
    # Verificar acceso: el documento debe pertenecer a un proyecto del tenant
    dresult = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = dresult.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    # Verificar que el proyecto pertenece al tenant
    presult = await db.execute(
        select(Project).where(
            Project.id == document.project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not presult.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    vresult = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.uploaded_at.desc())
    )
    versions = vresult.scalars().all()

    return {
        "document_id": document_id,
        "document_title": document.title,
        "current_version_id": document.current_version_id,
        "versions": [
            {
                "id": v.id,
                "version_label": v.version_label,
                "revision_number": v.revision_number,
                "file_name": v.file_name,
                "file_type": v.file_type,
                "processing_status": v.processing_status,
                "page_count": v.page_count,
                "file_size_bytes": v.file_size_bytes,
                "uploaded_at": v.uploaded_at.isoformat() if v.uploaded_at else None,
                "processed_at": v.processed_at.isoformat() if v.processed_at else None,
                "is_current": v.id == document.current_version_id,
            }
            for v in versions
        ],
    }


# ─────────────────────────────────────────────────────────────
# Comparar dos versiones (diff semantico)
# ─────────────────────────────────────────────────────────────

@router.post("/documents/{document_id}/diff")
async def compare_versions(
    document_id: str,
    previous_version_id: str = Query(..., description="ID de la version anterior"),
    new_version_id: str = Query(..., description="ID de la version nueva"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "contract_manager", "document_controller")
    ),
):
    """
    Compara dos versiones de un documento con GPT-4o.
    Detecta cambios semanticos en obligaciones, plazos, multas y alcance.
    Genera alerta automatica si el nivel de riesgo es high o critical.
    """
    # Verificar documento y acceso
    dresult = await db.execute(select(Document).where(Document.id == document_id))
    document = dresult.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    presult = await db.execute(
        select(Project).where(
            Project.id == document.project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = presult.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    # Recuperar versiones
    prev_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == previous_version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    prev_version = prev_result.scalar_one_or_none()
    if not prev_version:
        raise HTTPException(status_code=404, detail="Version anterior no encontrada.")

    new_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == new_version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    new_version = new_result.scalar_one_or_none()
    if not new_version:
        raise HTTPException(status_code=404, detail="Version nueva no encontrada.")

    if previous_version_id == new_version_id:
        raise HTTPException(status_code=400, detail="Las versiones deben ser distintas.")

    # Recuperar paginas de cada version
    prev_pages_result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_version_id == previous_version_id)
        .order_by(DocumentPage.page_number)
    )
    prev_pages = [
        {"page_number": p.page_number, "text": p.extracted_text or ""}
        for p in prev_pages_result.scalars().all()
    ]

    new_pages_result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_version_id == new_version_id)
        .order_by(DocumentPage.page_number)
    )
    new_pages = [
        {"page_number": p.page_number, "text": p.extracted_text or ""}
        for p in new_pages_result.scalars().all()
    ]

    if not prev_pages and not new_pages:
        raise HTTPException(
            status_code=400,
            detail="Ambas versiones deben tener texto extraido (estado 'processed').",
        )

    # Ejecutar diff semantico
    result = await diff_service.compare_versions(
        previous_pages=prev_pages,
        new_pages=new_pages,
        document_title=document.title,
        project_name=project.name,
        previous_revision=prev_version.revision_number or prev_version.version_label or "Anterior",
        new_revision=new_version.revision_number or new_version.version_label or "Nueva",
    )

    # Persistir diff
    diff_record = VersionDiff(
        document_id=document_id,
        previous_version_id=previous_version_id,
        new_version_id=new_version_id,
        diff_type="semantic",
        semantic_summary=result.semantic_summary,
        critical_changes=result.critical_changes,
        obligations_changed=result.obligations_changed,
        deadlines_changed=result.deadlines_changed,
        commercial_impacts=result.commercial_impacts,
        technical_impacts=result.technical_impacts,
        risk_level=result.risk_level,
        requires_legal_review=result.requires_legal_review,
        created_by=current_user.user_id,
    )
    db.add(diff_record)

    # Generar alerta automatica si el riesgo es alto
    alert_created = False
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    if risk_order.get(result.risk_level, 0) >= 2:
        severity_map = {"high": "high", "critical": "critical"}
        alert = Alert(
            project_id=document.project_id,
            alert_type="version_change",
            severity=severity_map.get(result.risk_level, "high"),
            title=f"[{result.risk_level.upper()}] Cambio significativo: {document.title}",
            description=(
                f"Revision {prev_version.revision_number or 'anterior'} → "
                f"{new_version.revision_number or 'nueva'}\n"
                f"{result.semantic_summary[:400]}"
            ),
            source_document_version_id=new_version_id,
            source_reference={
                "document_id": document_id,
                "previous_version_id": previous_version_id,
                "new_version_id": new_version_id,
            },
        )
        db.add(alert)
        alert_created = True

    await db.commit()
    await db.refresh(diff_record)

    return {
        "diff_id": diff_record.id,
        "document_id": document_id,
        "document_title": document.title,
        "previous_revision": prev_version.revision_number or prev_version.version_label,
        "new_revision": new_version.revision_number or new_version.version_label,
        "semantic_summary": result.semantic_summary,
        "risk_level": result.risk_level,
        "requires_legal_review": result.requires_legal_review,
        "alert_created": alert_created,
        "changes": {
            "critical_changes": result.critical_changes,
            "obligations_changed": result.obligations_changed,
            "deadlines_changed": result.deadlines_changed,
            "commercial_impacts": result.commercial_impacts,
            "technical_impacts": result.technical_impacts,
        },
    }


# ─────────────────────────────────────────────────────────────
# Listar diffs previos de un documento
# ─────────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/diffs")
async def list_diffs(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista el historial de comparaciones semanticas de un documento."""
    dresult = await db.execute(select(Document).where(Document.id == document_id))
    document = dresult.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    presult = await db.execute(
        select(Project).where(
            Project.id == document.project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not presult.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    diffsresult = await db.execute(
        select(VersionDiff)
        .where(VersionDiff.document_id == document_id)
        .order_by(VersionDiff.created_at.desc())
    )
    diffs = diffsresult.scalars().all()

    return [
        {
            "id": d.id,
            "previous_version_id": d.previous_version_id,
            "new_version_id": d.new_version_id,
            "semantic_summary": d.semantic_summary,
            "risk_level": d.risk_level,
            "requires_legal_review": d.requires_legal_review,
            "critical_changes_count": len(d.critical_changes or []),
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in diffs
    ]


# ─────────────────────────────────────────────────────────────
# Promover una version como "vigente"
# ─────────────────────────────────────────────────────────────

@router.patch("/documents/{document_id}/versions/{version_id}/set-current")
async def set_current_version(
    document_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "contract_manager")
    ),
):
    """Promueve una version como la version vigente del documento."""
    dresult = await db.execute(select(Document).where(Document.id == document_id))
    document = dresult.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    presult = await db.execute(
        select(Project).where(
            Project.id == document.project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not presult.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    vresult = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    version = vresult.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version no encontrada.")
    if version.processing_status != "processed":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden promover versiones procesadas. Estado: {version.processing_status}",
        )

    document.current_version_id = version_id
    await db.commit()

    return {
        "document_id": document_id,
        "new_current_version_id": version_id,
        "revision_number": version.revision_number,
        "version_label": version.version_label,
    }
