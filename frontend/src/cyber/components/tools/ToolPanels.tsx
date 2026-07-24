/**
 * Simulated tool panels — realistic-looking cybersecurity tool UIs.
 *
 * Each tool renders contextual data based on the current scene's telemetry.
 * All data is scripted/simulated — no real tool execution.
 */
import { useState } from "react";
import { TEAM_COLORS, type ToolDef } from "./ToolRegistry";

interface ToolPanelProps {
  tool: ToolDef;
  telemetry: { sev: string; source: string; msg: string }[];
  sceneIndex: number;
  network: { containment_index: number; infected: number; encrypted: number; isolated: number; backup_destroyed: boolean };
  scenarioId: string;
}

const SEV_COLORS: Record<string, string> = {
  critical: "#C8413E", high: "#E07A3E", medium: "#E6B400", low: "#5B7FB0", info: "#4E5D73",
};

function ToolShell({ tool, children }: { tool: ToolDef; children: React.ReactNode }) {
  const color = TEAM_COLORS[tool.team] || "var(--gc-muted)";
  return (
    <div style={{ background: "#0a0e16", borderRadius: 8, border: `1px solid ${color}30`, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", background: `${color}10`, borderBottom: `1px solid ${color}20` }}>
        <i className={`fa ${tool.icon}`} style={{ color, fontSize: 12 }} />
        <span style={{ fontSize: 11, fontWeight: 700, color }}>{tool.name}</span>
        <span style={{ fontSize: 9, color: "var(--gc-muted)", marginLeft: "auto" }}>{tool.team.toUpperCase()}</span>
        <span className="status-dot" style={{ background: "#3BA776", width: 6, height: 6 }} />
      </div>
      <div style={{ padding: 8, maxHeight: 200, overflowY: "auto", fontFamily: "var(--mono)", fontSize: 11 }}>
        {children}
      </div>
    </div>
  );
}

function AlertQueue({ telemetry }: { telemetry: ToolPanelProps["telemetry"] }) {
  return (
    <>
      {telemetry.map((t, i) => (
        <div key={i} style={{ display: "flex", gap: 6, padding: "4px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
          <span style={{ fontSize: 9, padding: "1px 4px", borderRadius: 3, background: `${SEV_COLORS[t.sev]}20`, color: SEV_COLORS[t.sev], fontWeight: 700, textTransform: "uppercase", whiteSpace: "nowrap" }}>{t.sev}</span>
          <span style={{ color: "#5B8CFF", whiteSpace: "nowrap" }}>[{t.source}]</span>
          <span style={{ color: "#c8d6e5" }}>{t.msg}</span>
        </div>
      ))}
      {telemetry.length === 0 && <div style={{ color: "var(--gc-muted)" }}>No alerts in queue</div>}
    </>
  );
}

function ProcessTree({ sceneIndex }: { sceneIndex: number }) {
  const trees: Record<number, string[]> = {
    1: ["svchost.exe (PID 832)", "  └─ cmd.exe (PID 2104)", "      └─ powershell.exe (PID 3892) -enc [Base64...]"],
    2: ["explorer.exe (PID 1240)", "  └─ WINWORD.EXE (PID 4501)", "      └─ cmd.exe (PID 5012)", "          └─ powershell.exe (PID 5891)"],
    3: ["svchost.exe (PID 832)", "  └─ tasksche.exe (PID 6120) [SUSPICIOUS]", "  └─ mssecsvc.exe (PID 6244) [MALICIOUS]"],
    5: ["svchost.exe (PID 832)", "  └─ rundll32.exe (PID 7102)", "      └─ [ACCESS] lsass.exe (PID 652) PROCESS_VM_READ"],
  };
  const tree = trees[sceneIndex] || ["system (PID 4)", "  └─ smss.exe (PID 392)", "      └─ csrss.exe (PID 496)"];
  return (
    <>
      <div style={{ color: "var(--gc-muted)", marginBottom: 4 }}>Process Tree — Host: Patient-Zero</div>
      {tree.map((line, i) => (
        <div key={i} style={{ color: line.includes("SUSPICIOUS") || line.includes("MALICIOUS") ? "#C8413E" : line.includes("ACCESS") ? "#E07A3E" : "#c8d6e5", whiteSpace: "pre" }}>{line}</div>
      ))}
    </>
  );
}

function BackupStatus({ network }: { network: ToolPanelProps["network"] }) {
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Backup Server (BKP-01)</span>
        <span style={{ fontWeight: 700, color: network.backup_destroyed ? "#C8413E" : "#3BA776" }}>
          {network.backup_destroyed ? "COMPROMISED" : "ONLINE"}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Shadow Copies</span>
        <span style={{ color: network.encrypted > 0 ? "#C8413E" : "#3BA776" }}>
          {network.encrypted > 0 ? "DELETED" : "Available"}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Offline Tapes</span>
        <span style={{ color: "#3BA776" }}>INTACT (air-gapped)</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Last Full Backup</span>
        <span style={{ color: "#c8d6e5" }}>6 hours ago</span>
      </div>
    </>
  );
}

function FirewallRules({ sceneIndex }: { sceneIndex: number }) {
  const rules = [
    { id: "R001", action: "ALLOW", src: "Corp", dst: "Internet", port: "443", status: "active" },
    { id: "R002", action: "ALLOW", src: "Corp", dst: "DC", port: "389,636", status: "active" },
    { id: "R003", action: "DENY", src: "Clinical", dst: "Clinical", port: "445", status: sceneIndex >= 6 ? "active" : "inactive" },
    { id: "R004", action: "DENY", src: "*", dst: "Internet", port: "80", status: sceneIndex >= 5 ? "active" : "inactive" },
    { id: "R005", action: "DENY", src: "*", dst: "C2-domain", port: "*", status: sceneIndex >= 5 ? "active" : "inactive" },
  ];
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "50px 50px 70px 70px 50px 60px", gap: 4, fontSize: 10, color: "var(--gc-muted)", fontWeight: 700, marginBottom: 4 }}>
        <span>ID</span><span>Action</span><span>Src</span><span>Dst</span><span>Port</span><span>Status</span>
      </div>
      {rules.map(r => (
        <div key={r.id} style={{ display: "grid", gridTemplateColumns: "50px 50px 70px 70px 50px 60px", gap: 4, fontSize: 10, padding: "2px 0", color: "#c8d6e5" }}>
          <span>{r.id}</span>
          <span style={{ color: r.action === "DENY" ? "#C8413E" : "#3BA776" }}>{r.action}</span>
          <span>{r.src}</span><span>{r.dst}</span><span>{r.port}</span>
          <span style={{ color: r.status === "active" ? "#3BA776" : "var(--gc-muted)" }}>{r.status}</span>
        </div>
      ))}
    </>
  );
}

