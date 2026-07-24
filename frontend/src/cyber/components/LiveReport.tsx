import { useState } from "react";
import type { LiveMatchReport, LiveReportTeam } from "../api/types";

const fmt = (s: number) => `${Math.floor(s / 60)}m ${s % 60}s`;
const clock = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

const TEAM = {
  red: { label: "Red — Attacker", color: "var(--gc-red)", icon: "fa-user-secret" },
  soc: { label: "SOC — Detection", color: "#22d3a8", icon: "fa-tower-observation" },
  blue: { label: "Blue — Response", color: "#5B8CFF", icon: "fa-shield-halved" },
} as const;

function TeamCard({ team, data }: { team: keyof typeof TEAM; data: LiveReportTeam }) {
  const [open, setOpen] = useState(false);
  const meta = TEAM[team];
  return (
    <div className="card" style={{ borderTop: `3px solid ${meta.color}` }}>
      <div className="card-header">
        <div className="card-title" style={{ color: meta.color }}><i className={`fa ${meta.icon}`} /> {meta.label}</div>
        <div style={{ fontFamily: "var(--mono)", fontWeight: 700, fontSize: 18, color: meta.color }}>{data.score}</div>
      </div>

      {data.breakdown && (
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 11, color: "var(--gc-muted)", marginBottom: 8 }}>
          {Object.entries(data.breakdown).map(([k, v]) => (
            <span key={k}>{k.replace(/_/g, " ")}: <b style={{ color: "var(--gc-text)" }}>{v as number}</b></span>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        {Object.entries(data.kpis).map(([k, v]) => (
          <span key={k} className="tag" style={{ fontSize: 10 }}>{k.replace(/_/g, " ")}: {Array.isArray(v) ? (v.length ? v.join(", ") : "—") : String(v)}</span>
        ))}
      </div>

      {data.findings.strengths.map((x, i) => (
        <div key={"s" + i} style={{ fontSize: 12, marginBottom: 4 }}><i className="fa fa-check" style={{ color: "var(--gc-green)", marginRight: 6 }} />{x}</div>
      ))}
      {data.findings.weaknesses.map((x, i) => (
        <div key={"w" + i} style={{ fontSize: 12, marginBottom: 4 }}><i className="fa fa-triangle-exclamation" style={{ color: "var(--gc-yellow)", marginRight: 6 }} />{x}</div>
      ))}

      <button className="btn btn-ghost" style={{ marginTop: 10, fontSize: 11, padding: "4px 10px" }} onClick={() => setOpen(!open)}>
        <i className={`fa ${open ? "fa-chevron-up" : "fa-chevron-down"}`} /> {open ? "Hide" : "Show"} actions ({data.timeline.length})
      </button>
      {open && (
        <div style={{ marginTop: 8, maxHeight: 220, overflowY: "auto" }}>
          {data.timeline.map((a: any, i: number) => (
            <div key={i} style={{ fontSize: 11.5, display: "flex", gap: 8, marginBottom: 3 }}>
              <span className="ts">{clock(a.t)}</span>
              <span>{a.label}{a.target ? ` → ${a.target}` : ""}</span>
              {typeof a.score === "number" && <span style={{ marginLeft: "auto", color: meta.color }}>+{a.score}</span>}
            </div>
          ))}
          {data.timeline.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No actions taken.</div>}
        </div>
      )}
    </div>
  );
}

export default function LiveReport({ report }: { report: LiveMatchReport }) {
  const r = report;
  const win = r.result === "red" ? "var(--gc-red)" : r.result === "blue" ? "#5B8CFF" : "var(--gc-muted)";
  const o = r.outcome;
  return (
    <div style={{ marginBottom: 24 }}>
      {/* Headline */}
      <div className="card" style={{ borderLeft: `4px solid ${win}`, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <div>
            <div style={{ fontSize: 12, color: "var(--gc-muted)", textTransform: "uppercase", letterSpacing: 1 }}>
              <i className="fa fa-file-shield" /> Mission After-Action Report · {r.mission.klass}
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 700, margin: "4px 0" }}>{r.mission.name}</h2>
            <div style={{ fontSize: 13, color: win, fontWeight: 600 }}>{r.verdict}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>profile: {r.profile.replace(/_/g, " ")} · duration {fmt(r.duration_s)}</div>
            <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
              <span className="tag" style={{ color: "var(--gc-red)" }}>RED {r.teams.red.score}</span>
              <span className="tag" style={{ color: "#22d3a8" }}>SOC {r.teams.soc.score}</span>
              <span className="tag" style={{ color: "#5B8CFF" }}>BLUE {r.teams.blue.score}</span>
            </div>
          </div>
        </div>

        {/* Outcome stats */}
        <div className="stats-row" style={{ gridTemplateColumns: "repeat(6,1fr)", marginTop: 14 }}>
          <div className="stat-card"><div className="stat-label">Objective</div><div className="stat-value" style={{ fontSize: 14, color: o.objective_met ? "var(--gc-red)" : "var(--gc-green)" }}>{o.objective_met ? "Achieved" : "Stopped"}</div></div>
          <div className="stat-card"><div className="stat-label">Coverage</div><div className="stat-value" style={{ fontSize: 18 }}>{o.coverage_pct}%</div></div>
          <div className="stat-card"><div className="stat-label">Eviction</div><div className="stat-value" style={{ fontSize: 14 }}>{o.eviction_complete ? "Complete" : "Partial"}</div></div>
          <div className="stat-card"><div className="stat-label">Compromised</div><div className="stat-value" style={{ fontSize: 18 }}>{o.assets_compromised}</div></div>
          <div className="stat-card"><div className="stat-label">Contained</div><div className="stat-value" style={{ fontSize: 18 }}>{o.assets_contained}</div></div>
          <div className="stat-card"><div className="stat-label">Down</div><div className="stat-value" style={{ fontSize: 18 }}>{o.assets_down}</div></div>
        </div>

        {/* Objectives */}
        <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 10 }}>
          {o.objectives.map((ob) => (
            <span key={ob.key} style={{ fontSize: 12 }}>
              <i className={`fa ${ob.met ? "fa-check-circle" : "fa-circle"}`} style={{ color: ob.met ? "var(--gc-red)" : "var(--gc-muted)", marginRight: 5 }} />
              {ob.label}{ob.primary ? " (primary)" : ""}
            </span>
          ))}
        </div>
      </div>

      {/* Per-team scorecards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 16 }}>
        <TeamCard team="red" data={r.teams.red} />
        <TeamCard team="soc" data={r.teams.soc} />
        <TeamCard team="blue" data={r.teams.blue} />
      </div>

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* MITRE coverage / kill-chain */}
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-sitemap" /> Attack path & detection coverage</div>
            <span className="tag">{r.mitre.filter((m) => m.detected).length}/{r.mitre.length} detected</span>
          </div>
          <div style={{ maxHeight: 320, overflowY: "auto" }}>
            {r.mitre.map((m, i) => (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, padding: "4px 0", borderBottom: "1px solid var(--gc-border)" }}>
                <span className="ts">{clock(m.t)}</span>
                <i className={`fa ${m.detected ? "fa-eye" : "fa-eye-slash"}`} style={{ color: m.detected ? "var(--gc-green)" : "var(--gc-muted)" }} title={m.detected ? "detected" : "missed"} />
                <span style={{ flex: 1 }}>{m.label}{m.target ? ` → ${m.target}` : ""}</span>
                {m.mitre && <span className="tag" style={{ fontSize: 9 }}>{m.mitre}</span>}
              </div>
            ))}
            {r.mitre.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No attack steps recorded.</div>}
          </div>
        </div>

        {/* Recommendations */}
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-lightbulb" /> Recommendations</div></div>
          {r.recommendations.map((rec, i) => (
            <div key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, marginBottom: 8 }}>
              <i className="fa fa-arrow-right" style={{ color: "var(--gc-accent, #5B8CFF)", marginTop: 3 }} />
              <span>{rec}</span>
            </div>
          ))}
          {r.recommendations.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No recommendations.</div>}
          <div className="muted" style={{ fontSize: 11, marginTop: 10, fontStyle: "italic" }}>{r.note}</div>
        </div>
      </div>
    </div>
  );
}
