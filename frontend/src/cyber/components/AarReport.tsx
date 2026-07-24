import { useState } from "react";
import "./sim/sim.css";

/* A real, readable After-Action Report for the immersive sim + guided scenarios (and tolerant of the
   live-mission shape). Rendered in the workspace result screen AND the Reports & AAR page; the Print
   button produces a clean PDF (print stylesheet isolates `.aar-print`). */

const clock = (s: number) => `${String(Math.floor((s || 0) / 60)).padStart(2, "0")}:${String((s || 0) % 60).padStart(2, "0")}`;
const TEAM: Record<string, { label: string; color: string; icon: string }> = {
  red: { label: "Red — Attacker", color: "#ef4444", icon: "fa-user-secret" },
  soc: { label: "SOC — Detection", color: "#22d3a8", icon: "fa-tower-observation" },
  blue: { label: "Blue — Response", color: "#5B8CFF", icon: "fa-shield-halved" },
};

function TeamCard({ team, data }: { team: string; data: any }) {
  const [open, setOpen] = useState(false);
  const m = TEAM[team] || { label: team, color: "#94a3b8", icon: "fa-user" };
  const tl = data.timeline || [];
  return (
    <div className="aar-card" style={{ borderTop: `3px solid ${m.color}`, marginBottom: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <b style={{ color: m.color }}><i className={`fa ${m.icon}`} /> {m.label}</b>
        <span style={{ fontFamily: "var(--mono, monospace)", fontWeight: 700, fontSize: 18, color: m.color }}>{data.score}</span>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        {Object.entries(data.kpis || {}).map(([k, v]) => (
          <span key={k} className="aar-chip" style={{ fontSize: 11 }}>{k.replace(/_/g, " ")}: {Array.isArray(v) ? (v.length ? v.join(", ") : "—") : String(v)}</span>
        ))}
      </div>
      {(data.findings?.strengths || []).map((x: string, i: number) => (
        <div key={"s" + i} style={{ fontSize: 12.5, marginBottom: 4 }}><i className="fa fa-check" style={{ color: "#22c55e", marginRight: 6 }} />{x}</div>
      ))}
      {(data.findings?.weaknesses || []).map((x: string, i: number) => (
        <div key={"w" + i} style={{ fontSize: 12.5, marginBottom: 4 }}><i className="fa fa-triangle-exclamation" style={{ color: "#f59e0b", marginRight: 6 }} />{x}</div>
      ))}
      {tl.length > 0 && (
        <>
          <button className="btn btn-ghost no-print" style={{ marginTop: 10, fontSize: 12, padding: "4px 10px" }} onClick={() => setOpen(!open)}>
            <i className={`fa ${open ? "fa-chevron-up" : "fa-chevron-down"}`} /> {open ? "Hide" : "Show"} actions ({tl.length})
          </button>
          {open && (
            <div style={{ marginTop: 8, maxHeight: 220, overflowY: "auto" }}>
              {tl.map((a: any, i: number) => (
                <div key={i} style={{ fontSize: 12, display: "flex", gap: 8, marginBottom: 3 }}>
                  <span style={{ color: "#64748b", fontFamily: "var(--mono, monospace)" }}>{clock(a.t)}</span>
                  <span>{a.label}{a.target ? ` → ${a.target}` : ""}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function AarReport({ report, onClose }: { report: any; onClose?: () => void }) {
  const r = report || {};
  const title = r.scenario?.name || r.mission?.name || "After-Action Report";
  const sub = r.scenario?.subtitle || r.mission?.klass || "";
  const band = r.outcome_band || r.outcome?.outcome_band;
  const c = band === "Contained" ? "#22c55e" : band === "Degraded" ? "#f59e0b"
    : r.result === "blue" ? "#5B8CFF" : r.result === "red" ? "#ef4444" : "#94a3b8";
  const o = r.outcome || {};
  const teams = r.teams || {};

  const tiles: [string, any][] = [];
  if (band) tiles.push(["Outcome", band]);
  if (o.infected != null) tiles.push(["Infected", o.infected]);
  if (o.impacted != null) tiles.push(["Impacted", o.impacted]);
  if (o.total_hosts != null) tiles.push(["Fleet", o.total_hosts]);
  if (o.financial_loss != null) tiles.push(["Est. loss", `$${(o.financial_loss / 1000).toFixed(0)}k`]);
  if (o.coverage_pct != null) tiles.push(["Coverage", `${o.coverage_pct}%`]);
  if (o.assets_compromised != null) tiles.push(["Compromised", o.assets_compromised]);

  return (
    <div className="aar aar-print" style={{ maxWidth: 1000, margin: "0 auto", padding: 20 }}>
      {/* header */}
      <div className="aar-card" style={{ borderLeft: `4px solid ${c}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10 }}>
          <div>
            <div style={{ fontSize: 12, color: "#8aa0c2", textTransform: "uppercase", letterSpacing: 1 }}>
              <i className="fa fa-file-shield" /> After-Action Report{sub ? ` · ${sub}` : ""}
            </div>
            <h2 style={{ fontSize: 22, fontWeight: 800, margin: "4px 0" }}>{title}</h2>
            <div style={{ fontSize: 13, color: c, fontWeight: 600 }}>{r.verdict || band}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 12, color: "#8aa0c2" }}>duration {clock(r.duration_s)}</div>
            <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
              {Object.entries(teams).map(([t, d]: any) => (
                <span key={t} className="aar-chip" style={{ color: TEAM[t]?.color }}>{t.toUpperCase()} {d.score}</span>
              ))}
            </div>
            <div className="no-print" style={{ display: "flex", gap: 8, marginTop: 10, justifyContent: "flex-end" }}>
              <button className="btn btn-primary" onClick={() => window.print()}><i className="fa fa-print" /> Print / Save PDF</button>
              {onClose && <button className="btn" onClick={onClose}><i className="fa fa-xmark" /> Close</button>}
            </div>
          </div>
        </div>
        {tiles.length > 0 && (
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginTop: 14 }}>
            {tiles.map(([label, value]) => (
              <div key={label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: label === "Outcome" ? c : "#e2e8f0" }}>{value}</div>
                <div style={{ fontSize: 10.5, color: "#8aa0c2", textTransform: "uppercase", letterSpacing: .5 }}>{label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* per-team scorecards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        {["red", "soc", "blue"].filter((t) => teams[t]).map((t) => <TeamCard key={t} team={t} data={teams[t]} />)}
      </div>

      {/* MITRE chain + recommendations */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
        {(r.mitre || []).length > 0 && (
          <div className="aar-card" style={{ marginBottom: 0 }}>
            <b><i className="fa fa-sitemap" /> Attack path (MITRE ATT&CK)</b>
            <div style={{ marginTop: 8, maxHeight: 320, overflowY: "auto" }}>
              {r.mitre.map((m: any, i: number) => (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12.5, padding: "4px 0", borderBottom: "1px solid #1e293b" }}>
                  {m.t != null && <span style={{ color: "#64748b", fontFamily: "var(--mono, monospace)" }}>{clock(m.t)}</span>}
                  {m.detected != null && <i className={`fa ${m.detected ? "fa-eye" : "fa-eye-slash"}`} style={{ color: m.detected ? "#22c55e" : "#64748b" }} />}
                  <span style={{ flex: 1 }}>{m.label}{m.target ? ` → ${m.target}` : ""}</span>
                  {m.mitre && <span className="aar-chip" style={{ fontSize: 10.5 }}>{m.mitre}</span>}
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="aar-card" style={{ marginBottom: 0 }}>
          <b><i className="fa fa-lightbulb" /> Recommendations</b>
          <div style={{ marginTop: 8 }}>
            {(r.recommendations || []).map((rec: string, i: number) => (
              <div key={i} style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 8 }}>
                <i className="fa fa-arrow-right" style={{ color: "#5B8CFF", marginTop: 3 }} /><span>{rec}</span>
              </div>
            ))}
            {(r.recommendations || []).length === 0 && <div style={{ fontSize: 12.5, color: "#8aa0c2" }}>No recommendations.</div>}
          </div>
          {r.note && <div style={{ fontSize: 12, color: "#8aa0c2", marginTop: 10, fontStyle: "italic" }}>{r.note}</div>}
        </div>
      </div>
    </div>
  );
}