function AssetList({ network }: { network: ToolPanelProps["network"] }) {
  const total = network.infected + network.isolated + (250 - network.infected - network.isolated);
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, textAlign: "center", marginBottom: 8 }}>
        <div><div style={{ fontSize: 16, fontWeight: 700, color: "#3BA776" }}>{250 - network.infected - network.isolated}</div><div style={{ fontSize: 9, color: "var(--gc-muted)" }}>Clean</div></div>
        <div><div style={{ fontSize: 16, fontWeight: 700, color: "#E07A3E" }}>{network.infected}</div><div style={{ fontSize: 9, color: "var(--gc-muted)" }}>Infected</div></div>
        <div><div style={{ fontSize: 16, fontWeight: 700, color: "#C8413E" }}>{network.encrypted}</div><div style={{ fontSize: 9, color: "var(--gc-muted)" }}>Encrypted</div></div>
        <div><div style={{ fontSize: 16, fontWeight: 700, color: "#5B7FB0" }}>{network.isolated}</div><div style={{ fontSize: 9, color: "var(--gc-muted)" }}>Isolated</div></div>
      </div>
    </>
  );
}

function IAMPanel({ sceneIndex }: { sceneIndex: number }) {
  const accounts = [
    { user: "j.harper", status: sceneIndex >= 5 ? "DISABLED" : "Active", mfa: false, risk: sceneIndex >= 1 ? "HIGH" : "Normal" },
    { user: "svc_backup", status: sceneIndex >= 6 ? "DISABLED" : "Active", mfa: false, risk: sceneIndex >= 5 ? "CRITICAL" : "Normal" },
    { user: "admin", status: "Active", mfa: true, risk: "Normal" },
  ];
  return (
    <>
      {accounts.map(a => (
        <div key={a.user} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
          <span style={{ color: "#c8d6e5" }}>{a.user}</span>
          <span style={{ fontSize: 9, color: a.mfa ? "#3BA776" : "#E07A3E" }}>{a.mfa ? "MFA" : "NO MFA"}</span>
          <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, background: a.status === "DISABLED" ? "rgba(200,65,62,0.15)" : "rgba(59,167,118,0.15)", color: a.status === "DISABLED" ? "#C8413E" : "#3BA776" }}>{a.status}</span>
          <span style={{ fontSize: 9, color: a.risk === "CRITICAL" ? "#C8413E" : a.risk === "HIGH" ? "#E07A3E" : "var(--gc-muted)" }}>{a.risk}</span>
        </div>
      ))}
    </>
  );
}

