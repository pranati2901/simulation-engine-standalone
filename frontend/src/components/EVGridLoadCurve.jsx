import React from 'react'
// EVGridLoadCurve — 24h charging demand vs solar vs transformer capacity, with demand-response
// windows (ported from the NextXR twin, adapted to SimCore tokens). Pure render of net.load_curve.

export default function EVGridLoadCurve({ curve }) {
  if (!curve || !curve.length) return null
  const W = 640, H = 220, padL = 40, padB = 22, padT = 10, padR = 10
  const cap = curve[0].capacity_kw || 1
  const maxY = cap * 1.15
  const x = (h) => padL + (h / 23) * (W - padL - padR)
  const y = (v) => padT + (1 - v / maxY) * (H - padT - padB)
  const line = (key) => curve.map((p) => `${x(p.hour)},${y(p[key])}`).join(' ')
  const area = (key) => `${x(0)},${y(0)} ${line(key)} ${x(23)},${y(0)}`
  const overload = curve.filter((p) => p.demand_kw > cap)

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {curve.map((p) => p.dr_event && (
          <rect key={'dr' + p.hour} x={x(p.hour) - 6} y={padT} width="13" height={H - padT - padB} fill="var(--amber)" opacity="0.1" />
        ))}
        <line x1={padL} y1={y(cap)} x2={W - padR} y2={y(cap)} stroke="var(--red)" strokeWidth="1.4" strokeDasharray="5 4" />
        <text x={W - padR} y={y(cap) - 3} fontSize="10" textAnchor="end" fill="var(--red)">transformer capacity {cap} kW</text>
        <polygon points={area('solar_kw')} fill="rgba(245,158,11,.16)" stroke="none" />
        <polyline points={line('solar_kw')} fill="none" stroke="var(--amber)" strokeWidth="1.6" />
        <polyline points={line('demand_kw')} fill="none" stroke="var(--accent)" strokeWidth="2.4" strokeLinejoin="round" />
        <polyline points={line('grid_kw')} fill="none" stroke="#2563eb" strokeWidth="1.6" strokeDasharray="3 2" />
        <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--border)" />
        {[0, 6, 12, 18, 23].map((h) => (
          <text key={h} x={x(h)} y={H - padB + 13} fontSize="10" textAnchor="middle" fill="var(--muted)">{String(h).padStart(2, '0')}:00</text>
        ))}
      </svg>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 6, fontSize: 11.5 }}>
        {[['Charging demand', 'var(--accent)'], ['Solar', 'var(--amber)'], ['Grid import', '#2563eb'], ['DR window', 'rgba(245,158,11,.5)']].map(([l, c]) => (
          <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--muted)' }}>
            <span style={{ width: 12, height: 4, borderRadius: 2, background: c }} />{l}
          </span>
        ))}
        {overload.length > 0 && <span style={{ marginLeft: 'auto', color: 'var(--red)', fontWeight: 600 }}>⚠ demand exceeds capacity for {overload.length}h</span>}
      </div>
    </div>
  )
}
