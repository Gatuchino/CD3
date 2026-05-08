/**
 * DocuBot — Biblioteca documental.
 * Tabla de documentos con filtros por proyecto, tipo documental y disciplina.
 */
import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, AlertCircle, CheckCircle2, Clock, Search, Filter } from "lucide-react";
import { documentsApi } from "../services/api";

const DOCUMENT_TYPES: Record<string, string> = {
  contract: "Contrato",
  addendum: "Adenda",
  rfi: "RFI",
  transmittal: "Transmittal",
  meeting_minutes: "Acta",
  technical_specification: "Especificación técnica",
  drawing: "Plano",
  schedule: "Cronograma",
  commercial_proposal: "Propuesta comercial",
  technical_proposal: "Propuesta técnica",
  purchase_order: "Orden de compra",
  change_order: "Orden de cambio",
  claim: "Reclamo",
  letter: "Carta",
  report: "Informe",
  other: "Otro",
};

const DISCIPLINES: Record<string, string> = {
  contractual: "Contractual",
  commercial: "Comercial",
  engineering: "Ingeniería",
  construction: "Construcción",
  procurement: "Procurement",
  safety: "Seguridad",
  environmental: "Medio ambiente",
  quality: "Calidad",
  planning: "Planificación",
  operations: "Operaciones",
  legal: "Legal",
  other: "Otro",
};

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    uploaded: { label: "Cargado", color: "bg-blue-100 text-blue-700" },
    processing: { label: "Procesando", color: "bg-yellow-100 text-yellow-700" },
    processed: { label: "Procesado", color: "bg-green-100 text-green-700" },
    error: { label: "Error", color: "bg-red-100 text-red-700" },
    pending_review: { label: "En revisión", color: "bg-purple-100 text-purple-700" },
  };
  const { label, color } = map[status] ?? { label: status, color: "bg-gray-100 text-gray-600" };
  return (
    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

interface DocumentLibraryProps {
  projectId: string;
}

export default function DocumentLibrary({ projectId }: DocumentLibraryProps) {
  const qc = useQueryClient();
  const [filterType, setFilterType] = useState("");
  const [filterDiscipline, setFilterDiscipline] = useState("");
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["documents", projectId, filterType, filterDiscipline],
    queryFn: () =>
      documentsApi
        .list(projectId, {
          document_type: filterType || undefined,
          discipline: filterDiscipline || undefined,
        })
        .then((r) => r.data),
    enabled: !!projectId,
  });

  const filtered = documents.filter((d: any) =>
    search
      ? d.title.toLowerCase().includes(search.toLowerCase()) ||
        d.document_code?.toLowerCase().includes(search.toLowerCase())
      : true
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (!acceptedFiles.length) return;
      setUploading(true);
      setUploadError(null);
      try {
        for (const file of acceptedFiles) {
          const fd = new FormData();
          fd.append("file", file);
          await documentsApi.upload(projectId, fd);
        }
        qc.invalidateQueries({ queryKey: ["documents", projectId] });
      } catch (err: any) {
        setUploadError(err.response?.data?.detail ?? "Error al cargar el archivo.");
      } finally {
        setUploading(false);
      }
    },
    [projectId, qc]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/tiff": [".tiff"],
    },
    multiple: true,
  });

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Biblioteca documental</h2>

      {/* Zona de carga */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-blue-300 hover:bg-gray-50"
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        {uploading ? (
          <p className="text-blue-600 font-medium">Cargando documentos…</p>
        ) : isDragActive ? (
          <p className="text-blue-600 font-medium">Suelta los archivos aquí</p>
        ) : (
          <>
            <p className="text-gray-600 font-medium">
              Arrastra documentos o haz clic para cargar
            </p>
            <p className="text-gray-400 text-sm mt-1">
              PDF, DOCX, XLSX, PNG, JPG, TIFF — máximo 50 MB por archivo
            </p>
          </>
        )}
      </div>

      {uploadError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {uploadError}
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Buscar documento…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">Todos los tipos</option>
          {Object.entries(DOCUMENT_TYPES).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={filterDiscipline}
          onChange={(e) => setFilterDiscipline(e.target.value)}
        >
          <option value="">Todas las disciplinas</option>
          {Object.entries(DISCIPLINES).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {/* Tabla de documentos */}
      {isLoading ? (
        <div className="text-gray-400 text-sm">Cargando documentos…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No se encontraron documentos</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">Documento</th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-left">Disciplina</th>
                <th className="px-4 py-3 text-center">Revisión</th>
                <th className="px-4 py-3 text-center">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((doc: any) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{doc.title}</div>
                    {doc.document_code && (
                      <div className="text-xs text-gray-400">{doc.document_code}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {DOCUMENT_TYPES[doc.document_type] ?? doc.document_type ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {DISCIPLINES[doc.discipline] ?? doc.discipline ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-center text-gray-500">
                    {doc.revision_number ?? "Rev.0"}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={doc.processing_status ?? "uploaded"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
