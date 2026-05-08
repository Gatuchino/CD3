/**
 * DocuBot — Página de Control de Versiones y Diff Semántico.
 * Permite comparar dos revisiones de un documento con GPT-4o
 * y visualizar los cambios semanticos detectados.
 */
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { versionsApi, documentsApi, projectsApi } from "../services/api";

// ── Tipos ────────────────────────────────────────────────────────

interface Change {
  change_type: string;
  previous_text: string;
  new_text: string;
  semantic_impact: string;
  risk_level: string;
  recommended_action: string;
  source_reference_previous?: { page?: string; paragraph?: string };
  source_reference_new?: { page?: string; paragraph?: string };
}

interface DiffResponse {
  diff_id: string;
  document_title: string;
  previous_revision: string;
  new_revision: string;
  semantic_summary: string;
  risk_level: string;
  requires_legal_review: boolean;
  alert_created: boolean;
  changes: {
    critical_changes: Change[];
    obligations_changed: Change[];
    deadlines_changed: Change[];
    commercial_impacts: Change[];
    technical_impacts: Change[];
  };
}

// ── Helpers ──────────────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-300",
  high: "bg-orange-100 text-orange-800 border-orange-300",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
  low: "bg-green-100 text-green-800 border-green-300",
};

const CHANGE_TYPE_LABELS: Record<string, string> = {
  obligation_changed: "Obligación modificada",
  deadline_changed: "Plazo modificado",
  penalty_added: "Nueva penalidad",
  penalty_removed: "Penalidad eliminada",
  responsibility_changed: "Responsable cambiado",
  scope_changed: "Alcance modificado",
  technical_changed: "Cambio técnico",
  commercial_changed: "Cambio comercial",
  risk_changed: "Riesgo modificado",
  clause_added: "Cláusula nueva",
  clause_removed: "Cláusula eliminada",
};

