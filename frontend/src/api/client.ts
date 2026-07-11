/**
 * Typed client for the Forensic Wace REST API (mirrors services/api schemas).
 * All paths are relative: vite dev-server and nginx both proxy /api.
 */

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    // a dead session anywhere in the app sends the user back to the login
    // screen (AuthProvider listens); /auth/* handles its own 401s
    if (response.status === 401 && !path.startsWith("/auth/")) {
      window.dispatchEvent(new Event("fw:unauthorized"));
    }
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** DELETE endpoints answer 204 with no body, so request<T>'s .json() does not apply. */
async function requestDelete(path: string): Promise<void> {
  const response = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, detail);
  }
}

// --- Types -------------------------------------------------------------

export type Platform = "ios" | "android";

export interface Me {
  id: number | null;
  username: string;
  role: "admin" | "analyst";
  auth_disabled: boolean;
}

export interface UserAccount {
  id: number;
  username: string;
  role: "admin" | "analyst";
  is_active: boolean;
  created_at: string | null;
  last_login: string | null;
}

export interface AuditEntry {
  id: number;
  at: string;
  user_id: number | null;
  username: string | null;
  action: string;
  resource: string | null;
  detail: string | null;
}

export interface IosBackup {
  udid: string;
  device_name: string | null;
  ios_version: string | null;
  serial_number: string | null;
  device_type: string | null;
  backup_date: string | null;
}

export interface AndroidBackup {
  folder: string;
  db_file: string;
  size_mb: number | null;
  created_at: string | null;
}

export interface DatabaseFingerprint {
  sha256: string;
  md5: string;
  size_mb: number | null;
}

export interface SchemaInfo {
  id?: string;
  display_name?: string;
  capabilities?: Record<string, boolean>;
  missing_optional_tables?: string[];
  // present instead of the fields above when no descriptor matched
  error?: string;
  user_version?: number;
  tables?: Record<string, string[]>;
}

export interface BackupDetail {
  info?: IosBackup | null;
  folder?: string;
  db_file?: string;
  database: DatabaseFingerprint;
  schema?: SchemaInfo;
}

export interface PrivateChat {
  counters: Record<string, number | string | null>;
  messages: Record<string, unknown>[];
}

export interface AnalyzerStatus {
  name: string;
  available: boolean;
  detail: string;
}

export type Capability = "pii" | "password" | "transcription" | "ocr" | "caption";

export interface InstalledAnalyzer {
  key: string;
  name: string;
  version: string;
  type: "builtin" | "http";
  capabilities: Capability[];
  input: "text" | "audio" | "image";
  trust: "local" | "cloud";
  enabled: boolean;
  endpoint: string | null;
  image_digest: string | null;
  config: Record<string, unknown>;
}

export interface AnalysisRequest {
  platform: Platform;
  backup_id: string;
  db_file?: string;
  date_from?: string | null;
  date_to?: string | null;
  received: boolean;
  sent: boolean;
  contacts: string[];
  groups: string[];
  message_types: string[];
  analyzers: string[];
}

export interface Process {
  process_id: string;
  platform: string | null;
  backup_id: string | null;
  status: string | null;
  details: string | null;
  start_time: string | null;
  end_time: string | null;
  analyzers: string[];
  total_messages: number;
  analyzed_messages: number;
  failed_messages: number;
}

/** Live process updates via Server-Sent Events; returns an unsubscribe function. */
export function subscribeAnalysisEvents(
  processId: string,
  onUpdate: (process: Process) => void,
  onEnd?: () => void,
): () => void {
  const source = new EventSource(`${BASE}/analyses/${encodeURIComponent(processId)}/events`);
  source.onmessage = (event) => {
    const process = JSON.parse(event.data) as Process;
    onUpdate(process);
    if (process.status === "Finish" || process.status === "Error") {
      source.close();
      onEnd?.();
    }
  };
  source.onerror = () => {
    source.close();
    onEnd?.();
  };
  return () => source.close();
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string | null;
  backup_count: number;
}

export interface ProjectBackup {
  id: string;
  platform: Platform;
  identifier: string;
  status: "processing" | "hydrating" | "stored" | "error";
  detail: string | null;
  original_filename: string | null;
  size_bytes: number;
  file_count: number;
  uploaded_at: string | null;
  completed_at: string | null;
  hydrated: boolean;
}

export interface ProjectDetail extends Project {
  backups: ProjectBackup[];
}

/**
 * Upload a backup ZIP into a project with browser-side progress reporting
 * (XMLHttpRequest: fetch has no upload progress events).
 */
