import React from 'react'
import { useNavigate } from 'react-router-dom'
import { SITES, siteExposure, siteRisk, siteToNetwork } from '../ev/sites.js'
import { loadNetwork } from '../ev/networkModel.js'
import { inr } from '../ev/scenarios.js'

const COLOR = { high: '#ef4444', med: '#f59e0b', low: '#22c55e' }
const LABEL = { high: 'HIGH', med: 'MEDIUM', low: 'LOW' }

export default function Portfolio() {
  const nav = useNavigate()
  const rows = SITES.map(s => ({ ...s, exposure: siteExposure(s), risk: siteRisk(s) })).sort((a, b) => b.exposure - a.exposure)
  const total = rows.reduce((a, r) => a + r.exposure, 0)
  const atRisk = rows.filter(r => r.risk === 'high').length
  const maxE = Math.max(1, ...rows.map(r => r.exposure))
  const drill = (s) => { loadNetwork(siteToNetwork(s)); nav('/simulate') }

  return (
    <>
      <div className="mode-head">
        <h2>Network Operations</h2>
        <p>Every Gaadin charging site across the city — total exposure at a glance, and which site to open first.</p>
      </div>

      <div className="stat-row" style={{ marginBottom: 16 }}>
        <div className="hero-stat"><div className="v">{inr(total)}</div><div className="l">network exposure at risk</div></div>
        <div className="hero-stat"><div className="v">{rows.length}</div><div className="l">sites</div></div>
        <div className="hero-stat"><div className="v">{rows.reduce((a, r) => a + r.chargers, 0)}</div><div className="l">chargers</div></div>
        <div className="hero-stat"><div className="v" style={{ color: 'var(--red)' }}>{atRisk}</div><div className="l">sites at high risk</div></div>
      </div>

      <div className="grid">
        <div className="col">
          <div className="card">
            <div className="card-title">City network map<span className="tag">size = chargers · colour = risk</span></div>
            <svg viewBox="0 0 100 100" style={{ width: '100%', height: 'auto', display: 'block', background: 'radial-gradient(circle at 50% 40%, var(--surface), var(--surface-2))', borderRadius: 14, border: '1px solid var(--border)' }}>
              {[20, 40, 60, 80].map(v => <g key={v} stroke="var(--border)" strokeWidth="0.2" opacity="0.5"><line x1={v} y1="4" x2={v} y2="96" /><line x1="4" y1={v} x2="96" y2={v} /></g>)}
              {rows.map(s => (
                <g key={s.id} style={{ cursor: 'pointer' }} onClick={() => drill(s)}>
                  {s.risk === 'high' && <circle cx={s.x} cy={s.y} r={4 + s.chargers * 0.18} fill="none" stroke={COLOR.high} strokeWidth="0.4" opacity="0.6" />}
                  <circle cx={s.x} cy={s.y} r={2.6 + s.chargers * 0.14} fill={COLOR[s.risk]} fillOpacity="0.28" stroke={COLOR[s.risk]} strokeWidth="0.7" />
                  <text x={s.x} y={s.y + 0.9} fontSize="2.4" textAnchor="middle" fill={COLOR[s.risk]} style={{ fontWeight: 800 }}>{s.chargers}</text>
                  <text x={s.x} y={s.y + (2.6 + s.chargers * 0.14) + 2.6} fontSize="2.3" textAnchor="middle" fill="var(--muted)">{s.name}</text>
                </g>
              ))}
            </svg>
          </div>
        </div>
        <div className="col">
          <div className="card">
            <div className="card-title">Sites by exposure</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rows.map((s, i) => (
                <button key={s.id} className="scn" style={{ padding: '10px 12px' }} onClick={() => drill(s)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className="mono" style={{ color: 'var(--muted)', width: 12 }}>{i + 1}</span>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: COLOR[s.risk], flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}><b>{s.name}</b><b>{inr(s.exposure)}</b></div>
                      <div className="bar-track" style={{ marginTop: 3, height: 5 }}><div className="bar-fill" style={{ width: `${100 * s.exposure / maxE}%`, background: COLOR[s.risk] }} /></div>
                      <div style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 3 }}>{s.area} · {s.chargers} chargers · {Math.round(s.peak_util * 100)}% peak util · {LABEL[s.risk]} risk</div>
                    </div>
                    <span style={{ color: 'var(--accent)', fontSize: 12, fontWeight: 700 }}>Open →</span>
                  </div>
                </button>
              ))}
            </div>
            <div className="hint" style={{ marginTop: 10 }}>Click a site to load it and simulate faults on it in Mission Control.</div>
          </div>
        </div>
      </div>
    </>
  )
}
