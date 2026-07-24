export interface AssetType {
  key: string; name: string; category: string; icon: string; description: string;
  default_zone: string; default_criticality: number; default_data_sensitivity: number;
  supported_controls: string[];
}
export interface ControlType {
  key: string; name: string; icon: string; description: string;
  default_scope: string; default_enabled: boolean; attaches_to: string[];
}
export interface TechniqueType {
  key: string; name: string; mitre: string; tactic: string; description: string;
  severity: string; detects: string[]; prevents: string[];
}
export interface ScenarioSummary {
  id: string; name: string; type: string; industry: string; badge: string; label: string;
  description: string; is_seed: boolean; phases: string[]; nominal_duration_min: number;
  difficulties: string[]; objectives: { red: string[]; blue: string[] };
  step_count: number; mitre_tactics: string[];
}
export interface AssetSpec {
  id: string; type: string; name?: string; role?: string; zone?: string;
  criticality?: number; data_sensitivity?: number; props?: Record<string, unknown>;
}
export interface ControlSpec {
  id: string; type: string; name?: string; enabled: boolean;
  scope?: string; targets?: string[];
}
export interface Topology { assets: AssetSpec[]; controls: ControlSpec[]; }

export interface RoleInfo { role: string; name: string; mission: string; description: string; }
export interface TaskEffect { kind: string; scope?: string | null; magnitude: number; }
export interface WorkflowStepDef {
  id: string; team: string; kind: string; label: string; description: string;
  phase_hint: string; irp_ref: string; default_enabled: boolean; removable: boolean;
  effects: TaskEffect[];
}
export interface WorkflowDef {
  actor: string; id: string; name: string; description: string; steps: WorkflowStepDef[];
}
export interface RoleTask { id: string; label: string; description?: string; status: string; }

export interface RunConfig {
  difficulty: "Easy" | "Medium" | "Hard" | "Expert";
  readiness: number; duration_min: number; industry?: string; seed?: number;
  focus_role?: string; phase_range?: [number, number] | null;
  workflow_config?: { enabled: Record<string, string[]> };
}
export interface RunSummary {
  id: string; scenario_id: string; scenario_name: string; operator?: string | null;
  status: string; duration_s: number; focus_role?: string; scores: Record<string, number>;
  kpis: Record<string, number>; summary: Record<string, any>; created_at: string;
  environment?: AssetNode[]; objectives?: { red: ObjStatus[]; blue: ObjStatus[] };
  workflows?: WorkflowDef[]; role_tasks?: Record<string, RoleTask[]>;
}
export interface ObjStatus { text: string; met: boolean; }
export interface AssetNode {
  id: string; type: string; name: string; role?: string | null; zone: string;
  criticality: number; security_state: string; health: string;
}
export interface SimEvent {
  seq: number; t: number; type: string; side: string; actor: string;
  phase?: string | null; severity: string; title: string; message: string;
  technique?: string | null; asset_id?: string | null; asset_label?: string | null;
  channel?: string | null; data: Record<string, any>;
}
export interface RoleScorecard {
  role: string; title: string; score: number; tasks_done: number; tasks_total: number;
  kpis: Record<string, string | number>; headline: string; tasks: RoleTask[];
}
export interface ReportContent {
  scenario_name: string; duration_min: number; focus_role?: string; exec_summary: string;
  role_scorecards?: RoleScorecard[];
  timeline: any[]; mitre_map: any[]; scorecard: Record<string, any>;
  regulatory_impact: { framework_name: string; message: string; deadline_hours: number; penalty?: string; on_time?: boolean; framework_id?: string }[];
  financial_impact: { estimate_low_usd: number; estimate_high_usd: number; drivers: string[] };
  recommendations: string[]; maturity_score: { score: number; band: string; breakdown?: Record<string, number> };
  corrective_actions: { priority: string; action: string }[];
  key_findings?: { strengths: string[]; weaknesses: string[]; critical_moment: string };
  attack_path?: { t: number; clock: string; technique: string; name: string; target_name: string; phase: string; severity: string; result: string; blocked_by?: string }[];
  per_asset?: { id: string; name: string; type: string; zone: string; criticality: number; data_sensitivity: number; initial_state: string; final_state: string; final_health: string; times_targeted: number; times_blocked: number; times_detected: number; contained: boolean; avg_dwell_s: number; detected_by: string[]; risk_score: number }[];
  control_effectiveness?: { type: string; name: string; detections: number; blocks: number; techniques_detected: string[]; techniques_blocked: string[]; avg_dwell_s: number; total_actions: number }[];
  dwell_analysis?: { overall: { mean_s: number; median_s: number; min_s: number; max_s: number; count: number }; by_asset: { asset: string; mean_s: number; count: number }[]; by_phase: { phase: string; mean_s: number; count: number }[]; worst: { asset: string | null; max_dwell_s: number } };
  zone_analysis?: { zone: string; assets_total: number; assets_compromised: number; assets_contained: number; assets_down: number; assets_safe: number; breach_pct: number; status: string; asset_names: string[] }[];
  credential_timeline?: { t: number; clock: string; scope: string; rank: number; technique: string; description: string; target: string }[];
}
export interface Dashboard {
  total_runs: number; total_scenarios: number; avg_blue_score: number; critical_findings: number;
  recent_runs: any[]; threat_coverage: { label: string; pct: number }[];
  readiness: Record<string, number>;
}