export function uploadProjectBackup(
  projectId: string,
  body: { file: File; platform: Platform; identifier?: string; autoHydrate: boolean },
  onProgress?: (percent: number) => void,
): Promise<ProjectBackup> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/projects/${encodeURIComponent(projectId)}/backups`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as ProjectBackup);
      } else {
        let detail = xhr.statusText;
        try {
          detail = JSON.parse(xhr.responseText).detail ?? detail;
        } catch {
          /* non-JSON error body */
        }
        reject(new ApiError(xhr.status, detail));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error during upload"));
    const form = new FormData();
    form.append("file", body.file);
    form.append("platform", body.platform);
    if (body.identifier) form.append("identifier", body.identifier);
    form.append("auto_hydrate", String(body.autoHydrate));
    xhr.send(form);
  });
}

export interface Finding {
  type: string | null;
  value: string | null;
  source: string;
  analyzer_version: string | null;
  analyzer_digest: string | null;
}

export interface TextResult {
  msg_id: string;
  text: string;
  date: string | null;
  piis: Finding[];
  passwords: Finding[];
}

// --- Endpoints ------------------------------------------------------------

export const api = {
  login: (username: string, password: string) =>
    request<Me>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  logout: () => fetch(`${BASE}/auth/logout`, { method: "POST" }).then(() => undefined),
  me: () => request<Me>("/auth/me"),

  listUsers: () => request<UserAccount[]>("/users"),
  createUser: (username: string, password: string, role: string) =>
    request<UserAccount>("/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, role }),
    }),
  updateUser: (userId: number, body: { role?: string; is_active?: boolean; password?: string }) =>
    request<UserAccount>(`/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listAudit: (limit = 200) => request<AuditEntry[]>(`/audit?limit=${limit}`),

  listIosBackups: () => request<IosBackup[]>("/backups/ios"),
  listAndroidBackups: () => request<AndroidBackup[]>("/backups/android"),
  backupDetail: (platform: Platform, id: string) =>
    request<BackupDetail>(`/backups/${platform}/${encodeURIComponent(id)}`),

  chats: (platform: Platform, id: string) =>
    request<Record<string, unknown>[]>(`/backups/${platform}/${encodeURIComponent(id)}/chats`),
  privateChat: (platform: Platform, id: string, phone: string, typeFilter?: string) => {
    const query = typeFilter ? `?type_filter=${encodeURIComponent(typeFilter)}` : "";
    return request<PrivateChat>(
      `/backups/${platform}/${encodeURIComponent(id)}/chats/${encodeURIComponent(phone)}/messages${query}`,
    );
  },
  groups: (platform: Platform, id: string) =>
    request<Record<string, unknown>[]>(`/backups/${platform}/${encodeURIComponent(id)}/groups`),
  groupChat: (id: string, group: string, typeFilter?: string) => {
    const query = typeFilter ? `?type_filter=${encodeURIComponent(typeFilter)}` : "";
    return request<PrivateChat>(
      `/backups/ios/${encodeURIComponent(id)}/groups/${encodeURIComponent(group)}/messages${query}`,
    );
  },
  gpsLocations: (platform: Platform, id: string) =>
    request<Record<string, unknown>[]>(`/backups/${platform}/${encodeURIComponent(id)}/gps-locations`),
  blockedContacts: (id: string) =>
    request<Record<string, unknown>[]>(`/backups/ios/${encodeURIComponent(id)}/blocked-contacts`),

  analyzersStatus: () => request<AnalyzerStatus[]>("/analyzers/status"),
  listAnalyzers: () => request<InstalledAnalyzer[]>("/analyzers"),
  registerAnalyzer: (endpoint: string, config: Record<string, unknown> = {}) =>
    request<InstalledAnalyzer>("/analyzers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint, config }),
    }),
  updateAnalyzer: (key: string, body: { enabled?: boolean; config?: Record<string, unknown> }) =>
    request<InstalledAnalyzer>(`/analyzers/${encodeURIComponent(key)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  uninstallAnalyzer: (key: string) => requestDelete(`/analyzers/${encodeURIComponent(key)}`),

  submitAnalysis: (body: AnalysisRequest) =>
    request<{ process_id: string; status: string }>("/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listAnalyses: () => request<Process[]>("/analyses"),
  analysis: (processId: string) => request<Process>(`/analyses/${encodeURIComponent(processId)}`),
  analysisResults: (processId: string) =>
    request<TextResult[]>(`/analyses/${encodeURIComponent(processId)}/results`),

  verifyReport: (report: File, token: File) => {
    const form = new FormData();
    form.append("report", report);
    form.append("token", token);
    return request<{ verified: boolean }>("/reports/verify", { method: "POST", body: form });
  },

  listProjects: () => request<Project[]>("/projects"),
  createProject: (name: string, description: string) =>
    request<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    }),
  projectDetail: (projectId: string) => request<ProjectDetail>(`/projects/${encodeURIComponent(projectId)}`),
  deleteProject: (projectId: string) => requestDelete(`/projects/${encodeURIComponent(projectId)}`),
  projectBackup: (projectId: string, backupId: string) =>
    request<ProjectBackup>(
      `/projects/${encodeURIComponent(projectId)}/backups/${encodeURIComponent(backupId)}`,
    ),
  hydrateProjectBackup: (projectId: string, backupId: string) =>
    request<ProjectBackup>(
      `/projects/${encodeURIComponent(projectId)}/backups/${encodeURIComponent(backupId)}/hydrate`,
      { method: "POST" },
    ),
  deleteProjectBackup: (projectId: string, backupId: string, purgeLocal: boolean) =>
    requestDelete(
      `/projects/${encodeURIComponent(projectId)}/backups/${encodeURIComponent(backupId)}?purge_local=${purgeLocal}`,
    ),
};

/** URL of a signed PDF export (plain link → browser download). */
export function exportUrl(id: string, kind: string): string {
  return `${BASE}/backups/ios/${encodeURIComponent(id)}/exports/${kind}`;
}

/** URL of an iOS media file / profile picture. */
export function mediaUrl(id: string, params: { relativePath?: string; profileOf?: string }): string {
  const query = params.relativePath
    ? `relative_path=${encodeURIComponent(params.relativePath)}`
    : `profile_of=${encodeURIComponent(params.profileOf ?? "")}`;
  return `${BASE}/backups/ios/${encodeURIComponent(id)}/media?${query}`;
}
