/**
 * DocuBot — Panel de Métricas y Observabilidad.
 * Costos IA diarios, performance RAG y health del sistema.
 * Solo visible para admin_tenant.
 */
import { useQuery } from "@tanstack/react-query";
import { metricsApi } from "../services/api";

// ── Helpers ──────────────────────────────────────────────────
function formatUSD(n: number) {
  return `$${n.toFixed(4)}`;
}

function BudgetBar({ usedPct }: { usedPct: number }) {
  const color =
    usedPct >= 100
      ? "bg-red-500"
      : usedPct >= 80
      ? "bg-orange-400"
      : "bg-green-500";
  return (
    <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
      <div
        className={`${color} h-3 rounded-full transition-all`}
        style={{ width: `${Math.min(usedPct, 100)}%` }}
      />
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase font-semibold tracking-wide mb-1">
        {label}
      </p>
      <p className={`text-2xl font-bold ${accent ?? "text-gray-900"}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────
export default function MetricsDashboard() {
  const { data: todayData } = useQuery({
    queryKey: ["metrics-today"],
    queryFn: () => metricsApi.getTodayCosts().then((r) => r.data),
    refetchInterval: 60_000,
  });

  const { data: historyData } = useQuery({
    queryKey: ["metrics-history-30"],
    queryFn: () => metricsApi.getCostsHistory(30).then((r) => r.data),
  });

  const { data: perfData } = useQuery({
    queryKey: ["metrics-rag-perf-7"],
    queryFn: () => metricsApi.getRagPerformance(7).then((r) => r.data),
  });

  const { data: healthData } = useQuery({
    queryKey: ["metrics-health"],
    queryFn: () => metricsApi.getDetailedHealth().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const budgetPct = todayData?.budget_used_pct ?? 0;
  const budgetColor =
    budgetPct >= 100 ? "text-red-600" : budgetPct >= 80 ? "text-orange-500" : "text-green-600";

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Métricas y Observabilidad</h1>
        <p className="text-sm text-gray-500 mt-1">
          Costos de IA, performance del motor RAG y salud del sistema en tiempo real.
        </p>
      </div>

      {/* ── Health Badge ──────────────────────────────── */}
      {healthData && (
        <div
          className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium ${
            healthData.status === "healthy"
              ? "bg-green-50 border-green-200 text-green-700"
              : "bg-red-50 border-red-200 text-red-700"
          }`}
        >
          <span className={`w-2.5 h-2.5 rounded-full ${healthData.status === "healthy" ? "bg-green-500" : "bg-red-500"}`} />
          Sistema {healthData.status === "healthy" ? "operativo" : "con problemas"} —
          DB: {healthData.database} —
          Últimas 24h: {healthData.last_24h?.audit_events ?? 0} eventos, {healthData.last_24h?.rag_queries ?? 0} consultas RAG
        </div>
      )}

      {/* ── Costos hoy ───────────────────────────────── */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Costos IA — Hoy ({todayData?.date ?? "—"})
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            label="Costo del día"
            value={formatUSD(todayData?.total_cost_usd ?? 0)}
            sub={`Presupuesto: $${todayData?.budget_usd ?? 50}`}
            accent={budgetColor}
          />
          <KpiCard
            label="Llamadas IA"
            value={todayData?.calls_count ?? 0}
            sub="operaciones totales"
          />
          <KpiCard
            label="Tokens consumidos"
            value={(todayData?.total_tokens ?? 0).toLocaleString()}
            sub="estimado del día"
          />
          <KpiCard
            label="% Presupuesto usado"
            value={`${budgetPct}%`}
            accent={budgetColor}
          />
        </div>
        <BudgetBar usedPct={budgetPct} />
        <p className="text-xs text-gray-400">
          Presupuesto diario: ${todayData?.budget_usd ?? 50} USD. Se reinicia a las 00:00 UTC.
        </p>
      </section>

      {/* ── Performance RAG ──────────────────────────── */}
      {perfData && perfData.total_queries > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Performance RAG — Últimos 7 días
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard
              label="Consultas totales"
              value={perfData.total_queries}
            />
            <KpiCard
              label="Latencia P50"
              value={`${perfData.latency_ms?.p50 ?? 0}ms`}
              sub={`P90: ${perfData.latency_ms?.p90 ?? 0}ms`}
            />
            <KpiCard
              label="Confianza promedio"
              value={`${((perfData.confidence?.avg ?? 0) * 100).toFixed(0)}%`}
              accent={
                perfData.confidence?.avg >= 0.75 ? "text-green-600" : "text-orange-500"
              }
            />
            <KpiCard
              label="Revisión humana requerida"
              value={`${perfData.human_review_rate_pct ?? 0}%`}
              sub={`${perfData.human_review_count ?? 0} consultas`}
              accent={
                (perfData.human_review_rate_pct ?? 0) > 30 ? "text-orange-500" : "text-gray-900"
              }
            />
          </div>

          {/* Distribución de confianza */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              Distribución de confianza RAG
            </h3>
            <div className="space-y-3">
              {[
                { label: "Alta (≥80%)", key: "high_0.8_1.0", color: "bg-green-500" },
                { label: "Media (60–80%)", key: "medium_0.6_0.8", color: "bg-yellow-400" },
                { label: "Baja (<60%)", key: "low_below_0.6", color: "bg-red-400" },
              ].map(({ label, key, color }) => {
                const count = perfData.confidence?.distribution?.[key] ?? 0;
                const pct = perfData.total_queries > 0
                  ? Math.round((count / perfData.total_queries) * 100)
                  : 0;
                return (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-xs text-gray-600 w-36">{label}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-2">
                      <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs font-medium text-gray-700 w-16 text-right">
                      {count} ({pct}%)
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ── Historial de costos 30 días ───────────────── */}
      {historyData && historyData.daily_breakdown?.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Historial de costos — 30 días
            <span className="ml-2 text-gray-400 normal-case font-normal">
              Total: {formatUSD(historyData.total_estimated_cost_usd)} •{" "}
              {historyData.total_queries} consultas
            </span>
          </h2>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Fecha</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Consultas</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Latencia avg</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Confianza avg</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Tokens est.</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Costo est.</th>
                  </tr>
                </thead>
                <tbody>
                  {historyData.daily_breakdown.slice(0, 15).map((row: any) => (
                    <tr key={row.day} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2.5 text-gray-700 text-xs font-mono">{row.day}</td>
                      <td className="px-4 py-2.5 text-right text-gray-600">{row.queries}</td>
                      <td className="px-4 py-2.5 text-right text-gray-500 text-xs">{row.avg_latency_ms}ms</td>
                      <td className="px-4 py-2.5 text-right">
                        <span className={`text-xs font-medium ${
                          row.avg_confidence >= 0.75 ? "text-green-600" : "text-orange-500"
                        }`}>
                          {(row.avg_confidence * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-500 text-xs">
                        {row.estimated_tokens.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-700 text-xs font-medium">
                        {formatUSD(row.estimated_cost_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="text-xs text-gray-400">
            * Costos estimados basados en precios Azure OpenAI GPT-4o ($2.50/1M input, $10/1M output).
          </p>
        </section>
      )}

      {/* ── Tarifas de modelos ────────────────────────── */}
      {historyData?.model_rates && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Tarifas de modelos configuradas (USD / 1K tokens)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(historyData.model_rates).map(([model, rates]: [string, any]) => (
              <div key={model} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                <p className="text-xs font-mono font-semibold text-gray-700 truncate">{model}</p>
                <p className="text-xs text-gray-500 mt-1">
                  In: ${rates.input} / Out: ${rates.output}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
