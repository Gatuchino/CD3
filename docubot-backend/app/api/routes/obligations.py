"""
DocuBot — Endpoints de extracción de obligaciones, plazos y alertas.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import (
    DocumentVersion, DocumentPage, Document,
    ExtractedObligation, ExtractedDeadline, Alert,
)
from app.services.obligation_service import obligation_service
from app.core.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/v1/document-versions", tags=["Obligations"])


@router.post("/{version_id}/extract-obligations")
async def extract_obligations(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "contract_manager", "document_controller")
    ),
):
    """
    Extrae obligaciones contractuales y plazos de un documento con GPT-4o.
    Genera automáticamente alertas para plazos próximos o vencidos.
    """
    # Verificar versión
    vresult = await db.execute(
        select(DocumentVersion).where(DocumentVersion.id == version_id)
    )
    version = vresult.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Versión de documento no encontrada.")
    if version.processing_status not in ("processed", "pending_review"):
        raise HTTPException(
            status_code=400,
            detail=f"El documento debe estar en estado 'processed'. Estado actual: {version.processing_status}",
        )

    # Recuperar documento padre para project_id y metadatos
    dresult = await db.execute(
        select(Document).where(Document.current_version_id == version_id)
    )
    document = dresult.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Documento padre no encontrado.")

    # Recuperar páginas
    presult = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_version_id == version_id)
        .order_by(DocumentPage.page_number)
    )
    pages = presult.scalars().all()
    pages_data = [
        {"page_number": p.page_number, "text": p.extracted_text or ""}
        for p in pages
    ]

    # Ejecutar extracción
    result = await obligation_service.extract(
        pages_data=pages_data,
        file_name=version.file_name,
        document_type=document.document_type or "other",
        discipline=document.discipline or "other",
        version_id=version_id,
    )

    # ── Guardar obligaciones ─────────────────────────────────
    saved_obligations = []
    for ob in result.obligations:
        if not ob.obligation_text.strip():
            continue
        record = ExtractedObligation(
            project_id=document.project_id,
            document_version_id=version_id,
            obligation_type=ob.obligation_type,
            obligation_text=ob.obligation_text,
            responsible_party=ob.responsible_party,
            consequence=ob.consequence,
            source_reference=ob.source_reference,
            confidence_score=ob.confidence_score,
            requires_human_validation=ob.confidence_score < 0.75,
        )
        db.add(record)
        saved_obligations.append({
            "obligation_type": ob.obligation_type,
            "obligation_text": ob.obligation_text,
            "responsible_party": ob.responsible_party,
            "consequence": ob.consequence,
            "confidence_score": ob.confidence_score,
        })

    # ── Guardar plazos y generar alertas ─────────────────────
    saved_deadlines = []
    alerts_created = 0
    for dl in result.deadlines:
        if not dl.description.strip():
            continue
        dl_record = ExtractedDeadline(
            project_id=document.project_id,
            document_version_id=version_id,
            deadline_type=dl.deadline_type,
            description=dl.description,
            due_date=dl.due_date,
            relative_deadline=dl.relative_deadline,
            responsible_party=dl.responsible_party,
            source_reference=dl.source_reference,
            confidence_score=dl.confidence_score,
        )
        db.add(dl_record)
        saved_deadlines.append({
            "deadline_type": dl.deadline_type,
            "description": dl.description,
            "due_date": dl.due_date,
            "relative_deadline": dl.relative_deadline,
            "responsible_party": dl.responsible_party,
            "confidence_score": dl.confidence_score,
        })

        # Generar alerta si aplica
        alert_data = obligation_service.compute_alert_for_deadline(
            deadline=dl,
            project_id=document.project_id,
            document_version_id=version_id,
            document_title=document.title,
        )
        if alert_data:
            alert_record = Alert(**alert_data)
            db.add(alert_record)
            alerts_created += 1

    await db.commit()

    return {
        "document_version_id": version_id,
        "obligations_extracted": len(saved_obligations),
        "deadlines_extracted": len(saved_deadlines),
        "alerts_created": alerts_created,
        "obligations": saved_obligations,
        "deadlines": saved_deadlines,
    }


@router.get("/{version_id}/obligations")
async def list_obligations(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista las obligaciones extraídas para una versión de documento."""
    result = await db.execute(
        select(ExtractedObligation)
        .where(ExtractedObligation.document_version_id == version_id)
        .order_by(ExtractedObligation.created_at)
    )
    obligations = result.scalars().all()
    return [
        {
            "id": ob.id,
            "obligation_type": ob.obligation_type,
            "obligation_text": ob.obligation_text,
            "responsible_party": ob.responsible_party,
            "consequence": ob.consequence,
            "confidence_score": float(ob.confidence_score or 0),
            "requires_human_validation": ob.requires_human_validation,
            "source_reference": ob.source_reference,
        }
        for ob in obligations
    ]


@router.get("/{version_id}/deadlines")
async def list_deadlines(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista los plazos extraídos para una versión de documento."""
    result = await db.execute(
        select(ExtractedDeadline)
        .where(ExtractedDeadline.document_version_id == version_id)
        .order_by(ExtractedDeadline.due_date.asc().nullslast())
    )
    deadlines = result.scalars().all()
    return [
        {
            "id": dl.id,
            "deadline_type": dl.deadline_type,
            "description": dl.description,
            "due_date": str(dl.due_date) if dl.due_date else None,
            "relative_deadline": dl.relative_deadline,
            "responsible_party": dl.responsible_party,
            "confidence_score": float(dl.confidence_score or 0),
            "source_reference": dl.source_reference,
        }
        for dl in deadlines
    ]
