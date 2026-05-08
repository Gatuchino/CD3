"""
DocuBot — Middleware de auditoría automática.
Registra automáticamente las llamadas a endpoints críticos en audit_logs,
capturando IP, user_agent y metadata de la request.
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# Endpoints que se registran automáticamente en el audit trail
# Formato: (method, path_prefix, action_name)
AUDITED_ENDPOINTS = [
    ("POST", "/api/v1/projects", "project_created"),
    ("POST", "/api/v1/rag/query", "rag_query"),
    ("POST", "/api/v1/document-versions/", "document_action"),  # classify, extract, summary, diff
    ("POST", "/api/v1/documents/", "document_uploaded"),
    ("PATCH", "/api/v1/projects/", "project_status_changed"),
    ("PATCH", "/api/v1/projects/", "alert_status_changed"),
    ("POST", "/api/v1/documents/", "version_diff"),
]


def get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente considerando proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware que añade headers de timing y captura IP/user-agent
    para ser usados por los endpoints en su registro de auditoría.
    Los endpoints que necesitan registrar auditoría obtienen estos valores
    mediante request.state.audit_ip y request.state.audit_ua.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Inyectar datos de auditoría en el estado de la request
        request.state.audit_ip = get_client_ip(request)
        request.state.audit_ua = request.headers.get("User-Agent", "")[:500]
        request.state.request_start = time.time()

        response = await call_next(request)

        # Añadir header de latencia para observabilidad
        elapsed_ms = int((time.time() - request.state.request_start) * 1000)
        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)

        return response
