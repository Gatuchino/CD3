// ─── Proyectos ────────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  code?: string;
  client_name?: string;
  contract_name?: string;
  status: "active" | "closed" | "archived";
  document_count?: number;
  open_alerts?: number;
  created_at: string;
}

// ─── Documentos ───────────────────────────────────────────────
export interface Document {
  id: string;
  project_id: string;
  title: string;
  document_number?: string;
  document_type: string;
  discipline?: string;
  current_version_id?: string;
  current_revision?: string;
  processing_status?: "pending" | "processing" | "processed" | "error";
  created_at: string;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  revision_number?: string;
  file_name: string;
  file_type: string;
  file_size_bytes?: number;
  processing_status: "pending" | "processing" | "processed" | "error";
  processed_at?: string;
  created_at: string;
}

// ─── Alertas ──────────────────────────────────────────────────
export interface Alert {
  id: string;
  project_id: string;
  alert_type: string;
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description?: string;
  status: "open" | "acknowledged" | "resolved" | "dismissed";
  due_date?: string;
  document_title?: string;
  created_at: string;
}

// ─── Obligaciones ─────────────────────────────────────────────
export interface Obligation {
  id: string;
  obligation_type: string;
  obligation_text: string;
  responsible_party?: string;
  consequence?: string;
  source_reference?: string;
  confidence_score?: number;
  requires_human_validation?: boolean;
}

export interface Deadline {
  id: string;
  deadline_type: string;
  description: string;
  due_date?: string;
  relative_deadline?: string;
  responsible_party?: string;
  source_reference?: string;
  confidence_score?: number;
}

// ─── RAG ──────────────────────────────────────────────────────
export interface RagEvidence {
  document: string;
  revision?: string;
  page?: string;
  paragraph?: string;
  quote: string;
}

export interface RagResponse {
  query_id: string;
  answer: string;
  evidence: RagEvidence[];
  interpretation?: string;
  risks_or_warnings: string[];
  confidence: number;
  requires_human_review: boolean;
  latency_ms?: number;
}
