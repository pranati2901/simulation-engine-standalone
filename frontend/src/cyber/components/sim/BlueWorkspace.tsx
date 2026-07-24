import { useState } from "react";
import TopologyMap from "./TopologyMap";
import Terminal, { StagedCmd } from "./Terminal";
import ToolWorkspace from "./ToolWorkspace";
import { fmtUSD, STATE_COLOR, STATE_LABEL, toolCommand } from "./shared";

/* BLUE — "I respond." Network-health dashboard + a real IR console: stage a containment / eradication
   / recovery action from the palette, then TYPE its command (PowerShell, EDR, firewall, Veeam) to run
   it — the same hands-on-keyboard loop as Red, with simulated tool output streaming back. */
export default function BlueWorkspace({ sim, canPlay, runTool, events, error }:
  { sim: any; canPlay: boolean; runTool: (id: string, p?: Record<string, string>) => void;
    events: any[]; error?: string | null }) {
  const [tool, setTool] = useState<any>(null);
  const [pending, setPending] = useState<StagedCmd | null>(null);
  const blue = sim.teams.blue;
  const worm = sim.worm;
  const counts = sim.topology.counts;
  const inflight = (sim.inflight || []).filter((f: any) => f.team === "blue");
  const busy = inflight.length > 0;

  const hostName = (id?: string) => sim.topology.hosts.find((h: any) => h.id === id)?.name;
  const stage = (toolId: string, params: Record<string, string>, command: string, label: string) => {
    const hid = params.host || (params.hosts || "").split(",")[0];
    setPending({ toolId, params, command, label, targetLabel: hostName(hid) });
  };
  const onToolClick = (t: any) => { if (canPlay && t.available && !busy) setTool(t); };   // briefing first
  const execute = (toolId: string, params: Record<string, string>) => { runTool(toolId, params); setPending(null); };

  // The IR console shows Blue's own actions (its command + simulated result), not Red's.
  const blueEvents = events.filter((e: any) => e.role === "blue");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* health dashboard */}
      <div className="ws-card" style={{ margin: "12px 12px 0" }}>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center" }}>
          {["healthy", "vulnerable", "exploited", "infected", "impacted", "contained", "dormant", "recovered"].map((s) => (
            <div key={s} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 17, fontWeight: 800, color: STATE_COLOR[s] }}>
                {counts[s] || 0}{s === "infected" ? `+${worm.extra_infected || 0}` : s === "impacted" ? `+${worm.extra_impacted || 0}` : ""}
              </div>
              <div style={{ fontSize: 9, color: "var(--gc-muted)", textTransform: "uppercase" }}>{STATE_LABEL[s]}</div>
            </div>
          ))}
          <div style={{ marginLeft: "auto", textAlign: "center" }}>
            <div style={{ fontSize: 17, fontWeight: 800, color: worm.r_value > 1 ? "#f59e0b" : "#22c55e" }}>R {worm.r_value}</div>
            <div style={{ fontSize: 9, color: "var(--gc-muted)" }}>reproduction</div>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0, padding: 12 }}>
        {/* action center + business impact */}
        <div style={{ width: 290, display: "flex", flexDirection: "column", gap: 12, overflowY: "auto", flexShrink: 0 }}>
          <div className="ws-card">
            <h3>IR action center · score {blue.score}</h3>
            {!canPlay && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 8 }}><i className="fa fa-eye" /> spectating — claim Blue to act</div>}
            {canPlay && !busy && <div style={{ fontSize: 10.5, color: "var(--gc-muted)", marginBottom: 8 }}><i className="fa fa-keyboard" /> click an action to read its briefing, stage its command, then type it below.</div>}
            {busy && <div style={{ fontSize: 10.5, color: "#eab308", marginBottom: 8 }}><i className="fa fa-circle-notch fa-spin" /> {inflight[0].label} is running… let it finish.</div>}
            <div style={{ display: "grid", gap: 7 }}>
              {blue.tools.map((t: any) => {
                const staged = pending?.toolId === t.id;
                return (
                  <button key={t.id} className="tool-btn" disabled={!canPlay || !t.available || busy}
                    style={staged ? { borderColor: "#3b82f6", boxShadow: "0 0 0 1px #3b82f655" } : undefined}
                    onClick={() => onToolClick(t)} title={t.available ? t.summary : t.reason}>
                    <span className="t-name">
                      <i className="fa fa-shield-halved" style={{ marginRight: 6, color: "#3b82f6" }} />{t.name}
                      <span style={{ fontSize: 8, color: "#64748b", marginLeft: 4 }}>{t.stage}</span>
                      {staged && <span style={{ fontSize: 8, color: "#3b82f6", marginLeft: 4 }}>STAGED ↓</span>}
                    </span>
                    <span className="t-sum">{t.available ? t.summary : `🔒 ${t.reason}`}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="ws-card">
            <h3>Business impact</h3>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#f59e0b" }}>{fmtUSD(worm.financial_loss)}</div>
            <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 8 }}>estimated loss</div>
            <div style={{ fontSize: 12, color: "var(--gc-text2)" }}>{worm.impacted} hosts impacted · backups {worm.backups_safe ? "safe" : "lost"}</div>
            <div style={{ fontSize: 12, marginTop: 4, color: worm.outcome_band === "Contained" ? "#22c55e" : worm.outcome_band === "Degraded" ? "#f59e0b" : "#ef4444" }}>
              Trajectory: <b>{worm.outcome_band}</b>
            </div>
          </div>
        </div>
        {/* topology (read-only, so Blue sees the spread) */}
        <div style={{ flex: 1, minWidth: 0 }}><TopologyMap sim={sim} /></div>
      </div>

      <Terminal events={blueEvents} pending={pending} canPlay={canPlay} onExecute={execute} error={error} inflight={inflight}
        prompt="blue@ir-console" title="blue@ir-console — incident response"
        claimMsg="claim the Blue seat to run response actions."
        hint="stage a response, then type its command…"
        intro={<>Incident-response console — stage a containment / eradication / recovery action, then <b style={{ color: "#94a3b8" }}>type its command</b> to run it.</>} />

      {tool && <ToolWorkspace tool={tool} sim={sim} mode="stage" onRun={runTool}
        onStage={(id, p, cmd) => { stage(id, p, cmd, tool.name); setTool(null); }} onClose={() => setTool(null)} />}
    </div>
  );
}
