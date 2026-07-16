import React from 'react'
import { criticality } from '../impact.js'

export default function CriticalityPanel({ graph }) {
  const ranked = criticality(graph)
  if (!ranked.length) return null
  const top = ranked[0]
  return (
    <div className="card">
      <div className="card-title">Asset criticality<span className="tag">from cascade</span></div>
      <div style={{ background: '#fdf1e3', border: '1px solid #f5e0c2', borderRadius: 10, padding: '10px 12px', marginBottom: 12 }}>
        <div style={{ fontSize: 12.5 }}>
          <b>{top.name}</b> is the single point of failure — <b>{top.downstream}</b> downstream system(s) fail if it goes.
        </div>
        <div style={{ fontSize: 12, color: 'var(--amber)', fontWeight: 700, marginTop: 4 }}>→ Priority maintenance recommended</div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {ranked.map((r, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 9 }}>
            <span className="mono" style={{ color: 'var(--muted)', width: 14 }}>{i + 1}</span>
            <b style={{ flex: 1, fontSize: 12.5 }}>{r.name}</b>
            <span className="pill pill-muted">{r.downstream} downstream</span>
            {i === 0 && <span className="pill pill-amber">critical</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
