import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import EVWorld from '../components/EVWorld.jsx'
import { MODEL, FAULTS, faultsFor, resolveText } from '../ev/networkModel.js'
import { HEALTHY, buildScenario, inr } from '../ev/scenarios.js'

const PLAY_MS = 13000
const PRESETS = [
  { assetId: 'TX-1', faultId: 'overload', label: 'Transformer overload at peak' },
  { assetId: 'F-1', faultId: 'overcurrent_trip', label: 'DC feeder trips' },
  { assetId: 'BESS-A', faultId: 'thermal_runaway', label: 'BESS thermal runaway' },
  { assetId: 'GRID', faultId: 'supply_loss', label: 'Grid supply loss' },
]

const fallbackAnswer = (f) =>
  `If ${f.asset} suffers a ${f.fault.toLowerCase()} at ${f.site}, the grid load peaks around ${f.peak_grid_load_pct}% and ${f.chargers_down} charger(s) across ${f.stations_affected} station(s) drop — about ${f.sessions_dropped} sessions and ${f.kwh_curtailed} kWh lost. Exposure is ${inr(f.total_exposure_inr)} (${inr(f.revenue_lost_inr)} revenue + ${inr(f.sla_penalty_inr)} SLA), of which ~${f.preventable_pct}% is preventable with a prepared response. Recommended: ${f.recommended_action}`