function IRTimeline({ sceneIndex }: { sceneIndex: number }) {
  const events = [
    { t: "16:42", event: "Initial alert — scanning detected", done: sceneIndex >= 0 },
    { t: "16:55", event: "Patient zero identified (RAD-07)", done: sceneIndex >= 2 },
    { t: "17:10", event: "Persistence mechanisms found", done: sceneIndex >= 4 },
    { t: "17:30", event: "C2 channel identified", done: sceneIndex >= 5 },
    { t: "17:45", event: "Lateral movement confirmed", done: sceneIndex >= 6 },
    { t: "18:00", event: "Containment actions initiated", done: sceneIndex >= 7 },
    { t: "18:30", event: "Encryption detected", done: sceneIndex >= 9 },
    { t: "19:00", event: "Incident declared — IR plan activated", done: sceneIndex >= 10 },
  ];
  return (
    <>
      {events.filter(e => e.done).map((e, i) => (
        <div key={i} style={{ display: "flex", gap: 8, padding: "3px 0", alignItems: "center" }}>
          <span style={{ color: "#5B7FB0", whiteSpace: "nowrap", fontSize: 10 }}>{e.t}</span>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#3BA776", flexShrink: 0 }} />
          <span style={{ color: "#c8d6e5" }}>{e.event}</span>
        </div>
      ))}
      {events.filter(e => !e.done).length > 0 && (
        <div style={{ color: "var(--gc-muted)", fontSize: 10, marginTop: 4 }}>
          {events.filter(e => !e.done).length} pending actions...
        </div>
      )}
    </>
  );
}

function C2Panel({ sceneIndex }: { sceneIndex: number }) {
  const blocked = sceneIndex >= 5;
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Channel</span>
        <span style={{ color: "#c8d6e5" }}>HTTPS (443/tcp)</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Destination</span>
        <span style={{ color: "#E07A3E" }}>cdn-assets-update.azurewebsites.net</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Beacon Interval</span>
        <span style={{ color: "#c8d6e5" }}>60s (±15s jitter)</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Status</span>
        <span style={{ fontWeight: 700, color: blocked ? "#C8413E" : "#3BA776" }}>
          {blocked ? "BLOCKED" : "ACTIVE — beaconing"}
        </span>
      </div>
    </>
  );
}

