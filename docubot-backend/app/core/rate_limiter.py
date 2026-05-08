"""
DocuBot — Rate limiting por tenant usando sliding window en memoria.
En producción reemplazar por Redis con lua scripts para atomicidad.
"""
import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Deque
from fastapi import Request, HTTPException, status


# ── Configuración de límites por endpoint ──────────────────────────────
# (requests, window_seconds)
RATE_LIMITS: Dict[str, tuple[int, int]] = {
    # RAG: costoso en tokens, límite estricto
    "/api/v1/rag/query":                          (20, 60),
    # Carga de documentos: límite por abuso de storage
    "/api/v1/documents/":                         (30, 60),
    # Extracción de obligaciones: LLM costoso
    "/api/v1/document-versions/extract":          (15, 60),
    # Diff semántico: LLM costoso
    "/api/v1/documents/diff":                     (10, 60),
    # Resúmenes ejecutivos: LLM costoso
    "/api/v1/document-versions/summary":          (15, 60),
    # Clasificación: LLM costoso
    "/api/v1/document-versions/classify":         (20, 60),
    # Auth endpoints: prevenir brute force
    "/auth/":                                     (10, 60),
    # Default: endpoints de lectura
    "default":                                    (200, 60),
}

# Almacén en memoria: tenant_id → path_prefix → deque(timestamps)
_windows: Dict[str, Dict[str, Deque[float]]] = defaultdict(lambda: defaultdict(deque))
_lock = asyncio.Lock()


def _get_limit(path: str) -> tuple[int, int]:
    """Retorna (max_requests, window_seconds) para la ruta dada."""
    for prefix, limit in RATE_LIMITS.items():
        if prefix != "default" and path.startswith(prefix):
            return limit
    return RATE_LIMITS["default"]


async def check_rate_limit(tenant_id: str, path: str) -> None:
    """
    Valida que el tenant no haya superado el rate limit para esta ruta.
    Levanta HTTP 429 si se excede el límite.
    """
    max_requests, window_seconds = _get_limit(path)
    now = time.monotonic()
    cutoff = now - window_seconds

    async with _lock:
        dq = _windows[tenant_id][path]

        # Eliminar timestamps fuera de la ventana
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= max_requests:
            oldest = dq[0]
            retry_after = int(window_seconds - (now - oldest)) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Límite de {max_requests} solicitudes por {window_seconds}s superado.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        dq.append(now)


class RateLimitMiddleware:
    """
    Middleware ASGI ligero para rate limiting.
    Sólo actúa sobre rutas /api/v1/* para no afectar health checks.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # Solo aplica a rutas de API
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Extraer tenant del header inyectado por AuditMiddleware / security
        # En este punto no tenemos el JWT decodificado, así que usamos IP como fallback
        headers = dict(scope.get("headers", []))
        tenant_id = (
            headers.get(b"x-tenant-id", b"").decode() or
            headers.get(b"x-forwarded-for", b"127.0.0.1").decode().split(",")[0].strip()
        )

        max_requests, window_seconds = _get_limit(path)
        now = time.monotonic()
        cutoff = now - window_seconds

        async with _lock:
            dq = _windows[tenant_id][path]
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) >= max_requests:
                oldest = dq[0]
                retry_after = int(window_seconds - (now - oldest)) + 1
                body = (
                    f'{{"error":"rate_limit_exceeded","retry_after_seconds":{retry_after}}}'
                ).encode()
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"retry-after", str(retry_after).encode()],
                        [b"content-length", str(len(body)).encode()],
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return

            dq.append(now)

        await self.app(scope, receive, send)
