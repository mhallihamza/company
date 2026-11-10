// عميل الـ API الموحد — يضيف Bearer تلقائياً وإلا يفتح نافذة الرمز عبر حدث المتصفح

export type Health = {
  ok: boolean; version?: string; db_backend?: string; db_diag?: string;
  llm_mode?: string; counts?: Record<string, number>;
};

export type AdminHealth = Health;
export type AgentCard = {
  agent: string; role: string; tier: "reasoning" | "fast" | "deterministic" | string;
  tools: string[]; version: string;
  department_key: string; department_title_en: string; department_title_ar: string;
  approval_policy: string; enabled: boolean;
};
export type Capability = {
  id: string; title_en: string; title_ar: string;
  description_en: string; description_ar: string;
  used_by: string[]; deterministic: boolean; version: string;
};
export type DomainAgg = {
  domain: string; total: number; success: number; failed: number;
  last_finished: string | null;
};
export type AgentAgg = {
  agent: string; executions: number; tokens_used: number; success: number; failed: number;
};
export type Observability = {
  llm_mode: string; db_backend: string; db_diag: string; storage: string;
  counts: Record<string, number>;
  executions_by_agent: AgentAgg[];
  tasks_by_domain: DomainAgg[];
  approvals: { pending: number; approved: number; rejected: number };
  tokens_total: number;
  recent_tasks: Record<string, unknown>[];
  audit: AuditEntry[];
};
export type Department = {
  key: string; sector: string; title_ar: string; title_en: string;
  description_ar: string; description_en: string;
  capabilities: string[]; allowed_tools: string[];
  approval_policy: string; version: string; enabled: boolean;
};
export type CeoOut = {
  ok: boolean; task_id?: number; domain?: string; summary?: string;
  artifacts?: Record<string, unknown>; needs_approval?: boolean;
  llm_note?: string; error?: string;
};
export type Book = {
  slug: string; title: string; status: string; pdf_path?: string | null;
  cover_path?: string | null; final_file?: string | null;
  created_at?: string; updated_at?: string; product_id?: number;
};
export type Opportunity = {
  opportunity_id: number; sector: string; title: string; niche?: string;
  score?: number; status: string; payload?: string; created_at?: string;
  source?: "live" | "partial" | "demo" | string;
  evidence?: string;
};
export type Approval = {
  approval_id: number; kind: string; ref: string; status: string;
  note?: string; created_at?: string; decided_at?: string | null;
};
export type Report = {
  report_id: number; kind: string; path?: string; title?: string;
  content?: string; created_at?: string;
  source?: "live" | "partial" | "demo" | string;
  evidence?: string;
};
export type Settings = {
  llm_mode: string; db_backend: string; autonomy_level: number;
  autonomy_levels: { level: number; name: string; describe: string }[];
  keys: Record<string, string>; scheduler_enabled: boolean;
};
export type AuditEntry = {
  log_id: number; task_id?: number | null; actor: string; action: string;
  detail?: string; created_at?: string;
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8700";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function token(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("founder_token") ?? "";
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (resp.status === 401) {
    if (typeof window !== "undefined") window.dispatchEvent(new Event("hq:unauthorized"));
    throw new ApiError(401, "رمز المؤسس غير صالح — سجّله في الإعدادات");
  }
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try { const body = await resp.json(); msg = body?.detail ?? msg; } catch { /* ignore */ }
    throw new ApiError(resp.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return (await resp.json()) as T;
}

export const api = {
  base: BASE,
  health: () => req<{ status: string }>("/api/health"),
  adminHealth: () => req<AdminHealth>("/api/admin/health"),
  ceoRun: (task: string, human_confirmed = false) =>
    req<CeoOut>("/api/ceo/run", { method: "POST", body: JSON.stringify({ task, human_confirmed }) }),
  departments: () => req<Department[]>("/api/departments"),
  runDepartment: (key: string, task: string, human_confirmed = false) =>
    req<CeoOut>(`/api/departments/${encodeURIComponent(key)}/run`,
      { method: "POST", body: JSON.stringify({ task, human_confirmed }) }),
  books: () => req<Book[]>("/api/books"),
  book: (slug: string) => req<{ product: Book | null; story: unknown }>(`/api/books/${slug}`),
  createStory: (idea: string) =>
    req<Record<string, unknown>>("/api/books", { method: "POST", body: JSON.stringify({ idea }) }),
  buildBook: (slug: string) =>
    req<Record<string, unknown>>(`/api/books/${slug}/build`, { method: "POST" }),
  qaBook: (slug: string) =>
    req<Record<string, unknown>>(`/api/qa/${slug}`, { method: "POST" }),
  publishRequest: (slug: string, note = "") =>
    req<{ ok: boolean; approval_id: number; status: string }>(
      `/api/books/${slug}/publish-request`,
      { method: "POST", body: JSON.stringify({ slug, note }) }),
  opportunities: (sector = "", status = "") => {
    const p = new URLSearchParams();
    if (sector) p.set("sector", sector);
    if (status) p.set("status", status);
    const q = p.toString();
    return req<Opportunity[]>(`/api/opportunities${q ? `?${q}` : ""}`);
  },
  setOpportunityStatus: (id: number, status: string) =>
    req<{ ok: boolean }>(`/api/opportunities/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  approvals: (status = "") =>
    req<Approval[]>(`/api/approvals${status ? `?status=${status}` : ""}`),
  decideApproval: (id: number, decision: "approve" | "reject", note = "") =>
    req<Record<string, unknown>>(`/api/approvals/${id}/decide`,
      { method: "POST", body: JSON.stringify({ decision, note }) }),
  reports: (limit = 60) => req<Report[]>(`/api/reports?limit=${limit}`),
  audit: (limit = 40) => req<AuditEntry[]>(`/api/audit?limit=${limit}`),
  tasks: (limit = 40) => req<Record<string, unknown>[]>(`/api/tasks?limit=${limit}`),
  settings: () => req<Settings>("/api/settings"),
  setAutonomy: (level: number) =>
    req<{ ok: boolean; autonomy_level: number }>("/api/settings/autonomy",
      { method: "POST", body: JSON.stringify({ level }) }),
  downloadBook: async (slug: string) => {
    const resp = await fetch(`${BASE}/api/books/${encodeURIComponent(slug)}/pdf`, {
      headers: token() ? { Authorization: `Bearer ${token()}` } : {},
    });
    if (!resp.ok) throw new ApiError(resp.status, `HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${slug}.pdf`; a.click();
    URL.revokeObjectURL(url);
  },
  downloadReport: async (id: number, filename: string) => {
    const resp = await fetch(`${BASE}/api/reports/${id}/download`, {
      headers: token() ? { Authorization: `Bearer ${token()}` } : {},
    });
    if (!resp.ok) throw new ApiError(resp.status, `HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },
  agents: () => req<AgentCard[]>("/api/agents"),
  capabilities: () => req<Capability[]>("/api/capabilities"),
  observability: () => req<Observability>("/api/observability"),
};
