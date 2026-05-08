/**
 * DocuBot — Página de Auditoría y Trazabilidad.
 * Visualiza el log completo de acciones del sistema con filtros avanzados.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi } from "../services/api";

// ── Tipos ────────────────────────────────────────────────────────
interface AuditLogEntry {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  user_id: string | null;
  details: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

interface RagEntry {
  id: string;
  question: string;
  answer: string;
  confidence: number;
  requires_human_review: boolean;
  latency_ms: number;
  created_at: string;
}

// ── Helpers ──────────────────────────────────────────────────────
const ACTION_LABELS: Record<string, string> = {
  document_uploaded: "Carga de documento",
  document_processed: "Procesamiento completado",
  document_classified: "Clasificación",
  obligations_extracted: "Extracción de obligaciones",
  rag_query: "Consulta RAG",
  version_diff: "Diff semántico",
  alert_status_changed: "Estado de alerta",
  classification_confirmed: "Clasificación confirmada",
  version_promoted: "Versión promovida",
  project_created: "Proyecto creado",
  project_status_changed: "Estado de proyecto",
};

const ACTION_COLORS: Record<string, string> = {
  rag_query: "bg-blue-50 text-blue-700 border-blue-200",
  document_processed: "bg-green-50 text-green-700 border-green-200",
  document_uploaded: "bg-indigo-50 text-indigo-700 border-indigo-200",
  version_diff: "bg-purple-50 text-purple-700 border-purple-200",
  obligations_extracted: "bg-orange-50 text-orange-700 border-orange-200",
  alert_status_changed: "bg-yellow-50 text-yellow-700 border-yellow-200",
  project_created: "bg-teal-50 text-teal-700 border-teal-200",
};

function formatDate(iso: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── Componente principal ──────────────────────────────────────────
export default function AuditTrail() {
  const [activeTab, setActiveTab] = useState<"logs" | "rag" | "summary">("logs");
  const [filterAction, setFilterAction] = useState("");
  const [filterDays, setFilterDays] = useState("30");
  const [logOffset, setLogOffset] = useState(0);
  const [ragOffset, setRagOffset] = useState(0);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const LIMIT = 25;

  // Logs de auditoría
  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["audit-logs", filterAction, logOffset],
    queryFn: () =>
      auditApi
        .getLogs({
          action: filterAction || undefined,
          limit: LIMIT,
          offset: logOffset,
        })
        .then((r) => r.data),
  });

  // Resumen estadístico
  const { data: summaryData } = useQuery({
    queryKey: ["audit-summary", filterDays],
    queryFn: () => auditApi.getSummary(Number(filterDays)).then((r) => r.data),
    enabled: activeTab === "summary",
  });

  // Historial RAG
  const { data: ragData, isLoading: ragLoading } = useQuery({
    queryKey: ["rag-history", ragOffset],
    queryFn: () =>
      auditApi.getRagHistory({ limit: LIMIT, offset: ragOffset }).then((r) => r.data),
    enabled: activeTab === "rag",
  });

  const logs: AuditLogEntry[] = logsData?.logs ?? [];
  const logsTotal: number = logsData?.total ?? 0;
  const ragQueries: RagEntry[] = ragData?.queries ?? [];
  const ragTotal: number = ragData?.total ?? 0;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Auditoría y Trazabilidad</h1>
        <p className="text-sm text-gray-500 mt-1">
          Registro completo de todas las acciones del sistema con trazabilidad por usuario.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {[
          { key: "logs", label: "Log de Auditoría" },
          { key: "rag", label: "Historial RAG" },
          { key: "summary", label: "Resumen de Actividad" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Logs ─────────────────────────────────────── */}
      {activeTab === "logs" && (
        <div className="space-y-4">
          {/* Filtros */}
          <div className="flex gap-3 flex-wrap">
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={filterAction}
              onChange={(e) => { setFilterAction(e.target.value); setLogOffset(0); }}
            >
              <option value="">Todas las acciones</option>
              {Object.entries(ACTION_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <span className="text-sm text-gray-500 self-center">
              {logsTotal.toLocaleString()} eventos totales
            </span>
          </div>

          {/* Tabla */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Acción</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Entidad</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Usuario</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">IP</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Fecha</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {logsLoading && (
                    <tr><td colSpan={6} className="text-center py-8 text-gray-400">Cargando…</td></tr>
                  )}
                  {!logsLoading && logs.length === 0 && (
                    <tr><td colSpan={6} className="text-center py-8 text-gray-400">Sin registros para los filtros seleccionados.</td></tr>
                  )}
                  {logs.map((log) => (
                    <>
                      <tr
                        key={log.id}
                        className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                        onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
                      >
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded border ${ACTION_COLORS[log.action] ?? "bg-gray-100 text-gray-700 border-gray-200"}`}>
                            {ACTION_LABELS[log.action] ?? log.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {log.entity_type ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                          {log.user_id ? log.user_id.slice(0, 8) + "…" : "sistema"}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs">{log.ip_address ?? "—"}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                          {formatDate(log.created_at)}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs">
                          {expandedLog === log.id ? "▲" : "▼"}
                        </td>
                      </tr>
                      {expandedLog === log.id && (
                        <tr key={log.id + "-detail"} className="bg-gray-50">
                          <td colSpan={6} className="px-4 py-3">
                            <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-white border border-gray-200 rounded p-3 max-h-48 overflow-auto">
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Paginación */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <span className="text-xs text-gray-500">
                {logOffset + 1}–{Math.min(logOffset + LIMIT, logsTotal)} de {logsTotal}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setLogOffset(Math.max(0, logOffset - LIMIT))}
                  disabled={logOffset === 0}
                  className="px-3 py-1 text-xs border border-gray-300 rounded disabled:opacity-50 hover:bg-gray-50"
                >Anterior</button>
                <button
                  onClick={() => setLogOffset(logOffset + LIMIT)}
                  disabled={logOffset + LIMIT >= logsTotal}
                  className="px-3 py-1 text-xs border border-gray-300 rounded disabled:opacity-50 hover:bg-gray-50"
                >Siguiente</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: RAG History ──────────────────────────────── */}
      {activeTab === "rag" && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">{ragTotal} consultas registradas</p>
          {ragLoading && <p className="text-sm text-gray-400">Cargando…</p>}
          {ragQueries.map((q) => (
            <div key={q.id} className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">{q.question}</p>
                  {q.answer && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{q.answer}</p>
                  )}
                </div>
                <div className="text-right shrink-0 space-y-1">
                  <div className="text-xs text-gray-500">
                    Confianza: <span className={`font-bold ${q.confidence >= 0.7 ? "text-green-600" : "text-yellow-600"}`}>
                      {(q.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="text-xs text-gray-400">{q.latency_ms}ms</div>
                  {q.requires_human_review && (
                    <span className="text-xs bg-yellow-50 text-yellow-700 border border-yellow-200 px-1.5 py-0.5 rounded">
                      Revisión humana
                    </span>
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-2">{formatDate(q.created_at)}</p>
            </div>
          ))}
          {/* Paginación */}
          <div className="flex gap-2">
            <button
              onClick={() => setRagOffset(Math.max(0, ragOffset - LIMIT))}
              disabled={ragOffset === 0}
              className="px-3 py-1 text-xs border border-gray-300 rounded disabled:opacity-50"
            >Anterior</button>
            <button
              onClick={() => setRagOffset(ragOffset + LIMIT)}
              disabled={ragOffset + LIMIT >= ragTotal}
              className="px-3 py-1 text-xs border border-gray-300 rounded disabled:opacity-50"
            >Siguiente</button>
          </div>
        </div>
      )}

      {/* ── Tab: Summary ──────────────────────────────────── */}
      {activeTab === "summary" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-700">Período:</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={filterDays}
              onChange={(e) => setFilterDays(e.target.value)}
            >
              <option value="7">Últimos 7 días</option>
              <option value="30">Últimos 30 días</option>
              <option value="90">Últimos 90 días</option>
              <option value="365">Último año</option>
            </select>
          </div>

          {summaryData && (
            <>
              {/* KPIs RAG */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { label: "Consultas RAG", value: summaryData.rag_stats.total_queries, suffix: "" },
                  { label: "Latencia promedio", value: summaryData.rag_stats.avg_latency_ms, suffix: "ms" },
                  { label: "Confianza promedio", value: (summaryData.rag_stats.avg_confidence * 100).toFixed(0), suffix: "%" },
                ].map((kpi) => (
                  <div key={kpi.label} className="bg-white border border-gray-200 rounded-xl p-4 text-center">
                    <span className="block text-2xl font-bold text-gray-900">{kpi.value}{kpi.suffix}</span>
                    <span className="text-xs text-gray-500">{kpi.label}</span>
                  </div>
                ))}
              </div>

              {/* Desglose por acción */}
              <div className="bg-white border border-gray-200 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Desglose de actividad — {summaryData.total_events.toLocaleString()} eventos
                </h3>
                <div className="space-y-2">
                  {summaryData.actions_breakdown.map((row: any) => {
                    const pct = summaryData.total_events > 0
                      ? Math.round((row.count / summaryData.total_events) * 100)
                      : 0;
                    return (
                      <div key={row.action} className="flex items-center gap-3">
                        <span className="text-xs text-gray-600 w-44 truncate">
                          {ACTION_LABELS[row.action] ?? row.action}
                        </span>
                        <div className="flex-1 bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-gray-700 w-12 text-right">
                          {row.count.toLocaleString()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
