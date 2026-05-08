import { IS_DEMO } from "../auth/msalConfig";
/**
 * DocuBot — Cliente Axios con interceptor de autenticación B2C.
 */
import axios from "axios";
import { msalInstance } from "../main";
import { loginRequest } from "../auth/msalConfig";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// Demo mode: inyectar headers de autenticación simulados
if (IS_DEMO) {
  api.defaults.headers.common["Authorization"] = "Bearer demo-token";
  api.defaults.headers.common["X-Tenant-ID"] = "demo-tenant";
}


// Interceptor: adjunta token B2C en cada request
api.interceptors.request.use(async (config) => {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    try {
      const response = await msalInstance.acquireTokenSilent({
        ...loginRequest,
        account: accounts[0],
      });
      config.headers["Authorization"] = `Bearer ${response.accessToken}`;
    } catch {
      // Si el token silencioso falla, redirigir a login
      await msalInstance.acquireTokenRedirect(loginRequest);
    }
  }
  return config;
});

export default api;

// ─── Proyectos ────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get("/api/v1/projects"),
  get: (id: string) => api.get(`/api/v1/projects/${id}`),
  create: (data: { name: string; code?: string; client_name?: string; contract_name?: string }) =>
    api.post("/api/v1/projects", data),
  updateStatus: (id: string, status: string) =>
    api.patch(`/api/v1/projects/${id}/status`, null, { params: { new_status: status } }),
};

// ─── Documentos ───────────────────────────────────────────────
export const documentsApi = {
  list: (projectId: string, params?: { document_type?: string; discipline?: string }) =>
    api.get(`/api/v1/projects/${projectId}/documents`, { params }),
  upload: (projectId: string, formData: FormData) =>
    api.post(`/api/v1/projects/${projectId}/documents/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  getStatus: (versionId: string) =>
    api.get(`/api/v1/projects/document-versions/${versionId}/status`),
};

// ─── RAG ──────────────────────────────────────────────────────
export const ragApi = {
  query: (data: {
    project_id: string;
    question: string;
    top_k?: number;
    filters?: object;
  }) => api.post("/api/v1/rag/query", data),
};

// ─── Alertas ──────────────────────────────────────────────────
export const alertsApi = {
  list: (projectId: string, params?: { status?: string; severity?: string }) =>
    api.get(`/api/v1/projects/${projectId}/alerts`, { params }),
  updateStatus: (projectId: string, alertId: string, newStatus: string) =>
    api.patch(
      `/api/v1/projects/${projectId}/alerts/${alertId}/status`,
      null,
      { params: { new_status: newStatus } }
    ),
};

// ─── Obligaciones y Plazos ────────────────────────────────────
export const obligationsApi = {
  listObligations: (versionId: string) =>
    api.get(`/api/v1/document-versions/${versionId}/obligations`),
  listDeadlines: (versionId: string) =>
    api.get(`/api/v1/document-versions/${versionId}/deadlines`),
  extract: (versionId: string) =>
    api.post(`/api/v1/document-versions/${versionId}/extract-obligations`),
};

// ─── Versiones y Diff ─────────────────────────────────────────
export const versionsApi = {
  list: (documentId: string) =>
    api.get(`/api/v1/documents/${documentId}/versions`),
  diff: (documentId: string, prevVersionId: string, newVersionId: string) =>
    api.get(`/api/v1/documents/${documentId}/diff`, {
      params: { prev_version_id: prevVersionId, new_version_id: newVersionId },
    }),
  get: (versionId: string) =>
    api.get(`/api/v1/document-versions/${versionId}`),
};

// ─── Resúmenes Ejecutivos ─────────────────────────────────────
export const summaryApi = {
  generate: (
    versionId: string,
    audience: string,
    summaryType: string,
    includeRisks: boolean,
    includeDeadlines: boolean,
    includeObligations: boolean
  ) =>
    api.post(`/api/v1/document-versions/${versionId}/summary`, null, {
      params: {
        audience,
        summary_type: summaryType,
        include_risks: includeRisks,
        include_deadlines: includeDeadlines,
        include_obligations: includeObligations,
      },
    }),
};

// ─── Auditoría ────────────────────────────────────────────────
export const auditApi = {
  getLogs: (params: Record<string, unknown>) =>
    api.get("/api/v1/audit/logs", { params }),
  getSummary: (days: number) =>
    api.get("/api/v1/audit/logs/summary", { params: { days } }),
  getRagHistory: (params: Record<string, unknown>) =>
    api.get("/api/v1/audit/rag-history", { params }),
};

// ─── Métricas y Costos ────────────────────────────────────────
export const metricsApi = {
  getTodayCosts: () =>
    api.get("/api/v1/metrics/costs/today"),
  getCostsHistory: (days: number) =>
    api.get("/api/v1/metrics/costs/history", { params: { days } }),
  getRagPerformance: (days: number) =>
    api.get("/api/v1/metrics/performance/rag", { params: { days } }),
  getDetailedHealth: () =>
    api.get("/api/v1/metrics/system/health-detailed"),
};
