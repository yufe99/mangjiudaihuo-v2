/**
 * API client for the backend.
 *
 * Reads base URL from NEXT_PUBLIC_API_BASE env (default: http://localhost:8000).
 * Stores JWT in localStorage under "mjdh_token".
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const API_PREFIX = "/api/v1";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("mjdh_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("mjdh_token", token);
  else window.localStorage.removeItem("mjdh_token");
}

export function isAuthed(): boolean {
  return !!getToken();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail ?? data);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data as T;
}

// ===== Auth =====
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const authApi = {
  register: (email: string, password: string, name?: string) =>
    request<AuthTokens>("POST", "/auth/register", { email, password, name }),
  login: (email: string, password: string) =>
    request<AuthTokens>("POST", "/auth/login", { email, password }),
  me: () => request<{ id: number; email: string; name: string; credits: number; plan: string }>("GET", "/auth/me"),
};

// ===== Projects =====
export interface Project {
  id: number;
  name: string;
  type: string;
  style: string;
  topic: string;
  product_url: string;
  episode_count: number;
  seconds_per_episode: number;
  aspect_ratio: string;
  characters_status: string;
  storyboard_status: string;
  video_status: string;
  final_video_path: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  type?: string;
  style?: string;
  topic?: string;
  product_url?: string;
  product_detail?: string;
  episode_count?: number;
  seconds_per_episode?: number;
  aspect_ratio?: string;
}

export const projectApi = {
  list: () => request<Project[]>("GET", "/projects"),
  create: (data: ProjectCreate) => request<Project>("POST", "/projects", data),
  get: (id: number) => request<Project>("GET", `/projects/${id}`),
  update: (id: number, data: Partial<ProjectCreate>) =>
    request<Project>("PATCH", `/projects/${id}`, data),
  remove: (id: number) => request<void>("DELETE", `/projects/${id}`),
};

// ===== Script =====
export interface ScriptData {
  logline: string;
  style: string;
  characters: Array<{ name: string; description: string; appearance: string }>;
  assets: Array<{ type: string; name: string; description: string }>;
  episodes: Array<{ index: number; title: string; outline: string }>;
}

export const scriptApi = {
  generate: (projectId: number) =>
    request<ScriptData>("POST", `/projects/${projectId}/script/generate`),
  get: (projectId: number) =>
    request<ScriptData>("GET", `/projects/${projectId}/script`),
};

// ===== Settings =====
export interface SettingsData {
  billing_mode: string;
  provider_configs: Record<string, Record<string, string>>;
  default_llm_model: string;
  default_image_model: string;
  default_video_model: string;
  notify_email: boolean;
}

export const settingsApi = {
  get: () => request<SettingsData>("GET", "/settings"),
  update: (data: Partial<SettingsData>) =>
    request<SettingsData>("PATCH", "/settings", data),
};