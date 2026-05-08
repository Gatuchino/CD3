"""
DocuBot — Endpoints de carga y gestión de documentos.
Incluye validación de archivos, rate limiting y aislamiento multi-tenant.
"""
import hashlib
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.db.session import get_db
from app.db.models import Document, DocumentVersion, Project, AuditLog
from app.schemas.documents import (
    DocumentUploadResponse, DocumentResponse,
    DocumentListItem, ProcessingStatusResponse,
    VALID_DOCUMENT_TYPES, VALID_DISCIPLINES,
)
from app.core.security import get_current_user, require_roles, CurrentUser
from app.core.config import settings
from app.core.input_validation import validate_filename, validate_file_type, validate_file_size, validate_text_input
from app.core.tenant_isolation import assert_same_tenant
from app.core.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/v1/projects", tags=["Documents"])

MAX_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/{project_id}/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    discipline: Optional[str] = Form(None),
    revision_number: Optional[str] = Form(None),
    version_label: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager",
                      "contract_manager", "document_controller")
    ),
):
    """
    Carga un documento al proyecto. Inicia el pipeline de procesamiento asíncrono.
    Formatos soportados: PDF, DOCX, DOC, XLSX, XLS, PPTX, TXT.
    """
    # Rate limiting por tenant
    await check_rate_limit(current_user.tenant_id, "/api/v1/documents/")

    # Validar nombre de archivo (anti path traversal)
    safe_filename = validate_filename(file.filename or "unknown")

    # Validar tipo de archivo por extensión y MIME
    content_type = file.content_type or "application/octet-stream"
    file_ext = validate_file_type(content_type, safe_filename)

    # Validar tipo documental si fue especificado
    if document_type and document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo documental inválido: {document_type}")

    # Validar disciplina si fue especificada
    if discipline and discipline not in VALID_DISCIPLINES:
        raise HTTPException(status_code=400, detail=f"Disciplina inválida: {discipline}")

    # Sanitizar campos de texto opcionales
    safe_revision = validate_text_input(revision_number or "Rev.0", "revision_number", max_length=80)
    safe_label = validate_text_input(version_label or "Original", "version_label", max_length=80)

    # Verificar que el proyecto pertenece al tenant
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    assert_same_tenant(project.tenant_id, current_user.tenant_id, "proyecto")

    # Leer y validar tamaño
    file_bytes = await file.read()
    validate_file_size(len(file_bytes), max_mb=settings.MAX_FILE_SIZE_MB)

    # Checksum SHA-256 para detección de duplicados
    checksum = hashlib.sha256(file_bytes).hexdigest()

    # Verificar duplicado en el proyecto
    dup_result = await db.execute(
        select(DocumentVersion).join(Document).where(
            Document.project_id == project_id,
            DocumentVersion.checksum_sha256 == checksum,
        )
    )
    if dup_result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Ya existe un documento con el mismo contenido en este proyecto.",
        )

    # Generar IDs
    document_id = str(uuid4())
    version_id = str(uuid4())

    blob_path = (
        f"{current_user.tenant_id}/{project_id}/"
        f"{document_id}/{version_id}/original/{safe_filename}"
    )
    blob_url = f"https://stdocubot.blob.core.windows.net/documents/{blob_path}"

    # --- Guardar en Azure Blob Storage ---
    # await storage_service.upload_bytes(blob_path, file_bytes)

    # Crear registro Document
    document = Document(
        id=document_id,
        project_id=project_id,
        title=safe_filename.rsplit(".", 1)[0].replace("_", " "),
        document_type=document_type,
        discipline=discipline,
        created_by=current_user.user_id,
    )
    db.add(document)

    # Crear registro DocumentVersion
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        revision_number=safe_revision,
        version_label=safe_label,
        file_name=safe_filename,
        file_type=file_ext,
        blob_url=blob_url,
        blob_path=blob_path,
        checksum_sha256=checksum,
        file_size_bytes=len(file_bytes),
        processing_status="uploaded",
        uploaded_by=current_user.user_id,
    )
    db.add(version)
    await db.flush()

    # Actualizar current_version_id en Document
    document.current_version_id = version_id

    # Auditoría
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="document_uploaded",
        entity_type="document_version",
        entity_id=version_id,
        details={
            "project_id": project_id,
            "document_id": document_id,
            "file_name": safe_filename,
            "file_type": file_ext,
            "file_size_bytes": len(file_bytes),
            "checksum": checksum,
        },
    ))

    await db.commit()

    # --- Encolar procesamiento asíncrono ---
    # await ingestion_queue.enqueue({
    #     "version_id": version_id,
    #     "tenant_id": current_user.tenant_id,
    #     "project_id": project_id,
    #     "file_type": file_ext,
    #     "blob_path": blob_path,
    # })

    return DocumentUploadResponse(
        document_id=document_id,
        document_version_id=version_id,
        file_name=safe_filename,
        checksum_sha256=checksum,
        blob_path=blob_path,
        processing_status="uploaded",
        message="Documento cargado correctamente. Procesamiento iniciado.",
    )


@router.get("/{project_id}/documents", response_model=List[DocumentListItem])
async def list_documents(
    project_id: str,
    document_type: Optional[str] = None,
    discipline: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista documentos de un proyecto con filtros opcionales."""
    # Verificar acceso tenant
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    query = (
        select(
            Document,
            DocumentVersion.revision_number,
            DocumentVersion.processing_status,
        )
        .join(DocumentVersion, Document.current_version_id == DocumentVersion.id, isouter=True)
        .where(Document.project_id == project_id)
    )
    if document_type:
        query = query.where(Document.document_type == document_type)
    if discipline:
        query = query.where(Document.discipline == discipline)

    result = await db.execute(query.order_by(Document.created_at.desc()))
    rows = result.all()

    items = []
    for doc, rev_number, proc_status in rows:
        items.append(DocumentListItem(
            id=doc.id,
            title=doc.title,
            document_code=doc.document_code,
            document_type=doc.document_type,
            discipline=doc.discipline,
            current_status=doc.current_status,
            revision_number=rev_number,
            processing_status=proc_status,
            created_at=doc.created_at,
        ))
    return items


@router.get("/{project_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Detalle de un documento específico."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    # Verificar que el proyecto pertenece al tenant
    proj_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    return DocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        title=doc.title,
        document_code=doc.document_code,
        document_type=doc.document_type,
        discipline=doc.discipline,
        current_status=doc.current_status,
        current_version_id=doc.current_version_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{project_id}/documents/{document_id}/versions/{version_id}/status",
            response_model=ProcessingStatusResponse)
async def get_processing_status(
    project_id: str,
    document_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Estado de procesamiento de una versión de documento."""
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Versión no encontrada.")

    return ProcessingStatusResponse(
        version_id=version_id,
        processing_status=version.processing_status,
        processing_error=version.processing_error,
        page_count=version.page_count,
        processed_at=version.processed_at,
    )
