import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, exposureByCategory, exposureAt, savingFactor, money, pct } from '../impact.js'
import CascadeGraph from '../components/CascadeGraph.jsx'
import MonteCarloPanel from '../components/MonteCarloPanel.jsx'
import TornadoPanel from '../components/TornadoPanel.jsx'

// Simulation — takes the scenario(s) built on the Builder page, runs the engine at a chosen
// response readiness, and shows the resulting exposure, cascade, breakdown and sensitivity.
export default function Simulation() {
  const { simSel, setSimSel, allScenarios } = useStore()
  const nav = useNavigate()
  const [readiness, setReadiness] = useState(55)
  const [raw, setRaw] = useState(null)
  const [busy, setBusy] = useState(false)

  const items = simSel?.items || []

  const run = async () => {
    if (!items.length) return
    setBusy(true)
    try {
      const gs = await Promise.all(items.map(it => api.runGraph(it.id, it.domainKey, readiness)))
      setRaw({ domain: items[0].domainKey, nodes: gs.flatMap(g => g.nodes), edges: gs.flatMap(g => g.edges), modeView: gs[0]?.mode_view })
    } finally { setBusy(false) }
  }
  useEffect(() => { if (items.length) run() }, [simSel]) // eslint-disable-line

  // fold Builder tuning (keyed by node name) back onto the fresh run
  const graph = useMemo(() => {
    if (!raw) return null
    const o = simSel?.overrides || {}
    return { ...raw, nodes: raw.nodes.map(n => ({ ...n, ...(o[n.scenario_name] || {}) })) }
  }, [raw, simSel])

  const imp = graph ? computeImpact(graph) : null
  const full = imp?.moneyTotal || 0, prev = imp?.moneyPrev || 0
  const containment = readiness / 100
  const residual = exposureAt(full, prev, containment)
  const avoided = full - residual
  const cats = graph ? exposureByCategory(graph) : []
  const mv = raw?.modeView

  if (!items.length) return (
    <>
      <div className="mode-head"><h2>Simulation</h2><p>Run a built scenario and read the resulting exposure.</p></div>
      <div className="card"><div className="empty">
        <div style={{ marginBottom: 14 }}>Nothing loaded yet — build a scenario, then hit <b>Run Simulation</b>.</div>
        <button className="btn btn-primary" onClick={() => nav('/builder')}>Go to Builder →</button>
      </div></div>
    </>
  )

  return (
    <>
      <div className="mode-head"><h2>Simulation</h2><p>{simSel.label || 'Scenario run'} — engine output at your chosen response readiness.</p></div>

      <MonteCarloPanel scenarioId={items[0].id} domain={items[0].domainKey} full={full} prev={prev} />

      <div className="card sim-controls" style={{ marginTop: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
            <b>Response readiness</b><b style={{ color: 'var(--accent)' }}>{readiness}%</b>
          </div>
          <input type="range" min="0" max="100" value={readiness} onChange={e => setReadiness(+e.target.value)} style={{ width: '100%' }} />
          <div className="hint" style={{ marginTop: 4 }}>How prepared the response is — higher readiness contains more of the avoidable exposure.</div>
        </div>
        <button className="btn btn-primary" onClick={run} disabled={busy}>{busy ? <><span className="spin" /> Running…</> : '▶ Run simulation'}</button>
      </div>

      <div className="stat-row" style={{ margin: '16px 0' }}>
        <div className="hero-stat"><div className="v">{money(residual)}</div><div className="l">residual exposure</div></div>
        <div className="hero-stat"><div className="v" style={{ color: 'var(--green)' }}>{money(avoided)}</div><div className="l">avoided by response</div></div>
        <div className="hero-stat"><div className="v">{pct(containment * savingFactor(full, prev))}</div><div className="l">exposure contained</div></div>
      </div>

      <div className="grid">
        <div className="col">
          <div className="card">
            <div className="card-title">Cascade at {readiness}% readiness</div>
            {busy ? <div className="empty"><span className="spin spin-dark" /> Running engine…</div>
              : graph ? <CascadeGraph graph={graph} mode="decision" /> : null}
          </div>
        </div>
        <div className="col">
          <TornadoPanel item={items[0]} full={full} prev={prev} />

          <div className="card">
            <div className="card-title">Where the exposure sits</div>
            {cats.map(c => (
              <div key={c.category} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}><b style={{ textTransform: 'capitalize' }}>{c.category}</b><b>{money(c.value)}</b></div>
                <div className="bar-track" style={{ marginTop: 4 }}><div className="bar-fill" style={{ width: `${c.pct}%`, background: 'var(--gradient, var(--accent))' }} /></div>
              </div>
            ))}
          </div>

          {mv?.top_drivers?.length > 0 && (
            <div className="card">
              <div className="card-title">Engine lens<span className="tag">{mv.lens}</span></div>
              <div className="hint" style={{ marginBottom: 10 }}>{mv.headline} — {mv.preventable_links} preventable link{mv.preventable_links === 1 ? '' : 's'} in the cascade.</div>
              {mv.top_drivers.map((d, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, padding: '5px 0' }}>
                  <span className="mono" style={{ color: 'var(--muted)', width: 14 }}>{i + 1}</span>
                  <b style={{ flex: 1 }}>{d.name}</b>
                  <span className="pill pill-muted" style={{ textTransform: 'capitalize' }}>{d.impact_level}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
