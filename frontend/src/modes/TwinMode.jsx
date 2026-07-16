import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import ScenarioPicker from '../components/ScenarioPicker.jsx'
import CascadeGraph from '../components/CascadeGraph.jsx'
import CriticalityPanel from '../components/CriticalityPanel.jsx'
import AssetPanel from '../components/AssetPanel.jsx'

export default function TwinMode() {
  const { selected, domain } = useStore()
  const [graph, setGraph] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!selected) { setGraph(null); return }
    let ok = true; setBusy(true); setErr(null); setGraph(null)
    api.runGraph(selected.id, domain, 55).then(g => ok && setGraph(g)).catch(e => ok && setErr(e.message)).finally(() => ok && setBusy(false))
    return () => { ok = false }
  }, [selected?.id, domain])

  return (
    <>
      <div className="mode-head"><h2>Twin Intelligence</h2><p>Which asset is the weak point, and what to fix first — before it fails.</p></div>
      <div className="grid">
        <div className="col">
          <div className="card"><div className="card-title">Trace a failure</div><ScenarioPicker /></div>
        </div>
        <div className="col">
          {!selected && <div className="card"><div className="empty">Pick a failure to trace.</div></div>}
          {busy && <div className="card"><div className="empty"><span className="spin spin-dark" /> Tracing failure path…</div></div>}
          {err && <div className="err">{err}</div>}
          {graph && !busy && (
            <>
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
