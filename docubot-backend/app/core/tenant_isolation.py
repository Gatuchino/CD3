"""
DocuBot — Middleware y helpers de aislamiento multi-tenant.
Garantiza que ninguna consulta cruce fronteras de tenant.
"""
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any
import logging

logger = logging.getLogger("docubot.tenant")


class TenantIsolationError(Exception):
    """Intento de acceder a un recurso de otro tenant."""
    pass


async def verify_project_tenant(
    project_id: str,
    tenant_id: str,
    db: AsyncSession,
) -> Any:
    """
    Verifica que el proyecto pertenezca al tenant del usuario.
    Levanta HTTP 403 si hay cruce de tenant.
    """
    from app.db.models import Project

    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")

    if str(project.tenant_id) != str(tenant_id):
        logger.warning(
            "TENANT_ISOLATION_VIOLATION: user tenant=%s attempted access to project %s (tenant=%s)",
            tenant_id, project_id, project.tenant_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: recurso de otro tenant.",
        )

    return project


async def verify_document_tenant(
    document_id: str,
    tenant_id: str,
    db: AsyncSession,
) -> Any:
    """
    Verifica que el documento pertenezca al tenant del usuario
    (a través de la cadena documento → proyecto → tenant).
    """
    from app.db.models import Document, Project
    from sqlalchemy.orm import joinedload

    result = await db.execute(
        select(Document)
        .options(joinedload(Document.project))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    if str(doc.project.tenant_id) != str(tenant_id):
        logger.warning(
            "TENANT_ISOLATION_VIOLATION: user tenant=%s attempted access to document %s",
            tenant_id, document_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: recurso de otro tenant.",
        )

    return doc


async def verify_document_version_tenant(
    version_id: str,
    tenant_id: str,
    db: AsyncSession,
) -> Any:
    """
    Verifica que la versión de documento pertenezca al tenant del usuario.
    """
    from app.db.models import DocumentVersion, Document, Project
    from sqlalchemy.orm import joinedload

    result = await db.execute(
        select(DocumentVersion)
        .options(joinedload(DocumentVersion.document).joinedload(Document.project))
        .where(DocumentVersion.id == version_id)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Versión de documento no encontrada.")

    if str(version.document.project.tenant_id) != str(tenant_id):
        logger.warning(
            "TENANT_ISOLATION_VIOLATION: user tenant=%s attempted access to version %s",
            tenant_id, version_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: recurso de otro tenant.",
        )

    return version


def assert_same_tenant(resource_tenant_id: Any, user_tenant_id: str, resource_name: str = "recurso") -> None:
    """
    Helper síncrono para verificar tenant en casos donde ya tenemos el objeto.
    Levanta HTTP 403 si los tenant IDs no coinciden.
    """
    if str(resource_tenant_id) != str(user_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: {resource_name} de otro tenant.",
        )
