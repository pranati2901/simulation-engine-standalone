import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ScenarioSummary } from "../api/types";

const FILTERS = [
  { key: "all", label: "All" }, { key: "red", label: "Red Team" }, { key: "blue", label: "Blue Team" },
  { key: "purple", label: "Purple" }, { key: "soc", label: "SOC" }, { key: "ics", label: "ICS/OT" },
  { key: "cloud", label: "Cloud" }, { key: "edu", label: "Educational" },
];

// Educational simulation scenarios (interactive, SOC-console based)
const EDU_SCENARIOS = [
  {
    id: "scn-wannacry-w1", name: "Operation Tripwire",
    subtitle: "Breach the Hospital Patient Portal",
    description: "Attack a custom hospital patient portal from a real Kali shell: fingerprint it, pull a leaked DB backup, and SQL-inject the login to reach protected patient records and capture the flag.",
    icon: "fa-virus", color: "#C8413E", gradient: "linear-gradient(135deg, #C8413E, #E07A3E)",
    stages: 4, duration: 20, mitre: ["T1046", "T1190", "T1213", "T1078"],
    difficulty: ["Standard", "Pressure"],
    setting: "Mercy Regional Health · SQL injection", role: "Solo · Kali terminal",
  },
  {
    id: "scn-r5-phishing", name: "R5 — Phishing to Encrypt",
    subtitle: "Mailbox → Remote Code Execution",
    description: "From a real Kali shell, brute a weak webmail mailbox, log in, then abuse the diagnostics tool's command injection to land code execution and read the flag — the ransomware crew's foothold.",
    icon: "fa-envelope-open-text", color: "#7c3aed", gradient: "linear-gradient(135deg, #7c3aed, #C8413E)",
    stages: 4, duration: 25, mitre: ["T1110", "T1078", "T1059", "T1203"],
    difficulty: ["Standard", "Pressure"],
    setting: "MediumCorp SecureMail · cmd injection", role: "Solo · Kali terminal",
  },
  {
    id: "scn-c5-edr", name: "C5 — EDR Outage Exploitation",
    subtitle: "Attack While the Agent is Blind",
    description: "The EDR is offline and the IT admin console is wide open. Password-spray the admins from a real Kali shell, log in, and use the remote runbook to execute commands and read the flag.",
    icon: "fa-eye-slash", color: "#0284c7", gradient: "linear-gradient(135deg, #5B7FB0, #c084fc)",
    stages: 4, duration: 25, mitre: ["T1110.003", "T1078", "T1059", "T1569"],
    difficulty: ["Standard", "Pressure"],
    setting: "GlobalTech Admin Console · spray + RCE", role: "Solo · Kali terminal",
  },
];

