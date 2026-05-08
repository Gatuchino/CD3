"""
DocuBot — Middleware de cabeceras de seguridad HTTP.
Añade headers estándar OWASP: CSP, HSTS, X-Frame-Options, etc.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


SECURITY_HEADERS = {
    # Evitar clickjacking
    "X-Frame-Options": "DENY",
    # Deshabilitar detección de MIME sniffing
    "X-Content-Type-Options": "nosniff",
    # XSS protection legacy browsers
    "X-XSS-Protection": "1; mode=block",
    # HSTS: forzar HTTPS por 1 año
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Referrer policy
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Permissions policy: deshabilitar features innecesarias
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    # CSP: permitir solo recursos propios + Azure OpenAI
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' https://*.openai.azure.com https://*.blob.core.windows.net; "
        "frame-ancestors 'none';"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inyecta cabeceras de seguridad HTTP estándar en todas las respuestas."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
