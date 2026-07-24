import { useMemo, useState } from "react";
import { hostsForFilter, SimHost, toolCommand } from "./shared";

/* Generic tool workspace — renders a tool's schema as a form and previews the command.
   In "run" mode (Blue) it executes immediately; in "stage" mode (Red) it hands the command to the
   terminal, where the operator must TYPE it to fire — real tools then stream live-fire output. */
export default function ToolWorkspace({ tool, sim, onRun, onStage, mode = "run", onClose }:
  { tool: any; sim: any; onRun: (toolId: string, params: Record<string, string>) => void;
    onStage?: (toolId: string, params: Record<string, string>, command: string) => void;
    mode?: "run" | "stage"; onClose: () => void }) {
  const hosts: SimHost[] = sim.topology.hosts;
  const alerts: any[] = sim.alerts || [];
  const [params, setParams] = useState<Record<string, string>>(() => {
    const p: Record<string, string> = {};
    for (const f of tool.schema || []) if (f.default) p[f.key] = f.default;
    return p;
  });
  const set = (k: string, v: string) => setParams((p) => ({ ...p, [k]: v }));

  const command = useMemo(() => toolCommand(tool), [tool]);
  // pull MITRE ATT&CK technique ids out of the tool's "how"/teaching text for the briefing panel
  const mitre = useMemo<string[]>(
    () => Array.from(new Set(((tool.how || "") + " " + (tool.teaching_note || "")).match(/T\d{4}(?:\.\d{3})?/g) || [])),
    [tool]);
  // Targets must be picked before the command can fire — gate the CTA so the engine never rejects it.
  const ready = (tool.schema || []).every((f: any) =>
    !["host", "hosts", "alert"].includes(f.type) || (params[f.key] || "").length > 0);

  const go = () => {
    if (mode === "stage" && onStage) onStage(tool.id, params, command);
    else onRun(tool.id, params);
    onClose();
  };
  const accent = tool.team === "red" ? "#ef4444" : tool.team === "blue" ? "#3b82f6" : "#a855f7";

  return (
    <div style={{ position: "fixed", inset: 0, background: "#0008", zIndex: 70, display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={onClose}>
      <div className="ws-card" style={{ width: 760, maxWidth: "95vw", borderColor: accent, display: "flex", flexDirection: "column" }} onClick={(e) => e.stopPropagation()}>
        {/* header spans the whole modal */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <span style={{ color: accent, fontWeight: 700, fontSize: 16 }}>{tool.name}</span>
          {tool.kind === "real" && <span style={{ fontSize: 9, color: "#22d3ee", border: "1px solid #22d3ee66", borderRadius: 4, padding: "0 5px" }}>REAL TOOL</span>}
          <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--gc-muted)" }}>{tool.stage}</span>
          <button className="btn" style={{ padding: "1px 7px" }} onClick={onClose}><i className="fa fa-xmark" /></button>
        </div>

        <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
          {/* LEFT — briefing, target selection, the action button */}
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 12, color: "var(--gc-text2)", lineHeight: 1.55, display: "grid", gap: 5, marginBottom: 12 }}>
              <div><b style={{ color: "var(--gc-muted)" }}>Does:</b> {tool.does}</div>
              <div><b style={{ color: "var(--gc-muted)" }}>How:</b> {tool.how}</div>
              <div><b style={{ color: "var(--gc-muted)" }}>Outcome:</b> {tool.outcome}</div>
            </div>

            {(tool.schema || []).map((f: any) => (
              <div key={f.key} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 4 }}>{f.label}</div>
                {f.type === "select" && (
                  <select className="form-select" value={params[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} style={{ width: "100%" }}>
                    {f.options.map((o: [string, string]) => <option key={o[0]} value={o[0]}>{o[1]}</option>)}
                  </select>
                )}
                {f.type === "host" && (
                  <select className="form-select" value={params[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} style={{ width: "100%" }}>
                    <option value="">select host…</option>
                    {hostsForFilter(hosts, f.filter).map((h) => <option key={h.id} value={h.id}>{h.name} ({h.vlan})</option>)}
                  </select>
                )}
                {f.type === "hosts" && (
                  <div style={{ display: "grid", gap: 4, maxHeight: 150, overflowY: "auto", border: "1px solid var(--gc-border)", borderRadius: 6, padding: 6 }}>
                    {hostsForFilter(hosts, f.filter).map((h) => {
                      const sel = (params[f.key] || "").split(",").filter(Boolean);
                      const on = sel.includes(h.id);
                      return (
                        <label key={h.id} style={{ fontSize: 12, display: "flex", gap: 6, alignItems: "center" }}>
                          <input type="checkbox" checked={on} onChange={() => {
                            const next = on ? sel.filter((x) => x !== h.id) : [...sel, h.id];
                            set(f.key, next.join(","));
                          }} /> {h.name} <span style={{ color: "#64748b" }}>({h.vlan})</span>
                        </label>
                      );
                    })}
                    <button className="btn btn-ghost" style={{ fontSize: 10 }}
                      onClick={() => set(f.key, hostsForFilter(hosts, f.filter).map((h) => h.id).join(","))}>select all</button>
                  </div>
                )}
                {f.type === "alert" && (
                  <select className="form-select" value={params[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} style={{ width: "100%" }}>
                    <option value="">select alert…</option>
                    {alerts.filter((a) => a.status === (f.filter === "new" ? "new" : "triaged"))
                      .map((a) => <option key={a.id} value={a.id}>{a.label}{a.host_name ? ` · ${a.host_name}` : ""}</option>)}
                  </select>
                )}
                {f.type === "text" && (
                  <input className="form-input" value={params[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} style={{ width: "100%" }} />
                )}
              </div>
            ))}

            <button className="btn btn-primary" style={{ width: "100%", marginTop: "auto", background: accent, borderColor: accent, opacity: ready ? 1 : 0.5 }}
              disabled={!ready} onClick={go}>
              {mode === "stage"
                ? <><i className="fa fa-keyboard" /> Stage command — type it to run</>
                : <><i className={`fa ${tool.kind === "real" ? "fa-terminal" : tool.team === "blue" ? "fa-shield" : "fa-bolt"}`} /> RUN — {tool.name}</>}
            </button>
          </div>

          {/* RIGHT — the real-world command(s) + warning, on the immediate right */}
          <div style={{ width: 300, flexShrink: 0, borderLeft: "1px solid var(--gc-border)", paddingLeft: 16,
            display: "flex", flexDirection: "column", gap: 10 }}>
            <div>
              <div style={{ fontSize: 9, letterSpacing: 1, color: "var(--gc-muted)", marginBottom: 5, textTransform: "uppercase", fontWeight: 700 }}>
                <i className="fa fa-terminal" /> Real-world command
              </div>
              {command
                ? <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 11.5, color: "#22d3ee", background: "#05080f",
                    border: `1px solid ${accent}55`, borderRadius: 6, padding: "8px 9px", wordBreak: "break-all", lineHeight: 1.5 }}>
                    <span style={{ color: "#64748b" }}>$ </span>{command}
                  </div>
                : <div style={{ fontSize: 11, color: "#64748b" }}>UI/console action — no shell command.</div>}
              <div style={{ fontSize: 9.5, color: "#64748b", marginTop: 5 }}>
                {tool.kind === "real" ? "Fires live against the Kali range." : "Simulated here — safe to run for training."}
              </div>
            </div>

            {mitre.length > 0 && (
              <div>
                <div style={{ fontSize: 9, letterSpacing: 1, color: "var(--gc-muted)", marginBottom: 4, textTransform: "uppercase", fontWeight: 700 }}>MITRE ATT&amp;CK</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {mitre.map((m) => <span key={m} style={{ fontSize: 10, color: "var(--gc-text2)", border: "1px solid var(--gc-border2)", borderRadius: 4, padding: "1px 5px" }}>{m}</span>)}
                </div>
              </div>
            )}

            {tool.team === "red"
              ? <div style={{ fontSize: 10.5, color: "#b91c1c", background: "#fef2f2", border: "1px solid #7f1d1d",
                  borderRadius: 6, padding: "8px 9px", lineHeight: 1.5, marginTop: "auto" }}>
                  <i className="fa fa-triangle-exclamation" /> <b>Offensive technique.</b> This is the actual command an
                  attacker runs. Using it against systems you don't own is illegal — here it's a safe, simulated range
                  for learning detection &amp; defense.
                </div>
              : <div style={{ fontSize: 10.5, color: "#1d4ed8", background: "#eff6ff", border: "1px solid #1e3a5f",
                  borderRadius: 6, padding: "8px 9px", lineHeight: 1.5, marginTop: "auto" }}>
                  <i className="fa fa-shield-halved" /> <b>Defender action.</b> This is the real command a {tool.team === "soc" ? "SOC analyst" : "responder"} would
                  run. Learn what it does and when to use it.
                </div>}

            {mode === "stage" && (
              <div style={{ fontSize: 10, color: "var(--gc-muted)" }}>
                <i className="fa fa-keyboard" /> You'll <b>type this</b> in the terminal — it then takes a little time to execute.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
