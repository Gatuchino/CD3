"""
DocuBot — Azure Function Timer para ejecución programada del alert job.

Corre cada hora: "0 0 * * * *"
La función hace un HTTP POST al endpoint interno del backend.

Deploy:
  func azure functionapp publish docubot-alert-fn

Variables de entorno requeridas (Application Settings):
  BACKEND_URL            — URL del backend, ej: https://docubot-backend.azurecontainerapps.io
  INTERNAL_API_KEY       — Misma clave que en el backend
"""
import os
import logging
import azure.functions as func
import urllib.request
import json

app = func.FunctionApp()

BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


@app.timer_trigger(
    schedule="0 0 * * * *",   # cada hora en punto
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def alert_job_timer(timer: func.TimerRequest) -> None:
    """Dispara el job de alertas programadas una vez por hora."""
    if timer.past_due:
        logging.warning("Timer estaba atrasado — ejecutando job igualmente.")

    if not BACKEND_URL or not INTERNAL_API_KEY:
        logging.error("BACKEND_URL o INTERNAL_API_KEY no configurados.")
        return

    url = f"{BACKEND_URL}/api/v1/internal/run-alert-job"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Key": INTERNAL_API_KEY,
    }

    try:
        req = urllib.request.Request(url, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=120) as response:
            body = json.loads(response.read())
            result = body.get("result", {})
            logging.info(
                f"Alert job OK — "
                f"alertas creadas: {result.get('alerts_created', 0)}, "
                f"escaladas: {result.get('alerts_escalated', 0)}, "
                f"errores: {len(result.get('errors', []))}"
            )
    except Exception as e:
        logging.error(f"Error ejecutando alert job: {e}")
        raise
