"""
DocuBot — Aurenza IA — Módulo 02
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.audit_middleware import AuditMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.core.observability import ObservabilityMiddleware
from app.api.routes import projects, documents, rag, alerts, classifications, obligations, versions, summaries, audit, metrics, internal, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y shutdown de la aplicación."""
    yield


app = FastAPI(
    title="DocuBot API — Aurenza IA",
    description=(
        "Motor de gestión documental inteligente para proyectos mineros, "
        "construcción y EPC/EPCM. RAG contractual con citas exactas, "
        "clasificación automática, control de versiones y alertas."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# ── Middlewares (orden inverso a ejecución: el último añadido ejecuta primero) ──

# 1. Observabilidad (ejecuta más externo — registra toda la latencia real)
app.add_middleware(ObservabilityMiddleware)

# 2. Rate limiting (bloquea temprano — antes de procesar)
app.add_middleware(RateLimitMiddleware)

# 3. Cabeceras de seguridad HTTP
app.add_middleware(SecurityHeadersMiddleware)

# 4. Auditoría (captura IP real antes de CORS)
app.add_middleware(AuditMiddleware)

# 4. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(alerts.router)
app.include_router(classifications.router)
app.include_router(obligations.router)
app.include_router(versions.router)
app.include_router(summaries.router)
app.include_router(audit.router)
app.include_router(metrics.router)
app.include_router(internal.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint para Azure App Service."""
    return {
        "status": "healthy",
        "service": "DocuBot API",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "DocuBot API — Aurenza IA",
        "docs": "/docs",
    }
