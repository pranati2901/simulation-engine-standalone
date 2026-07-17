import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, money } from '../impact.js'
import { metricTemplate, seedMetrics, metricsMoney, tierFromMoney } from '../nodeMetrics.js'
import { conditionsFor, effectiveReadiness } from '../domains.js'
import CascadeGraph from '../components/CascadeGraph.jsx'
import ScenarioChat from '../components/ScenarioChat.jsx'

const VKEY = 'simcore_versions'
const loadV = () => { try { return JSON.parse(localStorage.getItem(VKEY) || '[]') } catch { return [] } }

const TIERS = ['low', 'medium', 'high', 'critical']

// Scenario Builder — inspect the full failure web, tune it three ways (talk to it, retune
// a node's real quantities, or stack operating conditions on it), then hand off to the
// Simulation page.
export default function Builder() {
  const { allScenarios, setSimSel, builderPick, setBuilderPick, activeDomain, reloadAll } = useStore()
  const nav = useNavigate()
  const [aId, setA] = useState('')
  const [bId, setB] = useState('')
  const [combine, setCombine] = useState(false)
  const [raw, setRaw] = useState(null)          // { nodes, edges, domain } straight from the engine
  const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState(null)          // selected run_id
  const [ov, setOv] = useState({})              // run_id -> { metrics, impact_level }
  const [versions, setVersions] = useState(loadV)
  const [tab, setTab] = useState('node')        // node | chat
  const [conds, setConds] = useState([])        // operating conditions carried into the sim
  const [webReadiness, setWebReadiness] = useState(20)

  // Inside the hub the domain comes from the active twin (integration plan §0.9); the
  // picker stays as an override so every vertical is still reachable without a twin.
  const [domainFilter, setDomainFilter] = useState('all')
  useEffect(() => { if (activeDomain) setDomainFilter(activeDomain) }, [activeDomain])

  const pool = useMemo(
    () => (domainFilter === 'all' ? allScenarios : allScenarios.filter(s => s.domainKey === domainFilter)),
    [allScenarios, domainFilter])

  // Library → Builder hand-off wins over the default first-scenario selection
  useEffect(() => {
    if (builderPick) { setA(builderPick.id); setCombine(false); setBuilderPick(null) }
  }, [builderPick, setBuilderPick])
  useEffect(() => {
    if (pool.length && !builderPick && !pool.some(s => s.id === aId)) {
      setA(pool[0].id); setB(pool[1]?.id || pool[0].id)
    }
  }, [pool, aId, builderPick])

  const a = allScenarios.find(s => s.id === aId)
  const b = allScenarios.find(s => s.id === bId) || pool.find(s => s.id !== aId)
  const domainConds = conditionsFor(a?.domainKey)
  const effReadiness = effectiveReadiness(a?.domainKey, webReadiness, conds)

  // build the web — run at low readiness so every branch fires (fullest cascade)
  useEffect(() => {
    if (!a) return
    let ok = true; setBusy(true); setSel(null); setOv({})
    const jobs = [api.runGraph(a.id, a.domainKey, effReadiness)]
    if (combine && b) jobs.push(api.runGraph(b.id, b.domainKey, effReadiness))
    Promise.all(jobs).then(gs => {
      if (!ok) return
      setRaw({ domain: a.domainKey, nodes: gs.flatMap(g => g.nodes), edges: gs.flatMap(g => g.edges) })
    }).finally(() => ok && setBusy(false))
    return () => { ok = false }
  }, [aId, bId, combine, effReadiness]) // eslint-disable-line

  // apply per-node overrides on top of the raw graph
  const graph = useMemo(() => {
    if (!raw) return null
    return { ...raw, nodes: raw.nodes.map(n => ({ ...n, ...ov[n.run_id] })) }
  }, [raw, ov])

  const imp = graph ? computeImpact(graph) : null
  const node = graph?.nodes.find(n => n.run_id === sel)
  const downstream = useMemo(() => {
    if (!node || !graph) return 0
    const kids = {}; graph.edges.forEach(e => { (kids[e.parent_run_id] = kids[e.parent_run_id] || []).push(e.child_run_id) })
    const seen = new Set(); const walk = id => (kids[id] || []).forEach(c => { if (!seen.has(c)) { seen.add(c); walk(c) } })
    walk(node.run_id); return seen.size
  }, [node, graph])

  const rawNode = raw?.nodes.find(n => n.run_id === sel)
  const tpl = graph ? metricTemplate(graph.domain) : []
  const metrics = (sel && ov[sel]?.metrics) || (rawNode ? seedMetrics(graph.domain, rawNode.impact_level) : {})
  const nodeMoney = graph ? metricsMoney(graph.domain, metrics) : 0
  const setMetric = (key, val) => {
    const next = { ...metrics, [key]: val }
    setOv(o => ({ ...o, [sel]: { metrics: next, impact_level: tierFromMoney(graph.domain, metricsMoney(graph.domain, next)) } }))
  }
  // Set severity directly. The metrics reseed from the tier so the tangible numbers and the
  // tier never contradict — an override that left them out of sync would show "critical"
  // next to a $ contribution that says "low".
  const setTier = (tier) => {
    setOv(o => ({ ...o, [sel]: { metrics: seedMetrics(graph.domain, tier), impact_level: tier } }))
  }
  const edited = Object.keys(ov).length

  const toggleCond = (id) => setConds(c => c.includes(id) ? c.filter(x => x !== id) : [...c, id])

  const runSim = () => {
    // run_ids are per-run, so carry tuning keyed by the stable node name
    const byName = {}
    raw?.nodes.forEach(n => { if (ov[n.run_id]) byName[n.scenario_name] = ov[n.run_id] })
    setSimSel({
      items: combine && b ? [{ domainKey: a.domainKey, id: a.id }, { domainKey: b.domainKey, id: b.id }]
        : [{ domainKey: a.domainKey, id: a.id }],
      overrides: byName, label: combine && b ? `${a.name} + ${b.name}` : a.name,
      conditions: conds,
    })
    nav('/simulation')
  }

  const saveVersion = () => {
    const v = {
      id: `${aId}${combine ? '+' + bId : ''}-${versions.length + 1}`,
      name: combine && b ? `${a.name} + ${b.name}` : a?.name, n: versions.length + 1,
      a: aId, b: bId, combine, ov, conds, exposure: imp?.moneyTotal || 0, ts: Date.now(),
    }
    const next = [v, ...versions].slice(0, 20)
    setVersions(next); localStorage.setItem(VKEY, JSON.stringify(next))
  }
  const restore = (v) => { setA(v.a); setB(v.b); setCombine(v.combine); setOv(v.ov || {}); setConds(v.conds || []) }
  const myVersions = versions.filter(v => v.a === aId)

  // A committed AI revision is a NEW scenario — pull the library so it appears in the
  // picker, then select it. Without the reload it exists on the engine but not in this
  // list, and selecting it would find nothing.
  const onApplied = async (saved) => {
    await reloadAll()
    setA(saved.id); setCombine(false); setTab('node')
  }

  const label = (s) => `${s.domainName?.split(' ')[0]} · ${s.name}`

  return (
    <>
      <div className="mode-head"><h2>Scenario Builder</h2><p>Inspect the full failure web, tune it, then run the simulation.</p></div>

      <div className="card builder-bar">
        {!activeDomain && (
          <select className="select" value={domainFilter} onChange={e => setDomainFilter(e.target.value)}>
            <option value="all">All verticals</option>
            {[...new Set(allScenarios.map(s => s.domainKey))].map(d => (
              <option key={d} value={d}>{allScenarios.find(s => s.domainKey === d)?.domainName || d}</option>
            ))}
          </select>
        )}
        <select className="select" style={{ flex: 1, minWidth: 190 }} value={aId} onChange={e => setA(e.target.value)}>
          {pool.map(s => <option key={s.id} value={s.id}>{label(s)}</option>)}
        </select>
        <button className={`chip ${combine ? 'on' : ''}`} onClick={() => setCombine(c => !c)} title="Overlay a second scenario onto the same operating picture">
          {combine ? '✓ ' : '＋ '}Combine scenarios
        </button>
        {combine && (
          <select className="select" style={{ flex: 1, minWidth: 190 }} value={b?.id || ''} onChange={e => setB(e.target.value)}>
            {pool.map(s => <option key={s.id} value={s.id}>{label(s)}</option>)}
          </select>
        )}
        <div className="spacer" />
        <button className="btn" onClick={saveVersion} disabled={!graph} title="Snapshot the current tuning as a version">⧉ Save version</button>
        <button className="btn btn-primary" onClick={runSim} disabled={!a}>Run Simulation ▶</button>
      </div>

      <div className="grid builder-grid">
        <div className="col">
          <div className="card">
            <div className="card-title">
              Failure web
              <span className="tag">{graph?.nodes.length || 0} nodes</span>
              <span className="tag">{graph?.edges.length || 0} links</span>
              {imp && <span className="tag">exposure {money(imp.moneyTotal)}</span>}
              {edited > 0 && <span className="pill pill-amber" style={{ marginLeft: 8 }}>{edited} edited</span>}
            </div>
            {busy ? <div className="empty"><span className="spin spin-dark" /> Building the web…</div>
              : graph ? <CascadeGraph graph={graph} mode="decision" selectedId={sel} onSelect={setSel} />
                : <div className="empty">Pick a scenario to build its web.</div>}
          </div>

          <div className="card">
            <div className="card-title">Operating conditions<span className="tag">shapes the web</span></div>
            <div className="hint" style={{ marginBottom: 10 }}>
              The engine models operator <b>readiness</b>, not weather — so a condition applies as a
              readiness penalty. That is not cosmetic: push readiness low enough and the root fault’s
              containment fails, which fires the engine’s preventable branch and grows the cascade.
            </div>
            {domainConds.length ? (
              <div className="cond-row">
                {domainConds.map(c => (
                  <button key={c.id} className={`chip ${conds.includes(c.id) ? 'on' : ''}`} onClick={() => toggleCond(c.id)}>
                    {conds.includes(c.id) ? '✓ ' : ''}{c.label} −{c.penalty}
                  </button>
                ))}
              </div>
            ) : <div className="hint">No conditions registered for this vertical.</div>}

            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
                <b>Baseline readiness</b>
                <b style={{ color: 'var(--accent)' }}>
                  {webReadiness}%{conds.length > 0 && <span style={{ color: 'var(--muted)', fontWeight: 600 }}> → {effReadiness}% effective</span>}
                </b>
              </div>
              <input type="range" min="0" max="100" value={webReadiness} onChange={e => setWebReadiness(+e.target.value)} />
              <div className="hint" style={{ marginTop: 4 }}>
                Low readiness makes every branch fire, so you author against the <b>fullest</b> web.
                Raise it to see which consequences a prepared response removes entirely.
              </div>
            </div>
          </div>

          {myVersions.length > 0 && (
            <div className="card">
              <div className="card-title">Versions<span className="tag">{myVersions.length}</span></div>
              <div className="ver-list">
                {myVersions.map(v => (
                  <button key={v.id} className="ver-row" onClick={() => restore(v)}>
                    <b>v{v.n}</b>
                    <span className="hint" style={{ flex: 1 }}>{Object.keys(v.ov || {}).length} tuned · {new Date(v.ts).toLocaleString()}</span>
                    <b>{money(v.exposure)}</b>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="col">
          <div className="seg" style={{ alignSelf: 'flex-start' }}>
            <button className={tab === 'node' ? 'on' : ''} onClick={() => setTab('node')}>Node metrics</button>
            <button className={tab === 'chat' ? 'on' : ''} onClick={() => setTab('chat')}>Customise with AI</button>
          </div>

          {tab === 'chat' ? (
            <ScenarioChat scenario={a} onApplied={onApplied} />
          ) : (
            <div className="card">
              <div className="card-title">Node metrics</div>
              {!node ? <div className="hint">Click any node in the web to inspect and tune its metrics.</div> : (
                <div className="node-ed">
                  <div className="node-ed-head">
                    <b style={{ fontSize: 13.5 }}>{node.scenario_name}</b>
                    <span className={`pill ${node.node_kind === 'fault' ? 'pill-violet' : 'pill-muted'}`}>{node.node_kind}</span>
                  </div>

                  <label className="ne-field">
                    <span>Severity</span>
                    <select className="select" value={node.impact_level || 'medium'} onChange={e => setTier(e.target.value)}>
                      {TIERS.map(t => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
                    </select>
                  </label>

                  {tpl.map(m => (
                    <label key={m.key} className="ne-field">
                      <span>{m.label}</span>
                      <input className="ne-input" type="number" min="0" value={metrics[m.key] ?? 0}
                        onChange={e => setMetric(m.key, Math.max(0, +e.target.value || 0))} />
                    </label>
                  ))}

                  <div className="ne-stats">
                    <div><div className="v">{money(nodeMoney)}</div><div className="l">$ contribution</div></div>
                    <div><div className="v" style={{ textTransform: 'capitalize' }}>{tierFromMoney(graph.domain, nodeMoney)}</div><div className="l">derived severity</div></div>
                    <div><div className="v">{downstream}</div><div className="l">downstream nodes</div></div>
                    <div><div className="v">{Math.round(100 * nodeMoney / (imp?.moneyTotal || 1))}%</div><div className="l">of total exposure</div></div>
                  </div>

                  {ov[node.run_id] && <button className="btn btn-ghost" style={{ marginTop: 10 }} onClick={() => setOv(o => { const n = { ...o }; delete n[node.run_id]; return n })}>↺ Reset this node</button>}
                  <div className="hint" style={{ marginTop: 10 }}>These are the real operational quantities behind the node — edit them and the whole web’s exposure updates live. Tuning carries into the simulation and can be saved as a version.</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
