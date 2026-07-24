import { useMemo, useState } from "react";
import type { LiveAlert, LiveAsset, LiveEvent, LiveSnapshot, LiveSocAction } from "../api/types";
import NetworkMap from "./NetworkMap";

const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const SEV_COLOR: Record<string, string> = {
  critical: "var(--gc-red)", high: "#FF8A3D", medium: "var(--gc-yellow)", low: "#7FB2FF", info: "var(--gc-muted)",
};
const STATUS_COLOR: Record<string, string> = {
  new: "var(--gc-red)", triaged: "var(--gc-yellow)", escalated: "var(--gc-green)",
};

export default function SocConsole({
  snapshot, canPlay, onAction,
}: {
  snapshot: LiveSnapshot;
  canPlay: boolean;
  onAction: (actionId: string, targetId?: string | null) => void;
}) {
  const sc = snapshot.soc!;
  const [stage, setStage] = useState<string>("all");

  const assetMap = useMemo(() => {
    const m: Record<string, LiveAsset> = {};
    for (const a of snapshot.assets) m[a.id] = a;
    return m as any;
  }, [snapshot.assets]);

  const capActions = sc.actions.filter((a) => a.target_mode === "none");
  const byStage = useMemo(() => {
    const m: Record<string, LiveSocAction[]> = {};
    for (const a of capActions) (m[a.stage] ??= []).push(a);
    return m;
  }, [capActions]);
  const shownCaps = stage === "all" ? capActions : byStage[stage] ?? [];

  const alerts = sc.alerts.slice().reverse();
  const newCount = sc.alerts.filter((a) => a.status === "new").length;

  return (
    <>
      {/* Objectives + posture */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-tower-observation" /> SOC objectives</div></div>
          {sc.objectives.map((o) => (
            <div key={o.key} style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 6, alignItems: "flex-start" }}>
              <i className={`fa ${o.met ? "fa-check-circle" : "fa-circle"}`} style={{ color: o.met ? "var(--gc-green)" : "var(--gc-muted)", marginTop: 2 }} />
              <span style={{ color: o.met ? "var(--gc-text)" : "var(--gc-muted)" }}>{o.label}</span>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-gauge-high" /> SOC posture</div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 13 }}>coverage {sc.coverage_pct}%</div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${sc.coverage_pct}%`, background: "#22d3a8" }} /></div>
          <div className="stats-row" style={{ gridTemplateColumns: "repeat(4,1fr)", marginTop: 14 }}>
            <div className="stat-card"><div className="stat-label">SOC score</div><div className="stat-value" style={{ fontSize: 20, color: "#22d3a8" }}>{sc.score}</div></div>
            <div className="stat-card"><div className="stat-label">New alerts</div><div className="stat-value" style={{ fontSize: 20, color: newCount ? "var(--gc-red)" : undefined }}>{newCount}</div></div>
            <div className="stat-card"><div className="stat-label">Triaged</div><div className="stat-value" style={{ fontSize: 20 }}>{sc.triaged}</div></div>
            <div className="stat-card"><div className="stat-label">Escalated</div><div className="stat-value" style={{ fontSize: 20 }}>{sc.escalated}</div></div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
            {sc.monitoring.map((m) => <span key={m} className="tag" style={{ fontSize: 9 }}><i className="fa fa-eye" /> {m}</span>)}
            {sc.capabilities.map((c) => <span key={c} className="tag" style={{ fontSize: 9, color: "#22d3a8" }}>{c}</span>)}
          </div>
        </div>
      </div>

      {sc.concluded && sc.final && (
        <div className="alert-item" style={{ marginBottom: 16 }}>
          <div className="alert-icon"><i className="fa fa-tower-observation" style={{ color: "#22d3a8" }} /></div>
          <div className="alert-content">
            <strong>SOC shift closed — score {sc.final.total_score}</strong>
            <div>Coverage {sc.final.coverage_pct}% ({sc.final.detected}/{sc.final.detectable}) · triaged {sc.final.triaged} ·
              escalated {sc.final.escalated} · MTTA {sc.final.mtta_s}s · {sc.final.open_alerts} alerts left open</div>
          </div>
        </div>
      )}

      {!canPlay && (
        <div className="alert-item" style={{ marginBottom: 16 }}>
          <div className="alert-icon"><i className="fa fa-eye" /></div>
          <div className="alert-content"><strong>Spectating</strong><div>Claim the SOC role in the lobby to work the alert queue.</div></div>
        </div>
      )}

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* Alert queue — the SOC's core */}
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-bell" /> Alert queue ({sc.alerts.length})</div>
            {newCount > 0 && <span className="tag" style={{ color: "var(--gc-red)" }}>{newCount} new</span>}
          </div>
          <div style={{ maxHeight: 480, overflowY: "auto", display: "grid", gap: 8 }}>
            {alerts.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No alerts yet — establish detection coverage and wait for adversary activity.</div>}
            {alerts.map((al: LiveAlert) => (
              <div key={al.id} style={{ border: "1px solid var(--gc-border)", borderRadius: 8, padding: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    <i className="fa fa-circle" style={{ fontSize: 8, color: STATUS_COLOR[al.status] ?? "var(--gc-muted)", marginRight: 6 }} />
                    {al.label}
                  </div>
                  <span className="tag" style={{ fontSize: 9, color: al.p_rank >= 3 ? "var(--gc-red)" : "var(--gc-muted)" }}>{al.p_label}</span>
                </div>
                <div style={{ fontSize: 11, color: "var(--gc-muted)", margin: "4px 0" }}>
                  {al.mitre} · {al.tactic}{al.asset_label ? ` · ${al.asset_label}` : ""} · {fmt(al.t)} · <b style={{ color: STATUS_COLOR[al.status] }}>{al.status}</b>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {al.status === "new" && (
                    <button className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 10px" }}
                      disabled={!canPlay} onClick={() => onAction("soc.triage", al.id)}>
                      <i className="fa fa-magnifying-glass" /> Triage & classify
                    </button>
                  )}
                  {al.status === "triaged" && (
                    <button className="btn btn-primary" style={{ fontSize: 11, padding: "4px 10px", background: "#22d3a8", borderColor: "#22d3a8" }}
                      disabled={!canPlay} onClick={() => onAction("soc.escalate", al.id)}>
                      <i className="fa fa-arrow-up" /> Escalate to IR
                    </button>
                  )}
                  {al.status === "escalated" && <span style={{ fontSize: 11, color: "var(--gc-green)" }}><i className="fa fa-check" /> incident declared</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Capabilities + estate + log */}
        <div style={{ display: "grid", gap: 16 }}>
          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-sliders" /> Detection & ops</div></div>
            <div className="phase-track" style={{ marginBottom: 10 }}>
              <div className={"phase-step" + (stage === "all" ? " active" : "")} onClick={() => setStage("all")} style={{ cursor: "pointer" }}>All</div>
              {snapshot.soc_stages.map((s) => (
                <div key={s.id} title={`${s.summary} (${s.ref})`} onClick={() => setStage(s.id)} style={{ cursor: "pointer" }}
                  className={"phase-step" + (stage === s.id ? " active" : (byStage[s.id] ?? []).some((a) => a.available) ? " done" : "")}>
                  {s.name}
                </div>
              ))}
            </div>
            <div style={{ display: "grid", gap: 8, maxHeight: 300, overflowY: "auto" }}>
              {shownCaps.map((a) => (
                <div key={a.id} style={{ border: "1px solid var(--gc-border)", borderRadius: 8, padding: 10, opacity: a.done ? 0.55 : a.available ? 1 : 0.7 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ fontWeight: 600, fontSize: 12.5 }}>{a.done && <i className="fa fa-check" style={{ color: "var(--gc-green)", marginRight: 6 }} />}{a.label}</div>
                    <span style={{ fontSize: 10, color: "#22d3a8" }}>+{a.score}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--gc-muted)", margin: "4px 0" }}>{a.description}</div>
                  {a.note && <div style={{ fontSize: 10, fontStyle: "italic", color: "#8aa0c2", marginBottom: 6 }}>{a.note}</div>}
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <button className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 10px" }} disabled={!a.available || !canPlay} onClick={() => onAction(a.id, null)}>
                      <i className="fa fa-bolt" /> Run
                    </button>
                    {!a.available && <span style={{ fontSize: 10, color: "var(--gc-muted)" }}><i className="fa fa-lock" /> {a.reason}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-network-wired" /> Estate</div></div>
            <NetworkMap assets={assetMap} />
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-terminal" /> Operation log</div></div>
            <div id="sim-console" style={{ maxHeight: 180 }}>
              {snapshot.events.slice().reverse().map((e: LiveEvent) => (
                <div key={e.seq} className="console-line" style={{ display: "flex", gap: 8 }}>
                  <span className="ts">{fmt(e.t)}</span>
                  <span className="msg" style={{ color: e.role === "soc" ? "#5eead4" : e.role === "blue" ? "#9ecbff" : e.role === "red" ? "#ff9a9a" : undefined }}>
                    {e.kind === "chat" ? <b>{e.title}: </b> : null}{e.message || e.title}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
