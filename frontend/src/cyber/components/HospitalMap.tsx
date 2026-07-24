import { useMemo } from "react";

interface NetworkState {
  containment_index: number;
  infected: number;
  encrypted: number;
  isolated: number;
  total_hosts: number;
  backup_destroyed: boolean;
}

interface Segment {
  id: string; label: string; host_count: number;
}

interface Props {
  network: NetworkState;
  sceneIndex: number;
  height?: number;
  segments?: Segment[];  // scenario-specific segments
}

// Default segments (WannaCry W1). Overridden by scenario-specific segments via props.
const DEFAULT_SEGMENTS = [
  { id: "pacs", label: "Radiology / PACS", count: 40, zone: "clinical", icon: "fa-x-ray", spreadOrder: 0, patientZero: true },
  { id: "clin", label: "Clinical Workstations", count: 120, zone: "clinical", icon: "fa-desktop", spreadOrder: 1 },
  { id: "admin", label: "Admin / Billing", count: 55, zone: "corp", icon: "fa-briefcase", spreadOrder: 2 },
  { id: "dc", label: "Domain Controllers", count: 2, zone: "infra", icon: "fa-user-shield", spreadOrder: 3 },
  { id: "file", label: "File Servers", count: 8, zone: "infra", icon: "fa-folder-open", spreadOrder: 4 },
  { id: "bkp", label: "Backup Server", count: 1, zone: "infra", icon: "fa-database", spreadOrder: 5 },
  { id: "soc", label: "SOC / Analyst Tools", count: 23, zone: "soc", icon: "fa-shield-alt", spreadOrder: 6 },
];

const ICON_MAP: Record<string, string> = {
  "seg-pacs": "fa-x-ray", "seg-clin": "fa-desktop", "seg-admin": "fa-briefcase",
  "seg-dc": "fa-user-shield", "seg-file": "fa-folder-open", "seg-bkp": "fa-database",
  "seg-soc": "fa-shield-alt", "seg-finance": "fa-dollar-sign", "seg-corp": "fa-desktop",
  "seg-it": "fa-wrench", "seg-srv": "fa-server", "seg-mail": "fa-envelope",
  "seg-edge": "fa-globe", "seg-dev": "fa-code", "seg-data": "fa-database",
  "seg-cloud": "fa-cloud",
};

const ZONE_LABELS: Record<string, string> = {
  clinical: "CLINICAL", corp: "CORPORATE", infra: "INFRASTRUCTURE", soc: "SOC",
  edge: "EDGE", data: "DATA", cloud: "CLOUD", dev: "DEVELOPMENT",
};

type SegState = "safe" | "suspicious" | "compromised" | "contained";

