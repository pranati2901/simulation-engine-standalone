import { useEffect, useRef, useState } from "react";
import { STATE_COLOR, STATE_LABEL, HOST_ICON, fmtUSD, SimHost } from "./shared";

/* Structured VLAN map — named host nodes coloured by state, R-value gauge, infection counter,
   strike-flash on state change + a scan ring on freshly-discovered hosts. Shared by every team view.
   An expand button opens the whole map full-screen with larger nodes (so the WS/PC states are legible). */
export default function TopologyMap({ sim, onPick, compact }: { sim: any; onPick?: (h: SimHost) => void; compact?: boolean }) {
  const topo = sim.topology;
  const worm = sim.worm;
  const hosts: SimHost[] = topo.hosts;
  const prev = useRef<Record<string, string>>({});
  const [flash, setFlash] = useState<Record<string, number>>({});
  const [full, setFull] = useState(false);

  useEffect(() => {
    const changed: Record<string, number> = {};
    for (const h of hosts) {
      if (prev.current[h.id] && prev.current[h.id] !== h.state) changed[h.id] = Date.now();
      prev.current[h.id] = h.state;
    }
    if (Object.keys(changed).length) {
      setFlash((f) => ({ ...f, ...changed }));
      const t = setTimeout(() => setFlash((f) => {
        const n = { ...f }; for (const k of Object.keys(changed)) delete n[k]; return n;
      }), 800);
      return () => clearTimeout(t);
    }
  }, [hosts]);

  const band = worm.outcome_band;
  const bandColor = band === "Contained" ? "#16a34a" : band === "Degraded" ? "#ea580c" : "#dc2626";

  const controlBar = (
    <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
      <Stat label="R-value" value={worm.r_value} color={worm.r_value > 1 ? "#ea580c" : "#16a34a"} />
      <Stat label="Infected" value={worm.infected} color="#dc2626" />
      <Stat label="Impacted" value={worm.impacted} color="#b91c1c" />
      <Stat label={`of ${topo.total_hosts}`} value={`${Math.round(((worm.infected + worm.impacted) / topo.total_hosts) * 100)}%`} />
      <Stat label="Est. loss" value={fmtUSD(worm.financial_loss)} color="#ea580c" />
      <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center", fontSize: 11 }}>
        {worm.propagating && <span style={{ color: "#dc2626", fontWeight: 600 }}><i className="fa fa-radiation" /> SPREADING</span>}
        {worm.segmented && <span style={{ color: "#2563eb" }}><i className="fa fa-network-wired" /> segmented</span>}
        {worm.kill_switch === "tripped" && <span style={{ color: "#64748b" }}><i className="fa fa-power-off" /> kill-switch</span>}
        {worm.smbv1_patched && <span style={{ color: "#16a34a" }}><i className="fa fa-shield" /> patched</span>}
        <span style={{ color: bandColor, fontWeight: 700, border: `1px solid ${bandColor}66`, borderRadius: 6, padding: "1px 8px" }}>{band}</span>
        <button className="ws-icon" onClick={() => setFull((f) => !f)} title={full ? "Exit full screen" : "Expand to full screen"}>
          <i className={`fa ${full ? "fa-compress" : "fa-expand"}`} />
        </button>
      </div>
    </div>
  );

  const grid = (big: boolean) => (
    <div className={"topo" + (big ? " big" : "")} style={{ gridTemplateColumns: `repeat(${Math.min(topo.vlans.length, big ? 4 : topo.vlans.length)}, 1fr)`, flex: 1, minHeight: 0, overflowY: "auto" }}>
      {topo.vlans.map((v: any) => {
        const vh = hosts.filter((h) => h.vlan === v.id);
        return (
          <div key={v.id} className="topo-vlan">
            <h4>{v.name} · {vh.length}</h4>
            <div className="topo-grid">
              {vh.map((h) => {
                const cls = "node" + (h.patient_zero ? " pz" : "")
                  + (flash[h.id] ? " strike" : "")
                  + (["infected", "propagating", "encrypting"].includes(h.state) ? " spreading" : "");
                return (
                  <div key={h.id} className={cls} title={`${h.name} — ${STATE_LABEL[h.state]}${h.vulnerable ? " · vulnerable" : ""}`}
                    onClick={() => onPick?.(h)}>
                    <div className="dot" style={{ background: STATE_COLOR[h.state] || "#334155" }}>
                      {!h.revealed && h.state === "healthy" ? <i className="fa fa-question" style={{ opacity: .5 }} />
                        : <i className={`fa ${HOST_ICON[h.role] || "fa-desktop"}`} />}
                      {worm.propagating && h.state === "propagating" && <span className="scan-ring" />}
                      {h.flags.includes("persistent") && <i className="fa fa-anchor anchor" />}
                    </div>
                    {(!compact || big) && <div className="nm">{h.name}</div>}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );

  const legend = (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, fontSize: 10.5, color: "var(--gc-muted)", flexWrap: "wrap", gap: 8 }}>
      <span>+ {topo.extra_hosts} more hosts in the fleet ({worm.extra_infected || 0} infected · {worm.extra_impacted || 0} impacted)</span>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {["healthy", "vulnerable", "exploited", "infected", "impacted", "contained", "dormant"].map((s) => (
          <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: STATE_COLOR[s], display: "inline-block" }} />{STATE_LABEL[s]}
          </span>
        ))}
      </div>
    </div>
  );

  return (
    <>
      <div className="ws-card" style={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
        {controlBar}
        {grid(false)}
        {legend}
      </div>

      {full && (
        <div style={{ position: "fixed", inset: 0, zIndex: 90, background: "rgba(20,12,40,.55)", backdropFilter: "blur(3px)",
          display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }} onClick={() => setFull(false)}>
          <div className="ws-card" style={{ width: "min(1200px, 96vw)", height: "92vh", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}><i className="fa fa-network-wired" style={{ marginRight: 6 }} /> Network topology — full view</h3>
              <button className="ws-icon" style={{ marginLeft: "auto" }} onClick={() => setFull(false)}><i className="fa fa-xmark" /></button>
            </div>
            {controlBar}
            {grid(true)}
            {legend}
          </div>
        </div>
      )}
    </>
  );
}

function Stat({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="gauge" style={{ textAlign: "center" }}>
      <div style={{ fontSize: 18, fontWeight: 800, color: color || "var(--gc-text)", lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 9, color: "var(--gc-muted)", textTransform: "uppercase", letterSpacing: .5 }}>{label}</div>
    </div>
  );
}
