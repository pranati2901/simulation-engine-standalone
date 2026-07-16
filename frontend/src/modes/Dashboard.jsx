import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, money } from '../impact.js'
import Flywheel from '../components/Flywheel.jsx'
import TrackRecord from '../components/TrackRecord.jsx'

const RISK = { low: 0.2, medium: 0.45, high: 0.7, extreme: 0.9 }

export default function Dashboard() {
  const { domains, domain, scenarios, allScenarios, favorites, openScenario } = useStore()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { setData(null) }, [domain])

  const scan = async () => {
    if (!scenarios.length) return
    setBusy(true)
    try {
      const rows = await Promise.all(scenarios.map(async s => {
        const g = await api.runGraph(s.id, domain, 45)
        const imp = computeImpact(g)
        return { id: s.id, name: s.name, exposure: imp.moneyTotal, risk: RISK[s.decision_gates?.[0]?.risk_level] ?? 0.55, domainKey: domain }
      }))
      setData(rows)
    } finally { setBusy(false) }
  }

  const total = data ? data.reduce((a, r) => a + r.exposure, 0) : null
  const maxExp = data ? Math.max(1, ...data.map(r => r.exposure)) : 1
  const top = data ? [...data].sort((a, b) => b.exposure - a.exposure) : []
  const recent = (allScenarios.filter(s => favorites.has(s.id)).concat(allScenarios)).slice(0, 5)

  return (
    <>
      <div className="mode-head"><h2>Dashboard</h2><p>Your operation at a glance — scenarios, exposure and quick actions.</p></div>

      <Flywheel />
      <div style={{ marginTop: 16 }}><TrackRecord /></div>

      <div className="stat-row" style={{ marginBottom: 16, marginTop: 16 }}>
        <div className="hero-stat"><div className="v">{allScenarios.length}</div><div className="l">scenarios</div></div>
        <div className="hero-stat"><div className="v">{domains.length}</div><div className="l">domains</div></div>
        <div className="hero-stat"><div className="v" style={{ color: 'var(--amber)' }}>{favorites.size}</div><div className="l">favourites</div></div>
        <div className="hero-stat"><div className="v">{total != null ? money(total) : '—'}</div><div className="l">exposure ({domains.find(d => d.key === domain)?.name.split(' ')[0] || domain})</div></div>
      </div>

      <div className="grid">
        <div className="col">
          <div className="card">
            <div className="card-title">Risk snapshot<span className="tag">{domains.find(d => d.key === domain)?.name}</span></div>
            {!data && <div className="empty" style={{ padding: '26px 8px' }}>
              <button className="btn btn-primary" onClick={scan} disabled={busy || !scenarios.length}>{busy ? <><span className="spin" /> Scanning…</> : 'Scan portfolio'}</button>
            </div>}
            {data && (
              <>
                <RiskMatrix rows={data} maxExp={maxExp} onPick={r => openScenario(r.domainKey, r.id)} />
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {top.slice(0, 4).map((r, i) => (
                    <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span className="mono" style={{ color: 'var(--muted)', width: 12 }}>{i + 1}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}><b>{r.name}</b><b>{money(r.exposure)}</b></div>
                        <div className="bar-track" style={{ marginTop: 3, height: 5 }}><div className="bar-fill" style={{ width: `${100 * r.exposure / maxExp}%`, background: 'var(--accent)' }} /></div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="col">
          <div className="card">
            <div className="card-title">Quick actions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="btn btn-block" onClick={() => navigate('/library')}>＋ Browse scenario library</button>
              <button className="btn btn-block" onClick={() => navigate('/training')}>✎ New scenario (AI)</button>
              <button className="btn btn-block" onClick={() => navigate('/decision')}>▶ Run a decision analysis</button>
              <button className="btn btn-block" onClick={() => navigate('/reports')}>📄 Generate a report</button>
            </div>
          </div>
          <div className="card">
            <div className="card-title">Recent & favourites</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {recent.map(s => (
                <button key={s.id} className="scn" style={{ padding: '8px 10px' }} onClick={() => openScenario(s.domainKey, s.id)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <b style={{ fontSize: 12.5 }}>{s.name}</b>
                    <span className="pill pill-muted">{s.domainName?.split(' ')[0]}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function RiskMatrix({ rows, maxExp, onPick }) {
  const W = 380, H = 230, P = 34
  const xf = r => P + r.risk * (W - 2 * P)
  const yf = r => H - P - (r.exposure / maxExp) * (H - 2 * P)
  return (
    <div style={{ overflowX: 'auto' }}>
      <svg width={W} height={H} style={{ maxWidth: '100%', display: 'block' }}>
        <rect x={P + (W - 2 * P) / 2} y={P} width={(W - 2 * P) / 2} height={(H - 2 * P) / 2} fill="#fdeaea" opacity=".5" />
        <line x1={P} y1={H - P} x2={W - P} y2={H - P} stroke="#dbe2ec" />
        <line x1={P} y1={P} x2={P} y2={H - P} stroke="#dbe2ec" />
        <text x={W - P} y={H - P + 15} fontSize="10" fill="#6b7789" textAnchor="end">higher likelihood →</text>
        <text x={4} y={P - 6} fontSize="10" fill="#6b7789">↑ $ impact</text>
        {rows.map((r, i) => (
          <circle key={i} cx={xf(r)} cy={yf(r)} r={7 + 10 * (r.exposure / maxExp)} fill="var(--accent)" opacity=".7"
            style={{ cursor: 'pointer' }} onClick={() => onPick && onPick(r)}><title>{r.name} · {money(r.exposure)}</title></circle>
        ))}
      </svg>
    </div>
  )
}
