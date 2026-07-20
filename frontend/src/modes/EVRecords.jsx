import React, { useState } from 'react'
import { inr } from '../ev/scenarios.js'

export const RECORDS_KEY = 'simcore_ev_records'
const load = () => { try { return JSON.parse(localStorage.getItem(RECORDS_KEY) || '[]') } catch { return [] } }

// EV Records — the saved simulations worth keeping (domain-specific; nothing cross-domain here).
export default function EVRecords() {
  const [rows, setRows] = useState(load)
  const del = (id) => { const n = rows.filter(r => r.id !== id); setRows(n); localStorage.setItem(RECORDS_KEY, JSON.stringify(n)) }
  const clear = () => { setRows([]); localStorage.removeItem(RECORDS_KEY) }

  return (
    <>
      <div className="mode-head"><h2>Records</h2><p>Saved EV simulations — the ones worth keeping. Review, and export for the board.</p></div>

      {!rows.length ? (
        <div className="card"><div className="empty">No saved simulations yet. In <b>Simulate</b>, run a fault and hit <b>★ Save</b> to log it here.</div></div>
      ) : (
        <>
          <div className="stat-row" style={{ marginBottom: 16 }}>
            <div className="hero-stat"><div className="v">{rows.length}</div><div className="l">saved simulations</div></div>
            <div className="hero-stat"><div className="v">{inr(rows.reduce((a, r) => a + (r.exposure || 0), 0))}</div><div className="l">total exposure logged</div></div>
            <div className="hero-stat"><div className="v">{new Set(rows.map(r => r.site)).size}</div><div className="l">sites</div></div>
          </div>

          <div className="card">
            <div className="card-title">Saved simulations
              <button className="btn btn-ghost" style={{ marginLeft: 'auto' }} onClick={() => window.print()}>⎙ Export / print</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rows.map(r => (
                <div key={r.id} className="rec-row">
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}><b>{r.asset} — {r.fault}</b><b>{inr(r.exposure)}</b></div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{r.site} · {r.preventable}% preventable · best fix: {r.best} · {new Date(r.ts).toLocaleString()}</div>
                  </div>
                  <button className="favbtn" onClick={() => del(r.id)} title="Delete" style={{ color: 'var(--muted)' }}>✕</button>
                </div>
              ))}
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 12 }} onClick={clear}>Clear all</button>
          </div>
        </>
      )}
    </>
  )
}
