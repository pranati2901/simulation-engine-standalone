import React from 'react'
import { pct } from '../impact.js'

// Click a cascade node → its details. Fault nodes carry a full scored result; consequence
// nodes just occurred, so we show what they are and where they sit.
export default function NodeInspector({ graph, selectedId }) {
  const node = (graph?.nodes || []).find(n => n.run_id === selectedId)
  if (!node) return <div className="hint">Click any node in the cascade to inspect it.</div>
  const fault = node.node_kind === 'fault'
  const k = node.result?.kpis || {}
  const objectives = node.result?.objectives?.operator || []
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <b style={{ fontSize: 14 }}>{node.scenario_name}</b>
        <span className={`pill ${fault ? 'pill-amber' : 'pill-muted'}`}>{fault ? 'fault' : 'consequence'}</span>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12, color: 'var(--muted)', marginBottom: 10 }}>
        <span>impact: <b style={{ color: 'var(--text)' }}>{node.impact_level}</b></span>
        <span>category: <b style={{ color: 'var(--text)' }}>{node.category}</b></span>
      </div>
      {fault && (
        <>
          <div className="stat-row">
            <div className="stat"><div className="v">{pct(k.containment_rate)}</div><div className="l">contained</div></div>
            <div className="stat"><div className="v">{pct(k.detection_rate)}</div><div className="l">detected</div></div>
            <div className="stat"><div className="v">{Math.round(k.mean_time_to_resolve_s || 0)}s</div><div className="l">time to resolve</div></div>
          </div>
          {objectives.length > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 7 }}>
              {objectives.map((o, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12.5 }}>
                  <span style={{ color: o.met ? 'var(--green)' : 'var(--red)', fontWeight: 800 }}>{o.met ? '✓' : '✗'}</span>
                  <span>{o.text}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      {!fault && <div className="hint">A downstream consequence spawned by the cascade — it occurred and was logged, not scored.</div>}
    </div>
  )
}
