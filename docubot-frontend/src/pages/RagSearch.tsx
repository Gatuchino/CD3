/**
 * DocuBot — Buscador inteligente RAG.
 * Consulta en lenguaje natural con respuestas, citas y nivel de confianza.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, AlertTriangle, BookOpen, ShieldAlert, CheckCircle2 } from "lucide-react";
import { ragApi } from "../services/api";

interface Evidence {
  document: string;
  revision?: string;
  page?: string;
  paragraph?: string;
  quote: string;
  relevance_score?: number;
}

interface RagResponse {
  query_id: string;
  answer: string;
  evidence: Evidence[];
  interpretation?: string;
  risks_or_warnings: string[];
  confidence: number;
  requires_human_review: boolean;
  latency_ms?: number;
}

interface RagSearchProps {
  projectId: string;
  projectName: string;
}

export default function RagSearch({ projectId, projectName }: RagSearchProps) {
  const [question, setQuestion] = useState("");
  const [revisionPolicy, setRevisionPolicy] = useState("latest_only");
  const [result, setResult] = useState<RagResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (q: string) =>
      ragApi.query({
        project_id: projectId,
        question: q,
        top_k: 8,
        filters: { revision_policy: revisionPolicy },
      }).then((r) => r.data),
    onSuccess: (data) => setResult(data),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim().length < 5) return;
    mutation.mutate(question.trim());
  };

  const confidenceColor =
    !result ? ""
    : result.confidence >= 0.8 ? "text-green-600"
    : result.confidence >= 0.6 ? "text-yellow-600"
    : "text-red-600";

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Buscador inteligente</h2>
        <p className="text-gray-500 text-sm mt-1">
          Consulta en lenguaje natural sobre los documentos del proyecto{" "}
          <strong>{projectName}</strong>.
        </p>
      </div>

      {/* Formulario */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
          placeholder="¿Cuál es el plazo de respuesta para RFIs? ¿Qué penalidades existen por atraso?…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="flex items-center gap-4">
          <select
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
            value={revisionPolicy}
            onChange={(e) => setRevisionPolicy(e.target.value)}
          >
            <option value="latest_only">Solo revisión vigente</option>
            <option value="all_revisions">Todas las revisiones</option>
          </select>
          <button
            type="submit"
            disabled={mutation.isPending || question.trim().length < 5}
            className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Search className="w-4 h-4" />
            {mutation.isPending ? "Consultando…" : "Consultar"}
          </button>
        </div>
      </form>

      {/* Error */}
      {mutation.isError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          Error al procesar la consulta. Intenta nuevamente.
        </div>
      )}

      {/* Resultado */}
      {result && (
        <div className="space-y-5 border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
          {/* Respuesta principal */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-800">Respuesta</h3>
              <div className="flex items-center gap-3 text-xs">
                <span className={`font-medium ${confidenceColor}`}>
                  Confianza: {(result.confidence * 100).toFixed(0)}%
                </span>
                {result.requires_human_review && (
                  <span className="flex items-center gap-1 text-amber-600 font-medium">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    Requiere revisión humana
                  </span>
                )}
              </div>
            </div>
            <p className="text-gray-700 leading-relaxed">{result.answer}</p>
          </div>

          {/* Evidencia documental */}
          {result.evidence.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5 mb-3">
                <BookOpen className="w-4 h-4 text-blue-500" />
                Evidencia documental
              </h4>
              <div className="space-y-3">
                {result.evidence.map((ev, i) => (
                  <div
                    key={i}
                    className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm"
                  >
                    <div className="flex flex-wrap gap-2 text-xs text-blue-700 font-medium mb-2">
                      <span>{ev.document}</span>
                      {ev.revision && <span>· {ev.revision}</span>}
                      {ev.page && <span>· Pág. {ev.page}</span>}
                      {ev.paragraph && <span>· {ev.paragraph}</span>}
                    </div>
                    <blockquote className="text-gray-700 italic border-l-2 border-blue-400 pl-3">
                      "{ev.quote}"
                    </blockquote>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Interpretación */}
          {result.interpretation && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-1">Interpretación</h4>
              <p className="text-gray-600 text-sm leading-relaxed">{result.interpretation}</p>
            </div>
          )}

          {/* Riesgos y advertencias */}
          {result.risks_or_warnings.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-amber-700 flex items-center gap-1.5 mb-2">
                <AlertTriangle className="w-4 h-4" />
                Advertencias
              </h4>
              <ul className="space-y-1">
                {result.risks_or_warnings.map((w, i) => (
                  <li key={i} className="text-sm text-amber-800 bg-amber-50 rounded px-3 py-1.5">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Footer */}
          <div className="pt-2 border-t border-gray-100 text-xs text-gray-400">
            Query ID: {result.query_id}
            {result.latency_ms && ` · ${result.latency_ms}ms`}
          </div>
        </div>
      )}
    </div>
  );
}
