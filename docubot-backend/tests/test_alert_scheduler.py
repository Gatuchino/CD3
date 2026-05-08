"""
DocuBot — Tests unitarios del job de alertas programadas.
Verifica: lógica de severity windows, escalación, deduplicación,
y detección de documentos con error de procesamiento.
"""
import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4

from app.workers.alert_scheduler import (
    run_alert_job,
    ALERT_WINDOWS,
)


# ── Helpers para construir mocks de ORM ──────────────────────────────
def make_project(tenant_id=None, project_id=None):
    p = MagicMock()
    p.id = project_id or str(uuid4())
    p.tenant_id = tenant_id or str(uuid4())
    p.name = "Proyecto Test EPC"
    p.status = "active"
    return p


def make_deadline(project_id=None, due_date=None, title="Entrega de informe"):
    d = MagicMock()
    d.id = str(uuid4())
    d.project_id = project_id or str(uuid4())
    d.title = title
    d.due_date = due_date or date.today() + timedelta(days=5)
    d.obligation_id = None
    d.document_version_id = str(uuid4())
    return d


def make_alert(severity="high", status="open", due_date=None):
    a = MagicMock()
    a.id = str(uuid4())
    a.severity = severity
    a.status = status
    a.due_date = due_date or date.today() - timedelta(days=2)
    return a


# ── Tests de ALERT_WINDOWS ────────────────────────────────────────────
class TestAlertWindows:
    def test_critical_window_is_shortest(self):
        assert ALERT_WINDOWS["critical"] < ALERT_WINDOWS["high"]
        assert ALERT_WINDOWS["high"] < ALERT_WINDOWS["medium"]

    def test_critical_is_7_days(self):
        assert ALERT_WINDOWS["critical"] == 7

    def test_medium_is_30_days(self):
        assert ALERT_WINDOWS["medium"] == 30

    def test_all_severities_present(self):
        assert set(ALERT_WINDOWS.keys()) == {"critical", "high", "medium"}


# ── Tests de lógica de severidad ──────────────────────────────────────
class TestSeverityAssignment:
    """Verifica que la severidad se asigna correctamente según días restantes."""

    def _days_to_severity(self, days_remaining: int) -> str:
        """Reproduce la lógica del scheduler sin llamar a la BD."""
        if days_remaining <= ALERT_WINDOWS["critical"]:
            return "critical"
        elif days_remaining <= ALERT_WINDOWS["high"]:
            return "high"
        elif days_remaining <= ALERT_WINDOWS["medium"]:
            return "medium"
        return "info"

    def test_overdue_is_critical(self):
        assert self._days_to_severity(-1) == "critical"
        assert self._days_to_severity(0) == "critical"

    def test_within_7_days_is_critical(self):
        for d in range(1, 8):
            assert self._days_to_severity(d) == "critical", f"día {d} debería ser critical"

    def test_8_to_14_days_is_high(self):
        for d in range(8, 15):
            assert self._days_to_severity(d) == "high", f"día {d} debería ser high"

    def test_15_to_30_days_is_medium(self):
        for d in range(15, 31):
            assert self._days_to_severity(d) == "medium", f"día {d} debería ser medium"

    def test_beyond_30_days_is_info(self):
        assert self._days_to_severity(31) == "info"
        assert self._days_to_severity(90) == "info"


# ── Tests del job completo (integración mockeada) ─────────────────────
class TestRunAlertJob:

    @pytest.mark.asyncio
    async def test_returns_stats_dict(self):
        """run_alert_job debe retornar un dict con las claves de estadísticas."""
        with patch("app.workers.alert_scheduler.AsyncSessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Sin proyectos activos
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            stats = await run_alert_job()

        assert "alerts_created" in stats
        assert "alerts_escalated" in stats
        assert "projects_checked" in stats
        assert "errors" in stats
        assert isinstance(stats["errors"], list)

    @pytest.mark.asyncio
    async def test_zero_projects_produces_zero_alerts(self):
        with patch("app.workers.alert_scheduler.AsyncSessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            stats = await run_alert_job()

        assert stats["projects_checked"] == 0
        assert stats["alerts_created"] == 0

    @pytest.mark.asyncio
    async def test_db_error_is_captured_in_stats(self):
        """Un error de BD no debe propagar excepción, debe quedar en stats['errors']."""
        with patch("app.workers.alert_scheduler.AsyncSessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_db.execute = AsyncMock(side_effect=Exception("DB connection refused"))

            stats = await run_alert_job()

        # No debe lanzar excepción — el error va en stats
        assert len(stats["errors"]) > 0
        assert "DB connection refused" in str(stats["errors"])