// ---- Live multiplayer ------------------------------------------------------
export interface LivePlayer { id: string; name: string; role: string | null; is_host: boolean; connected: boolean; }
export interface LiveSessionSummary {
  id: string; scenario_name: string; status: string; players: number; player_count: number;
  roles: Record<string, number>; created_at: number;
  guided?: boolean; scenario_id?: string | null;
}
export interface LiveStage { id: string; name: string; summary: string; ref: string; }
export interface LiveMission {
  id: string; name: string; klass: string; cadence: string; tagline: string; briefing: string;
  primary_objective: string | null; stealth_weight: number; forced_profile: string | null;
  recommended_profile: string; headline_metric: string; needs: string[];
  success: { red?: string; soc?: string; blue?: string };
}
export interface LiveProfile { id: string; name: string; description: string; budget: number; traits: string[]; assumed_breach: boolean; }
export interface LiveTarget { id: string; name: string; type: string; zone: string; }
export interface LiveAction {
  id: string; stage: string; label: string; description: string; tactic: string; mitre: string;
  base_noise: number; noise: number; score: number; available: boolean; reason: string; done: boolean;
  target_mode: "none" | "auto" | "select"; target_type: string | null; targets: LiveTarget[];
  watched_by: string[]; objective: string | null; opsec: string;
}
export interface LiveObjective { key: string; label: string; met: boolean; primary: boolean; }
export interface LiveIntel { t: number; text: string; }
export interface LiveFinal {
  objective_met: boolean; any_objective_met: boolean; secondary_met: number; action_score: number; stealth_bonus: number;
  discipline_bonus: number; overspend_penalty: number; total_score: number; noise_spent: number;
  budget: number; exposure_pct: number; actions_taken: number; objectives: LiveObjective[];
}
export interface LiveOperator {
  profile: string; budget: number; noise_spent: number; exposure_pct: number; noise_multiplier: number;
  score: number; concluded: boolean; final: LiveFinal | null; cred_scope: string; footholds: string[];
  objectives: LiveObjective[]; intel: LiveIntel[]; history: any[]; flags: string[]; world_flags: string[];
  actions: LiveAction[];
}
export interface LiveBlueAction {
  id: string; stage: string; label: string; description: string; framework: string; score: number;
  available: boolean; reason: string; done: boolean;
  target_mode: "none" | "select"; target_type: string | null; targets: LiveTarget[]; note: string;
}
export interface LiveBlueFinal {
  eviction_complete: boolean; coverage_pct: number; detected: number; detectable: number; mttc_s: number;
  contained: number; footholds_total: number; prevented: string[]; action_score: number;
  eviction_bonus: number; prevention_bonus: number; total_score: number; actions_taken: number;
}
export interface LiveDefender {
  score: number; concluded: boolean; final: LiveBlueFinal | null;
  monitoring: string[]; capabilities: string[]; coverage_pct: number; detected: number; detectable: number;
  mttc_s: number; contained: number; footholds_total: number; prevented: string[]; defense_flags: string[];
  objectives: LiveObjective[]; history: any[]; actions: LiveBlueAction[];
}
export interface LiveSocAction {
  id: string; stage: string; label: string; description: string; ref: string; score: number;
  available: boolean; reason: string; done: boolean; target_mode: "none" | "alert";
  note: string; targets: LiveTarget[];
}
export interface LiveAlert {
  id: string; t: number; action_id: string; label: string; mitre: string; tactic: string;
  severity: string; asset_id: string | null; asset_label: string | null; status: string;
  p_label: string; p_rank: number;
}
export interface LiveSocFinal {
  coverage_pct: number; detected: number; detectable: number; triaged: number; escalated: number;
  mtta_s: number; open_alerts: number; action_score: number; total_score: number; actions_taken: number;
}
export interface LiveSoc {
  score: number; concluded: boolean; final: LiveSocFinal | null;
  monitoring: string[]; capabilities: string[]; coverage_pct: number; detected: number; detectable: number;
  triaged: number; escalated: number; mtta_s: number; objectives: LiveObjective[]; history: any[];
  alerts: LiveAlert[]; actions: LiveSocAction[];
}
export interface LiveAsset {
  id: string; type: string; zone: string; criticality: number; role: string | null; revealed: boolean;
  name: string; security_state: string; health: string; is_foothold: boolean; incident: boolean;
}
export interface LiveReportTeam {
  score: number; breakdown?: Record<string, number>; kpis: Record<string, any>;
  objectives?: LiveObjective[]; timeline: any[]; intel?: LiveIntel[]; alerts?: LiveAlert[];
  findings: { strengths: string[]; weaknesses: string[] };
}
export interface LiveMitreStep {
  t: number; action_id: string; label: string; mitre: string; tactic: string;
  target: string | null; noise: number; detected: boolean;
}
export interface LiveMatchReport {
  session_id: string;
  mission: { id: string; name: string; klass: string; briefing: string; success: Record<string, string> };
  profile: string; result: string; verdict: string; duration_s: number;
  outcome: {
    objective_met: boolean; objectives: LiveObjective[]; assets_total: number;
    assets_compromised: number; assets_contained: number; assets_down: number;
    footholds_total: number; eviction_complete: boolean; coverage_pct: number;
  };
  teams: { red: LiveReportTeam; soc: LiveReportTeam; blue: LiveReportTeam };
  mitre: LiveMitreStep[]; recommendations: string[]; note: string;
}
export interface LiveEvent {
  seq: number; t: number; kind: string; role: string; title: string; message: string;
  severity: string; asset_id: string | null; asset_label: string | null; data: Record<string, any>;
}
// ---- Live-fire lab (real VMs + real tools) ----
export interface LabTarget { id: string; name: string; host: string; os: string; role: string; services: string[]; scenario?: string }
export interface LabStatus {
  backend: string; available: boolean; up: boolean; attacker_ready: boolean;
  targets: LabTarget[]; containers: { name: string; running: boolean }[]; detail: string;
  terminal_url: string;
  target_urls?: Record<string, string>;   // target id -> browsable http URL (when the range is up)
}
export interface LabTool {
  id: string; name: string; function: string; team: string; status: string;
  license: string; runner: string; backs: string[]; homepage: string; note: string;
}
export interface LabToolRegistry {
  counts: Record<string, number>; tools: LabTool[]; by_status: Record<string, LabTool[]>;
}

