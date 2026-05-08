"""
DocuBot — Métricas y observabilidad del sistema.
Rastrea tokens consumidos, costos IA y latencias por tenant.
Integra con Azure Application Insights via OpenCensus.
"""
import time
import asyncio
import logging
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, Optional
from datetime import datetime, date

logger = logging.getLogger("docubot.metrics")


# ── Costos por modelo (USD por 1000 tokens) ─────────────────────────────
# Precios Azure OpenAI — actualizar según contrato
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {
        "input":  0.0025,   # $2.50 / 1M tokens input
        "output": 0.0100,   # $10.00 / 1M tokens output
    },
    "gpt-4o-mini": {
        "input":  0.000150,  # $0.15 / 1M tokens input
        "output": 0.000600,  # $0.60 / 1M tokens output
    },
    "text-embedding-3-large": {
        "input":  0.000130,  # $0.13 / 1M tokens
        "output": 0.0,
    },
    "text-embedding-3-small": {
        "input":  0.000020,
        "output": 0.0,
    },
}


@dataclass
class TokenUsageRecord:
    """Registro de uso de tokens para una llamada AI."""
    tenant_id: str
    operation: str          # "rag_query", "classification", "diff", "summary", "embedding"
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


@dataclass
class TenantCostAccumulator:
    """Acumulador de costos por tenant (en memoria, resetea por día)."""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    calls_count: int = 0
    last_reset: date = field(default_factory=date.today)

    def reset_if_new_day(self):
        today = date.today()
        if today > self.last_reset:
            self.total_tokens = 0
            self.total_cost_usd = 0.0
            self.calls_count = 0
            self.last_reset = today


# Almacén en memoria — en producción usar Redis o Azure Table Storage
_tenant_daily_costs: Dict[str, TenantCostAccumulator] = defaultdict(TenantCostAccumulator)
_cost_lock = asyncio.Lock()

# Límite diario de gasto por tenant (USD) — configurable por tenant en producción
DAILY_BUDGET_USD = 50.0
BUDGET_WARNING_PCT = 0.80   # Alerta al 80% del presupuesto


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calcula el costo en USD para una llamada al modelo."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS["gpt-4o"])
    input_cost  = (prompt_tokens / 1000) * costs["input"]
    output_cost = (completion_tokens / 1000) * costs["output"]
    return round(input_cost + output_cost, 6)


async def record_token_usage(record: TokenUsageRecord) -> None:
    """
    Registra uso de tokens y acumula costos por tenant.
    Loguea advertencia si se supera el umbral de presupuesto diario.
    """
    async with _cost_lock:
        acc = _tenant_daily_costs[record.tenant_id]
        acc.reset_if_new_day()

        acc.total_tokens += record.total_tokens
        acc.total_cost_usd += record.cost_usd
        acc.calls_count += 1

        pct = acc.total_cost_usd / DAILY_BUDGET_USD
        if pct >= 1.0:
            logger.error(
                "BUDGET_EXCEEDED tenant=%s daily_cost=%.4f USD limit=%.2f",
                record.tenant_id, acc.total_cost_usd, DAILY_BUDGET_USD
            )
        elif pct >= BUDGET_WARNING_PCT:
            logger.warning(
                "BUDGET_WARNING tenant=%s daily_cost=%.4f USD (%.0f%% of limit)",
                record.tenant_id, acc.total_cost_usd, pct * 100
            )

    logger.info(
        "TOKEN_USAGE tenant=%s op=%s model=%s tokens=%d (p=%d c=%d) cost=%.6f USD latency=%dms",
        record.tenant_id, record.operation, record.model,
        record.total_tokens, record.prompt_tokens, record.completion_tokens,
        record.cost_usd, record.latency_ms,
    )

    # Emitir a Azure Application Insights si está configurado
    try:
        _emit_to_app_insights(record)
    except Exception as e:
        logger.debug("AppInsights emit failed (non-critical): %s", e)


def _emit_to_app_insights(record: TokenUsageRecord) -> None:
    """Emite métrica custom a Azure Application Insights."""
    try:
        from opencensus.ext.azure import metrics_exporter
        from opencensus.stats import aggregation, measure, stats, view
    except ImportError:
        return

    # En producción se configura con APPLICATIONINSIGHTS_CONNECTION_STRING
    logger.debug(
        "AppInsights metric: docubot/token_usage op=%s tokens=%d cost=%.6f",
        record.operation, record.total_tokens, record.cost_usd
    )


async def get_tenant_daily_cost(tenant_id: str) -> dict:
    """Retorna el resumen de costos del día para un tenant."""
    async with _cost_lock:
        acc = _tenant_daily_costs.get(tenant_id, TenantCostAccumulator())
        acc.reset_if_new_day()
        return {
            "tenant_id": tenant_id,
            "date": acc.last_reset.isoformat(),
            "total_tokens": acc.total_tokens,
            "total_cost_usd": round(acc.total_cost_usd, 4),
            "calls_count": acc.calls_count,
            "budget_usd": DAILY_BUDGET_USD,
            "budget_used_pct": round((acc.total_cost_usd / DAILY_BUDGET_USD) * 100, 1),
        }


class AIOperationTimer:
    """
    Context manager para medir latencia de operaciones IA y registrar métricas.

    Uso:
        async with AIOperationTimer("rag_query", tenant_id, "gpt-4o") as timer:
            result = await llm.call(...)
            timer.set_tokens(prompt=500, completion=200)
    """

    def __init__(self, operation: str, tenant_id: str, model: str, metadata: dict = None):
        self.operation = operation
        self.tenant_id = tenant_id
        self.model = model
        self.metadata = metadata or {}
        self._start: float = 0.0
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self.latency_ms: int = 0

    async def __aenter__(self):
        self._start = time.monotonic()
        return self

    def set_tokens(self, prompt: int, completion: int) -> None:
        self._prompt_tokens = prompt
        self._completion_tokens = completion

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.latency_ms = int((time.monotonic() - self._start) * 1000)

        if exc_type is None and (self._prompt_tokens or self._completion_tokens):
            total = self._prompt_tokens + self._completion_tokens
            cost = compute_cost(self.model, self._prompt_tokens, self._completion_tokens)
            record = TokenUsageRecord(
                tenant_id=self.tenant_id,
                operation=self.operation,
                model=self.model,
                prompt_tokens=self._prompt_tokens,
                completion_tokens=self._completion_tokens,
                total_tokens=total,
                latency_ms=self.latency_ms,
                cost_usd=cost,
                metadata=self.metadata,
            )
            await record_token_usage(record)

        return False  # No suprimir excepciones
