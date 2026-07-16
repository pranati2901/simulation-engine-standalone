import React, { useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, money } from '../impact.js'

const COLORS = { aerospace: '#2563eb', defence: '#6d28d9', hospital: '#0891b2', railway: '#059669', ev: '#0ea5e9' }

// Portfolio War Room — total $ at risk across every vertical at once. What gets a COO to sign.
export default function WarRoom() {
  const { allScenarios, domains, openScenario } = useStore()
  const [rows, setRows] = useState(null)
  const [busy, setBusy] = useState(false)

  const scan = async () => {
    setBusy(true)
    try {
      const out = await Promise.all(allScenarios.map(async s => {
        const g = await api.runGraph(s.id, s.domainKey, 45)
        const imp = computeImpact(g)
        return { ...s, exposure: imp.moneyTotal, avoidable: imp.moneyPrev }
      }))
      setRows(out.sort((a, b) => b.exposure - a.exposure))
    } finally { setBusy(false) }
  }

  const total = rows ? rows.reduce((a, r) => a + r.exposure, 0) : 0
  const avoid = rows ? rows.reduce((a, r) => a + r.avoidable, 0) : 0
  const maxExp = rows ? Math.max(1, ...rows.map(r => r.exposure)) : 1
  const byDomain = rows ? domains.map(d => ({
    ...d, total: rows.filter(r => r.domainKey === d.key).reduce((a, r) => a + r.exposure, 0),
  })).filter(d => d.total > 0).sort((a, b) => b.total - a.total) : []

  return (
    <>
      <div className="mode-head"><h2>Portfolio War Room</h2><p>Every scenario, every vertical, one exposure picture — where the money is really at risk.</p></div>

      {!rows && (
        <div className="card"><div className="empty">
          <div style={{ marginBottom: 14 }}>Scan the full portfolio — {allScenarios.length} scenarios across {domains.length} verticals.</div>
          <button className="btn btn-primary" onClick={scan} disabled={busy || !allScenarios.length}>{busy ? <><span className="spin" /> Scanning {allScenarios.length}…</> : 'Scan portfolio'}</button>
        </div></div>
      )}

      {rows && (
        <>
          <div className="stat-row" style={{ marginBottom: 16 }}>
            <div className="hero-stat"><div className="v">{money(total)}</div><div className="l">total exposure at risk</div></div>
            <div className="hero-stat"><div className="v" style={{ color: 'var(--red)' }}>{money(avoid)}</div><div className="l">avoidable</div></div>
            <div className="hero-stat"><div className="v">{domains.length}</div><div className="l">verticals</div></div>
            <div className="hero-stat"><div className="v">{rows.length}</div><div className="l">scenarios</div></div>
          </div>
          <div className="grid">
            <div className="col">
              <div className="card">
                <div className="card-title">Exposure by vertical</div>
                {byDomain.map(d => (
                  <div key={d.key} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}><b>{d.name}</b><b>{money(d.total)}</b></div>
                    <div className="bar-track" style={{ marginTop: 4 }}><div className="bar-fill" style={{ width: `${100 * d.total / total}%`, background: COLORS[d.key] || 'var(--accent)' }} /></div>
                  </div>
                ))}
              </div>
            </div>
            <div className="col">
              <div className="card">
                <div className="card-title">Top exposures across the estate</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {rows.slice(0, 8).map((r, i) => (
                    <button key={r.id} className="scn" style={{ padding: '9px 11px' }} onClick={() => openScenario(r.domainKey, r.id)}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="mono" style={{ color: 'var(--muted)', width: 14 }}>{i + 1}</span>
                        <span style={{ width: 8, height: 8, borderRadius: 2, background: COLORS[r.domainKey] || 'var(--muted)' }} />
                        <b style={{ flex: 1, fontSize: 12.5 }}>{r.name}</b>
                        <b style={{ fontSize: 12.5 }}>{money(r.exposure)}</b>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  )
}
