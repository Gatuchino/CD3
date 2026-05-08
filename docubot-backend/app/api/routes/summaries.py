"""
DocuBot — Endpoints de resúmenes ejecutivos de contratos y documentos.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import Document, DocumentVersion, DocumentPage, Project
from app.services.summary_service import summary_service
from app.core.security import get_current_user, CurrentUser

router = APIRouter(prefix="/api/v1/document-versions", tags=["Summaries"])


@router.post("/{version_id}/summary")
async def generate_summary(
    version_id: str,
    audience: str = Query(
        default="project_manager",
        description="Audiencia: gerente_proyecto | project_manager | contract_manager | legal | auditor",
    ),
    summary_type: str = Query(
        default="contractual",
        description="Tipo: contractual | technical | commercial",
    ),
    include_risks: bool = Query(default=True),
    include_deadlines: bool = Query(default=True),
    include_obligations: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Genera un resumen ejecutivo del documento con GPT-4o.
    El resumen se adapta según la audiencia y tipo solicitados.
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
            detail=f"El documento debe estar procesado. Estado: {version.processing_status}",
        )

    # Recuperar documento padre y proyecto
    dresult = await db.execute(
        select(Document).where(Document.current_version_id == version_id)
    )
    document = dresult.scalar_one_or_none()

    # Fallback: buscar por document_id de la versión
    if not document:
        dresult2 = await db.execute(
            select(Document).where(Document.id == version.document_id)
        )
        document = dresult2.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento padre no encontrado.")

    # Verificar acceso vía proyecto/tenant
    presult = await db.execute(
        select(Project).where(
            Project.id == document.project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = presult.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    # Recuperar páginas
    presult2 = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_version_id == version_id)
        .order_by(DocumentPage.page_number)
    )
    pages = presult2.scalars().all()
    pages_data = [
        {"page_number": p.page_number, "text": p.extracted_text or ""}
        for p in pages
    ]

    # Generar resumen
    result = await summary_service.generate(
        pages_data=pages_data,
        document_title=document.title,
        revision_number=version.revision_number or version.version_label or "—",
        project_name=project.name,
        audience=audience,
        summary_type=summary_type,
        include_risks=include_risks,
        include_deadlines=include_deadlines,
        include_obligations=include_obligations,
    )

    return {
        "document_version_id": version_id,
        "document_title": document.title,
        "revision_number": version.revision_number or version.version_label,
        "project_name": project.name,
        "audience": audience,
        "summary_type": summary_type,
        "summary": {
            "executive_overview": result.executive_overview,
            "key_obligations": result.key_obligations,
            "critical_deadlines": result.critical_deadlines,
            "risks": result.risks,
            "commercial_conditions": result.commercial_conditions,
            "recommended_actions": result.recommended_actions,
        },
    }
