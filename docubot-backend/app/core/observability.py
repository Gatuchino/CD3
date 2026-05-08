"""
DocuBot — Middleware de observabilidad y tracing distribuido.
Registra request metrics, errores y performance en structured logs.
Compatible con Azure Monitor / Application Insights.
"""
import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("docubot.observability")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware que añade:
    - Correlation ID en cada request (X-Correlation-ID)
    - Structured logging de entrada/salida de cada request
    - Métricas de latencia y status codes
    - Propagación de errores al log sin exponerlos al cliente
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.monotonic()

        # Correlation ID — reutilizar el del cliente si existe, o generar uno nuevo
        correlation_id = (
            request.headers.get("X-Correlation-ID") or
            request.headers.get("X-Request-ID") or
            str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        # Log de entrada
        logger.info(
            "REQUEST_IN method=%s path=%s correlation_id=%s",
            request.method, request.url.path, correlation_id,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "REQUEST_ERROR method=%s path=%s correlation_id=%s latency_ms=%d error=%s",
                request.method, request.url.path, correlation_id, elapsed_ms, str(exc),
                exc_info=True,
            )
            raise

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Log de salida con status y latencia
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "REQUEST_OUT method=%s path=%s status=%d latency_ms=%d correlation_id=%s",
            request.method, request.url.path,
            response.status_code, elapsed_ms, correlation_id,
        )

        # Añadir correlation ID a la respuesta para trazabilidad cliente
        response.headers["X-Correlation-ID"] = correlation_id

        # Alertar si latencia es alta (umbral 10s para endpoints LLM)
        LLM_PATHS = ["/rag/query", "/classify", "/extract-obligations", "/diff", "/summary"]
        is_llm_path = any(p in request.url.path for p in LLM_PATHS)
        threshold_ms = 10000 if is_llm_path else 3000

        if elapsed_ms > threshold_ms:
            logger.warning(
                "SLOW_REQUEST method=%s path=%s latency_ms=%d threshold_ms=%d correlation_id=%s",
                request.method, request.url.path,
                elapsed_ms, threshold_ms, correlation_id,
            )

        return response
