import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { computeImpact, money } from '../impact.js'
import CascadeGraph from '../components/CascadeGraph.jsx'

// Scenario collision — two independently-authored faults hitting the same operation at once.
// Only possible because every scenario shares one graph model. This is the differentiator.
export default function Composer() {
  const { allScenarios } = useStore()
  const [aId, setA] = useState('')
  const [bId, setB] = useState('')
  const [out, setOut] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (allScenarios.length && !aId) { setA(allScenarios[0].id); setB(allScenarios[1]?.id || allScenarios[0].id) }
  }, [allScenarios, aId])

  const a = allScenarios.find(s => s.id === aId), b = allScenarios.find(s => s.id === bId)

  const collide = async () => {
    if (!a || !b) return
    setBusy(true); setOut(null)
    try {
      const [ga, gb] = await Promise.all([api.runGraph(a.id, a.domainKey, 45), api.runGraph(b.id, b.domainKey, 45)])
      const merged = { domain: a.domainKey, nodes: [...ga.nodes, ...gb.nodes], edges: [...ga.edges, ...gb.edges], totals: {} }
      const exposure = computeImpact(ga).moneyTotal + computeImpact(gb).moneyTotal
      setOut({ merged, exposure, nodes: ga.nodes.length + gb.nodes.length })
    } finally { setBusy(false) }
  }

  return (
    <>
      <div className="mode-head"><h2>Scenario Composer</h2><p>Collide two faults into one operating picture — the combined failure surface no single simulator can show.</p></div>

      <div className="card" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <select className="select" style={{ flex: 1, minWidth: 180 }} value={aId} onChange={e => { setA(e.target.value); setOut(null) }}>
          {allScenarios.map(s => <option key={s.id} value={s.id}>{s.domainName?.split(' ')[0]} · {s.name}</option>)}
        </select>
        <span style={{ fontWeight: 800, color: 'var(--accent)' }}>✕</span>
        <select className="select" style={{ flex: 1, minWidth: 180 }} value={bId} onChange={e => { setB(e.target.value); setOut(null) }}>
          {allScenarios.map(s => <option key={s.id} value={s.id}>{s.domainName?.split(' ')[0]} · {s.name}</option>)}
        </select>
        <button className="btn btn-primary" onClick={collide} disabled={busy || !a || !b}>{busy ? <><span className="spin" /> Colliding…</> : 'Compose'}</button>
      </div>

      {out && (
        <>
          <div className="stat-row" style={{ margin: '16px 0' }}>
            <div className="hero-stat"><div className="v">{money(out.exposure)}</div><div className="l">combined exposure</div></div>
            <div className="hero-stat"><div className="v">{out.nodes}</div><div className="l">failure nodes</div></div>
            <div className="hero-stat"><div className="v">2</div><div className="l">concurrent faults</div></div>
          </div>
          <div className="card">
            <div className="card-title">Combined failure surface<span className="tag">emergent</span></div>
            <CascadeGraph graph={out.merged} mode="decision" />
            <div className="hint" style={{ marginTop: 10 }}>Two concurrent faults on one operation. Because both scenarios share the same graph model, they compose into a single exposure picture instead of two disconnected reports.</div>
          </div>
        </>
      )}
    </>
  )
}
