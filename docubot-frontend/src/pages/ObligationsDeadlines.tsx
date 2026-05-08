/**
 * DocuBot — Página de Obligaciones y Plazos Contractuales.
 * Permite visualizar y ejecutar la extracción de obligaciones
 * y plazos de versiones de documentos procesados.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { obligationsApi, documentsApi, projectsApi } from "../services/api";

// ── Tipos ────────────────────────────────────────────────────────

interface Obligation {
  id: string;
  obligation_type: string;
  obligation_text: string;
  responsible_party: string | null;
  consequence: string | null;
  confidence_score: number;
  requires_human_validation: boolean;
  source_reference: {
    document?: string;
    revision?: string;
    page?: string;
    paragraph?: string;
    quote?: string;
  };
}

interface Deadline {
  id: string;
  deadline_type: string;
  description: string;
  due_date: string | null;
  relative_deadline: string | null;
  responsible_party: string | null;
  confidence_score: number;
  source_reference: {
    document?: string;
    paragraph?: string;
    quote?: string;
  };
}

// ── Helpers ──────────────────────────────────────────────────────

const SEVERITY_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-gray-100 text-gray-700 border-gray-200",
};

const OB_TYPE_LABEL: Record<string, string> = {
  entregable: "Entregable",
  pago: "Pago",
  reporte: "Reporte",
  permiso: "Permiso",
  seguro: "Seguro",
  garantia: "Garantía",
  penalidad: "Penalidad",
  notificacion: "Notificación",
  aprobacion: "Aprobación",
  inspeccion: "Inspección",
  capacitacion: "Capacitación",
  otro: "Otro",
};

const DL_TYPE_LABEL: Record<string, string> = {
  inicio_obra: "Inicio de Obra",
  hito: "Hito",
  entrega: "Entrega",
  pago: "Pago",
  vencimiento_garantia: "Vencimiento Garantía",
  vencimiento_seguro: "Vencimiento Seguro",
  plazo_reporte: "Plazo Reporte",
  plazo_rfi: "Plazo RFI",
  penalidad: "Penalidad",
  cierre: "Cierre",
  otro: "Otro",
};

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function urgencyBadge(dateStr: string | null): JSX.Element | null {
  const days = daysUntil(dateStr);
  if (days === null) return null;
  if (days < 0)
    return <span className="ml-2 text-xs font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded">VENCIDO</span>;
  if (days <= 7)
    return <span className="ml-2 text-xs font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded">{days}d</span>;
  if (days <= 30)
    return <span className="ml-2 text-xs font-semibold text-orange-700 bg-orange-100 px-2 py-0.5 rounded">{days}d</span>;
  return <span className="ml-2 text-xs text-gray-500">{days}d</span>;
}

// ── Componente principal ──────────────────────────────────────────

export default function ObligationsDeadlines() {
  const queryClient = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"obligations" | "deadlines">("deadlines");
  const [extractResult, setExtractResult] = useState<{
    obligations_extracted: number;
    deadlines_extracted: number;
    alerts_created: number;
  } | null>(null);

  // Proyectos disponibles
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
  });

  // Documentos del proyecto seleccionado
  const { data: documentsData } = useQuery({
    queryKey: ["documents", selectedProjectId],
    queryFn: () => documentsApi.list(selectedProjectId).then((r) => r.data),
    enabled: !!selectedProjectId,
  });

  // Obligaciones de la versión seleccionada
  const { data: obligationsData, isLoading: loadingOb } = useQuery({
    queryKey: ["obligations", selectedVersionId],
    queryFn: () => obligationsApi.listObligations(selectedVersionId).then((r) => r.data),
    enabled: !!selectedVersionId,
  });

  // Plazos de la versión seleccionada
  const { data: deadlinesData, isLoading: loadingDl } = useQuery({
    queryKey: ["deadlines", selectedVersionId],
    queryFn: () => obligationsApi.listDeadlines(selectedVersionId).then((r) => r.data),
    enabled: !!selectedVersionId,
  });

  // Mutación: extraer obligaciones
  const extractMutation = useMutation({
    mutationFn: () => obligationsApi.extract(selectedVersionId),
    onSuccess: (res) => {
      setExtractResult(res.data);
      queryClient.invalidateQueries({ queryKey: ["obligations", selectedVersionId] });
      queryClient.invalidateQueries({ queryKey: ["deadlines", selectedVersionId] });
    },
  });

  const obligations: Obligation[] = obligationsData ?? [];
  const deadlines: Deadline[] = deadlinesData ?? [];

  // Versiones del documento seleccionado (tomar current_version_id del primer doc que matchee)
  const allVersions: { id: string; label: string }[] =
    (documentsData ?? []).flatMap((doc: any) =>
      doc.current_version_id
        ? [{ id: doc.current_version_id, label: `${doc.title} — ${doc.document_type ?? "?"}` }]
        : []
    );

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Obligaciones y Plazos Contractuales</h1>
        <p className="text-sm text-gray-500 mt-1">
          Extracción automática con GPT-4o de obligaciones, plazos y alertas de vencimiento.
        </p>
      </div>

      {/* Selección de proyecto y documento */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-white rounded-xl border border-gray-200 p-4">
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">
            Proyecto
          </label>
          <select
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            value={selectedProjectId}
            onChange={(e) => {
              setSelectedProjectId(e.target.value);
              setSelectedVersionId("");
              setExtractResult(null);
            }}
          >
            <option value="">Seleccionar proyecto…</option>
            {(projectsData ?? []).map((p: any) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">
            Documento (versión vigente)
          </label>
          <select
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            value={selectedVersionId}
            onChange={(e) => {
              setSelectedVersionId(e.target.value);
              setExtractResult(null);
            }}
            disabled={!selectedProjectId}
          >
            <option value="">Seleccionar documento…</option>
            {allVersions.map((v) => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <button
            onClick={() => extractMutation.mutate()}
            disabled={!selectedVersionId || extractMutation.isPending}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-lg text-sm transition-colors"
          >
            {extractMutation.isPending ? "Extrayendo…" : "⚡ Extraer con IA"}
          </button>
        </div>
      </div>

      {/* Resultado de extracción */}
      {extractResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex gap-8 text-sm">
          <div className="text-center">
            <span className="block text-2xl font-bold text-green-700">{extractResult.obligations_extracted}</span>
            <span className="text-green-600">Obligaciones</span>
          </div>
          <div className="text-center">
            <span className="block text-2xl font-bold text-green-700">{extractResult.deadlines_extracted}</span>
            <span className="text-green-600">Plazos</span>
          </div>
          <div className="text-center">
            <span className="block text-2xl font-bold text-orange-600">{extractResult.alerts_created}</span>
            <span className="text-orange-600">Alertas generadas</span>
          </div>
        </div>
      )}

      {extractMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          Error al extraer: {(extractMutation.error as any)?.response?.data?.detail ?? "Error desconocido"}
        </div>
      )}

      {/* Tabs */}
      {selectedVersionId && (
        <div>
          <div className="flex border-b border-gray-200 mb-4">
            {(["deadlines", "obligations"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {tab === "deadlines"
                  ? `Plazos (${deadlines.length})`
                  : `Obligaciones (${obligations.length})`}
              </button>
            ))}
          </div>

          {/* Plazos */}
          {activeTab === "deadlines" && (
            <div className="space-y-3">
              {loadingDl && <p className="text-sm text-gray-500">Cargando plazos…</p>}
              {!loadingDl && deadlines.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-8">
                  No hay plazos extraídos. Usa el botón "Extraer con IA" para analizarlos.
                </p>
              )}
              {deadlines
                .sort((a, b) => {
                  const da = a.due_date ? new Date(a.due_date).getTime() : Infinity;
                  const db_ = b.due_date ? new Date(b.due_date).getTime() : Infinity;
                  return da - db_;
                })
                .map((dl) => (
                  <div
                    key={dl.id}
                    className="bg-white border border-gray-200 rounded-xl p-4 hover:border-blue-200 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center flex-wrap gap-2 mb-1">
                          <span className="text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded">
                            {DL_TYPE_LABEL[dl.deadline_type] ?? dl.deadline_type}
                          </span>
                          {dl.due_date && (
                            <span className="text-xs text-gray-500">
                              {new Date(dl.due_date).toLocaleDateString("es-CL")}
                              {urgencyBadge(dl.due_date)}
                            </span>
                          )}
                          {dl.relative_deadline && !dl.due_date && (
                            <span className="text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                              {dl.relative_deadline}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-800">{dl.description}</p>
                        {dl.responsible_party && (
                          <p className="text-xs text-gray-500 mt-1">
                            <span className="font-medium">Responsable:</span> {dl.responsible_party}
                          </p>
                        )}
                        {dl.source_reference?.quote && (
                          <blockquote className="mt-2 text-xs text-gray-500 italic border-l-2 border-gray-200 pl-2">
                            "{dl.source_reference.quote}"
                            {dl.source_reference.paragraph && (
                              <span className="not-italic text-gray-400"> — {dl.source_reference.paragraph}</span>
                            )}
                          </blockquote>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-xs text-gray-400">
                          Conf. {(dl.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* Obligaciones */}
          {activeTab === "obligations" && (
            <div className="space-y-3">
              {loadingOb && <p className="text-sm text-gray-500">Cargando obligaciones…</p>}
              {!loadingOb && obligations.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-8">
                  No hay obligaciones extraídas. Usa el botón "Extraer con IA" para analizarlas.
                </p>
              )}
              {obligations.map((ob) => (
                <div
                  key={ob.id}
                  className="bg-white border border-gray-200 rounded-xl p-4 hover:border-blue-200 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center flex-wrap gap-2 mb-1">
                        <span className="text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded">
                          {OB_TYPE_LABEL[ob.obligation_type] ?? ob.obligation_type}
                        </span>
                        {ob.requires_human_validation && (
                          <span className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 px-2 py-0.5 rounded">
                            ⚠ Validación requerida
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-800">{ob.obligation_text}</p>
                      <div className="flex flex-wrap gap-4 mt-1">
                        {ob.responsible_party && (
                          <p className="text-xs text-gray-500">
                            <span className="font-medium">Responsable:</span> {ob.responsible_party}
                          </p>
                        )}
                        {ob.consequence && (
                          <p className="text-xs text-red-600">
                            <span className="font-medium">Consecuencia:</span> {ob.consequence}
                          </p>
                        )}
                      </div>
                      {ob.source_reference?.quote && (
                        <blockquote className="mt-2 text-xs text-gray-500 italic border-l-2 border-gray-200 pl-2">
                          "{ob.source_reference.quote}"
                          {ob.source_reference.paragraph && (
                            <span className="not-italic text-gray-400"> — {ob.source_reference.paragraph}</span>
                          )}
                        </blockquote>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <span className="text-xs text-gray-400">
                        Conf. {(ob.confidence_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
