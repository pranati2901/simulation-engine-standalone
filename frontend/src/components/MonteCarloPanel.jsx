import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { pct, money, exposureAt } from '../impact.js'
import { Histogram } from './charts.jsx'

function binExposure(samples, full, prev, n = 12) {
  const xs = samples.map(c => exposureAt(full, prev, c))
  const mn = Math.min(...xs), mx = Math.max(...xs), span = (mx - mn) || 1
  const bins = Array.from({ length: n }, (_, i) => ({ lo: mn + span * i / n, hi: mn + span * (i + 1) / n, count: 0 }))
  xs.forEach(x => { bins[Math.min(n - 1, Math.floor((x - mn) / span * n))].count++ })
  return bins
}

// Runs against the store's selected scenario by default; pass scenarioId/domain to run it
// against a specific scenario. Pass full/prev to also render the $-outcome distribution.
export default function MonteCarloPanel({ scenarioId, domain, full, prev }) {
  const store = useStore()
  const local = scenarioId != null
  const [lmc, setLmc] = useState(null)
  const [lrun, setLrun] = useState(false)
  useEffect(() => { setLmc(null) }, [scenarioId])
  const mc = local ? lmc : store.mc
  const mcRunning = local ? lrun : store.mcRunning
  const runMonteCarlo = local
    ? async () => { setLrun(true); try { setLmc(await api.monteCarlo(scenarioId, domain)) } finally { setLrun(false) } }
    : store.runMonteCarlo
  const score = mc?.score_stats?.operator
  return (
    <div className="card">
      <div className="card-title">Confidence<span className="tag">Monte Carlo</span></div>
      {!mc && (
        <>
          <div className="hint" style={{ marginBottom: 12 }}>
            Run the scenario many times across a range of operator readiness — a probability, not a single guess.
          </div>
          <button className="btn btn-block" onClick={runMonteCarlo} disabled={mcRunning}>
            {mcRunning ? <><span className="spin spin-dark" /> Running 120 iterations…</> : 'Run 120 iterations'}
          </button>
        </>
      )}
      {mc && (
        <>
          <div style={{ fontSize: 26, fontWeight: 800, fontFamily: 'var(--display)' }}>
            {pct(mc.certified_rate)}
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginLeft: 8 }}>chance of containment</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>average across {mc.iterations} runs · readiness {mc.readiness_range?.[0]}–{mc.readiness_range?.[1]}</div>
          {score && (() => {
            const spread = score.p95 - score.p05
            const lvl = spread < 25 ? 'HIGH' : spread < 60 ? 'MEDIUM' : 'LOW'
            const col = spread < 25 ? 'var(--green)' : spread < 60 ? 'var(--amber)' : 'var(--red)'
            return (
              <div style={{ marginTop: 14 }}>
                <div className="meter"><div className="meter-fill" style={{ width: `${Math.max(10, Math.round(100 - spread))}%` }} /></div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 5 }}>
                  <b style={{ color: col }}>{lvl} CONFIDENCE</b>
                  {lvl === 'LOW' && <span style={{ color: 'var(--muted)' }}>outcome uncertain — more runs recommended</span>}
                </div>
              </div>
            )
          })()}
          {score && (
            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                <span style={{ color: 'var(--muted)' }}>Operator score range</span>
                <b>{Math.round(score.p05)}–{Math.round(score.p95)}</b>
              </div>
              <div className="ci">
                <div className="rng" style={{ left: `${score.p05}%`, width: `${Math.max(2, score.p95 - score.p05)}%` }} />
                <div className="mean" style={{ left: `${score.mean}%` }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--muted)' }}>
                <span>worst 5%</span><span>mean {Math.round(score.mean)}</span><span>best 5%</span>
              </div>
            </div>
          )}
          {full != null && mc.samples?.containment_rate?.length > 1 && (() => {
            const bins = binExposure(mc.samples.containment_rate, full, prev || 0)
            const modeIdx = bins.indexOf(bins.reduce((a, b) => b.count > a.count ? b : a, bins[0]))
            return (
              <div style={{ marginTop: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
                  <b>Distribution of financial outcomes</b>
                  <span style={{ color: 'var(--muted)' }}>{mc.iterations} runs</span>
                </div>
                <Histogram bins={bins} markerIdx={modeIdx} labelFn={(b) => money(b.lo)} />
                <div className="hint" style={{ marginTop: 4 }}>Most-likely outcome around <b>{money(bins[modeIdx].lo)}</b>; the spread is your real financial risk band, not a single point estimate.</div>
              </div>
            )
          })()}
          <button className="btn btn-block" style={{ marginTop: 14 }} onClick={runMonteCarlo} disabled={mcRunning}>
            {mcRunning ? <><span className="spin spin-dark" /> Re-running…</> : 'Run again'}
          </button>
        </>
      )}
    </div>
  )
}
