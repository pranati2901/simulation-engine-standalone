import { useState } from "react";
import TopologyMap from "./TopologyMap";
import Terminal, { StagedCmd } from "./Terminal";
import ToolWorkspace from "./ToolWorkspace";
import { toolCommand } from "./shared";

/* RED — "I am patient zero, watching the infection spread." Mission rail + live topology + tool
   palette (Kali tools) + the interactive terminal dock. Clicking a tool STAGES its real command;
   the operator then types it in the terminal to fire it — a hands-on-keyboard "real hack" loop. */
export default function RedWorkspace({ sim, canPlay, runTool, events, termUrl, error }:
  { sim: any; canPlay: boolean; runTool: (id: string, p?: Record<string, string>) => void;
    events: any[]; termUrl?: string | null; error?: string | null }) {
  const [tool, setTool] = useState<any>(null);
  const [pending, setPending] = useState<StagedCmd | null>(null);
  const red = sim.teams.red;
  const worm = sim.worm;
  const hosts = sim?.topology?.hosts || [];
  const pz = hosts.find((h: any) => h.patient_zero);
  const inflight = (sim.inflight || []).filter((f: any) => f.team === "red");
  const busy = inflight.length > 0;

  const hostName = (id?: string) => hosts.find((h: any) => h.id === id)?.name;
  const stage = (toolId: string, params: Record<string, string>, command: string, label: string) => {
    const hid = params.host || (params.hosts || "").split(",")[0];
    setPending({ toolId, params, command, label, targetLabel: hostName(hid) });
  };
  // Every step opens its briefing pop-up first (does / how / outcome / the real command) — so the
  // learner reads what they're about to do before staging it.
  const onToolClick = (t: any) => { if (canPlay && t.available && !busy) setTool(t); };
  const execute = (toolId: string, params: Record<string, string>) => { runTool(toolId, params); setPending(null); };

  const objectives = [
    { label: "Establish a foothold", met: hosts.some((h: any) => ["exploited", "infected", "propagating"].includes(h.state)) },
    { label: "Discover the network", met: hosts.some((h: any) => h.revealed && !h.patient_zero) },
    { label: "Move laterally / spread", met: worm.propagating || worm.infected > 1 },
    { label: "Disable recovery", met: !worm.backups_safe || hosts.some((h: any) => (h.flags || []).includes("recovery_disabled")) },
    { label: "Encrypt for impact", met: worm.impacted > 0 },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0, padding: 12 }}>
        {/* left rail */}
        <div style={{ width: 270, display: "flex", flexDirection: "column", gap: 12, overflowY: "auto", flexShrink: 0 }}>
          <div className="ws-card">
            <h3>Attacker console</h3>
            <div style={{ fontSize: 12, lineHeight: 1.7 }}>
              <div>Patient zero: <b style={{ color: "#b45309" }}>{pz?.name ?? "—"}</b></div>
              <div>State: <b style={{ color: "#ef4444" }}>{pz ? pz.state.charAt(0).toUpperCase() + pz.state.slice(1) : "—"}</b></div>
              <div style={{ color: "var(--gc-muted)", marginTop: 6 }}>Mission: progress the kill chain and detonate before the defenders stop you.</div>
            </div>
          </div>
          <div className="ws-card">
            <h3>Objectives</h3>
            {objectives.map((o) => (
              <div key={o.label} style={{ display: "flex", gap: 8, fontSize: 12.5, marginBottom: 6 }}>
                <i className={`fa ${o.met ? "fa-circle-check" : "fa-circle"}`} style={{ color: o.met ? "#22c55e" : "#475569" }} />
                <span style={{ color: o.met ? "var(--gc-text)" : "var(--gc-muted)" }}>{o.label}</span>
              </div>
            ))}
            <div style={{ marginTop: 8, fontSize: 12, color: "var(--gc-muted)" }}>Red score: <b style={{ color: "#ef4444" }}>{red.score}</b></div>
          </div>
          <div className="ws-card">
            <h3>Kali tools</h3>
            {!canPlay && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 8 }}><i className="fa fa-eye" /> spectating — claim Red to act</div>}
            {canPlay && !busy && <div style={{ fontSize: 10.5, color: "var(--gc-muted)", marginBottom: 8 }}><i className="fa fa-keyboard" /> click a tool to read its briefing, stage its command, then type it below.</div>}
            {busy && <div style={{ fontSize: 10.5, color: "#eab308", marginBottom: 8 }}><i className="fa fa-circle-notch fa-spin" /> {inflight[0].label} is running… let it finish.</div>}
            <div style={{ display: "grid", gap: 7 }}>
              {red.tools.map((t: any) => {
                const staged = pending?.toolId === t.id;
                return (
                  <button key={t.id} className="tool-btn" disabled={!canPlay || !t.available || busy}
                    style={staged ? { borderColor: "var(--gc-primary)", boxShadow: "0 0 0 1px #22d3ee55" } : undefined}
                    onClick={() => onToolClick(t)} title={t.available ? t.summary : t.reason}>
                    <span className="t-name">
                      <i className={`fa ${t.kind === "real" ? "fa-terminal" : "fa-bolt"}`} style={{ marginRight: 6, color: t.kind === "real" ? "var(--gc-primary)" : "#ef4444" }} />
                      {t.name} {t.kind === "real" && <span style={{ fontSize: 8, color: "var(--gc-primary)" }}>REAL</span>}
                      {staged && <span style={{ fontSize: 8, color: "var(--gc-primary)", marginLeft: 4 }}>STAGED ↓</span>}
                    </span>
                    <span className="t-sum">{t.available ? t.summary : `🔒 ${t.reason}`}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        {/* center: topology */}
        <div style={{ flex: 1, minWidth: 0 }}><TopologyMap sim={sim} /></div>
      </div>
      <Terminal events={events} termUrl={termUrl} pending={pending} canPlay={canPlay} onExecute={execute} error={error} inflight={inflight} />
      {tool && <ToolWorkspace tool={tool} sim={sim} mode="stage" onRun={runTool}
        onStage={(id, p, cmd) => { stage(id, p, cmd, tool.name); setTool(null); }} onClose={() => setTool(null)} />}
    </div>
  );
}
