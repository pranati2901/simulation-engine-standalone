import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { BAND_COLOR } from "./Studio";

const SEV_COLOR: Record<string, string> = {
  info: "#94a3b8", low: "#60a5fa", medium: "#eab308", high: "#f97316", critical: "#ef4444",
};

export default function StudioRun() {
  const { runId = "" } = useParams();
  const nav = useNavigate();
  const { data: run, isLoading } = useQuery({ queryKey: ["studio-run", runId], queryFn: () => api.studioRunGet(runId) });

  const [revealed, setRevealed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timer = useRef<number | null>(null);
  const total = run?.events.length ?? 0;

  // reveal all immediately, then let "Replay" animate it
  useEffect(() => { if (run) setRevealed(run.events.length); }, [run]);
  useEffect(() => {
    if (!playing) { if (timer.current) window.clearInterval(timer.current); return; }
    timer.current = window.setInterval(() => {
      setRevealed((r) => {
        if (r >= total) { setPlaying(false); return r; }
        return r + 1;
      });
    }, 1200 / speed);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, speed, total]);

  const replay = () => { setRevealed(0); setPlaying(true); };

  if (isLoading || !run) return <div className="center-empty"><span className="spinner" /> Loading run…</div>;
  const k = run.kpis;
  const band = run.outcome_band;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <button className="btn btn-ghost" onClick={() => nav("/studio")} style={{ marginBottom: 8 }}><i className="fa fa-arrow-left" /> Studio</button>
          <h1 style={{ fontSize: 22 }}>{run.name}</h1>
          <p className="muted" style={{ fontSize: 13 }}>{run.system} · {run.domain} · {run.duration_min}-min horizon · AI {run.ai_mode === "agent" ? "Claude" : "stub"}</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ textAlign: "center", padding: "8px 16px", borderRadius: 12, border: `1px solid ${BAND_COLOR[band]}55`, background: `${BAND_COLOR[band]}12` }}>
            <div style={{ fontSize: 10, letterSpacing: 1, color: "var(--gc-muted)" }}>OUTCOME</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: BAND_COLOR[band] }}>{band}</div>
          </div>
          <div style={{ textAlign: "center", padding: "8px 16px", borderRadius: 12, border: "1px solid var(--gc-border)" }}>
            <div style={{ fontSize: 10, letterSpacing: 1, color: "var(--gc-muted)" }}>READINESS</div>
            <div style={{ fontSize: 20, fontWeight: 800 }}>{k.readiness_score} <span style={{ fontSize: 13, color: "var(--gc-muted)" }}>{k.grade}</span></div>
          </div>
        </div>
      </div>

      <div style={{ fontSize: 14, marginBottom: 16, padding: "10px 14px", borderRadius: 10, background: "var(--gc-surface)", borderLeft: `3px solid ${BAND_COLOR[band]}` }}>
        {run.headline}
      </div>

      {/* KPI strip */}
      <div className="stats-row" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(120px,1fr))", marginBottom: 20 }}>
        <Kpi label="Detected" value={k.detected ? "Yes" : "No"} sub={k.detected ? "monitoring caught it" : "blind spot"} />
        <Kpi label="Time to detect" value={`${k.mttd_min}m`} sub="first indication" />
        <Kpi label="Lead time" value={`${k.lead_time_min}m`} sub="window to act" />
        <Kpi label="Peak severity" value={`${k.peak_severity_pct}%`} />
        <Kpi label="Downtime" value={`${k.downtime_min}m`} />
        <Kpi label="Affected units" value={`${k.affected_units}`} />
        <Kpi label="Mitigations" value={`${k.mitigations_identified}`} sub="actionable" />
      </div>

      <div className="grid-2" style={{ alignItems: "start", gap: 18 }}>
        {/* Timeline */}
        <div className="card">
          <div className="card-header" style={{ marginBottom: 8 }}>
            <div className="card-title"><i className="fa fa-timeline" /> Simulated timeline</div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <button className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 9px" }} onClick={playing ? () => setPlaying(false) : replay}>
                <i className={`fa ${playing ? "fa-pause" : "fa-play"}`} /> {playing ? "Pause" : "Replay"}
              </button>
              {[1, 2, 4].map((s) => <button key={s} className={"filter-chip" + (speed === s ? " active" : "")} style={{ padding: "2px 7px", fontSize: 10 }} onClick={() => setSpeed(s)}>{s}×</button>)}
            </div>
          </div>
          <div style={{ position: "relative" }}>
            {run.events.map((e, i) => {
              const on = i < revealed;
              const c = SEV_COLOR[e.severity] || "#94a3b8";
              return (
                <div key={i} style={{ display: "flex", gap: 12, opacity: on ? 1 : 0.25, transition: "opacity .3s" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <div style={{ width: 12, height: 12, borderRadius: "50%", background: c, boxShadow: on ? `0 0 0 4px ${c}22` : "none", flexShrink: 0, marginTop: 4 }} />
                    {i < run.events.length - 1 && <div style={{ width: 2, flex: 1, background: "var(--gc-border)", minHeight: 22 }} />}
                  </div>
                  <div style={{ paddingBottom: 16, flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--gc-muted)" }}>t+{e.t_min}m</span>
                      <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: .5, color: c, textTransform: "uppercase" }}>{e.phase}</span>
                      <span style={{ fontSize: 9, color: "var(--gc-muted)" }}>· {e.actor}</span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: 13, marginTop: 1 }}>{e.title}</div>
                    {e.detail && <div style={{ fontSize: 12, color: "var(--gc-body)", marginTop: 2 }}>{e.detail}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Analysis + actions */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 8 }}><i className="fa fa-brain" /> AI analysis</div>
            <div style={{ fontSize: 13, lineHeight: 1.65, color: "var(--gc-body)", whiteSpace: "pre-wrap" }}>{run.narrative || "—"}</div>
          </div>
          <ListCard icon="fa-shield" title="Recommended mitigations" items={run.mitigations} color="#22c55e" />
          <ListCard icon="fa-triangle-exclamation" title="Key risks" items={run.risks} color="#ef4444" />
          <ListCard icon="fa-magnifying-glass" title="Detection signals" items={run.detections} color="#4a66e0" />
          <div className="card" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 13, marginBottom: 10 }}>Turn this into a graded, guided repair drill.</div>
            <button className="btn btn-primary" onClick={() => {
              const s = run.spec!;
              nav(`/studio/train?${new URLSearchParams({ domain: s.domain, system: s.system, fault: s.fault, title: s.name })}`);
            }}><i className="fa fa-graduation-cap" /> Open training simulator</button>
          </div>
        </div>
      </div>
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ fontSize: 20 }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function ListCard({ icon, title, items, color }: { icon: string; title: string; items: string[]; color: string }) {
  if (!items?.length) return null;
  return (
    <div className="card">
      <div className="card-title" style={{ marginBottom: 8 }}><i className={`fa ${icon}`} style={{ color }} /> {title}</div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--gc-body)", display: "grid", gap: 4 }}>
        {items.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    </div>
  );
}
