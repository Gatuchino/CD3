/**
 * DocuBot — Dashboard principal.
 * KPIs: documentos cargados, procesados, alertas críticas, proyectos activos.
 */
import { useQuery } from "@tanstack/react-query";
import {
  FileText, AlertTriangle, CheckCircle2,
  FolderKanban, DollarSign, Users, Clock, XCircle,
} from "lucide-react";
import { projectsApi } from "../services/api";

interface KpiCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}

function KpiCard({ title, value, icon, color, subtitle }: KpiCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 flex items-start gap-4 shadow-sm hover:shadow-md transition-shadow">
      <div className={`p-3 rounded-lg ${color}`}>{icon}</div>
      <div>
        <p className="text-sm text-gray-500 font-medium">{title}</p>
        <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: projects = [], isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
  });

  const totalDocs = projects.reduce((acc: number, p: any) => acc + (p.document_count ?? 0), 0);
  const totalAlerts = projects.reduce((acc: number, p: any) => acc + (p.open_alerts ?? 0), 0);
  const activeProjects = projects.filter((p: any) => p.status === "active").length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard DocuBot</h1>
        <p className="text-gray-500 mt-1">
          Gestión documental inteligente — Aurenza IA
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Proyectos activos"
          value={isLoading ? "…" : activeProjects}
          icon={<FolderKanban className="text-blue-600 w-5 h-5" />}
          color="bg-blue-50"
        />
        <KpiCard
          title="Documentos cargados"
          value={isLoading ? "…" : totalDocs}
          icon={<FileText className="text-indigo-600 w-5 h-5" />}
          color="bg-indigo-50"
          subtitle="Todas las revisiones"
        />
        <KpiCard
          title="Alertas abiertas"
          value={isLoading ? "…" : totalAlerts}
          icon={<AlertTriangle className="text-amber-600 w-5 h-5" />}
          color="bg-amber-50"
          subtitle="Requieren atención"
        />
        <KpiCard
          title="RFIs sin respuesta"
          value="—"
          icon={<Clock className="text-red-600 w-5 h-5" />}
          color="bg-red-50"
          subtitle="Disponible en Fase 3"
        />
      </div>

      {/* Proyectos recientes */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Proyectos recientes</h2>
        {isLoading ? (
          <div className="text-gray-400">Cargando proyectos…</div>
        ) : projects.length === 0 ? (
          <div className="bg-gray-50 border border-dashed border-gray-300 rounded-xl p-12 text-center">
            <FolderKanban className="w-10 h-10 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">Sin proyectos</p>
            <p className="text-gray-400 text-sm mt-1">
              Crea tu primer proyecto documental para comenzar.
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-gray-200 shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left">Proyecto</th>
                  <th className="px-4 py-3 text-left">Cliente</th>
                  <th className="px-4 py-3 text-center">Documentos</th>
                  <th className="px-4 py-3 text-center">Alertas</th>
                  <th className="px-4 py-3 text-center">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {projects.slice(0, 10).map((p: any) => (
                  <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {p.name}
                      {p.code && (
                        <span className="ml-2 text-xs text-gray-400">{p.code}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{p.client_name ?? "—"}</td>
                    <td className="px-4 py-3 text-center text-gray-700">{p.document_count ?? 0}</td>
                    <td className="px-4 py-3 text-center">
                      {p.open_alerts > 0 ? (
                        <span className="inline-flex items-center gap-1 text-amber-700 font-medium">
                          <AlertTriangle className="w-3.5 h-3.5" /> {p.open_alerts}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                        p.status === "active"
                          ? "bg-green-100 text-green-700"
                          : p.status === "closed"
                          ? "bg-gray-100 text-gray-600"
                          : "bg-yellow-100 text-yellow-700"
                      }`}>
                        {p.status === "active" ? "Activo"
                          : p.status === "closed" ? "Cerrado"
                          : "Archivado"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Aviso de fases pendientes */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 text-blue-800 text-sm">
        <strong>Estado del sistema:</strong> MVP Fase 1 activo. Las funcionalidades de búsqueda RAG,
        clasificación automática, extracción de obligaciones y comparador de versiones estarán
        disponibles en las Fases 2, 3 y 4.
      </div>
    </div>
  );
}
