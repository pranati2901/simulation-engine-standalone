import { useMemo, useState } from "react";
import type { LiveAsset, LiveBlueAction, LiveEvent, LiveSnapshot } from "../api/types";
import NetworkMap from "./NetworkMap";

const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

const SEV_COLOR: Record<string, string> = {
  critical: "var(--gc-red)", high: "#FF8A3D", medium: "var(--gc-yellow)",
  low: "#7FB2FF", info: "var(--gc-muted)",
};
const KIND_ICON: Record<string, string> = {
  action: "fa-bolt", alert: "fa-bell", miss: "fa-eye-slash", response: "fa-shield-halved",
  intel: "fa-lightbulb", objective: "fa-flag-checkered", state: "fa-bullseye",
  system: "fa-circle-info", score: "fa-star", chat: "fa-comment", defense: "fa-ban", opsec: "fa-eye",
};

export default function BlueConsole({
  snapshot, canPlay, onAction, onConclude,
}: {
  snapshot: LiveSnapshot;
  canPlay: boolean;
  onAction: (actionId: string, targetId?: string | null) => void;
  onConclude: () => void;
}) {
  const bd = snapshot.defender!;
  const [stage, setStage] = useState<string>("all");
  const [targets, setTargets] = useState<Record<string, string>>({});

  // Blue knows its own environment — full visibility of the asset map.
  const assetMap = useMemo(() => {
    const m: Record<string, LiveAsset> = {};
    for (const a of snapshot.assets) m[a.id] = a;
    return m as any;
  }, [snapshot.assets]);

  const actionsByStage = useMemo(() => {
    const m: Record<string, LiveBlueAction[]> = {};
    for (const a of bd.actions) (m[a.stage] ??= []).push(a);
    return m;
  }, [bd.actions]);

  const shown = stage === "all" ? bd.actions : actionsByStage[stage] ?? [];
  const events = snapshot.events.slice().reverse();
  // the "what is Red doing" incident feed
  const redFeed = events.filter((e) => ["action", "alert", "miss", "state", "objective"].includes(e.kind));

  const exec = (a: LiveBlueAction) => {
    if (!a.available || !canPlay || bd.concluded) return;
    const tid = a.target_mode === "select" ? targets[a.id] : null;
    if (a.target_mode === "select" && !tid) return;
    onAction(a.id, tid);
  };

  return (
    <>
      {/* Objectives + posture strip */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-shield-halved" /> Defensive objectives</div></div>
          {bd.objectives.map((o) => (
            <div key={o.key} style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 6, alignItems: "flex-start" }}>
              <i className={`fa ${o.met ? "fa-check-circle" : "fa-circle"}`}
                style={{ color: o.met ? "var(--gc-green)" : "var(--gc-muted)", marginTop: 2 }} />
              <span style={{ color: o.met ? "var(--gc-text)" : "var(--gc-muted)" }}>{o.label}</span>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-gauge-high" /> Response posture</div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 13 }}>coverage {bd.coverage_pct}%</div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--gc-muted)", marginBottom: 6 }}>
            <span>Detection coverage</span><span>{bd.detected}/{bd.detectable} behaviours</span>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${bd.coverage_pct}%`, background: "#5B8CFF" }} /></div>
          <div className="stats-row" style={{ gridTemplateColumns: "repeat(4,1fr)", marginTop: 14 }}>
            <div className="stat-card"><div className="stat-label">Blue score</div><div className="stat-value" style={{ fontSize: 20, color: "#5B8CFF" }}>{bd.score}</div></div>
            <div className="stat-card"><div className="stat-label">Contained</div><div className="stat-value" style={{ fontSize: 20 }}>{bd.contained}/{bd.footholds_total}</div></div>
            <div className="stat-card"><div className="stat-label">MTTC</div><div className="stat-value" style={{ fontSize: 16 }}>{bd.mttc_s ? `${Math.round(bd.mttc_s)}s` : "—"}</div></div>
            <div className="stat-card"><div className="stat-label">Prevented</div><div className="stat-value" style={{ fontSize: 16 }}>{bd.prevented.length || "—"}</div></div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
            {bd.monitoring.map((m) => <span key={m} className="tag" style={{ fontSize: 9 }}><i className="fa fa-eye" /> {m}</span>)}
            {bd.defense_flags.map((f) => <span key={f} className="tag" style={{ fontSize: 9, color: "var(--gc-green)" }}><i className="fa fa-lock" /> {f.replace("_", " ")}</span>)}
          </div>
          {!bd.concluded && canPlay && (
            <button className="btn btn-ghost" style={{ marginTop: 12, width: "100%" }} onClick={onConclude}>
              <i className="fa fa-stop" /> Conclude defense (lessons learned)
            </button>
          )}
        </div>
      </div>

      {bd.concluded && bd.final && (
        <div className={"alert-item " + (bd.final.eviction_complete ? "success" : "")} style={{ marginBottom: 16 }}>
          <div className="alert-icon"><i className="fa fa-shield-halved" style={{ color: bd.final.eviction_complete ? "var(--gc-green)" : "var(--gc-yellow)" }} /></div>
          <div className="alert-content">
            <strong>Defense concluded — total score {bd.final.total_score}</strong>
            <div>{bd.final.eviction_complete ? "Adversary fully evicted." : "Adversary not fully evicted."} Coverage {bd.final.coverage_pct}% ·
              contained {bd.final.contained}/{bd.final.footholds_total} · MTTC {bd.final.mttc_s}s ·
              prevented [{bd.final.prevented.join(", ") || "none"}] · actions {bd.final.action_score} +
              eviction {bd.final.eviction_bonus} + prevention {bd.final.prevention_bonus}</div>
          </div>
        </div>
      )}

      {!canPlay && (
        <div className="alert-item" style={{ marginBottom: 16 }}>
          <div className="alert-icon"><i className="fa fa-eye" /></div>
          <div className="alert-content"><strong>Spectating</strong><div>Claim the Blue role in the lobby to run the defense.</div></div>
        </div>
      )}

      {/* Lifecycle stage rail */}
      <div className="phase-track" style={{ marginBottom: 14 }}>
        <div className={"phase-step" + (stage === "all" ? " active" : "")} onClick={() => setStage("all")} style={{ cursor: "pointer" }}>All</div>
        {snapshot.blue_stages.map((s) => {
          const acts = actionsByStage[s.id] ?? [];
          const anyAvail = acts.some((a) => a.available);
          return (
            <div key={s.id} title={`${s.summary} (${s.ref})`} onClick={() => setStage(s.id)} style={{ cursor: "pointer" }}
              className={"phase-step" + (stage === s.id ? " active" : anyAvail ? " done" : "")}>
              {s.name}
            </div>
          );
        })}
      </div>

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* Action panel */}
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-list-check" /> Defender actions{stage !== "all" && <span className="tag" style={{ marginLeft: 8 }}>{stage}</span>}</div></div>
          <div style={{ display: "grid", gap: 10, maxHeight: 560, overflowY: "auto", paddingRight: 4 }}>
            {shown.map((a) => (
              <div key={a.id} style={{
                border: "1px solid var(--gc-border)", borderRadius: 8, padding: 12,
                opacity: a.done && a.target_mode === "none" ? 0.55 : a.available ? 1 : 0.7,
                background: a.available ? "var(--gc-surface)" : "transparent",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {a.done && a.target_mode === "none" && <i className="fa fa-check" style={{ color: "var(--gc-green)", marginRight: 6 }} />}{a.label}
                  </div>
                  <span style={{ fontSize: 10, color: "#5B8CFF", whiteSpace: "nowrap" }}>+{a.score}</span>
                </div>
                <div style={{ fontSize: 11.5, color: "var(--gc-muted)", margin: "5px 0" }}>{a.description}</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 10, color: "var(--gc-muted)", marginBottom: 6 }}>
                  {a.framework && <span className="tag">{a.framework}</span>}
                </div>
                {a.note && <div style={{ fontSize: 10.5, fontStyle: "italic", color: "#8aa0c2", marginBottom: 8 }}><i className="fa fa-quote-left" style={{ marginRight: 4 }} />{a.note}</div>}
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {a.target_mode === "select" && (
                    <select className="form-select" style={{ flex: 1, minWidth: 120, fontSize: 12 }}
                      value={targets[a.id] ?? ""} disabled={!a.available || !canPlay}
                      onChange={(e) => setTargets((t) => ({ ...t, [a.id]: e.target.value }))}>
                      <option value="">{a.targets.length ? "select target…" : "no matching asset"}</option>
                      {a.targets.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.zone})</option>)}
                    </select>
                  )}
                  <button className="btn btn-primary" style={{ fontSize: 12, padding: "5px 12px" }}
                    disabled={!a.available || !canPlay || bd.concluded || (a.target_mode === "select" && !targets[a.id])}
                    onClick={() => exec(a)}>
                    <i className="fa fa-shield" /> Execute
                  </button>
                  {!a.available && <span style={{ fontSize: 10.5, color: "var(--gc-muted)" }}><i className="fa fa-lock" /> {a.reason}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Map + incident feed + log */}
        <div style={{ display: "grid", gap: 16 }}>
          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-network-wired" /> Estate</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{snapshot.assets.filter((a) => a.security_state === "compromised").length} compromised</div>
            </div>
            <NetworkMap assets={assetMap} />
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-bell" /> Adversary activity (live)</div></div>
            <div style={{ maxHeight: 200, overflowY: "auto" }}>
              {redFeed.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No adversary activity observed yet.</div>}
              {redFeed.map((e: LiveEvent) => (
                <div key={e.seq} className={"alert-item " + (e.kind === "alert" ? "" : "")} style={{ padding: 8 }}>
                  <div className="alert-icon"><i className={`fa ${KIND_ICON[e.kind] ?? "fa-angle-right"}`} style={{ color: SEV_COLOR[e.severity] ?? "var(--gc-muted)" }} /></div>
                  <div className="alert-content" style={{ fontSize: 12 }}>
                    <strong>{e.title}</strong><div>{e.message}</div>
                    <span>{fmt(e.t)}{e.kind === "alert" ? " · DETECTED" : e.kind === "miss" ? " · uncovered" : ""}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-terminal" /> Operation log</div></div>
            <div id="sim-console" style={{ maxHeight: 200 }}>
              {events.map((e: LiveEvent) => (
                <div key={e.seq} className="console-line" style={{ display: "flex", gap: 8 }}>
                  <span className="ts">{fmt(e.t)}</span>
                  <i className={`fa ${KIND_ICON[e.kind] ?? "fa-angle-right"}`} style={{ color: SEV_COLOR[e.severity] ?? "var(--gc-muted)", marginTop: 3, fontSize: 11 }} />
                  <span className="msg" style={{ color: e.role === "blue" ? "#9ecbff" : e.role === "red" ? "#ff9a9a" : undefined }}>
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
