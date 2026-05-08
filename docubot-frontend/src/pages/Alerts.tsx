/**
 * DocuBot — Panel de alertas de vencimiento y obligaciones críticas.
 */
import { useState } from "react";
import { Bell, AlertTriangle, CheckCircle2, Clock, ChevronDown, Filter } from "lucide-react";
import { useAlerts, useUpdateAlertStatus } from "../hooks/useAlerts";
import type { Alert } from "../types";

const SEVERITY_CONFIG = {
  critical: { label: "Crítica",  cls: "badge-red",   dot: "bg-red-500" },
  high:     { label: "Alta",     cls: "badge-amber",  dot: "bg-amber-500" },
  medium:   { label: "Media",    cls: "badge-blue",   dot: "bg-blue-500" },
  low:      { label: "Baja",     cls: "badge-gray",   dot: "bg-gray-400" },
};

const STATUS_CONFIG = {
  open:         { label: "Abierta",      cls: "badge-amber" },
  acknowledged: { label: "Reconocida",   cls: "badge-blue" },
  resolved:     { label: "Resuelta",     cls: "badge-green" },
  dismissed:    { label: "Descartada",   cls: "badge-gray" },
};

function AlertRow({ alert, projectId }: { alert: Alert; projectId: string }) {
  const updateStatus = useUpdateAlertStatus(projectId);
  const sev = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.low;
  const sta = STATUS_CONFIG[alert.status] ?? STATUS_CONFIG.open;

  const dueDays = alert.due_date
    ? Math.ceil((new Date(alert.due_date).getTime() - Date.now()) / 86_400_000)
    : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className={`mt-1 w-2.5 h-2.5 rounded-full flex-shrink-0 ${sev.dot}`} />
          <div className="min-w-0">
            <p className="font-medium text-gray-900 text-sm leading-snug">{alert.title}</p>
            {alert.description && (
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">{alert.description}</p>
            )}
            {alert.document_title && (
              <p className="text-xs text-gray-400 mt-1">Documento: {alert.document_title}</p>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <span className={`badge ${sev.cls}`}>{sev.label}</span>
          <span className={`badge ${sta.cls}`}>{sta.label}</span>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="w-3.5 h-3.5" />
          {alert.due_date ? (
            <span className={dueDays !== null && dueDays <= 7 ? "text-red-600 font-medium" : ""}>
              {dueDays !== null && dueDays < 0
                ? `Vencida hace ${Math.abs(dueDays)} días`
                : dueDays === 0
                ? "Vence hoy"
                : dueDays !== null
                ? `Vence en ${dueDays} días`
                : alert.due_date}
            </span>
          ) : (
            <span>Sin fecha</span>
          )}
        </div>

        {alert.status === "open" && (
          <div className="flex gap-2">
            <button
              onClick={() => updateStatus.mutate({ alertId: alert.id, newStatus: "acknowledged" })}
              disabled={updateStatus.isPending}
              className="text-xs px-2.5 py-1 border border-blue-200 text-blue-600 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"
            >
              Reconocer
            </button>
            <button
              onClick={() => updateStatus.mutate({ alertId: alert.id, newStatus: "resolved" })}
              disabled={updateStatus.isPending}
              className="text-xs px-2.5 py-1 border border-green-200 text-green-600 rounded-lg hover:bg-green-50 transition-colors disabled:opacity-50"
            >
              Resolver
            </button>
          </div>
        )}
        {alert.status === "acknowledged" && (
          <button
            onClick={() => updateStatus.mutate({ alertId: alert.id, newStatus: "resolved" })}
            disabled={updateStatus.isPending}
            className="text-xs px-2.5 py-1 border border-green-200 text-green-600 rounded-lg hover:bg-green-50 transition-colors disabled:opacity-50"
          >
            Marcar resuelta
          </button>
        )}
      </div>
    </div>
  );
}

interface AlertsProps {
  projectId: string;
}

export default function Alerts({ projectId }: AlertsProps) {
  const [statusFilter, setStatusFilter] = useState<string>("open");
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const { data: alerts = [], isLoading, isError } = useAlerts(projectId, {
    status: statusFilter || undefined,
    severity: severityFilter || undefined,
  });

  const counts = {
    open:     alerts.filter((a) => a.status === "open").length,
    critical: alerts.filter((a) => a.severity === "critical").length,
    high:     alerts.filter((a) => a.severity === "high").length,
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <Bell className="w-5 h-5 text-amber-500" /> Alertas y vencimientos
        </h2>
        <p className="text-gray-500 text-sm mt-1">
          Alertas generadas automáticamente a partir de plazos contractuales detectados por IA.
        </p>
      </div>

      {/* KPIs rápidos */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-xs text-amber-600 font-medium">Alertas abiertas</p>
          <p className="text-3xl font-bold text-amber-700 mt-1">{counts.open}</p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-xs text-red-600 font-medium">Críticas</p>
          <p className="text-3xl font-bold text-red-700 mt-1">{counts.critical}</p>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <p className="text-xs text-orange-600 font-medium">Alta prioridad</p>
          <p className="text-3xl font-bold text-orange-700 mt-1">{counts.high}</p>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap gap-3 items-center">
        <Filter className="w-4 h-4 text-gray-400" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todos los estados</option>
          <option value="open">Abiertas</option>
          <option value="acknowledged">Reconocidas</option>
          <option value="resolved">Resueltas</option>
          <option value="dismissed">Descartadas</option>
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todas las severidades</option>
          <option value="critical">Crítica</option>
          <option value="high">Alta</option>
          <option value="medium">Media</option>
          <option value="low">Baja</option>
        </select>
      </div>

      {/* Lista */}
      {isLoading ? (
        <div className="space-y-3">
          {[1,2,3].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
              <div className="h-3 bg-gray-100 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          Error al cargar alertas.
        </div>
      ) : alerts.length === 0 ? (
        <div className="bg-gray-50 border border-dashed border-gray-300 rounded-xl p-12 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-400 mx-auto mb-3" />
          <p className="text-gray-600 font-medium">Sin alertas {statusFilter ? "con este estado" : ""}</p>
          <p className="text-gray-400 text-sm mt-1">
            Las alertas se generan automáticamente al procesar documentos.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} projectId={projectId} />
          ))}
        </div>
      )}
    </div>
  );
}
