import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, exposureByCategory, exposureAt, savingFactor, money, pct } from '../impact.js'
import { conditionsFor, effectiveReadiness } from '../domains.js'
import CascadeGraph from '../components/CascadeGraph.jsx'
import MonteCarloPanel from '../components/MonteCarloPanel.jsx'
import TornadoPanel from '../components/TornadoPanel.jsx'
import HealthTimeline from '../components/HealthTimeline.jsx'
import CriticalityPanel from '../components/CriticalityPanel.jsx'
import AssetPanel from '../components/AssetPanel.jsx'

// Simulation — one page for "what does this fault do to this asset".
//
// This merges what used to be two pages, Simulation and Twin. They were never really two
// things: Twin injected a fault and drew the asset's health decaying; Simulation ran the
// same engine call and drew the exposure. Same run, same cascade, two half-views. You
// simulate a twin's scenario — so it's one page with two lenses over ONE run:
//   • Exposure — what it costs, where it sits, what a better response avoids
//   • Asset    — how health decays, which asset is the real weak point
//
// The twin itself comes from the hub when embedded (activeDomain, integration plan §0.9);
// standalone it comes from whatever the Builder handed over.
export default function Simulation() {
  const { simSel, allScenarios, activeDomain, activeTwinName } = useStore()
  const nav = useNavigate()
  const [readiness, setReadiness] = useState(55)
  const [conds, setConds] = useState([])
  const [raw, setRaw] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [lens, setLens] = useState('exposure')   // exposure | asset
  const [sel, setSel] = useState(null)

  const items = simSel?.items || []
  const domain = items[0]?.domainKey
  const domainConds = conditionsFor(domain)
  const eff = effectiveReadiness(domain, readiness, conds)

  // Conditions chosen in the Builder carry over — the operator set up the picture there
  // and shouldn't have to rebuild it here.
  useEffect(() => { setConds(simSel?.conditions || []) }, [simSel])

  const run = async () => {
    if (!items.length) return
    setBusy(true); setErr(null)
    try {
      const gs = await Promise.all(items.map(it => api.runGraph(it.id, it.domainKey, eff)))
      setRaw({ domain, nodes: gs.flatMap(g => g.nodes), edges: gs.flatMap(g => g.edges), modeView: gs[0]?.mode_view })
    } catch (e) { setErr(e.message); setRaw(null) } finally { setBusy(false) }
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
  const containment = eff / 100
  const residual = exposureAt(full, prev, containment)
  const avoided = full - residual
  const cats = graph ? exposureByCategory(graph) : []
  const mv = raw?.modeView
  const scenario = allScenarios.find(s => s.id === items[0]?.id) || null

  if (!items.length) return (
    <>
      <div className="mode-head"><h2>Simulation</h2><p>Run a scenario against the twin and read what it costs.</p></div>
      <div className="card"><div className="empty">
        <div style={{ marginBottom: 14 }}>Nothing loaded yet — build a scenario, then hit <b>Run Simulation</b>.</div>
        <button className="btn btn-primary" onClick={() => nav('/builder')}>Go to Builder →</button>
      </div></div>
    </>
  )

  return (
    <>
      <div className="mode-head">
        <h2>Simulation</h2>
        <p>{simSel.label || 'Scenario run'} — one run, read as exposure or as asset health.</p>
      </div>

      {/* Which twin are we simulating? In the hub this is the twin the operator has open. */}
      {(activeTwinName || activeDomain) && (
        <div className="twin-ctx">
          <div className="twin-ctx-ic">◆</div>
          <div style={{ flex: 1 }}>
            <div className="twin-ctx-name">{activeTwinName || scenario?.domainName}</div>
            <div className="twin-ctx-sub">Simulating this twin’s scenarios · engine domain <span className="mono">{domain}</span></div>
          </div>
        </div>
      )}

      <div className="card sim-controls">
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
            <b>Response readiness</b>
            <b style={{ color: 'var(--accent)' }}>
              {readiness}%{conds.length > 0 && <span style={{ color: 'var(--muted)', fontWeight: 600 }}> → {eff}% effective</span>}
            </b>
          </div>
          <input type="range" min="0" max="100" value={readiness} onChange={e => setReadiness(+e.target.value)} />
          <div className="hint" style={{ marginTop: 4 }}>How prepared the response is — higher readiness contains more of the avoidable exposure.</div>
          {domainConds.length > 0 && (
            <div className="cond-row" style={{ marginTop: 10 }}>
              {domainConds.map(c => (
                <button key={c.id} className={`chip ${conds.includes(c.id) ? 'on' : ''}`}
                  onClick={() => setConds(x => x.includes(c.id) ? x.filter(y => y !== c.id) : [...x, c.id])}>
                  {conds.includes(c.id) ? '✓ ' : ''}{c.label} −{c.penalty}
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="btn btn-primary" onClick={run} disabled={busy}>{busy ? <><span className="spin" /> Running…</> : '▶ Run simulation'}</button>
      </div>

      {err && <div className="err" style={{ marginTop: 12 }}>{err}</div>}

      <div className="stat-row" style={{ margin: '16px 0' }}>
        <div className="hero-stat"><div className="v">{money(residual)}</div><div className="l">residual exposure</div></div>
        <div className="hero-stat"><div className="v" style={{ color: 'var(--green)' }}>{money(avoided)}</div><div className="l">avoided by response</div></div>
        <div className="hero-stat"><div className="v">{pct(containment * savingFactor(full, prev))}</div><div className="l">exposure contained</div></div>
      </div>

      <div className="seg" style={{ marginBottom: 14 }}>
        <button className={lens === 'exposure' ? 'on' : ''} onClick={() => setLens('exposure')}>Exposure</button>
        <button className={lens === 'asset' ? 'on' : ''} onClick={() => setLens('asset')}>Asset health</button>
      </div>

      {busy && <div className="card"><div className="empty"><span className="spin spin-dark" /> Running engine…</div></div>}

      {!busy && graph && lens === 'exposure' && (
        <>
          <MonteCarloPanel scenarioId={items[0].id} domain={domain} full={full} prev={prev} />
          {/* wide-left template: the cascade is the thing you look at, the panels annotate it */}
          <div className="grid builder-grid" style={{ marginTop: 16 }}>
            <div className="col">
              <div className="card">
                <div className="card-title">Cascade at {eff}% readiness</div>
                <CascadeGraph graph={graph} mode="decision" selectedId={sel} onSelect={setSel} />
              </div>
            </div>
            <div className="col">
              <TornadoPanel item={items[0]} full={full} prev={prev} />

              <div className="card">
                <div className="card-title">Where the exposure sits</div>
                {cats.map(c => (
                  <div key={c.category} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}><b style={{ textTransform: 'capitalize' }}>{c.category}</b><b>{money(c.value)}</b></div>
                    <div className="bar-track" style={{ marginTop: 4 }}><div className="bar-fill" style={{ width: `${c.pct}%`, background: 'var(--gradient)' }} /></div>
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
      )}

      {!busy && graph && lens === 'asset' && (
        <div className="grid builder-grid">
          <div className="col">
            <div className="card">
              <div className="card-title">Asset health under cascade<span className="tag">fault injected</span></div>
              <HealthTimeline graph={graph} readiness={eff} />
              <div className="hint" style={{ marginTop: 10 }}>
                The asset’s health as the cascade propagates. Same run as the Exposure lens —
                this is what it does to the machine rather than to the P&amp;L.
              </div>
            </div>
            <div className="card">
              <div className="card-title">Failure propagation</div>
              <CascadeGraph graph={graph} mode="twin" selectedId={sel} onSelect={setSel} />
            </div>
          </div>
          <div className="col">
            {scenario && <AssetPanel scenario={scenario} />}
            <CriticalityPanel graph={graph} />
          </div>
        </div>
      )}
    </>
  )
}
