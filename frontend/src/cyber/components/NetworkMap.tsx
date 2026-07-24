import { useMemo } from "react";
import type { AssetNode } from "../api/types";

const ICON: Record<string, string> = {
  endpoint: "fa-desktop", server: "fa-server", domain_controller: "fa-user-shield",
  email_server: "fa-envelope", file_share: "fa-folder-open", erp: "fa-cubes",
  mes: "fa-industry", digital_twin: "fa-clone", cloud: "fa-cloud", ot_plc: "fa-microchip",
  siem_platform: "fa-lock", edr_platform: "fa-virus-slash", firewall: "fa-shield-alt",
  vuln_mgmt: "fa-clipboard-check",
};

const ZONE_ORDER = ["perimeter", "corp", "soc", "cloud", "ot_dmz", "ot"];

export default function NetworkMap({ assets }: { assets: Record<string, AssetNode> }) {
  const positions = useMemo(() => {
    const list = Object.values(assets);
    const zones = [...new Set(list.map((a) => a.zone))].sort(
      (a, b) => (ZONE_ORDER.indexOf(a) + 99) % 100 - (ZONE_ORDER.indexOf(b) + 99) % 100,
    );
    const out: Record<string, { x: number; y: number; zone: string }> = {};
    zones.forEach((zone, zi) => {
      const inZone = list.filter((a) => a.zone === zone);
      const x = ((zi + 0.5) / zones.length) * 100;
      inZone.forEach((a, ai) => {
        const y = ((ai + 0.5) / inZone.length) * 82 + 10;
        out[a.id] = { x, y, zone };
      });
    });
    return { out, zones };
  }, [assets]);

  return (
    <div style={{ position: "relative", height: 420, background: "#080E18", borderRadius: 8, overflow: "hidden" }}>
      {positions.zones.map((zone, zi) => (
        <div key={zone} style={{
          position: "absolute", top: 6, left: `${((zi + 0.5) / positions.zones.length) * 100}%`,
          transform: "translateX(-50%)", fontSize: 9, letterSpacing: 1, textTransform: "uppercase",
          color: "var(--gc-muted)", fontFamily: "var(--mono)",
        }}>{zone}</div>
      ))}
      {Object.values(assets).map((a) => {
        const p = positions.out[a.id];
        if (!p) return null;
        return (
          <div key={a.id} className={`net-node ns-${a.security_state}`} style={{ left: `${p.x}%`, top: `${p.y}%` }}
            title={`${a.name} — ${a.security_state}${a.health !== "nominal" ? " / " + a.health : ""}`}>
            <div className="circle"><i className={`fa ${ICON[a.type] || "fa-server"}`} /></div>
            <div className="label">{a.name}</div>
          </div>
        );
      })}
    </div>
  );
}
