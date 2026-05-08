/**
 * DocuBot — Página de Resúmenes Ejecutivos de Contratos.
 * Genera resúmenes con GPT-4o adaptados a la audiencia:
 * gerente, contract manager, legal, auditor.
 */
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { documentsApi, projectsApi, summaryApi } from "../services/api";

// ── Tipos ────────────────────────────────────────────────────────
interface Risk {
  risk: string;
  impact: string;
  severity: string;
}
interface Deadline {
  description: string;
  deadline: string;
  responsible: string;
}
interface Summary {
  executive_overview: string;
  key_obligations: string[];
  critical_deadlines: Deadline[];
  risks: Risk[];
  commercial_conditions: string[];
  recommended_actions: string[];
}
interface SummaryResponse {
  document_title: string;
  revision_number: string;
  project_name: string;
  audience: string;
  summary_type: string;
  summary: Summary;
}

// ── Helpers ──────────────────────────────────────────────────────
const AUDIENCE_OPTIONS = [
  { value: "project_manager", label: "Project Manager" },
  { value: "gerente_proyecto", label: "Gerente de Proyecto" },
  { value: "contract_manager", label: "Contract Manager" },
  { value: "legal", label: "Legal" },
  { value: "auditor", label: "Auditor" },
];
const TYPE_OPTIONS = [
  { value: "contractual", label: "Contractual" },
  { value: "technical", label: "Técnico" },
  { value: "commercial", label: "Comercial" },
];
const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-700 bg-red-50 border-red-200",
  high: "text-orange-700 bg-orange-50 border-orange-200",
  medium: "text-yellow-700 bg-yellow-50 border-yellow-200",
  low: "text-green-700 bg-green-50 border-green-200",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">{title}</h3>
      {children}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────
export default function ContractSummary() {
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [audience, setAudience] = useState("project_manager");
  const [summaryType, setSummaryType] = useState("contractual");
  const [includeRisks, setIncludeRisks] = useState(true);
  const [includeDeadlines, setIncludeDeadlines] = useState(true);
  const [includeObligations, setIncludeObligations] = useState(true);
  const [result, setResult] = useState<SummaryResponse | null>(null);

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
  });

  const { data: documentsData } = useQuery({
    queryKey: ["documents", selectedProjectId],
    queryFn: () => documentsApi.list(selectedProjectId).then((r) => r.data),
    enabled: !!selectedProjectId,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      summaryApi.generate(
        selectedVersionId,
        audience,
        summaryType,
        includeRisks,
        includeDeadlines,
        includeObligations
      ),
    onSuccess: (res) => setResult(res.data),
  });

  const allVersions: { id: string; label: string }[] = (documentsData ?? []).flatMap((doc: any) =>
    doc.current_version_id
      ? [{ id: doc.current_version_id, label: `${doc.title} — ${doc.document_type ?? "?"}` }]
      : []
  );

  const summary = result?.summary;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Resúmenes Ejecutivos</h1>
        <p className="text-sm text-gray-500 mt-1">
          Genera resúmenes orientados a la toma de decisiones con GPT-4o, adaptados a tu rol.
        </p>
      </div>

      {/* Configuración */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Configurar resumen</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Proyecto</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={selectedProjectId}
              onChange={(e) => { setSelectedProjectId(e.target.value); setSelectedVersionId(""); setResult(null); }}
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
              value={selectedVersionId}
              onChange={(e) => { setSelectedVersionId(e.target.value); setResult(null); }}
              disabled={!selectedProjectId}
            >
              <option value="">Seleccionar…</option>
              {allVersions.map((v) => (
                <option key={v.id} value={v.id}>{v.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Audiencia</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
            >
              {AUDIENCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1">Tipo de análisis</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={summaryType}
              onChange={(e) => setSummaryType(e.target.value)}
            >
              {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col justify-center gap-2">
            <label className="text-xs font-semibold text-gray-500 mb-1">Incluir secciones</label>
            {[
              { label: "Riesgos", value: includeRisks, set: setIncludeRisks },
              { label: "Plazos críticos", value: includeDeadlines, set: setIncludeDeadlines },
              { label: "Obligaciones clave", value: includeObligations, set: setIncludeObligations },
            ].map(({ label, value, set }) => (
              <label key={label} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={value}
                  onChange={(e) => set(e.target.checked)}
                  className="rounded border-gray-300"
                />
                {label}
              </label>
            ))}
          </div>
        </div>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={!selectedVersionId || generateMutation.isPending}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-6 rounded-lg text-sm transition-colors"
        >
          {generateMutation.isPending ? "Generando resumen…" : "⚡ Generar resumen ejecutivo"}
        </button>
      </div>

      {generateMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {(generateMutation.error as any)?.response?.data?.detail ?? "Error al generar el resumen."}
        </div>
      )}

      {/* Resultado */}
      {result && summary && (
        <div className="space-y-4">
          {/* Header del resumen */}
          <div className="bg-slate-800 text-white rounded-xl p-5">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-lg font-bold">{result.document_title}</h2>
                <p className="text-slate-300 text-sm">
                  {result.revision_number} — {result.project_name}
                </p>
              </div>
              <div className="text-right text-xs text-slate-400">
                <div>Audiencia: <span className="text-white font-medium">
                  {AUDIENCE_OPTIONS.find(o => o.value === result.audience)?.label}
                </span></div>
                <div>Tipo: <span className="text-white font-medium">
                  {TYPE_OPTIONS.find(o => o.value === result.summary_type)?.label}
                </span></div>
              </div>
            </div>
            <p className="text-slate-100 text-sm leading-relaxed">{summary.executive_overview}</p>
          </div>

          {/* Acciones recomendadas */}
          {summary.recommended_actions.length > 0 && (
            <Section title="Acciones recomendadas">
              <ul className="space-y-2">
                {summary.recommended_actions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-blue-500 font-bold mt-0.5">→</span>
                    {action}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Obligaciones clave */}
            {includeObligations && summary.key_obligations.length > 0 && (
              <Section title="Obligaciones clave">
                <ul className="space-y-2">
                  {summary.key_obligations.map((ob, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-purple-500 font-bold mt-0.5">•</span>
                      {ob}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Plazos críticos */}
            {includeDeadlines && summary.critical_deadlines.length > 0 && (
              <Section title="Plazos críticos">
                <div className="space-y-2">
                  {summary.critical_deadlines.map((dl, i) => (
                    <div key={i} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
                      <p className="font-medium text-gray-800">{dl.description}</p>
                      <div className="flex gap-4 mt-1 text-xs text-gray-500">
                        <span><b>Plazo:</b> {dl.deadline}</span>
                        {dl.responsible && <span><b>Responsable:</b> {dl.responsible}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Riesgos */}
            {includeRisks && summary.risks.length > 0 && (
              <Section title="Riesgos identificados">
                <div className="space-y-2">
                  {summary.risks.map((risk, i) => (
                    <div
                      key={i}
                      className={`border rounded-lg p-3 text-sm ${SEVERITY_COLORS[risk.severity] ?? SEVERITY_COLORS.low}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-medium">{risk.risk}</p>
                        <span className="text-xs font-bold uppercase">{risk.severity}</span>
                      </div>
                      <p className="text-xs opacity-80">{risk.impact}</p>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Condiciones comerciales */}
            {summary.commercial_conditions.length > 0 && (
              <Section title="Condiciones comerciales">
                <ul className="space-y-2">
                  {summary.commercial_conditions.map((cc, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-green-500 font-bold mt-0.5">$</span>
                      {cc}
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
