import { useMemo, useState } from "react";
import type { LiveAction, LiveAsset, LiveEvent, LiveSnapshot } from "../api/types";
import NetworkMap from "./NetworkMap";

const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

const SEV_COLOR: Record<string, string> = {
  critical: "var(--gc-red)", high: "#FF8A3D", medium: "var(--gc-yellow)",
  low: "#7FB2FF", info: "var(--gc-muted)",
};
const KIND_ICON: Record<string, string> = {
  action: "fa-bolt", intel: "fa-lightbulb", objective: "fa-flag-checkered", opsec: "fa-eye",
  state: "fa-bullseye", system: "fa-circle-info", score: "fa-star", chat: "fa-comment",
};

function noiseColor(noise: number) {
  return noise >= 9 ? "var(--gc-red)" : noise >= 6 ? "#FF8A3D" : noise >= 3 ? "var(--gc-yellow)" : "var(--gc-green)";
}

// Real-tool execution block shown under a Red action when live-fire is armed.
function LiveFireBlock({ lf }: { lf: any }) {
  const [open, setOpen] = useState(true);
  const queued = lf.status === "queued";
  const unavailable = lf.status === "unavailable";
  const ok = lf.status === "done" && lf.success;
  const headColor = queued ? "var(--gc-yellow)" : unavailable ? "var(--gc-muted)" : ok ? "var(--gc-green)" : "var(--gc-red)";
  return (
    <div style={{ margin: "6px 0 6px 26px", border: "1px solid var(--gc-border)", borderLeft: `3px solid ${headColor}`,
      borderRadius: 6, background: "#0a0e16", fontFamily: "var(--mono)", fontSize: 11.5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 8px", cursor: "pointer" }} onClick={() => setOpen((v) => !v)}>
        <i className="fa fa-bolt" style={{ color: headColor }} />
        <span style={{ color: "var(--gc-text)", fontWeight: 600 }}>REAL TOOL · {lf.tool}</span>
        <span style={{ color: "var(--gc-muted)" }}>{lf.function}</span>
        {queued && <span style={{ color: "var(--gc-yellow)" }}><span className="spinner" style={{ width: 10, height: 10 }} /> running…</span>}
        {unavailable && <span className="tag" style={{ fontSize: 9 }}>needs Windows-AD lab</span>}
        {lf.status === "done" && (
          <span className="tag" style={{ fontSize: 9, color: ok ? "var(--gc-green)" : "var(--gc-red)", borderColor: ok ? "var(--gc-green)" : "var(--gc-red)" }}>
            {ok ? "executed" : "failed"}
          </span>
        )}
        {lf.detected && <span className="tag" style={{ fontSize: 9, marginLeft: "auto", color: "#22d3a8", borderColor: "#22d3a8" }}><i className="fa fa-tower-observation" /> DETECTED</span>}
      </div>
      {open && (
        <div style={{ padding: "0 8px 8px" }}>
          {lf.command && <div style={{ color: "#9ecbff" }}><span style={{ color: "var(--gc-red)" }}>kali@gc-attacker</span>:~$ {lf.command}</div>}
          {lf.output && <pre style={{ margin: "4px 0 0", whiteSpace: "pre-wrap", color: "var(--gc-muted)", maxHeight: 180, overflowY: "auto" }}>{lf.output}</pre>}
          {lf.detected && lf.detection_evidence && (
            <div style={{ color: "#22d3a8", marginTop: 4 }}><i className="fa fa-magnifying-glass" /> {lf.detection_evidence}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RedConsole({
  snapshot, canPlay, onAction, onConclude,
}: {
  snapshot: LiveSnapshot;
  canPlay: boolean;
  onAction: (actionId: string, targetId?: string | null) => void;
  onConclude: () => void;
}) {
  const op = snapshot.operator!;
  const [stage, setStage] = useState<string>("all");
  const [targets, setTargets] = useState<Record<string, string>>({});

  // Red operates under fog of war — mask undiscovered assets client-side.
  const assetMap = useMemo(() => {
    const m: Record<string, any> = {};
    for (const a of snapshot.assets) {
      m[a.id] = a.revealed ? a
        : { ...a, name: "· undiscovered ·", security_state: "safe", health: "nominal" };
    }
    return m;
  }, [snapshot.assets]);

  const actionsByStage = useMemo(() => {
    const m: Record<string, LiveAction[]> = {};
    for (const a of op.actions) (m[a.stage] ??= []).push(a);
    return m;
  }, [op.actions]);

  const shown = stage === "all" ? op.actions : actionsByStage[stage] ?? [];
  const expPct = op.exposure_pct;
  const expColor = expPct >= 85 ? "var(--gc-red)" : expPct >= 60 ? "var(--gc-yellow)" : "var(--gc-green)";
  const primary = op.objectives.find((o) => o.primary);
  const objectiveMet = !!primary?.met;
  const events = snapshot.events.slice().reverse();

  const exec = (a: LiveAction) => {
    if (!a.available || !canPlay || op.concluded) return;
    const tid = a.target_mode === "select" ? targets[a.id] : null;
    if (a.target_mode === "select" && !tid) return;
    onAction(a.id, tid);
  };

  return (
    <>
      {/* Objective + OPSEC strip */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-crosshairs" /> Mission objectives</div>
            <span className="tag">profile: {op.profile.replace("_", " ")}</span>
          </div>
          {op.objectives.map((o) => (
            <div key={o.key} style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 6, alignItems: "flex-start" }}>
              <i className={`fa ${o.met ? "fa-check-circle" : "fa-circle"}`}
                style={{ color: o.met ? "var(--gc-green)" : "var(--gc-muted)", marginTop: 2 }} />
              <span style={{ color: o.met ? "var(--gc-text)" : "var(--gc-muted)" }}>
                {o.label} {o.primary && <span className="tag" style={{ marginLeft: 4 }}>PRIMARY</span>}
              </span>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-eye-slash" /> Detection-risk budget</div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 13 }}>{op.noise_spent} / {op.budget}</div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--gc-muted)", marginBottom: 6 }}>
            <span>Exposure</span><span style={{ color: expColor }}>{expPct}%</span>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${expPct}%`, background: expColor }} /></div>
          <div className="stats-row" style={{ gridTemplateColumns: "repeat(3,1fr)", marginTop: 14 }}>
            <div className="stat-card"><div className="stat-label">Red score</div><div className="stat-value" style={{ fontSize: 22, color: "var(--gc-red)" }}>{op.score}</div></div>
            <div className="stat-card"><div className="stat-label">Credentials</div><div className="stat-value" style={{ fontSize: 16 }}>{op.cred_scope.replace("_", " ")}</div></div>
            <div className="stat-card"><div className="stat-label">Footholds</div><div className="stat-value" style={{ fontSize: 22 }}>{op.footholds.length}</div></div>
          </div>
          {objectiveMet && !op.concluded && canPlay && (
            <button className="btn btn-success" style={{ marginTop: 12, width: "100%" }}
              onClick={() => onAction("objective.capture_proof", null)}>
              <i className="fa fa-flag-checkered" /> Capture proof & conclude (minimum footprint)
            </button>
          )}
          {!op.concluded && canPlay && (
            <button className="btn btn-ghost" style={{ marginTop: 8, width: "100%" }} onClick={onConclude}>
              <i className="fa fa-stop" /> Abort / conclude operation
            </button>
          )}
        </div>
      </div>

      {op.concluded && op.final && (
        <div className={"alert-item " + (op.final.any_objective_met ? "success" : "")} style={{ marginBottom: 16 }}>
          <div className="alert-icon"><i className="fa fa-trophy" style={{ color: op.final.any_objective_met ? "var(--gc-green)" : "var(--gc-yellow)" }} /></div>
          <div className="alert-content">
            <strong>Operation concluded — total score {op.final.total_score}</strong>
            <div>{op.final.objective_met ? "Primary objective achieved." : op.final.any_objective_met ? "Secondary objective achieved (primary not proven)." : "Objective not proven."} Actions {op.final.action_score} ·
              stealth +{op.final.stealth_bonus} · discipline +{op.final.discipline_bonus} · overspend −{op.final.overspend_penalty} ·
              {" "}{op.final.actions_taken} actions · exposure {op.final.exposure_pct}%</div>
          </div>
        </div>
      )}

      {!canPlay && (
        <div className="alert-item" style={{ marginBottom: 16 }}>
          <div className="alert-icon"><i className="fa fa-eye" /></div>
          <div className="alert-content"><strong>Spectating</strong><div>Only players on the Red role drive the operation. Claim Red in the lobby to act.</div></div>
        </div>
      )}

      {/* Lifecycle stage rail */}
      <div className="phase-track" style={{ marginBottom: 14 }}>
        <div className={"phase-step" + (stage === "all" ? " active" : "")} onClick={() => setStage("all")} style={{ cursor: "pointer" }}>All</div>
        {snapshot.stages.map((s) => {
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
          <div className="card-header"><div className="card-title"><i className="fa fa-list-check" /> Operator actions{stage !== "all" && <span className="tag" style={{ marginLeft: 8 }}>{stage}</span>}</div></div>
          <div style={{ display: "grid", gap: 10, maxHeight: 560, overflowY: "auto", paddingRight: 4 }}>
            {shown.map((a) => (
              <div key={a.id} style={{
                border: "1px solid var(--gc-border)", borderRadius: 8, padding: 12,
                opacity: a.done ? 0.55 : a.available ? 1 : 0.7,
                background: a.available && !a.done ? "var(--gc-surface)" : "transparent",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {a.done && <i className="fa fa-check" style={{ color: "var(--gc-green)", marginRight: 6 }} />}{a.label}
                  </div>
                  <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: noiseColor(a.base_noise), whiteSpace: "nowrap" }}>
                    <i className="fa fa-volume-high" /> {a.noise}
                  </span>
                </div>
                <div style={{ fontSize: 11.5, color: "var(--gc-muted)", margin: "5px 0" }}>{a.description}</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 10, color: "var(--gc-muted)", marginBottom: 6 }}>
                  {a.mitre && <span className="tag">{a.mitre}</span>}
                  <span>{a.tactic}</span>
                  <span style={{ color: "var(--gc-red)" }}>+{a.score} pts</span>
                  {a.watched_by.length > 0 && <span title="controls that raise your exposure"><i className="fa fa-eye" /> {a.watched_by.join(", ")}</span>}
                </div>
                {a.opsec && <div style={{ fontSize: 10.5, fontStyle: "italic", color: "#8aa0c2", marginBottom: 8 }}><i className="fa fa-quote-left" style={{ marginRight: 4 }} />{a.opsec}</div>}
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {a.target_mode === "select" && (
                    <select className="form-select" style={{ flex: 1, minWidth: 120, fontSize: 12 }}
                      value={targets[a.id] ?? ""} disabled={!a.available || !canPlay}
                      onChange={(e) => setTargets((t) => ({ ...t, [a.id]: e.target.value }))}>
                      <option value="">{a.targets.length ? "select target…" : "no target in view"}</option>
                      {a.targets.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.zone})</option>)}
                    </select>
                  )}
                  {a.target_mode === "auto" && <span className="tag" style={{ fontSize: 10 }}>auto-target</span>}
                  <button className="btn btn-danger" style={{ fontSize: 12, padding: "5px 12px" }}
                    disabled={!a.available || !canPlay || op.concluded || (a.target_mode === "select" && !targets[a.id])}
                    onClick={() => exec(a)}>
                    <i className="fa fa-bolt" /> Execute
                  </button>
                  {!a.available && <span style={{ fontSize: 10.5, color: "var(--gc-muted)" }}><i className="fa fa-lock" /> {a.reason}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Map + intel + log */}
        <div style={{ display: "grid", gap: 16 }}>
          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-network-wired" /> Terrain (fog of war)</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{snapshot.assets.filter((a) => a.revealed).length}/{snapshot.assets.length} discovered</div>
            </div>
            <NetworkMap assets={assetMap} />
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-lightbulb" /> Intel</div></div>
            <div style={{ maxHeight: 140, overflowY: "auto" }}>
              {op.intel.length === 0 && <div className="muted" style={{ fontSize: 12 }}>Run reconnaissance to build intelligence.</div>}
              {op.intel.slice().reverse().map((i, idx) => (
                <div key={idx} style={{ fontSize: 12, marginBottom: 6, color: "var(--gc-text)" }}>
                  <span className="ts" style={{ marginRight: 6 }}>{fmt(i.t)}</span>{i.text}
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-terminal" /> Operation log</div></div>
            <div id="sim-console" style={{ maxHeight: 220 }}>
              {events.map((e: LiveEvent) => (
                <div key={e.seq} className="console-line" style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <span className="ts">{fmt(e.t)}</span>
                    <i className={`fa ${KIND_ICON[e.kind] ?? "fa-angle-right"}`} style={{ color: SEV_COLOR[e.severity] ?? "var(--gc-muted)", marginTop: 3, fontSize: 11 }} />
                    <span className="msg" style={{ color: e.kind === "chat" ? "#9ecbff" : undefined }}>
                      {e.kind === "chat" ? <b>{e.title}: </b> : null}{e.message || e.title}
                    </span>
                  </div>
                  {e.data?.live_fire && <LiveFireBlock lf={e.data.live_fire} />}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
