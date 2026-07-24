import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AssetType, ControlType, TechniqueType } from "../api/types";

const TABS = ["assets", "controls", "techniques"] as const;

export default function Catalog() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("assets");
  const assets = useQuery<AssetType[]>({ queryKey: ["assets"], queryFn: api.assets });
  const controls = useQuery<ControlType[]>({ queryKey: ["controls"], queryFn: api.controls });
  const techniques = useQuery<TechniqueType[]>({ queryKey: ["techniques"], queryFn: api.techniques });

  return (
    <>
      <div className="section-header">
        <h1>Building-Block Catalog</h1>
        <p>The reusable models the engine composes — assets, controls and attacker techniques</p>
      </div>
      <div className="tabs" style={{ maxWidth: 420 }}>
        {TABS.map((t) => <button key={t} className={"tab-btn" + (tab === t ? " active" : "")} onClick={() => setTab(t)}>
          {t[0].toUpperCase() + t.slice(1)} ({(t === "assets" ? assets.data : t === "controls" ? controls.data : techniques.data)?.length ?? 0})
        </button>)}
      </div>

      {tab === "assets" && (
        <div className="grid-3">
          {(assets.data ?? []).map((a) => (
            <div key={a.key} className="card">
              <div className="card-title" style={{ marginBottom: 8 }}><i className={`fa ${a.icon}`} /> {a.name}</div>
              <div className="muted" style={{ fontSize: 12, lineHeight: 1.5, marginBottom: 8 }}>{a.description}</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span className="tag">{a.category}</span>
                <span className="tag" style={{ background: "rgba(123,97,255,.12)", color: "var(--gc-accent2)" }}>zone: {a.default_zone}</span>
                <span className="tag" style={{ background: "rgba(255,214,0,.12)", color: "var(--gc-yellow)" }}>crit {a.default_criticality}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "controls" && (
        <div className="grid-3">
          {(controls.data ?? []).map((c) => (
            <div key={c.key} className="card">
              <div className="card-title" style={{ marginBottom: 8 }}><i className={`fa ${c.icon}`} /> {c.name}</div>
              <div className="muted" style={{ fontSize: 12, lineHeight: 1.5, marginBottom: 8 }}>{c.description}</div>
              <span className="tag" style={{ background: "rgba(0,230,118,.12)", color: "var(--gc-green)" }}>{c.default_scope}</span>
            </div>
          ))}
        </div>
      )}

      {tab === "techniques" && (
        <div className="card">
          <table className="score-table">
            <thead><tr><th>MITRE</th><th>Technique</th><th>Tactic</th><th>Severity</th><th>Detected by</th><th>Prevented by</th></tr></thead>
            <tbody>
              {(techniques.data ?? []).map((t) => (
                <tr key={t.key}>
                  <td style={{ fontFamily: "var(--mono)", color: "var(--gc-accent)", fontSize: 11 }}>{t.mitre}</td>
                  <td style={{ fontWeight: 600 }}>{t.name}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{t.tactic}</td>
                  <td><span className={`diff-badge diff-${t.severity === "critical" || t.severity === "high" ? "expert" : t.severity === "medium" ? "hard" : "easy"}`}>{t.severity}</span></td>
                  <td className="muted" style={{ fontSize: 11 }}>{t.detects.join(", ") || "—"}</td>
                  <td className="muted" style={{ fontSize: 11 }}>{t.prevents.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
