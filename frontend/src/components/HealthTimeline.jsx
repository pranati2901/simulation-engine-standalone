import React, { useEffect, useMemo, useState } from 'react'
import { savingFactor } from '../impact.js'

const W = { low: 0.4, medium: 1, high: 2.2, critical: 4 }
const FLOOR_DROP = 72   // how far health falls when the whole cascade fires uncontained

// Health deterioration over time — derived from the real cascade: each node drags asset
// health down as it fires at its t_offset; a prepared response mitigates the *preventable*
// branches, so the two lines diverge. Play it forward to watch it happen.
export default function HealthTimeline({ graph, readiness = 55 }) {
  const model = useMemo(() => {
    const nodes = (graph?.nodes || []).map((n, i) => ({
      name: n.scenario_name, w: W[n.impact_level] ?? 1, kind: n.node_kind,
      t: (n.t_offset_s ?? 0) || i * 30, id: n.run_id,
    }))
    const prev = new Set((graph?.edges || []).filter(e => e.preventable).map(e => e.child_run_id))
    const Wt = nodes.reduce((a, n) => a + n.w, 0) || 1
    const Wp = nodes.filter(n => prev.has(n.id)).reduce((a, n) => a + n.w, 0)
    const scale = FLOOR_DROP / Wt
    const factor = savingFactor(Wt, Wp) * (readiness / 100)
    const maxT = Math.max(30, ...nodes.map(n => n.t))
    const events = nodes.filter(n => n.kind !== 'fault' || nodes.length === 1)
    const steps = 56
    const series = Array.from({ length: steps + 1 }, (_, k) => {
      const t = (k / steps) * maxT
      const fired = nodes.filter(n => n.t <= t)
      const sNo = fired.reduce((a, n) => a + n.w, 0)
      const sYes = fired.reduce((a, n) => a + n.w * (prev.has(n.id) ? (1 - factor) : 1), 0)
      return { t, hNo: Math.max(8, 100 - scale * sNo), hYes: Math.max(8, 100 - scale * sYes) }
    })
    return { nodes: events, maxT, series }
  }, [graph, readiness])

  const [p, setP] = useState(1)
  const [playing, setPlaying] = useState(false)
  useEffect(() => { setP(1); setPlaying(false) }, [graph])
  useEffect(() => {
    if (!playing) return
    let raf, start
    const step = (ts) => { if (!start) start = ts; const t = Math.min(1, (ts - start) / 4200); setP(t); if (t < 1) raf = requestAnimationFrame(step); else setPlaying(false) }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [playing])

  const WD = 560, H = 230, PX = 40, PY = 18
  const { series, maxT, nodes } = model
  const xf = t => PX + (t / maxT) * (WD - PX - 14)
  const yf = h => PY + (1 - h / 100) * (H - PY - 26)
  const cutT = p * maxT
  const shown = series.filter(s => s.t <= cutT + 1e-6)
  const line = (key) => shown.map((s, i) => `${i ? 'L' : 'M'}${xf(s.t).toFixed(1)} ${yf(s[key]).toFixed(1)}`).join(' ')
  const areaYes = shown.length ? `M${xf(0)} ${yf(100)} ${shown.map(s => `L${xf(s.t).toFixed(1)} ${yf(s.hYes).toFixed(1)}`).join(' ')} L${xf(shown[shown.length - 1].t)} ${H - 26} L${xf(0)} ${H - 26} Z` : ''
  const cur = shown[shown.length - 1] || series[0]
  const hColor = cur.hYes >= 70 ? 'var(--green)' : cur.hYes >= 45 ? 'var(--amber)' : 'var(--red)'

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 20, marginBottom: 10 }}>
        <div><div style={{ fontFamily: 'var(--display)', fontSize: 30, fontWeight: 800, lineHeight: 1, color: hColor }}>{Math.round(cur.hYes)}%</div><div className="ds-l">asset health · with response</div></div>
        <div><div style={{ fontFamily: 'var(--display)', fontSize: 22, fontWeight: 800, lineHeight: 1, color: 'var(--red)' }}>{Math.round(cur.hNo)}%</div><div className="ds-l">if left unmanaged</div></div>
        <div style={{ marginLeft: 'auto' }}>
          <button className="btn btn-primary" onClick={() => { setP(0); setPlaying(true) }} disabled={playing}>{playing ? '▶ Playing…' : '▶ Play cascade'}</button>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <svg width={WD} height={H} viewBox={`0 0 ${WD} ${H}`} style={{ maxWidth: '100%', display: 'block' }}>
          <defs><linearGradient id="htg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity=".22" /><stop offset="100%" stopColor="var(--accent)" stopOpacity="0" /></linearGradient></defs>
          {[0, 25, 50, 75, 100].map(h => (
            <g key={h}><line x1={PX} y1={yf(h)} x2={WD - 14} y2={yf(h)} stroke="var(--border)" strokeDasharray={h === 0 ? '' : '3 4'} />
              <text x={PX - 6} y={yf(h) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">{h}</text></g>
          ))}
          <path d={areaYes} fill="url(#htg)" />
          <path d={line('hNo')} fill="none" stroke="var(--red)" strokeWidth="2" strokeDasharray="5 4" opacity=".8" />
          <path d={line('hYes')} fill="none" stroke="var(--accent)" strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" />
          {nodes.filter(n => n.t <= cutT + 1e-6).map((n, i) => {
            const s = series.reduce((a, b) => Math.abs(b.t - n.t) < Math.abs(a.t - n.t) ? b : a, series[0])
            return <g key={i}><circle cx={xf(n.t)} cy={yf(s.hNo)} r="4" fill="var(--red)"><title>{n.name} — fires at t+{Math.round(n.t)}s</title></circle></g>
          })}
          <line x1={xf(cutT)} y1={PY} x2={xf(cutT)} y2={H - 26} stroke="var(--text)" strokeWidth="1" opacity=".35" />
          <circle cx={xf(cutT)} cy={yf(cur.hYes)} r="4.5" fill="var(--accent)" stroke="#fff" strokeWidth="1.5" />
          <text x={PX} y={H - 8} fontSize="9.5" fill="var(--muted)">t+0s</text>
          <text x={WD - 14} y={H - 8} fontSize="9.5" fill="var(--muted)" textAnchor="end">t+{Math.round(maxT)}s</text>
        </svg>
      </div>
      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--muted)', marginTop: 4, flexWrap: 'wrap' }}>
        <span><span style={{ display: 'inline-block', width: 14, height: 0, borderTop: '2.6px solid var(--accent)', verticalAlign: 3, marginRight: 5 }} />with response ({readiness}%)</span>
        <span><span style={{ display: 'inline-block', width: 14, height: 0, borderTop: '2px dashed var(--red)', verticalAlign: 3, marginRight: 5 }} />unmanaged</span>
        <span style={{ marginLeft: 'auto' }}>{nodes.length} downstream events over {Math.round(maxT)}s</span>
      </div>
    </div>
  )
}