function RiskBadge({ level }: { level: string }) {
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded border ${RISK_COLORS[level] ?? RISK_COLORS.low}`}>
      {level.toUpperCase()}
    </span>
  );
}

function ChangeCard({ change, index }: { change: Change; index: number }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`border rounded-xl p-4 ${RISK_COLORS[change.risk_level] ?? ""} bg-opacity-30`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-gray-600">#{index + 1}</span>
            <span className="text-xs bg-white border border-gray-200 text-gray-700 px-2 py-0.5 rounded font-medium">
              {CHANGE_TYPE_LABELS[change.change_type] ?? change.change_type}
            </span>
            <RiskBadge level={change.risk_level} />
          </div>
          <p className="text-sm font-medium text-gray-800">{change.semantic_impact}</p>
          {change.recommended_action && (
            <p className="text-xs text-indigo-700 mt-1">
              <span className="font-semibold">Acción recomendada:</span> {change.recommended_action}
            </p>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-blue-600 hover:underline shrink-0"
        >
          {expanded ? "Ocultar" : "Ver textos"}
        </button>
      </div>
      {expanded && (
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-1">TEXTO ANTERIOR</p>
            <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-gray-700 whitespace-pre-wrap">
              {change.previous_text || "(no disponible)"}
            </div>
            {change.source_reference_previous?.paragraph && (
              <p className="text-xs text-gray-400 mt-1">{change.source_reference_previous.paragraph}</p>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-1">TEXTO NUEVO</p>
            <div className="bg-green-50 border border-green-200 rounded p-2 text-xs text-gray-700 whitespace-pre-wrap">
              {change.new_text || "(no disponible)"}
            </div>
            {change.source_reference_new?.paragraph && (
              <p className="text-xs text-gray-400 mt-1">{change.source_reference_new.paragraph}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────

export default function VersionDiff() {
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [prevVersionId, setPrevVersionId] = useState("");
  const [newVersionId, setNewVersionId] = useState("");
  const [diffResult, setDiffResult] = useState<DiffResponse | null>(null);
  const [activeSection, setActiveSection] = useState("critical_changes");

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
  });

  const { data: documentsData } = useQuery({
    queryKey: ["documents", selectedProjectId],
    queryFn: () => documentsApi.list(selectedProjectId).then((r) => r.data),
    enabled: !!selectedProjectId,
  });

  const { data: versionsData } = useQuery({
    queryKey: ["versions", selectedDocumentId],
    queryFn: () => versionsApi.list(selectedDocumentId).then((r) => r.data),
    enabled: !!selectedDocumentId,
  });

  const diffMutation = useMutation({
    mutationFn: () => versionsApi.diff(selectedDocumentId, prevVersionId, newVersionId),
    onSuccess: (res) => setDiffResult(res.data),
  });

  const versions: any[] = versionsData?.versions ?? [];
  const processedVersions = versions.filter((v) => v.processing_status === "processed");

  const SECTIONS = [
    { key: "critical_changes", label: "Críticos", data: diffResult?.changes.critical_changes ?? [] },
    { key: "obligations_changed", label: "Obligaciones", data: diffResult?.changes.obligations_changed ?? [] },
    { key: "deadlines_changed", label: "Plazos", data: diffResult?.changes.deadlines_changed ?? [] },
    { key: "commercial_impacts", label: "Comercial", data: diffResult?.changes.commercial_impacts ?? [] },
    { key: "technical_impacts", label: "Técnico", data: diffResult?.changes.technical_impacts ?? [] },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Control de Versiones y Diff Semántico</h1>
        <p className="text-sm text-gray-500 mt-1">
          Compara revisiones de documentos con GPT-4o y detecta cambios contractuales relevantes.
        </p>
      </div>

      {/* Selección */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Configurar comparación</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Proyecto</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                setSelectedDocumentId("");
                setPrevVersionId("");
                setNewVersionId("");
                setDiffResult(null);
              }}
            >
              <option value="">Seleccionar…</option>
              {(projectsData ?? []).map((p: any) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Documento</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={selectedDocumentId}
              onChange={(e) => {
                setSelectedDocumentId(e.target.value);
                setPrevVersionId("");
                setNewVersionId("");
                setDiffResult(null);
              }}
              disabled={!selectedProjectId}
            >
              <option value="">Seleccionar…</option>
              {(documentsData ?? []).map((d: any) => (
                <option key={d.id} value={d.id}>{d.title}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Versión anterior</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={prevVersionId}
              onChange={(e) => { setPrevVersionId(e.target.value); setDiffResult(null); }}
              disabled={!selectedDocumentId}
            >
              <option value="">Seleccionar…</option>
              {processedVersions.map((v: any) => (
                <option key={v.id} value={v.id}>
                  {v.revision_number || v.version_label || v.file_name} {v.is_current ? "(vigente)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Versión nueva</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={newVersionId}
              onChange={(e) => { setNewVersionId(e.target.value); setDiffResult(null); }}
              disabled={!selectedDocumentId}
            >
              <option value="">Seleccionar…</option>
              {processedVersions
                .filter((v: any) => v.id !== prevVersionId)
                .map((v: any) => (
                  <option key={v.id} value={v.id}>
                    {v.revision_number || v.version_label || v.file_name} {v.is_current ? "(vigente)" : ""}
                  </option>
                ))}
            </select>
          </div>
        </div>
        <button
          onClick={() => diffMutation.mutate()}
          disabled={!prevVersionId || !newVersionId || diffMutation.isPending}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-6 rounded-lg text-sm transition-colors"
        >
          {diffMutation.isPending ? "Analizando con IA…" : "⚡ Comparar versiones"}
        </button>
      </div>

      {diffMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {(diffMutation.error as any)?.response?.data?.detail ?? "Error al comparar."}
        </div>
      )}

      {/* Resultado del diff */}
      {diffResult && (
        <div className="space-y-4">
          {/* Resumen ejecutivo */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800">
                {diffResult.document_title}: {diffResult.previous_revision} → {diffResult.new_revision}
              </h2>
              <div className="flex items-center gap-2">
                <RiskBadge level={diffResult.risk_level} />
                {diffResult.requires_legal_review && (
                  <span className="text-xs bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded font-semibold">
                    Revisión legal requerida
                  </span>
                )}
                {diffResult.alert_created && (
                  <span className="text-xs bg-orange-50 text-orange-700 border border-orange-200 px-2 py-0.5 rounded">
                    Alerta generada
                  </span>
                )}
              </div>
            </div>
            <p className="text-sm text-gray-700">{diffResult.semantic_summary}</p>
          </div>

          {/* Tabs de cambios */}
          <div className="bg-white border border-gray-200 rounded-xl">
            <div className="flex border-b border-gray-200 overflow-x-auto">
              {SECTIONS.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setActiveSection(s.key)}
                  className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                    activeSection === s.key
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {s.label} ({s.data.length})
                </button>
              ))}
            </div>
            <div className="p-4 space-y-3">
              {SECTIONS.find((s) => s.key === activeSection)?.data.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-6">No se detectaron cambios en esta categoría.</p>
              ) : (
                SECTIONS.find((s) => s.key === activeSection)?.data.map((change, i) => (
                  <ChangeCard key={i} change={change} index={i} />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
