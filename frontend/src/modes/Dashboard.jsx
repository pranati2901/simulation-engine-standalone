import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, money } from '../impact.js'
import { Donut, Sparkline } from '../components/charts.jsx'
import Flywheel from '../components/Flywheel.jsx'
import TrackRecord from '../components/TrackRecord.jsx'

const RISK = { low: 0.2, medium: 0.45, high: 0.7, extreme: 0.9 }
const COLORS = { aerospace: '#2563eb', defence: '#6d28d9', hospital: '#0891b2', railway: '#059669', ev: '#0ea5e9' }
const TKEY = 'simcore_exposure_trend'
const loadTrend = () => { try { return JSON.parse(localStorage.getItem(TKEY) || '[]') } catch { return [] } }

export default function Dashboard() {
  const { domains, allScenarios, favorites, openScenario } = useStore()
  const navigate = useNavigate()
  const [rows, setRows] = useState(null)
  const [busy, setBusy] = useState(false)
  const [trend, setTrend] = useState(loadTrend)

  const scan = async () => {
    if (!allScenarios.length) return
    setBusy(true)
    try {
      const out = await Promise.all(allScenarios.map(async s => {
        const g = await api.runGraph(s.id, s.domainKey, 45)
        const imp = computeImpact(g)
        return { id: s.id, name: s.name, domainKey: s.domainKey, exposure: imp.moneyTotal, avoidable: imp.moneyPrev, risk: RISK[s.decision_gates?.[0]?.risk_level] ?? 0.55 }
      }))
      out.sort((a, b) => b.exposure - a.exposure)
      setRows(out)
      const total = out.reduce((a, r) => a + r.exposure, 0)
      const last = trend[trend.length - 1]
      if (!last || Math.abs(last.total - total) > 1) {
        const next = [...trend, { total }].slice(-20)
        setTrend(next); localStorage.setItem(TKEY, JSON.stringify(next))
      }
    } finally { setBusy(false) }
  }
  useEffect(() => { if (allScenarios.length && !rows) scan() }, [allScenarios]) // eslint-disable-line

  const total = rows ? rows.reduce((a, r) => a + r.exposure, 0) : 0
  const avoidable = rows ? rows.reduce((a, r) => a + r.avoidable, 0) : 0
  const maxExp = rows ? Math.max(1, ...rows.map(r => r.exposure)) : 1
  const byDomain = rows ? domains.map(d => ({
    label: d.name.split(' ')[0], color: COLORS[d.key] || '#94a3b8',
    value: rows.filter(r => r.domainKey === d.key).reduce((a, r) => a + r.exposure, 0),
  })).filter(d => d.value > 0).sort((a, b) => b.value - a.value) : []
  const attention = rows ? rows.filter(r => r.risk >= 0.7 || r.exposure >= 0.66 * maxExp).slice(0, 6) : []
  const recent = (allScenarios.filter(s => favorites.has(s.id)).concat(allScenarios)).slice(0, 5)

  return (
    <>
      <div className="mode-head"><h2>Dashboard</h2><p>Your operation at a glance — portfolio exposure, what’s avoidable, and where to look first.</p></div>

      <Flywheel />

      {busy && !rows && <div className="card" style={{ marginTop: 16 }}><div className="empty"><span className="spin spin-dark" /> Scanning {allScenarios.length} scenarios across {domains.length} verticals…</div></div>}

      {rows && (
        <>
          <div className="stat-row" style={{ margin: '16px 0' }}>
            <div className="hero-stat"><div className="v">{money(total)}</div><div className="l">total exposure at risk</div></div>
            <div className="hero-stat"><div className="v" style={{ color: 'var(--green)' }}>{money(avoidable)}</div><div className="l">avoidable with response</div></div>
            <div className="hero-stat"><div className="v" style={{ color: 'var(--red)' }}>{attention.length}</div><div className="l">scenarios need review</div></div>
          </div>

          <div className="grid">
            <div className="col">
              <div className="card">
                <div className="card-title">Exposure by vertical</div>
                <Donut data={byDomain} center={money(total)} sub="total" />
              </div>
            </div>
            <div className="col">
              <div className="card prevent-card">
                <div className="pc-k">{money(avoidable)}</div>
                <div className="pc-l">is avoidable with a prepared response</div>
                <div className="bar-track" style={{ margin: '12px 0 6px', background: 'rgba(255,255,255,.25)' }}>
                  <div className="bar-fill" style={{ width: `${Math.round(100 * avoidable / (total || 1))}%`, background: '#fff' }} />
                </div>
                <div className="pc-sub">{Math.round(100 * avoidable / (total || 1))}% of {money(total)} total exposure is preventable — the rest is inherent to the faults.</div>
              </div>
              <div className="card">
                <div className="card-title">Exposure trend<span className="tag">{trend.length} scans</span></div>
                <Sparkline values={trend.map(t => t.total)} color="var(--accent)" id="dash-trend" />
                {trend.length >= 2 && (
                  <div className="hint" style={{ marginTop: 4 }}>
                    {trend[trend.length - 1].total <= trend[trend.length - 2].total ? '▼ down' : '▲ up'} {money(Math.abs(trend[trend.length - 1].total - trend[trend.length - 2].total))} vs last scan.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="grid" style={{ marginTop: 16 }}>
            <div className="col">
              <div className="card">
                <div className="card-title">Risk snapshot<span className="tag">likelihood × impact</span></div>
                <RiskMatrix rows={rows} maxExp={maxExp} onPick={r => openScenario(r.domainKey, r.id)} />
              </div>
            </div>
            <div className="col">
              <div className="card">
                <div className="card-title">Needs review<span className="tag">{attention.length}</span></div>
                {attention.length === 0 && <div className="hint">Nothing above threshold — portfolio looks contained.</div>}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {attention.map(r => (
                    <button key={r.id} className="scn" style={{ padding: '9px 11px' }} onClick={() => openScenario(r.domainKey, r.id)}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                        <span style={{ width: 9, height: 9, borderRadius: '50%', flexShrink: 0, background: r.risk >= 0.7 ? 'var(--red)' : 'var(--amber)' }} />
                        <b style={{ flex: 1, fontSize: 12.5 }}>{r.name}</b>
                        <span className="pill pill-muted">{domains.find(d => d.key === r.domainKey)?.name.split(' ')[0]}</span>
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

      <div style={{ marginTop: 16 }}><TrackRecord /></div>

      <div className="grid" style={{ marginTop: 16 }}>
        <div className="col">
          <div className="card">
            <div className="card-title">Quick actions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="btn btn-block" onClick={() => navigate('/library')}>＋ Browse scenario library</button>
              <button className="btn btn-block" onClick={() => navigate('/builder')}>◆ Build a scenario</button>
              <button className="btn btn-block" onClick={() => navigate('/decision')}>▶ Run a decision analysis</button>
              <button className="btn btn-block" onClick={() => navigate('/reports')}>📄 Generate a report</button>
              <button className="btn btn-block" onClick={scan} disabled={busy}>{busy ? <><span className="spin spin-dark" /> Rescanning…</> : '↻ Rescan portfolio'}</button>
            </div>
          </div>
        </div>
        <div className="col">
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
          <circle key={i} cx={xf(r)} cy={yf(r)} r={7 + 10 * (r.exposure / maxExp)} fill={COLORS[r.domainKey] || 'var(--accent)'} opacity=".7"
            style={{ cursor: 'pointer' }} onClick={() => onPick && onPick(r)}><title>{r.name} · {money(r.exposure)}</title></circle>
        ))}
      </svg>
    </div>
  )
}
