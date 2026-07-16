import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, money } from '../impact.js'

const RISK = { low: 0.2, medium: 0.45, high: 0.7, extreme: 0.9 }

// The Risk Command Center — scan every scenario in the domain, aggregate the exposure and
// plot each on a likelihood × impact matrix. This is the "one number to run on" landing.
export default function Overview() {
  const { domain, domains, scenarios } = useStore()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => { setData(null); setErr(null) }, [domain])

  const scan = async () => {
    if (!scenarios.length) return
    setBusy(true); setErr(null)
    try {
      const rows = await Promise.all(scenarios.map(async s => {
        const g = await api.runGraph(s.id, domain, 45)
        const imp = computeImpact(g)
        return {
          id: s.id, name: s.name,
          exposure: imp.moneyTotal, preventable: imp.moneyPrev,
          risk: RISK[s.decision_gates?.[0]?.risk_level] ?? 0.55,
        }
      }))
      setData(rows)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const total = data ? data.reduce((a, r) => a + r.exposure, 0) : 0
  const avoid = data ? data.reduce((a, r) => a + r.preventable, 0) : 0
  const maxExp = data ? Math.max(1, ...data.map(r => r.exposure)) : 1
  const top = data ? [...data].sort((a, b) => b.exposure - a.exposure) : []
  const dName = domains.find(d => d.key === domain)?.name || domain

  return (
    <>
      <div className="mode-head">
        <h2>Risk Command Center</h2>
        <p>Your whole operation at a glance — total exposure, where it hides, and what’s avoidable.</p>
      </div>

      {!data && !err && (
        <div className="card"><div className="empty">
          <div style={{ marginBottom: 14 }}>Scan every scenario in <b>{dName}</b> to build the risk picture.</div>
          <button className="btn btn-primary" onClick={scan} disabled={busy || !scenarios.length}>
            {busy ? <><span className="spin" /> Scanning {scenarios.length}…</> : `Scan ${scenarios.length} scenario(s)`}
          </button>
        </div></div>
      )}
      {err && <div className="err">{err}</div>}

      {data && (
        <>
          <div className="stat-row" style={{ marginBottom: 16 }}>
            <div className="hero-stat"><div className="v">{money(total)}</div><div className="l">total exposure</div></div>
            <div className="hero-stat"><div className="v" style={{ color: 'var(--red)' }}>{money(avoid)}</div><div className="l">avoidable if contained</div></div>
            <div className="hero-stat"><div className="v">{data.length}</div><div className="l">scenarios tracked</div></div>
          </div>
          <div className="grid">
            <div className="col">
              <div className="card">
                <div className="card-title">Risk matrix<span className="tag">likelihood × impact</span></div>
                <RiskMatrix rows={data} maxExp={maxExp} />
              </div>
            </div>
            <div className="col">
              <div className="card">
                <div className="card-title">Top exposures</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                  {top.map((r, i) => (
                    <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span className="mono" style={{ color: 'var(--muted)', width: 14 }}>{i + 1}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                          <b>{r.name}</b><b>{money(r.exposure)}</b>
                        </div>
                        <div className="bar-track" style={{ marginTop: 4, height: 6 }}>
                          <div className="bar-fill" style={{ width: `${100 * r.exposure / maxExp}%`, background: 'var(--accent)' }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="btn btn-block" style={{ marginTop: 14 }} onClick={scan} disabled={busy}>
                  {busy ? <><span className="spin spin-dark" /> Rescanning…</> : 'Rescan'}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  )
}

function RiskMatrix({ rows, maxExp }) {
  const W = 380, H = 260, P = 36
  const xf = r => P + r.risk * (W - 2 * P)
  const yf = r => H - P - (r.exposure / maxExp) * (H - 2 * P)
  return (
    <div style={{ overflowX: 'auto' }}>
      <svg width={W} height={H} style={{ maxWidth: '100%', display: 'block' }}>
        <rect x={P + (W - 2 * P) / 2} y={P} width={(W - 2 * P) / 2} height={(H - 2 * P) / 2} fill="#fdeaea" opacity=".55" />
        <text x={W - P} y={P + 14} fontSize="9.5" fill="#c98a8a" textAnchor="end">act first</text>
        <line x1={P} y1={H - P} x2={W - P} y2={H - P} stroke="#dbe2ec" />
        <line x1={P} y1={P} x2={P} y2={H - P} stroke="#dbe2ec" />
        <text x={W - P} y={H - P + 16} fontSize="10" fill="#6b7789" textAnchor="end">higher likelihood →</text>
        <text x={4} y={P - 6} fontSize="10" fill="#6b7789">↑ $ impact</text>
        {rows.map((r, i) => (
          <g key={i}>
            <circle cx={xf(r)} cy={yf(r)} r={7 + 11 * (r.exposure / maxExp)} fill="var(--accent)" opacity=".7" />
            <title>{r.name} · {money(r.exposure)}</title>
          </g>
        ))}
      </svg>
      <div className="hint" style={{ marginTop: 4 }}>Top-right = high-impact and hard to contain — deal with these first.</div>
    </div>
  )
}