// ---- Scenario Studio (LLM-driven, domain-agnostic what-if + training) ----
export interface StudioDomain { id: string; label: string; icon: string; system: string; fault_count: number }
export interface StudioFault { id: string; label: string }
export interface StudioPreset { title: string; description: string }
export interface StudioSpec {
  name: string; domain: string; kind: string; system: string; fault: string;
  severity: number; intensity: number; horizon_min: number; description: string;
  rationale: string; expected_outcome: string; objectives: string[];
}
export interface StudioScenario {
  id: string; name: string; domain: string; kind: string; description: string;
  is_seed: boolean; spec: StudioSpec; created_at: string | null;
}
export interface StudioEvent { t_min: number; phase: string; title: string; detail: string; severity: string; actor: string }
export interface StudioKpis {
  outcome_band: string; detected: boolean; mttd_min: number; lead_time_min: number;
  peak_severity_pct: number; downtime_min: number; affected_units: number;
  mitigations_identified: number; readiness_score: number; grade: string;
}
export interface StudioRunResult {
  id: string; scenario_id: string | null; name: string; domain: string; system: string;
  status: string; duration_min: number; spec: StudioSpec; outcome_band: string; headline: string;
  events: StudioEvent[]; metrics: Record<string, any>; detections: string[]; mitigations: string[];
  risks: string[]; kpis: StudioKpis; narrative: string; ai_mode: string; created_at: string;
}
export interface StudioRunSummary { id: string; name: string; domain: string; outcome_band: string; readiness_score: number; grade: string; created_at: string }
export interface StudioProcStep {
  id: string; title: string; action: string; rationale: string; criteria: string;
  safety: boolean; requires: string[]; skip_consequence: string; wrong_order_consequence: string;
}
export interface StudioProcedure {
  title: string; fault: string; domain: string; system: string; summary: string;
  steps: StudioProcStep[]; success_criteria: string; common_mistakes: string[];
}
export interface StudioGradeLog { step_id: string; ok: boolean; severe: boolean; skipped: boolean; text: string; health_after: number }
export interface StudioGrade {
  score: number; grade: string; health_pct: number; performed: number; total: number;
  violations: number; skips: number; complete: boolean; log: StudioGradeLog[]; summary: string;
}
export interface StudioSettings { has_key: boolean; source: string; model: string; masked_key: string; ai_mode: string }

export interface LiveSnapshot {
  type: "snapshot";
  session: { id: string; scenario_name: string; status: string; host_id: string; match_result: string | null; mission: string; mission_locked: boolean; live_fire: boolean };
  scenario: { name: string; description: string; type: string; label: string; phases: string[]; objectives: { red: string[]; blue: string[] } };
  missions: LiveMission[];
  mission: LiveMission;
  players: LivePlayer[];
  stages: LiveStage[];
  blue_stages: LiveStage[];
  soc_stages: LiveStage[];
  profiles: LiveProfile[];
  roles: { id: string; interactive: boolean }[];
  auto: Record<string, boolean>;
  operator: LiveOperator | null;
  soc: LiveSoc | null;
  defender: LiveDefender | null;
  assets: LiveAsset[];
  events: LiveEvent[];
  report: LiveMatchReport | null;
}
