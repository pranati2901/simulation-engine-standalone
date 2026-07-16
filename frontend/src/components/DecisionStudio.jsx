import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { compareInvestments, stars } from '../analysis.js'
import { exposureByCategory, money } from '../impact.js'

// Decision-first: auto-runs on open and leads with the recommendation, then the ranked
// explorer — the operator sees the answer before touching anything.
export default function DecisionStudio() {
  const { selected, domain } = useStore()
  const [cmp, setCmp] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [budget, setBudget] = useState(300_000)

  useEffect(() => {
    if (!selected) return
    let ok = true; setBusy(true); setCmp(null); setErr(null)
    compareInvestments(selected, domain).then(c => ok && setCmp(c)).catch(e => ok && setErr(e.message)).finally(() => ok && setBusy(false))
    return () => { ok = false }
  }, [selected?.id, domain])

  if (busy) return <div className="card"><div className="empty"><span className="spin spin-dark" /> Analysing strategies…</div></div>
  if (err) return <div className="card"><div className="err">{err}</div></div>
  if (!cmp) return null

  const affordable = cmp.ranked.filter(r => r.cost <= budget)
  const rec = affordable[0] || null
  const causes = exposureByCategory(cmp.worst.graph).slice(0, 2).map(c => c.category)

  return (
    <>
      <div className="card rec-hero">
        <div className="rec-kicker">◆ Recommended decision</div>
        {rec ? (
          <>
            <div className="rec-name">{rec.name}</div>
            <div className="rec-stats">
              <div><div className="rv">{money(rec.cost)}</div><div className="rl">investment</div></div>
              <div><div className="rv" style={{ color: '#4ade80' }}>{money(rec.saved)}</div><div className="rl">avoided</div></div>
              <div><div className="rv">{rec.roi.toFixed(1)}×</div><div className="rl">return</div></div>
              <div><div className="rv">{Math.round(rec.contain * 100)}%</div><div className="rl">confidence</div></div>
            </div>
            <div className="rec-why">Biggest exposure is <b style={{ textTransform: 'capitalize' }}>{causes.join(' & ')}</b> — this is the best return available under {money(budget)}.</div>
          </>
        ) : <div className="rec-name" style={{ fontSize: 15 }}>Nothing fits {money(budget)} — raise the budget to unlock a fix.</div>}
        <div style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5, opacity: .85 }}><span>Budget</span><b>{money(budget)}</b></div>
          <input className="slider slider-dark" type="range" min="0" max="300000" step="10000" value={budget} onChange={e => setBudget(+e.target.value)} />
        </div>
      </div>

      <div className="card">
        <div className="card-title">Decision Explorer<span className="tag">ranked by ROI</span></div>
        <div className="rank-list">
          {cmp.ranked.map((r, i) => (
            <div key={r.key} className={`rank-row ${rec && rec.key === r.key ? 'on' : ''}`}>
              <div className="rank-medal">{['🥇', '🥈', '🥉'][i] || '•'}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <b>{r.name}</b>
                  <span className="stars">{'★'.repeat(stars(r.roi))}<span style={{ color: 'var(--border)' }}>{'★'.repeat(5 - stars(r.roi))}</span></span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2 }}>{money(r.cost)} · avoids {money(r.saved)} · {Math.round(r.contain * 100)}% success</div>
              </div>
              <div className="rank-roi">{r.roi.toFixed(1)}×</div>
            </div>
          ))}
          {!cmp.ranked.length && <div className="hint">This fault is largely inherent — no paid option beats doing nothing.</div>}
        </div>
      </div>
    </>
  )
}
