/**
 * DocuBot — Vista de proyectos con creación y navegación.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderKanban, Plus, FileText, AlertTriangle, ChevronRight, X } from "lucide-react";
import { useProjects, useCreateProject } from "../hooks/useProjects";
import type { Project } from "../types";

function StatusBadge({ status }: { status: Project["status"] }) {
  const cfg = {
    active:   "bg-green-100 text-green-700",
    closed:   "bg-gray-100 text-gray-600",
    archived: "bg-yellow-100 text-yellow-700",
  }[status];
  const label = { active: "Activo", closed: "Cerrado", archived: "Archivado" }[status];
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cfg}`}>{label}</span>;
}

function CreateProjectModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ name: "", code: "", client_name: "", contract_name: "" });
  const createProject = useCreateProject();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    createProject.mutate(
      { name: form.name, code: form.code || undefined, client_name: form.client_name || undefined, contract_name: form.contract_name || undefined },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Nuevo proyecto</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del proyecto *</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: Proyecto Minero Los Andes"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Código</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: PROJ-001"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cliente</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: Compañía Minera XYZ"
              value={form.client_name}
              onChange={(e) => setForm({ ...form, client_name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del contrato</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: Contrato EPC Planta Concentradora"
              value={form.contract_name}
              onChange={(e) => setForm({ ...form, contract_name: e.target.value })}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-gray-300 text-gray-700 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={createProject.isPending || !form.name.trim()}
              className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {createProject.isPending ? "Creando…" : "Crear proyecto"}
            </button>
          </div>
          {createProject.isError && (
            <p className="text-sm text-red-600">Error al crear el proyecto. Intenta nuevamente.</p>
          )}
        </form>
      </div>
    </div>
  );
}

export default function Projects() {
  const { data: projects = [], isLoading } = useProjects();
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Proyectos</h1>
          <p className="text-gray-500 mt-1 text-sm">Administra tus proyectos documentales.</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" /> Nuevo proyecto
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
              <div className="h-3 bg-gray-100 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-gray-50 border border-dashed border-gray-300 rounded-xl p-16 text-center">
          <FolderKanban className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 font-medium mb-1">Sin proyectos</p>
          <p className="text-gray-400 text-sm mb-6">Crea tu primer proyecto documental para comenzar.</p>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" /> Crear proyecto
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <div
              key={project.id}
              className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer group"
              onClick={() => navigate(`/proyectos/${project.id}`)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                  <FolderKanban className="w-5 h-5 text-blue-600" />
                </div>
                <StatusBadge status={project.status} />
              </div>
              <h3 className="font-semibold text-gray-900 mb-1 group-hover:text-blue-600 transition-colors">
                {project.name}
              </h3>
              {project.code && <p className="text-xs text-gray-400 mb-2">{project.code}</p>}
              {project.client_name && (
                <p className="text-sm text-gray-500 mb-3 truncate">{project.client_name}</p>
              )}
              <div className="flex items-center gap-4 pt-3 border-t border-gray-100 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <FileText className="w-3.5 h-3.5" /> {project.document_count ?? 0} docs
                </span>
                {(project.open_alerts ?? 0) > 0 && (
                  <span className="flex items-center gap-1 text-amber-600 font-medium">
                    <AlertTriangle className="w-3.5 h-3.5" /> {project.open_alerts} alertas
                  </span>
                )}
                <ChevronRight className="w-3.5 h-3.5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
