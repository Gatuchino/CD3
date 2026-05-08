"""
DocuBot — Endpoint de clasificación documental.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import DocumentVersion, DocumentPage, Document, DocumentClassification
from app.services.classification_service import classification_service
from app.core.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/v1/document-versions", tags=["Classification"])


@router.post("/{version_id}/classify")
async def classify_document(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "contract_manager", "document_controller")
    ),
):
    """
    Clasifica un documento con GPT-4o: tipo documental, disciplina,
    fase del proyecto y metadatos detectados.
    """
    # Verificar que la versión existe y está procesada
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

    # Clasificar
    result = await classification_service.classify(
        pages_data=pages_data,
        file_name=version.file_name,
        version_id=version_id,
    )

    # Guardar clasificación
    from app.db.models import DocumentClassification
    classification_record = DocumentClassification(
        document_version_id=version_id,
        document_type=result.document_type,
        discipline=result.discipline,
        project_phase=result.project_phase,
        detected_metadata=result.detected_metadata,
        confidence_score=result.confidence_score,
        classification_reason=result.classification_reason,
        requires_human_validation=result.requires_human_validation,
    )
    db.add(classification_record)

    # Actualizar tipo y disciplina en el documento padre si confianza alta
    if result.confidence_score >= 0.75:
        dresult = await db.execute(
            select(Document).where(Document.current_version_id == version_id)
        )
        document = dresult.scalar_one_or_none()
        if document:
            if not document.document_type:
                document.document_type = result.document_type
            if not document.discipline:
                document.discipline = result.discipline

    return {
        "document_version_id": version_id,
        "classification": {
            "document_type": result.document_type,
            "discipline": result.discipline,
            "project_phase": result.project_phase,
            "confidence_score": result.confidence_score,
        },
        "suggested_metadata": result.detected_metadata,
        "requires_human_validation": result.requires_human_validation,
        "classification_reason": result.classification_reason,
    }


@router.post("/{version_id}/classify/confirm")
async def confirm_classification(
    version_id: str,
    document_type: str,
    discipline: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager", "contract_manager", "document_controller")
    ),
):
    """Confirma o corrige manualmente la clasificación de un documento."""
    dresult = await db.execute(
        select(Document).where(Document.current_version_id == version_id)
    )
    document = dresult.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    document.document_type = document_type
    document.discipline = discipline

    # Marcar clasificación como validada
    cresult = await db.execute(
        select(DocumentClassification)
        .where(DocumentClassification.document_version_id == version_id)
        .order_by(DocumentClassification.created_at.desc())
    )
    classification = cresult.scalars().first()
    if classification:
        from datetime import datetime
        classification.requires_human_validation = False
        classification.validated_by = current_user.user_id
        classification.validated_at = datetime.utcnow()

    return {"document_id": document.id, "document_type": document_type, "discipline": discipline}