export default function EVNetwork() {
  const [assetId, setAssetId] = useState('TX-1')
  const [faultId, setFaultId] = useState('overload')
  const [readiness, setReadiness] = useState(55)
  const [q, setQ] = useState('')
  const [note, setNote] = useState(null)

  const [scenario, setScenario] = useState(null)
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [answer, setAnswer] = useState(null)
  const [answering, setAnswering] = useState(false)
  const startRef = useRef(0)

  // keep fault valid for the chosen asset
  useEffect(() => { const fs = faultsFor(assetId); if (!fs.some(f => f.id === faultId)) setFaultId(fs[0]?.id) }, [assetId]) // eslint-disable-line

  useEffect(() => {
    if (!playing || !scenario) return
    let raf, start
    const stepFn = (ts) => {
      if (!start) start = ts
      const p = Math.min(1, (ts - start) / PLAY_MS)
      setIdx(Math.round(p * (scenario.steps.length - 1)))
      if (p < 1) raf = requestAnimationFrame(stepFn); else setPlaying(false)
    }
    raf = requestAnimationFrame(stepFn)
    return () => cancelAnimationFrame(raf)
  }, [playing, scenario])

  const groundedAnswer = async (scn, question) => {
    setAnswering(true); setAnswer(null)
    const ctx = `You are the operations copilot for ${scn.facts.site}, an EV charging hub. Answer ONLY from this simulated result — do not invent any numbers, cite the figures given:\n${JSON.stringify(scn.facts, null, 2)}`
    const question2 = question?.trim() || `What happens if ${scn.facts.asset} has a ${scn.facts.fault.toLowerCase()}, and what should the operator do?`
    try { const r = await api.ask(ctx, question2); setAnswer(r.answer || fallbackAnswer(scn.facts)) }
    catch { setAnswer(fallbackAnswer(scn.facts)) }
    finally { setAnswering(false) }
  }

  const run = (aId, fId, question) => {
    const scn = buildScenario(aId, fId, { readiness })
    setScenario(scn); setIdx(0); setPlaying(true); startRef.current++
    groundedAnswer(scn, question)
  }

  const onSimulate = () => { setNote(null); run(assetId, faultId, q) }
  const onAsk = () => {
    const r = resolveText(q)
    if (r) { setAssetId(r.assetId); setFaultId(r.faultId); setNote(null); run(r.assetId, r.faultId, q) }
    else { setNote('Couldn’t match a specific asset — simulating the closest modelled fault. Pick an asset above for an exact match.'); run(assetId, faultId, q) }
  }
  const onPreset = (p) => { setAssetId(p.assetId); setFaultId(p.faultId); setQ(''); setNote(null); run(p.assetId, p.faultId, null) }
  const onAskAsset = async (a) => {
    const aId = MODEL.assets.find(x => a?.id && (x.id === a.id || x.name.startsWith(a.id)))?.id || assetId
    setAssetId(aId); run(aId, faultsFor(aId)[0]?.id, null); return `Simulating ${aId}…`
  }

  const cur = scenario ? scenario.steps[idx] : null
  const live = cur ? cur.live : HEALTHY
  const m = cur ? cur.metrics : { revenueLost: 0, slaPenalty: 0, kwh: 0, sessions: 0, faulted: 0 }
  const log = scenario ? scenario.steps.slice(0, idx + 1).flatMap(s => s.events).slice(-6).reverse() : []
  const f = scenario?.facts

  return (
    <>
      <div className="mode-head">
        <h2>EV Charging Network — Live Twin & Copilot</h2>
        <p>Ask the copilot a fault question about a Gaadin asset — it simulates the cascade on the 3-D twin and answers with grounded numbers.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1.4fr 1fr' }}>
        <div className="col">
          <div className="card" style={{ padding: 10 }}>
            <EVWorld live={live} onAskAI={onAskAsset} height={430} />
          </div>
          <div className="stat-row">
            <div className="hero-stat"><div className="v" style={{ color: m.revenueLost ? 'var(--red)' : 'var(--text)' }}>{inr(m.revenueLost)}</div><div className="l">revenue lost</div></div>
            <div className="hero-stat"><div className="v" style={{ color: m.slaPenalty ? 'var(--red)' : 'var(--text)' }}>{inr(m.slaPenalty)}</div><div className="l">SLA penalty</div></div>
            <div className="hero-stat"><div className="v">{m.kwh}</div><div className="l">kWh curtailed</div></div>
            <div className="hero-stat"><div className="v">{m.sessions}</div><div className="l">sessions dropped</div></div>
          </div>
          {log.length > 0 && (
            <div className="card">
              <div className="card-title">Event feed</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {log.map((e, i) => (
                  <div key={i} style={{ display: 'flex', gap: 9, alignItems: 'center', fontSize: 12.5 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: e.kind === 'crit' ? 'var(--red)' : e.kind === 'warn' ? 'var(--amber)' : 'var(--green)' }} />
                    <span style={{ color: 'var(--muted)', width: 34 }}>+{e.t}m</span>
                    <span style={{ flex: 1 }}>{e.msg}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="col">
          <div className="card">
            <div className="card-title">◆ Ask the Gaadin copilot</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <label className="ne-field" style={{ flex: 1, margin: 0 }}>
                <span>Asset</span>
                <select className="select" style={{ width: '100%' }} value={assetId} onChange={e => setAssetId(e.target.value)}>
                  {MODEL.assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <label className="ne-field" style={{ flex: 1, margin: 0 }}>
                <span>Fault</span>
                <select className="select" style={{ width: '100%' }} value={faultId} onChange={e => setFaultId(e.target.value)}>
                  {faultsFor(assetId).map(fo => <option key={fo.id} value={fo.id}>{fo.label}</option>)}
                </select>
              </label>
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', marginBottom: 4 }}>Response readiness · {readiness}%</div>
            <input type="range" min="0" max="100" value={readiness} onChange={e => setReadiness(+e.target.value)} style={{ width: '100%' }} />
            <button className="btn btn-primary btn-block" style={{ marginTop: 10 }} onClick={onSimulate}>▶ Simulate this fault</button>

            <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
              <input className="ne-input" style={{ flex: 1 }} placeholder="…or ask in your own words: what if TX-1 trips at peak?"
                value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && q.trim() && onAsk()} />
              <button className="btn" onClick={onAsk} disabled={!q.trim()}>Ask</button>
            </div>
            {note && <div className="hint" style={{ marginTop: 8, color: 'var(--amber)' }}>{note}</div>}

            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
              {PRESETS.map(p => <button key={p.label} className="chip" onClick={() => onPreset(p)}>{p.label}</button>)}
            </div>
          </div>

          {(answering || answer) && (
            <div className="card">
              <div className="card-title">Copilot answer{f && <span className="tag">{f.asset}</span>}</div>
              {answering ? <div className="hint"><span className="spin spin-dark" /> simulating &amp; reasoning…</div>
                : <div style={{ fontSize: 13, lineHeight: 1.6 }}>{answer}</div>}
              {f && !answering && (
                <div className="ne-stats" style={{ marginTop: 12 }}>
                  <div><div className="v">{inr(f.total_exposure_inr)}</div><div className="l">total exposure</div></div>
                  <div><div className="v">{f.preventable_pct}%</div><div className="l">preventable</div></div>
                  <div><div className="v">{f.peak_grid_load_pct}%</div><div className="l">peak transformer load</div></div>
                  <div><div className="v">{f.sessions_dropped}</div><div className="l">sessions dropped</div></div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
