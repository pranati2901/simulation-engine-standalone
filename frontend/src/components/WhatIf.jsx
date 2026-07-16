import React, { useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, exposureAt, money } from '../impact.js'
import { costOf as assumeCost } from '../assumptions.js'

// Levers the operator controls. Conditions are modelled the honest way the engine reasons
// about — as readiness penalties (worse conditions → lower effective readiness → the fault
// is less likely to be contained).
const CONDS = [
  { id: 'peak', label: 'Peak load', pen: 14 },
  { id: 'weather', label: 'Adverse weather', pen: 10 },
  { id: 'staff', label: 'Reduced staff', pen: 12 },
]
const costOf = (r) => (r >= 80 ? assumeCost('full') : r >= 55 ? assumeCost('std') : 0)
const effOf = (v) => Math.max(0, Math.min(100, v.r - CONDS.filter(c => v.conds.includes(c.id)).reduce((a, c) => a + c.pen, 0)))

async function evaluate(scenario, domain, eff, full, prevPot) {
  const g = await api.runGraph(scenario.id, domain, eff)
  const contain = g.nodes?.[0]?.result?.kpis?.containment_rate ?? 0
  return { graph: g, contain, exposure: exposureAt(full, prevPot, contain) }
}

export default function WhatIf({ onRun }) {
  const { selected, domain } = useStore()
  const [a, setA] = useState({ r: 55, conds: ['peak'] })
  const [b, setB] = useState({ r: 90, conds: [] })
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const runBoth = async () => {
    if (!selected) return
    setBusy(true); setErr(null)
    try {
      const base = computeImpact(await api.runGraph(selected.id, domain, 30))
      const full = base.moneyTotal, prevPot = base.moneyPrev
      const [A, B] = await Promise.all([
        evaluate(selected, domain, effOf(a), full, prevPot),
        evaluate(selected, domain, effOf(b), full, prevPot),
      ])
      setRes({ A, B, savings: A.exposure - B.exposure, cost: costOf(b.r) - costOf(a.r) })
      onRun && onRun(B.graph)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const toggle = (v, set, id) => set({ ...v, conds: v.conds.includes(id) ? v.conds.filter(x => x !== id) : [...v.conds, id] })

  const Knobs = ({ v, set, after }) => (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: .4, color: after ? 'var(--accent)' : 'var(--muted)', marginBottom: 8 }}>{after ? 'What if' : 'Current'}</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 2 }}>Readiness <b style={{ color: 'var(--text)' }}>{v.r}</b> <span style={{ opacity: .7 }}>· effective {effOf(v)}</span></div>
      <input className="slider" type="range" min="0" max="100" value={v.r} onChange={e => set({ ...v, r: +e.target.value })} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
        {CONDS.map(c => (
          <button key={c.id} className={`chip ${v.conds.includes(c.id) ? 'on' : ''}`} onClick={() => toggle(v, set, c.id)}>{c.label} −{c.pen}</button>
        ))}
      </div>
    </div>
  )

  return (
    <div className="card">
      <div className="card-title">What-if analysis<span className="tag">before → after</span></div>
      <div style={{ display: 'flex', gap: 18 }}>
        <Knobs v={a} set={setA} />
        <div style={{ width: 1, background: 'var(--border)' }} />
        <Knobs v={b} set={setB} after />
      </div>
      <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} onClick={runBoth} disabled={busy || !selected}>
        {busy ? <><span className="spin" /> Running both…</> : 'Run comparison'}
      </button>
      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
      {res && (
        <div className="wi-out">
          <div className="wi-col"><div className="wi-h">Before</div>
            <div className="wi-v">{Math.round(res.A.contain * 100)}%</div><div className="wi-l">success</div>
            <div className="wi-v2">{money(res.A.exposure)}</div><div className="wi-l">exposure</div>
          </div>
          <div className="wi-arrow">→</div>
          <div className="wi-col"><div className="wi-h" style={{ color: 'var(--accent)' }}>After</div>
            <div className="wi-v" style={{ color: 'var(--accent)' }}>{Math.round(res.B.contain * 100)}%</div><div className="wi-l">success</div>
            <div className="wi-v2">{money(res.B.exposure)}</div><div className="wi-l">exposure</div>
          </div>
          <div className="wi-col wi-delta"><div className="wi-h">Impact</div>
            <div className="wi-v" style={{ color: res.savings >= 0 ? 'var(--green)' : 'var(--red)' }}>{res.savings >= 0 ? '+' : '−'}{money(Math.abs(res.savings))}</div><div className="wi-l">saved</div>
            <div className="wi-v2" style={{ color: res.cost > 0 ? 'var(--red)' : 'var(--muted)' }}>{res.cost > 0 ? '+' + money(res.cost) : '—'}</div><div className="wi-l">extra cost</div>
          </div>
        </div>
      )}
    </div>
  )
}
