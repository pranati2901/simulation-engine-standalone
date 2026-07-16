import React from 'react'
import { computeImpact, money, num } from '../impact.js'

export default function ImpactPanel({ graph }) {
  const m = computeImpact(graph)
  return (
    <div className="card">
      <div className="card-title">Estimated impact<span className="tag">estimate</span></div>
      <div style={{ fontSize: 30, fontWeight: 800, fontFamily: 'var(--display)', lineHeight: 1.1 }}>
        {money(m.moneyTotal)}
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginLeft: 8 }}>total exposure</span>
      </div>
      {m.hasPreventable ? (
        <div style={{ marginTop: 10 }}>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${m.prevPct}%`, background: 'var(--red)' }} /></div>
          <div style={{ fontSize: 12.5, marginTop: 6 }}>
            <b style={{ color: 'var(--red)' }}>{money(m.moneyPrev)}</b> preventable
            <span style={{ color: 'var(--muted)' }}> — {m.prevPct}% avoidable if contained. Floor if contained: <b>{money(m.moneyFloor)}</b>.</span>
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 8 }}>All inherent — nothing here was avoidable by the operator.</div>
      )}
      <div className="stat-row" style={{ marginTop: 14 }}>
        {m.units.map((u, i) => (
          <div className="stat" key={i}>
            <div className="v" style={{ color: u.neg ? 'var(--red)' : undefined }}>{u.neg ? '−' : ''}{num(u.value)}{u.suffix || ''}</div>
            <div className="l">{u.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
