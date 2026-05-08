"""
DocuBot — Endpoints internos (no expuestos al público).
Usados por Azure Function Timer o cron jobs para tareas programadas.
Protegidos por API key interna.
"""
import os
from fastapi import APIRouter, HTTPException, Header
from app.workers.alert_scheduler import run_alert_job

router = APIRouter(prefix="/api/v1/internal", tags=["Internal"])

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _verify_internal_key(x_internal_key: str = Header(...)):
    if not INTERNAL_API_KEY or x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Acceso denegado.")


@router.post("/run-alert-job")
async def trigger_alert_job(x_internal_key: str = Header(...)):
    """
    Ejecuta el job de alertas programadas manualmente.
    Requiere header X-Internal-Key con el valor de INTERNAL_API_KEY.
    """
    _verify_internal_key(x_internal_key)
    result = await run_alert_job()
    return {"status": "ok", "result": result}


@router.get("/health-internal")
async def internal_health():
    """Health check simple para Azure Function."""
    return {"status": "ok", "service": "docubot-backend"}