function RansomwarePanel({ network }: { network: ToolPanelProps["network"] }) {
  if (network.encrypted === 0) return <div style={{ color: "var(--gc-muted)" }}>No encryption activity detected</div>;
  const pct = Math.min(100, Math.round(network.encrypted / 250 * 100));
  return (
    <>
      <div style={{ color: "#C8413E", fontWeight: 700, marginBottom: 6 }}>⚠ ACTIVE ENCRYPTION DETECTED</div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Hosts encrypting</span>
        <span style={{ color: "#C8413E", fontWeight: 700 }}>{network.encrypted}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
        <span style={{ color: "var(--gc-muted)" }}>Coverage</span>
        <span style={{ color: "#C8413E" }}>{pct}%</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.05)", marginTop: 4 }}>
        <div style={{ height: "100%", borderRadius: 3, width: `${pct}%`, background: "#C8413E", transition: "width 0.5s" }} />
      </div>
      <div style={{ color: "var(--gc-muted)", fontSize: 10, marginTop: 4 }}>Extension: .WNCRY / .locked</div>
    </>
  );
}

/** Main dispatcher — renders the right panel for each tool type */
export default function ToolPanel({ tool, telemetry, sceneIndex, network, scenarioId }: ToolPanelProps) {
  switch (tool.id) {
    case "siem": return <ToolShell tool={tool}><AlertQueue telemetry={telemetry} /></ToolShell>;
    case "edr": return <ToolShell tool={tool}><ProcessTree sceneIndex={sceneIndex} /></ToolShell>;
    case "hunt": return <ToolShell tool={tool}><AlertQueue telemetry={telemetry.filter(t => t.sev === "critical" || t.sev === "high")} /></ToolShell>;
    case "backup": return <ToolShell tool={tool}><BackupStatus network={network} /></ToolShell>;
    case "firewall": return <ToolShell tool={tool}><FirewallRules sceneIndex={sceneIndex} /></ToolShell>;
    case "assets": return <ToolShell tool={tool}><AssetList network={network} /></ToolShell>;
    case "iam": return <ToolShell tool={tool}><IAMPanel sceneIndex={sceneIndex} /></ToolShell>;
    case "ir": return <ToolShell tool={tool}><IRTimeline sceneIndex={sceneIndex} /></ToolShell>;
    case "c2": return <ToolShell tool={tool}><C2Panel sceneIndex={sceneIndex} /></ToolShell>;
    case "ransomware": return <ToolShell tool={tool}><RansomwarePanel network={network} /></ToolShell>;
    case "dns": return <ToolShell tool={tool}><AlertQueue telemetry={telemetry.filter(t => t.source === "DNS" || t.source === "Proxy")} /></ToolShell>;
    case "http": return <ToolShell tool={tool}><AlertQueue telemetry={telemetry.filter(t => t.source === "Proxy" || t.source === "NetFlow")} /></ToolShell>;
    case "ad": return <ToolShell tool={tool}><AlertQueue telemetry={telemetry.filter(t => t.source === "AD" || t.source === "Azure AD")} /></ToolShell>;
    case "scoring":
      return (
        <ToolShell tool={tool}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, textAlign: "center" }}>
            <div><div style={{ fontSize: 14, fontWeight: 700, color: network.containment_index > 60 ? "#3BA776" : "#C8413E" }}>{network.containment_index}</div><div style={{ fontSize: 9, color: "var(--gc-muted)" }}>Containment</div></div>
            <div><div style={{ fontSize: 14, fontWeight: 700, color: "#E07A3E" }}>{network.infected}</div><div style={{ fontSize: 9, color: "var(--gc-muted)" }}>Infected</div></div>
          </div>
        </ToolShell>
      );
    default:
      return (
        <ToolShell tool={tool}>
          <div style={{ color: "var(--gc-muted)" }}>{tool.description}</div>
          <AlertQueue telemetry={telemetry} />
        </ToolShell>
      );
  }
}