export default function Library() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [deleting, setDeleting] = useState<string | null>(null);
  const { data, isLoading } = useQuery<ScenarioSummary[]>({ queryKey: ["scenarios"], queryFn: api.scenarios });

  const scenarios = (data ?? []).filter((s) => filter === "all" || s.type === filter || s.industry === filter);

  const removeScenario = async (s: ScenarioSummary) => {
    if (!confirm(`Delete scenario "${s.name}"? This cannot be undone.`)) return;
    setDeleting(s.id);
    try {
      await api.deleteScenario(s.id);
      await qc.invalidateQueries({ queryKey: ["scenarios"] });
    } catch (e) {
      alert("Delete failed: " + e);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <>
      <div className="section-header">
        <h1>Scenario Library</h1>
        <p>Hands-on hack labs — drive a <b>real Kali terminal</b> against a custom vulnerable app built for each mission. Follow the objectives, capture the flag.</p>
      </div>

      <div className="scenario-filters">
        {FILTERS.map((f) => (
          <button key={f.key} className={"filter-chip" + (filter === f.key ? " active" : "")} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Educational Simulations */}
      {(filter === "all" || filter === "edu") && (
        <>
          <div style={{ marginTop: 24, marginBottom: 12 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}><i className="fa fa-terminal" style={{ marginRight: 8, color: "var(--gc-orange)" }} />Hack Lab — Real Kali Terminal</h2>
            <p style={{ fontSize: 12.5, color: "var(--gc-muted)" }}>Each scenario ships with a custom, intentionally vulnerable web app on the live range. The inline Kali shell is yours — recon, exploit, and capture the flag, guided by per-phase objectives and suggested commands.</p>
          </div>
          <div className="scenario-grid">
            {EDU_SCENARIOS.map((s) => (
              <div key={s.id} className="scenario-card" style={{ cursor: "pointer", position: "relative" }}
                onClick={() => nav(`/play/${s.id}?mode=practice`)}>
                <span style={{ position: "absolute", top: 14, right: 14, fontSize: 9, fontWeight: 700, letterSpacing: .5,
                  padding: "3px 8px", borderRadius: 20, background: "rgba(234,88,12,.12)", color: "var(--gc-orange)" }}>
                  <i className="fa fa-terminal" /> HACK LAB
                </span>
                <div style={{ width: 46, height: 46, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", background: s.gradient, marginBottom: 12 }}>
                  <i className={`fa ${s.icon}`} style={{ color: "#fff", fontSize: 19 }} />
                </div>
                <div className="scenario-name">{s.name}</div>
                <div style={{ fontSize: 11.5, color: s.color, fontWeight: 600, marginBottom: 7 }}>{s.subtitle}</div>
                <div className="scenario-desc">{s.description}</div>
                <div style={{ fontSize: 11.5, color: "var(--gc-muted)", margin: "8px 0 4px" }}>
                  <i className="fa fa-location-dot" /> {s.setting} · <i className="fa fa-users" /> {s.role}
                </div>
                <div className="scenario-meta">
                  <div className="meta-item"><i className="fa fa-layer-group" /> {s.stages} phases</div>
                  <div className="meta-item"><i className="fa fa-clock" /> {s.duration}m</div>
                  <div className="meta-item"><i className="fa fa-shield-halved" /> {s.mitre.length} techniques</div>
                </div>
                <button className="btn btn-primary" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>
                  <i className="fa fa-terminal" /> Enter hack lab
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Engine Simulations */}
      {filter !== "edu" && (
        <div style={{ marginTop: 24, marginBottom: 12 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700 }}><i className="fa fa-cogs" style={{ marginRight: 8, color: "var(--gc-accent)" }} />Engine Simulations</h2>
          <p style={{ fontSize: 12, color: "var(--gc-muted)" }}>Model-driven, deterministic simulations with full AAR reporting</p>
        </div>
      )}
      {isLoading && <div className="center-empty"><span className="spinner" /> Loading…</div>}
      {filter !== "edu" && <div className="scenario-grid">
        {scenarios.map((s) => (
          <div key={s.id} className="scenario-card" onClick={() => nav(`/launch/${s.id}`)}>
            <div className={`scenario-badge ${s.badge}`}>{s.label}</div>
            <div className="scenario-name">{s.name}</div>
            <div className="scenario-desc">{s.description}</div>
            <div className="scenario-meta">
              <div className="meta-item"><i className="fa fa-clock" /> {s.nominal_duration_min}m</div>
              <div className="meta-item"><i className="fa fa-layer-group" /> {s.phases.length} phases</div>
              <div className="meta-item"><i className="fa fa-bolt" /> {s.step_count} steps</div>
              <div className="meta-item"><i className="fa fa-industry" /> {s.industry}</div>
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
              <button className="btn btn-ghost" style={{ fontSize: 10, padding: "4px 10px" }}
                onClick={(e) => { e.stopPropagation(); nav(`/builder?clone=${s.id}`); }}>
                <i className="fa fa-copy" /> Clone
              </button>
              {!s.is_seed && (
                <button className="btn btn-ghost" style={{ fontSize: 10, padding: "4px 10px", color: "var(--gc-red)" }}
                  disabled={deleting === s.id}
                  title="Delete this custom scenario"
                  onClick={(e) => { e.stopPropagation(); removeScenario(s); }}>
                  {deleting === s.id
                    ? <><span className="spinner" /> Deleting…</>
                    : <><i className="fa fa-trash" /> Delete</>}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>}
    </>
  );
}
