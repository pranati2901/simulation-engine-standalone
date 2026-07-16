import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, exposureAt, criticality, money } from '../impact.js'

// The flywheel: ONE scenario instance, three different intelligences out. Prem's whole
// pitch — "same data, three modes" — as a single interaction.
export default function Flywheel() {
  const { allScenarios } = useStore()
  const [sid, setSid] = useState('')
  const [out, setOut] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { if (!sid && allScenarios.length) setSid(allScenarios[0].id) }, [allScenarios, sid])
  const scenario = allScenarios.find(s => s.id === sid) || null

  const run = async () => {
    if (!scenario) return
    setBusy(true); setOut(null)
    try {
      const base = computeImpact(await api.runGraph(scenario.id, scenario.domainKey, 30))
      const g = await api.runGraph(scenario.id, scenario.domainKey, 60)
      const root = g.nodes?.[0]?.result || {}
      const contain = root.kpis?.containment_rate ?? 0
      const exposure = exposureAt(base.moneyTotal, base.moneyPrev, contain)
      const crit = criticality(g)[0]
      setOut({
        ops: { exposure, avoided: base.moneyTotal - exposure },
        training: { score: Math.round(root.scores?.operator ?? contain * 100), certified: !!root.summary?.clearance?.certified },
        twin: { asset: crit?.name || '—', downstream: crit?.downstream ?? 0, fail: Math.round((1 - contain) * 100) },
      })
    } finally { setBusy(false) }
  }

  return (
    <div className="card fly">
      <div className="fly-head">
        <div>
          <div className="fly-kicker">The flywheel · one scenario, three intelligences</div>
          <div className="fly-title">Same input → three coordinated answers</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select className="select" value={sid} onChange={e => { setSid(e.target.value); setOut(null) }}>
            {allScenarios.map(s => <option key={s.id} value={s.id}>{s.domainName?.split(' ')[0]} · {s.name}</option>)}
          </select>
          <button className="btn btn-primary" onClick={run} disabled={busy || !scenario}>{busy ? <><span className="spin" /> Running…</> : 'Run flywheel'}</button>
        </div>
      </div>
      {out && (
        <div className="fly-grid">
          <div className="fly-card" style={{ '--fc': '#3b82f6' }}>
            <div className="fly-mode">🟦 Decision — Ops / CFO</div>
            <div className="fly-v">{money(out.ops.exposure)}</div><div className="fly-l">exposure at risk</div>
            <div className="fly-sub"><b style={{ color: 'var(--red)' }}>{money(out.ops.avoided)}</b> avoidable</div>
          </div>
          <div className="fly-card" style={{ '--fc': '#22c55e' }}>
            <div className="fly-mode">🟩 Training — L&amp;D</div>
            <div className="fly-v">{out.training.score}<span style={{ fontSize: 15, color: 'var(--muted)' }}>/100</span></div><div className="fly-l">competency score</div>
            <div className="fly-sub"><span className={`pill ${out.training.certified ? 'pill-green' : 'pill-red'}`}>{out.training.certified ? 'CERTIFIED' : 'NOT CERTIFIED'}</span></div>
          </div>
          <div className="fly-card" style={{ '--fc': '#f59e0b' }}>
            <div className="fly-mode">🟧 Twin — Maintenance</div>
            <div className="fly-v" style={{ fontSize: 16, lineHeight: 1.3 }}>{out.twin.asset}</div><div className="fly-l">critical asset</div>
            <div className="fly-sub">{out.twin.fail}% failure risk · {out.twin.downstream} downstream</div>
          </div>
        </div>
      )}
      {!out && !busy && <div className="fly-hint">Pick a scenario and run it — watch one input produce a financial number, a training score, and a maintenance priority at once.</div>}
    </div>
  )
}
