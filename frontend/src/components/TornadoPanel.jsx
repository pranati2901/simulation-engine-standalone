import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { exposureAt, money } from '../impact.js'
import { Tornado } from './charts.jsx'

// Real multi-lever sensitivity. Conditions are modelled the same honest way as What-if —
// as readiness penalties — so every bar comes from an actual engine run, not a guess.
const BASE = 70
const CONDS = [
  { id: 'peak', label: 'Peak load', pen: 14 },
  { id: 'weather', label: 'Adverse weather', pen: 10 },
  { id: 'staff', label: 'Reduced staff', pen: 12 },
]

export default function TornadoPanel({ item, full, prev }) {
  const [rows, setRows] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setRows(null) }, [item?.id, full])

  const analyse = async () => {
    if (!item) return
    setBusy(true)
    try {
      const effs = [...new Set([20, 95, BASE, ...CONDS.map(c => Math.max(0, BASE - c.pen))])]
      const contain = {}
      await Promise.all(effs.map(async e => {
        const g = await api.runGraph(item.id, item.domainKey, e)
        contain[e] = g.nodes?.[0]?.result?.kpis?.containment_rate ?? 0
      }))
      const exp = e => exposureAt(full, prev, contain[e] ?? 0)
      const out = [
        { label: 'Response readiness', swing: Math.abs(exp(20) - exp(95)) },
        ...CONDS.map(c => ({ label: c.label, swing: Math.abs(exp(BASE - c.pen) - exp(BASE)) })),
      ].sort((a, b) => b.swing - a.swing)
      setRows(out)
    } finally { setBusy(false) }
  }

  return (
    <div className="card">
      <div className="card-title">Sensitivity — what moves the outcome<span className="tag">tornado</span></div>
      {!rows && (
        <div className="empty" style={{ padding: '20px 8px' }}>
          <div className="hint" style={{ marginBottom: 12 }}>Vary each lever independently and rank how much it swings the exposure.</div>
          <button className="btn btn-primary" onClick={analyse} disabled={busy || !item}>{busy ? <><span className="spin" /> Running levers…</> : 'Analyse sensitivity'}</button>
        </div>
      )}
      {rows && (
        <>
          <Tornado rows={rows} fmt={money} />
          <div className="hint" style={{ marginTop: 8 }}>
            <b>{rows[0].label}</b> is the biggest lever — it swings exposure by <b>{money(rows[0].swing)}</b>, {(rows[0].swing / Math.max(1, rows[rows.length - 1].swing)).toFixed(1)}× more than <b>{rows[rows.length - 1].label.toLowerCase()}</b>. Put your effort where the bar is longest.
          </div>
          <button className="btn btn-ghost btn-block" style={{ marginTop: 10 }} onClick={analyse} disabled={busy}>↻ Re-run</button>
        </>
      )}
    </div>
  )
}
