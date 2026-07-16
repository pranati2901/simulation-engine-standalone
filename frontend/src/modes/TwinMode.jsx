import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import ScenarioPicker from '../components/ScenarioPicker.jsx'
import CascadeGraph from '../components/CascadeGraph.jsx'
import CriticalityPanel from '../components/CriticalityPanel.jsx'
import AssetPanel from '../components/AssetPanel.jsx'
import HealthTimeline from '../components/HealthTimeline.jsx'

export default function TwinMode() {
  const { selected, domain } = useStore()
  const [graph, setGraph] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [readiness, setReadiness] = useState(55)

  useEffect(() => {
    if (!selected) { setGraph(null); return }
    let ok = true; setBusy(true); setErr(null); setGraph(null)
    api.runGraph(selected.id, domain, 55).then(g => ok && setGraph(g)).catch(e => ok && setErr(e.message)).finally(() => ok && setBusy(false))
    return () => { ok = false }
  }, [selected?.id, domain])

  return (
    <>
      <div className="mode-head"><h2>Twin Intelligence</h2><p>Inject a fault into an asset and watch how far — and how fast — it spreads before it fails. Find the weak point and what to fix first.</p></div>
      <div className="grid">
        <div className="col">
          <div className="card"><div className="card-title">Inject a failure</div><ScenarioPicker />
            <div className="hint" style={{ marginTop: 10 }}>Pick a fault to inject into the twin. The timeline shows the asset’s health deteriorating as the cascade propagates; the panels below rank which asset is the real weak point.</div>
          </div>
        </div>
        <div className="col">
          {!selected && <div className="card"><div className="empty">Pick a fault to inject.</div></div>}
          {busy && <div className="card"><div className="empty"><span className="spin spin-dark" /> Tracing failure path…</div></div>}
          {err && <div className="err">{err}</div>}
          {graph && !busy && (
            <>
              <div className="card">
                <div className="card-title">Asset health under cascade<span className="tag">fault injected</span></div>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
                    <b>Response readiness</b><b style={{ color: 'var(--accent)' }}>{readiness}%</b>
                  </div>
                  <input type="range" min="0" max="100" value={readiness} onChange={e => setReadiness(+e.target.value)} style={{ width: '100%' }} />
                </div>
                <HealthTimeline graph={graph} readiness={readiness} />
              </div>
              <AssetPanel scenario={selected} />
              <CriticalityPanel graph={graph} />
              <div className="card"><div className="card-title">Failure propagation</div><CascadeGraph graph={graph} mode="twin" /></div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
