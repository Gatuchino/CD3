/**
 * DocuBot — App principal con routing y layout.
 */
import { useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { loginRequest, IS_DEMO } from "./auth/msalConfig";
import {
  LayoutDashboard, FolderKanban, FileText, Search,
  Bell, ClipboardList, LogOut, Menu, CalendarClock,
  GitCompare, BookOpen, BarChart2,
} from "lucide-react";

import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import DocumentLibrary from "./pages/DocumentLibrary";
import RagSearch from "./pages/RagSearch";
import ObligationsDeadlines from "./pages/ObligationsDeadlines";
import VersionDiff from "./pages/VersionDiff";
import ContractSummary from "./pages/ContractSummary";
import Alerts from "./pages/Alerts";
import AuditTrail from "./pages/AuditTrail";
import MetricsDashboard from "./pages/MetricsDashboard";

const DEMO_PROJECT_ID = import.meta.env.VITE_DEMO_PROJECT_ID ?? "demo-project-id";

const NAV_ITEMS = [
  { to: "/",            icon: LayoutDashboard, label: "Dashboard" },
  { to: "/proyectos",   icon: FolderKanban,    label: "Proyectos" },
  { to: "/documentos",  icon: FileText,         label: "Documentos" },
  { to: "/buscar",      icon: Search,           label: "Búsqueda IA" },
  { to: "/obligaciones",icon: CalendarClock,   label: "Obligaciones" },
  { to: "/versiones",   icon: GitCompare,       label: "Versiones" },
  { to: "/resumenes",   icon: BookOpen,         label: "Resúmenes" },
  { to: "/alertas",     icon: Bell,             label: "Alertas" },
  { to: "/auditoria",   icon: ClipboardList,    label: "Auditoría" },
  { to: "/metricas",    icon: BarChart2,        label: "Métricas IA" },
];

function LoginPage() {
  const { instance } = useMsal();
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-700 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-2xl p-10 max-w-sm w-full mx-4">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-blue-600 rounded-xl mb-4">
            <FileText className="text-white w-7 h-7" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">DocuBot</h1>
          <p className="text-gray-500 text-sm mt-1">Aurenza IA — Gestión documental</p>
        </div>
        <button
          onClick={() => instance.loginRedirect(loginRequest)}
          className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors"
        >
          Iniciar sesión con Azure AD
        </button>
      </div>
    </div>
  );
}

function AppLayout({ children }: { children: React.ReactNode }) {
  const { instance, accounts } = useMsal();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const userName = IS_DEMO ? "Usuario Demo" : (accounts[0]?.name ?? "Usuario");

  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className={`${sidebarOpen ? "w-56" : "w-14"} bg-slate-900 text-white flex flex-col transition-all duration-200 flex-shrink-0`}>
        <div className="flex items-center gap-3 px-4 py-5 border-b border-slate-700">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <FileText className="w-4 h-4 text-white" />
          </div>
          {sidebarOpen && (
            <div className="overflow-hidden">
              <p className="font-bold text-sm truncate">DocuBot</p>
              <p className="text-slate-400 text-xs truncate">Aurenza IA</p>
            </div>
          )}
        </div>
        <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive ? "bg-blue-600 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-700">
          {sidebarOpen && (
            <div className="px-2 mb-2">
              <p className="text-xs text-slate-400 truncate">{userName}</p>
              {IS_DEMO && <span className="text-xs text-blue-400 font-medium">Modo demo</span>}
            </div>
          )}
          {!IS_DEMO && (
            <button
              onClick={() => instance.logoutRedirect()}
              className="flex items-center gap-2 w-full px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg text-sm"
            >
              <LogOut className="w-4 h-4" />
              {sidebarOpen && "Cerrar sesión"}
            </button>
          )}
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-500 hover:text-gray-800">
            <Menu className="w-5 h-5" />
          </button>
          <span className="text-sm text-gray-400">
            Proyecto: <span className="text-gray-700 font-medium">{IS_DEMO ? "Demo" : "—"}</span>
          </span>
        </div>
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}

export default function App() {
  const isAuthenticated = useIsAuthenticated();
  if (!IS_DEMO && !isAuthenticated) return <LoginPage />;
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/proyectos" element={<Projects />} />
        <Route path="/documentos" element={<DocumentLibrary projectId={DEMO_PROJECT_ID} />} />
        <Route path="/buscar" element={<RagSearch projectId={DEMO_PROJECT_ID} projectName="Proyecto Demo" />} />
        <Route path="/obligaciones" element={<ObligationsDeadlines />} />
        <Route path="/versiones" element={<VersionDiff />} />
        <Route path="/resumenes" element={<ContractSummary />} />
        <Route path="/alertas" element={<Alerts projectId={DEMO_PROJECT_ID} />} />
        <Route path="/auditoria" element={<AuditTrail />} />
        <Route path="/metricas" element={<MetricsDashboard />} />
      </Routes>
    </AppLayout>
  );
}
