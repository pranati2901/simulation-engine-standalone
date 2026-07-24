import type {
  AssetType, ControlType, TechniqueType, ScenarioSummary, Topology,
  RunConfig, RunSummary, SimEvent, ReportContent, Dashboard, RoleInfo, WorkflowDef,
  LiveSessionSummary, LiveMission, LabStatus, LabToolRegistry,
  StudioDomain, StudioFault, StudioPreset, StudioSpec, StudioScenario,
  StudioRunResult, StudioRunSummary, StudioProcedure, StudioGrade, StudioSettings,
} from "./types";

let authToken: string | null = localStorage.getItem("gc_token");
export function setAuthToken(t: string | null) {
  authToken = t;
  if (t) localStorage.setItem("gc_token", t);
  else localStorage.removeItem("gc_token");
}
function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}
function on401() {
  // Login is disabled in the embedded SimCore build — do not redirect to a (nonexistent)
  // /login route. Auth is optional on the backend, so this rarely fires.
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: authHeaders() });
  if (r.status === 401) { on401(); throw new Error("unauthenticated"); }
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}
async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (r.status === 401 && !url.includes("/auth/login")) { on401(); throw new Error("unauthenticated"); }
  if (!r.ok) throw new Error(`${r.status} ${url}: ${await r.text()}`);
  return r.json();
}
async function del<T>(url: string): Promise<T> {
  const r = await fetch(url, { method: "DELETE", headers: authHeaders() });
  if (r.status === 401) { on401(); throw new Error("unauthenticated"); }
  if (!r.ok) throw new Error(`${r.status} ${url}: ${await r.text()}`);
  return r.json();
}

export interface AuthUser { email: string; name: string; role: string }

export const api = {
  // ---- Auth ----
  login: (body: { email: string; password: string }) =>
    post<{ token: string; user: AuthUser }>("/api/auth/login", body),
  me: () => get<AuthUser>("/api/auth/me"),

  assets: () => get<AssetType[]>("/api/catalog/assets"),
  controls: () => get<ControlType[]>("/api/catalog/controls"),
  techniques: () => get<TechniqueType[]>("/api/catalog/techniques"),
  roles: () => get<RoleInfo[]>("/api/catalog/roles"),
  workflows: () => get<WorkflowDef[]>("/api/catalog/workflows"),

  scenarios: () => get<ScenarioSummary[]>("/api/scenarios"),
  scenario: (id: string) => get<any>(`/api/scenarios/${id}`),
  topology: (id: string) => get<Topology>(`/api/scenarios/${id}/topology`),
  deleteScenario: (id: string) => del<{ id: string; deleted: boolean }>(`/api/scenarios/${id}`),

  launch: (body: { scenario_id: string; environment_spec?: Topology; config?: RunConfig; operator?: string }) =>
    post<RunSummary>("/api/runs", body),
  runs: (limit = 20) => get<RunSummary[]>(`/api/runs?limit=${limit}`),
  run: (id: string) => get<RunSummary>(`/api/runs/${id}`),
  runEvents: (id: string) => get<SimEvent[]>(`/api/runs/${id}/events`),
  report: (id: string) => get<ReportContent>(`/api/runs/${id}/report`),

  dashboard: () => get<Dashboard>("/api/dashboard"),
  leaderboard: () => get<any[]>("/api/leaderboard"),

  // ---- Live multiplayer ----
  liveSessions: () => get<LiveSessionSummary[]>("/api/live/sessions"),
  liveMissions: () => get<LiveMission[]>("/api/live/missions"),
  liveSession: (id: string) => get<LiveSessionSummary & { players: any[] }>(`/api/live/sessions/${id}`),
  createLiveSession: (body: { host_name: string; mission_id?: string; scenario_id?: string }) =>
    post<{ session_id: string; player_id: string; scenario_name: string; status: string }>("/api/live/sessions", body),
  joinLiveSession: (id: string, body: { name: string }) =>
    post<{ session_id: string; player_id: string; scenario_name: string; status: string }>(`/api/live/sessions/${id}/join`, body),

  // ---- Guided scenarios (the 3 demo walkthroughs: W1/R5/C5) ----
  guidedScenarios: () => get<any[]>("/api/live/guided"),
  guidedScenario: (id: string) => get<any>(`/api/live/guided/${id}`),
  createGuidedSession: (body: { host_name: string; scenario_id: string; mode?: string }) =>
    post<{ session_id: string; player_id: string; scenario_id: string; scenario_name: string; status: string }>(
      "/api/live/guided/sessions", body),

  // ---- Live-fire lab (real VMs + real tools) ----
  labStatus: () => get<LabStatus>("/api/lab/status"),
  labTools: () => get<LabToolRegistry>("/api/lab/tools"),
  labUp: () => post<{ ok: boolean; detail: string; command: string }>("/api/lab/up", {}),
  labDown: () => post<{ ok: boolean; detail: string; command: string }>("/api/lab/down", {}),

  // ---- Scenario Studio (LLM-driven what-if + training) ----
  studioDomains: () => get<{ domains: StudioDomain[] }>("/api/studio/domains"),
  studioFaults: (domain: string) => get<{ domain: string; faults: StudioFault[] }>(`/api/studio/faults?domain=${domain}`),
  studioPresets: (domain: string) => get<{ domain: string; presets: StudioPreset[] }>(`/api/studio/presets?domain=${domain}`),
  studioScenarios: (domain?: string) =>
    get<{ scenarios: StudioScenario[] }>(`/api/studio/scenarios${domain ? `?domain=${domain}` : ""}`),
  studioAuthor: (body: { description: string; domain: string; kind: string; horizon_min?: number; save?: boolean }) =>
    post<{ spec: StudioSpec; scenario: StudioScenario | null; ai_mode: string }>("/api/studio/scenarios/author", body),
  studioDeleteScenario: (id: string) => del<{ id: string; deleted: boolean }>(`/api/studio/scenarios/${id}`),
  studioRun: (body: { scenario_id?: string; spec?: StudioSpec; analyze?: boolean }) =>
    post<StudioRunResult>("/api/studio/runs", body),
  studioRuns: (limit = 25) => get<{ runs: StudioRunSummary[] }>(`/api/studio/runs?limit=${limit}`),
  studioRunGet: (id: string) => get<StudioRunResult>(`/api/studio/runs/${id}`),
  studioProcedure: (body: { domain: string; system: string; fault: string; title?: string; context?: string }) =>
    post<{ procedure: StudioProcedure }>("/api/studio/training/procedure", body),
  studioGrade: (body: { procedure: StudioProcedure; actions: { step_id: string; action: string }[] }) =>
    post<StudioGrade>("/api/studio/training/grade", body),
  studioDirector: (procedure: StudioProcedure) =>
    post<{ beats: any[] }>("/api/studio/training/director", { procedure }),
  studioCoach: (body: { messages: { role: string; content: string }[]; context: Record<string, any> }) =>
    post<{ reply: string }>("/api/studio/training/coach", body),
  studioSettings: () => get<StudioSettings>("/api/studio/settings"),   // read-only AI status
};
