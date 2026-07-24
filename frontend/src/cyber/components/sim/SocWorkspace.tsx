import { useState } from "react";
import Terminal, { StagedCmd } from "./Terminal";
import ToolWorkspace from "./ToolWorkspace";
import { SEV_COLOR, fmtT } from "./shared";

/* SOC — "I am an analyst." Alert queue (triage → escalate) on the left; a real SIEM console on the
   right where the analyst STAGES a data-source / hunt query and TYPES it to run — matching detections
   stream back as query output. A live detections strip shows signals arriving in real time. */
export default function SocWorkspace({ sim, canPlay, runTool, events }:
  { sim: any; canPlay: boolean; runTool: (id: string, p?: Record<string, string>) => void; events: any[] }) {
  const [pending, setPending] = useState<StagedCmd | null>(null);
  const [tool, setTool] = useState<any>(null);
  const soc = sim.teams.soc;
  const alerts: any[] = sim.alerts || [];
  const detections = events.filter((e) => e.kind === "g_telemetry").slice(-8).reverse();
  const inflight = (sim.inflight || []).filter((f: any) => f.team === "soc");
  const busy = inflight.length > 0;

  // SOC palette = the queryable data-sources + hunt (triage/escalate live in the alert feed as buttons)
  const queries = (soc.tools || []).filter((t: any) => !(t.schema || []).some((f: any) => f.type === "alert"));
  const act = (toolId: string, params?: Record<string, string>) => canPlay && !busy && runTool(toolId, params);
  const stage = (toolId: string, command: string, label: string) => setPending({ toolId, params: {}, command, label });
  const execute = (toolId: string, params: Record<string, string>) => { runTool(toolId, params); setPending(null); };
  const socEvents = events.filter((e) => e.role === "soc" && (e.kind === "response" || e.kind === "running"));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 12, height: "100%", padding: 12, minHeight: 0 }}>
      {/* alert queue */}
      <div className="ws-card" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <h3>Alert queue · SOC score {soc.score}</h3>
        {!canPlay && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 6 }}><i className="fa fa-eye" /> spectating — claim SOC to triage</div>}
        <div style={{ flex: 1, overflowY: "auto", display: "grid", gap: 8 }}>
          {alerts.length === 0 && <div style={{ fontSize: 12, color: "var(--gc-muted)" }}>No alerts yet. The funnel starts quiet — run a query to hunt for early signals.</div>}
          {alerts.slice().reverse().map((a) => (
            <div key={a.id} style={{ border: "1px solid var(--gc-border)", borderLeft: `3px solid ${SEV_COLOR[a.severity]}`, borderRadius: 6, padding: 8 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>{a.label}</div>
              <div style={{ fontSize: 10.5, color: "var(--gc-muted)" }}>
                {fmtT(a.t)} · {a.severity.toUpperCase()}{a.host_name ? ` · ${a.host_name}` : ""}{a.mitre ? ` · ${a.mitre}` : ""}
              </div>
              {a.status === "new" && (a.noticed
                ? <div style={{ fontSize: 10, color: "#22c55e", marginTop: 3 }}><i className="fa fa-eye" /> detected — ready to triage</div>
                : <div style={{ fontSize: 10, color: "#64748b", marginTop: 3 }}><i className="fa fa-hourglass-half fa-spin" style={{ animationDuration: "2s" }} /> below the noise floor · auto-detect in ~{(a.detect_in ?? 0) * 3}s <span style={{ color: "#475569" }}>(triage now to beat MTTD)</span></div>)}
              <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                {a.status === "new" && <button className="btn" style={{ fontSize: 10, padding: "2px 8px" }} disabled={!canPlay}
                  onClick={() => act(triageId(soc), { alert: a.id })}>Triage</button>}
                {a.status === "triaged" && <button className="btn btn-primary" style={{ fontSize: 10, padding: "2px 8px" }} disabled={!canPlay}
                  onClick={() => runTool(escalateId(soc), { alert: a.id })}>Escalate to IR</button>}
                {a.status === "escalated" && <span style={{ fontSize: 10, color: "#22c55e" }}><i className="fa fa-flag" /> escalated</span>}
                {a.status !== "escalated" && <span style={{ fontSize: 10, color: "var(--gc-muted)", alignSelf: "center" }}>{a.status}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SIEM console */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
        {/* live detections strip */}
        <div className="ws-card" style={{ maxHeight: 132, overflowY: "auto", flexShrink: 0 }}>
          <h3><i className="fa fa-wave-square" /> Live detections</h3>
          {detections.length === 0 && <div style={{ fontSize: 11.5, color: "var(--gc-muted)" }}>No telemetry yet.</div>}
          {detections.map((e, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 2 }}>
              <span style={{ color: "#475569" }}>[{fmtT(e.t)}] </span>
              <span style={{ color: SEV_COLOR[e.severity], textTransform: "uppercase", fontSize: 9 }}>{e.data?.telemetry || "log"}</span>{" "}
              <span style={{ color: "var(--gc-text2)" }}>{e.title}</span>
              <span style={{ color: "#64748b" }}> — {e.message}</span>
            </div>
          ))}
        </div>

        {/* query palette */}
        <div className="ws-card" style={{ flexShrink: 0 }}>
          <h3>SIEM queries &amp; hunts</h3>
          {canPlay && !busy && <div style={{ fontSize: 10.5, color: "var(--gc-muted)", marginBottom: 6 }}><i className="fa fa-keyboard" /> click a source to read its briefing, stage the query, then type it below.</div>}
          {busy && <div style={{ fontSize: 10.5, color: "#eab308", marginBottom: 6 }}><i className="fa fa-circle-notch fa-spin" /> {inflight[0].label} is running…</div>}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {queries.map((t: any) => {
              const staged = pending?.toolId === t.id;
              return (
                <button key={t.id} className={"btn" + (staged ? " btn-primary" : "")} disabled={!canPlay || !t.available || busy}
                  style={{ fontSize: 11 }} onClick={() => setTool(t)} title={t.available ? t.summary : t.reason}>
                  <i className={`fa ${t.effect === "hunt" ? "fa-crosshairs" : "fa-magnifying-glass"}`} /> {t.name}
                  {staged && <span style={{ marginLeft: 4, fontSize: 8 }}>↓</span>}
                </button>
              );
            })}
          </div>
        </div>

        {/* the typed SIEM console */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <Terminal events={socEvents} pending={pending} canPlay={canPlay} onExecute={execute} height={320} inflight={inflight}
            prompt="soc@siem" title="soc@siem — investigation console"
            claimMsg="claim the SOC seat to run queries."
            hint="stage a query, then type it to search…"
            intro={<>SIEM console — stage a data source above, then <b style={{ color: "#94a3b8" }}>type its query</b> to search the index. Matching detections stream back as results.</>} />
        </div>
      </div>

      {tool && <ToolWorkspace tool={tool} sim={sim} mode="stage" onRun={runTool}
        onStage={(id, _p, cmd) => { stage(id, cmd, tool.name); setTool(null); }} onClose={() => setTool(null)} />}
    </div>
  );
}

// triage/escalate tool ids differ per scenario (soc_triage/soc_escalate for W1, triage_r5/escalate_r5 for R5)
function triageId(soc: any): string {
  const t = (soc.tools || []).find((x: any) => (x.schema || []).some((f: any) => f.type === "alert" && f.filter === "new"));
  return t ? t.id : "soc_triage";
}
function escalateId(soc: any): string {
  const t = (soc.tools || []).find((x: any) => (x.schema || []).some((f: any) => f.type === "alert" && f.filter === "triaged"));
  return t ? t.id : "soc_escalate";
}