export default function HospitalMap({ network, sceneIndex, height = 420, segments: propSegments }: Props) {
  // Build segments from props or use defaults
  const SEGMENTS = useMemo(() => {
    if (!propSegments || propSegments.length === 0) return DEFAULT_SEGMENTS;
    const zones = ["clinical", "corp", "infra", "soc", "edge", "data", "cloud", "dev"];
    return propSegments.map((s, i) => ({
      id: s.id,
      label: s.label,
      count: s.host_count,
      zone: zones[Math.min(i, zones.length - 1)] || "corp",
      icon: ICON_MAP[s.id] || "fa-server",
      spreadOrder: i,
      patientZero: i === 0,
    }));
  }, [propSegments]);

  const ZONES = useMemo(() => {
    const seen = new Set<string>();
    return SEGMENTS.map(s => s.zone).filter(z => { if (seen.has(z)) return false; seen.add(z); return true; });
  }, [SEGMENTS]);

  const segStates = useMemo(() => {
    const total = network.total_hosts || 250;
    const infRatio = network.infected / total;
    const result: Record<string, { state: SegState; infected: number; pct: number }> = {};

    for (const seg of SEGMENTS) {
      const reach = Math.max(0, Math.min(1, infRatio * 3.5 - seg.spreadOrder * 0.35));
      const inf = Math.round(seg.count * reach);
      const pct = Math.round((inf / seg.count) * 100);
      let state: SegState = "safe";
      if (inf > 0 && inf < seg.count * 0.5) state = "suspicious";
      else if (inf >= seg.count * 0.5) state = "compromised";
      // If isolated count is high and this segment is "contained"
      if (network.isolated > total * 0.15 && seg.spreadOrder <= 2 && inf > 0 && inf < seg.count * 0.3) state = "contained";
      result[seg.id] = { state, infected: inf, pct };
    }

    // Backup special case
    if (network.backup_destroyed) result["bkp"] = { state: "compromised", infected: 1, pct: 100 };

    return result;
  }, [network]);

  // Position: zones are columns, segments stack within
  const positions = useMemo(() => {
    const out: Record<string, { x: number; y: number }> = {};
    ZONES.forEach((zone, zi) => {
      const segsInZone = SEGMENTS.filter(s => s.zone === zone);
      const x = ((zi + 0.5) / ZONES.length) * 100;
      segsInZone.forEach((seg, si) => {
        const y = ((si + 0.5) / segsInZone.length) * 72 + 16;
        out[seg.id] = { x, y };
      });
    });
    return out;
  }, [SEGMENTS, ZONES]);

  const ci = network.containment_index;
  const ciColor = ci > 60 ? "var(--gc-green)" : ci > 30 ? "var(--gc-yellow)" : "var(--gc-red)";

  return (
    <div style={{ position: "relative", height, background: "#080E18", borderRadius: 8, overflow: "hidden", border: "1px solid var(--gc-border)" }}>

      {/* Zone labels */}
      {ZONES.map((zone, zi) => (
        <div key={zone} style={{
          position: "absolute", top: 6, left: `${((zi + 0.5) / ZONES.length) * 100}%`,
          transform: "translateX(-50%)", fontSize: 9, letterSpacing: 1.5,
          color: "var(--gc-muted)", fontFamily: "var(--mono)", fontWeight: 700,
        }}>{ZONE_LABELS[zone]}</div>
      ))}

      {/* Connection lines (SVG) */}
      <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
        {[["pacs", "clin"], ["clin", "admin"], ["clin", "dc"], ["dc", "file"], ["file", "bkp"], ["pacs", "soc"], ["dc", "soc"], ["admin", "file"]].map(([a, b]) => {
          const pa = positions[a], pb = positions[b];
          if (!pa || !pb) return null;
          const sa = segStates[a], sb = segStates[b];
          const active = sa?.state !== "safe" && sb?.state !== "safe";
          return (
            <line key={`${a}-${b}`} x1={`${pa.x}%`} y1={`${pa.y}%`} x2={`${pb.x}%`} y2={`${pb.y}%`}
              stroke={active ? "rgba(255,71,87,0.25)" : "rgba(255,255,255,0.06)"}
              strokeWidth={active ? 2 : 1}
              strokeDasharray={active ? "6 4" : "none"} />
          );
        })}
      </svg>

      {/* Segment nodes */}
      {SEGMENTS.map((seg) => {
        const p = positions[seg.id];
        if (!p) return null;
        const s = segStates[seg.id] || { state: "safe" as SegState, infected: 0, pct: 0 };
        const cssState = `ns-${s.state}`;

        return (
          <div key={seg.id} className={`net-node ${cssState}`}
            style={{ left: `${p.x}%`, top: `${p.y}%` }}
            title={`${seg.label}\n${seg.count} hosts total\n${s.infected} infected (${s.pct}%)\nState: ${s.state}`}>
            <div className="circle" style={{ width: Math.max(38, Math.min(56, Math.sqrt(seg.count) * 5.5)), height: Math.max(38, Math.min(56, Math.sqrt(seg.count) * 5.5)) }}>
              <i className={`fa ${seg.icon}`} />
              {seg.patientZero && sceneIndex >= 0 && s.infected > 0 && (
                <div style={{ position: "absolute", top: -4, right: -4, width: 14, height: 14, borderRadius: "50%",
                  background: "var(--gc-red)", display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 7, fontWeight: 700, color: "#fff", animation: "pulse-red 1.5s infinite" }}>P0</div>
              )}
              {seg.id === "bkp" && network.backup_destroyed && (
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 22, fontWeight: 800, color: "var(--gc-red)" }}>✕</div>
              )}
            </div>
            <div className="label">{seg.label}</div>
            <div style={{ fontSize: 8, fontFamily: "var(--mono)", color: s.infected > 0 ? "var(--gc-red)" : "var(--gc-muted)", marginTop: 1 }}>
              {s.infected > 0 ? `${s.infected}/${seg.count} infected` : `${seg.count} hosts`}
            </div>
          </div>
        );
      })}

      {/* Containment gauge (bottom) */}
      <div style={{ position: "absolute", bottom: 8, left: 10, right: 10, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 9, fontFamily: "var(--mono)", fontWeight: 700, color: "var(--gc-muted)", whiteSpace: "nowrap" }}>CONTAINMENT</span>
        <div style={{ flex: 1, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.04)" }}>
          <div style={{ height: "100%", borderRadius: 3, width: `${ci}%`, background: ciColor, transition: "width 0.5s, background 0.5s" }} />
        </div>
        <span style={{ fontSize: 10, fontFamily: "var(--mono)", fontWeight: 700, color: ciColor }}>{ci}%</span>
      </div>
    </div>
  );
}
