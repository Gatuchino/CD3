"""
DocuBot — Pruebas de carga con Locust.
Simula carga realista de usuarios concurrentes en los endpoints críticos.

Uso:
    locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5

Escenarios:
    - DocubotReaderUser: simula usuario lectura (consultas RAG, listados)
    - DocubotUploaderUser: simula subida de documentos
    - DocubotAdminUser: simula admin consultando métricas y auditoría
"""
import json
import random
import string
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask


# ── Constantes de prueba ────────────────────────────────────────────────
DEMO_PROJECT_ID = "550e8400-e29b-41d4-a716-446655440000"
DEMO_VERSION_ID = "550e8400-e29b-41d4-a716-446655440001"
DEMO_DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440002"

# Preguntas RAG variadas para simular uso real
RAG_QUESTIONS = [
    "¿Cuál es el plazo de garantía establecido en el contrato?",
    "¿Qué multas se aplican por retraso en la entrega?",
    "¿Cuáles son las condiciones de pago contempladas?",
    "¿Qué obligaciones tiene el contratista respecto a seguridad?",
    "¿Cuál es el alcance del trabajo definido en las especificaciones técnicas?",
    "¿Existe cláusula de fuerza mayor y cuáles son sus condiciones?",
    "¿Qué documentos son necesarios para la recepción provisional?",
    "¿Cuáles son los seguros requeridos por el contrato?",
    "¿Qué condiciones aplican para la resolución anticipada del contrato?",
    "¿Cuál es el procedimiento para gestionar cambios en el alcance?",
    "¿Qué garantías financieras se exigen?",
    "¿Cuáles son los hitos de pago y porcentajes asociados?",
]

# Headers JWT simulados (en pruebas reales usar token válido)
AUTH_HEADERS = {
    "Authorization": "Bearer TEST_TOKEN_LOCUST",
    "Content-Type": "application/json",
    "X-Tenant-ID": "test-tenant-locust",
}


def random_string(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


# ── Usuario lector (principal carga de producción) ──────────────────────

class DocubotReaderUser(HttpUser):
    """
    Simula un usuario que consulta documentos y realiza búsquedas RAG.
    Weight=3 → 3 lectores por cada uploader.
    """
    weight = 3
    wait_time = between(2, 8)  # Segundos entre requests

    def on_start(self):
        """Setup inicial del usuario."""
        self.project_id = DEMO_PROJECT_ID
        self.version_id = DEMO_VERSION_ID
        self.document_id = DEMO_DOCUMENT_ID

    @task(5)
    def rag_query(self):
        """Consulta RAG — tarea más frecuente."""
        question = random.choice(RAG_QUESTIONS)
        payload = {
            "project_id": self.project_id,
            "question": question,
            "top_k": 8,
        }
        with self.client.post(
            "/api/v1/rag/query",
            json=payload,
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/rag/query",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "answer" not in data:
                    resp.failure("Response missing 'answer' field")
                elif data.get("confidence", 0) < 0:
                    resp.failure("Negative confidence score")
                else:
                    resp.success()
            elif resp.status_code == 429:
                resp.success()  # Rate limit es comportamiento esperado bajo carga
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(3)
    def list_documents(self):
        """Listar documentos del proyecto."""
        with self.client.get(
            f"/api/v1/projects/{self.project_id}/documents",
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/projects/{id}/documents",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(2)
    def list_projects(self):
        """Listar proyectos del tenant."""
        with self.client.get(
            "/api/v1/projects",
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/projects",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(2)
    def list_rag_history(self):
        """Consultar historial RAG."""
        with self.client.get(
            "/api/v1/audit/rag-history",
            params={"limit": 20},
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/audit/rag-history",
        ) as resp:
            if resp.status_code in (200, 403):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def get_audit_logs(self):
        """Consultar logs de auditoría."""
        with self.client.get(
            "/api/v1/audit/logs",
            params={"limit": 25, "offset": 0},
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/audit/logs",
        ) as resp:
            if resp.status_code in (200, 403):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def get_document_versions(self):
        """Obtener versiones de un documento."""
        with self.client.get(
            f"/api/v1/documents/{self.document_id}/versions",
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/documents/{id}/versions",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def health_check(self):
        """Health check — simula monitoreo externo."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") != "healthy":
                    resp.failure("Service not healthy")
                else:
                    resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")


# ── Usuario uploader (carga de documentos) ──────────────────────────────

class DocubotUploaderUser(HttpUser):
    """
    Simula un document controller cargando documentos al sistema.
    Weight=1 → menos frecuente que lectores.
    """
    weight = 1
    wait_time = between(10, 30)  # Subidas menos frecuentes

    def on_start(self):
        self.project_id = DEMO_PROJECT_ID

    @task(1)
    def upload_document(self):
        """Subida de documento PDF."""
        filename = f"contrato_{random_string(6)}.pdf"
        # PDF mínimo válido (3 bytes de contenido fake para prueba)
        fake_pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"

        with self.client.post(
            f"/api/v1/projects/{self.project_id}/documents/upload",
            files={"file": (filename, fake_pdf_content, "application/pdf")},
            data={
                "document_type": random.choice(["contract", "addendum", "specification"]),
                "revision_number": f"Rev.{random.randint(0, 5)}",
            },
            headers={"Authorization": AUTH_HEADERS["Authorization"]},
            catch_response=True,
            name="/api/v1/projects/{id}/documents/upload",
        ) as resp:
            if resp.status_code in (200, 201, 409, 429):
                # 409=duplicado es válido, 429=rate limit es válido
                resp.success()
            else:
                resp.failure(f"Upload failed: {resp.status_code}")


# ── Usuario admin (métricas y auditoría) ───────────────────────────────

class DocubotAdminUser(HttpUser):
    """
    Simula un admin consultando métricas y resúmenes ejecutivos.
    Weight=1 → muy poco frecuente.
    """
    weight = 1
    wait_time = between(15, 45)

    @task(2)
    def get_metrics_today(self):
        """Consultar costos del día."""
        with self.client.get(
            "/api/v1/metrics/costs/today",
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/metrics/costs/today",
        ) as resp:
            if resp.status_code in (200, 403):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def get_audit_summary(self):
        """Resumen de auditoría."""
        with self.client.get(
            "/api/v1/audit/logs/summary",
            params={"days": 30},
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/audit/logs/summary",
        ) as resp:
            if resp.status_code in (200, 403):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")

    @task(1)
    def get_rag_performance(self):
        """Métricas de performance RAG."""
        with self.client.get(
            "/api/v1/metrics/performance/rag",
            params={"days": 7},
            headers=AUTH_HEADERS,
            catch_response=True,
            name="/api/v1/metrics/performance/rag",
        ) as resp:
            if resp.status_code in (200, 403):
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")


# ── Listeners de eventos para reporte personalizado ─────────────────────

@events.request.add_listener
def on_request(request_type, name, response_time, response_length,
               response, context, exception, **kwargs):
    """Listener para métricas adicionales — detecta SLA violations."""
    SLA_LIMITS = {
        "/api/v1/rag/query": 15000,       # 15s para RAG
        "/api/v1/projects/{id}/documents/upload": 5000,  # 5s para upload
        "default": 3000,                   # 3s para el resto
    }
    limit = SLA_LIMITS.get(name, SLA_LIMITS["default"])
    if response_time > limit and exception is None:
        print(f"⚠ SLA VIOLATION: {name} took {response_time:.0f}ms (limit: {limit}ms)")
