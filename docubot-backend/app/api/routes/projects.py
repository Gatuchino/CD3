"""
DocuBot — Endpoints de gestión de proyectos.
Incluye validación de inputs y aislamiento multi-tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.db.session import get_db
from app.db.models import Project, Document, Alert, AuditLog
from app.schemas.projects import ProjectCreate, ProjectResponse, ProjectSummary
from app.core.security import get_current_user, require_roles, CurrentUser
from app.core.input_validation import validate_text_input, validate_project_code, validate_uuid
from app.core.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

VALID_STATUSES = ["active", "closed", "archived"]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager")
    ),
):
    """Crea un nuevo proyecto documental."""
    await check_rate_limit(current_user.tenant_id, "/api/v1/projects")

    # Validar y sanitizar campos de texto
    safe_name = validate_text_input(data.name, "name", max_length=255)
    safe_client = validate_text_input(data.client_name or "", "client_name", max_length=255)
    safe_contract = validate_text_input(data.contract_name or "", "contract_name", max_length=255)
    safe_code = validate_project_code(data.code) if data.code else None

    project = Project(
        tenant_id=current_user.tenant_id,
        code=safe_code,
        name=safe_name,
        client_name=safe_client or None,
        contract_name=safe_contract or None,
        created_by=current_user.user_id,
    )
    db.add(project)
    await db.flush()

    # Auditoría
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="project_created",
        entity_type="project",
        entity_id=project.id,
        details={"name": safe_name, "code": safe_code},
    ))

    await db.refresh(project)
    await db.commit()
    return project


@router.get("", response_model=List[ProjectSummary])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista todos los proyectos activos del tenant."""
    result = await db.execute(
        select(Project).where(
            Project.tenant_id == current_user.tenant_id,
            Project.status != "archived",
        ).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    summaries = []
    for p in projects:
        doc_count = await db.scalar(
            select(func.count(Document.id)).where(Document.project_id == p.id)
        )
        alert_count = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.project_id == p.id,
                Alert.status == "open",
            )
        )
        summaries.append(
            ProjectSummary(
                id=p.id,
                code=p.code,
                name=p.name,
                client_name=p.client_name,
                status=p.status,
                document_count=doc_count or 0,
                open_alerts=alert_count or 0,
                created_at=p.created_at,
            )
        )
    return summaries


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Obtiene detalle de un proyecto."""
    validated_id = validate_uuid(project_id, "project_id")
    result = await db.execute(
        select(Project).where(
            Project.id == validated_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return project


@router.patch("/{project_id}/status")
async def update_project_status(
    project_id: str,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin_tenant", "project_manager")
    ),
):
    """Actualiza el estado de un proyecto (active | closed | archived)."""
    validated_id = validate_uuid(project_id, "project_id")

    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Opciones: {VALID_STATUSES}",
        )

    result = await db.execute(
        select(Project).where(
            Project.id == validated_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    old_status = project.status
    project.status = new_status

    # Auditoría
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="project_status_changed",
        entity_type="project",
        entity_id=validated_id,
        details={"old_status": old_status, "new_status": new_status},
    ))

    await db.commit()
    return {"project_id": validated_id, "status": new_status}
