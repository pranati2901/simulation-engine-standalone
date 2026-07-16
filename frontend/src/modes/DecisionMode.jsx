import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { pct } from '../impact.js'
import ScenarioPicker from '../components/ScenarioPicker.jsx'
import WhatIf from '../components/WhatIf.jsx'
import DecisionStudio from '../components/DecisionStudio.jsx'
import MonteCarloPanel from '../components/MonteCarloPanel.jsx'
import CascadeGraph from '../components/CascadeGraph.jsx'
import NodeInspector from '../components/NodeInspector.jsx'
import RiskTimeline from '../components/RiskTimeline.jsx'
import Copilot from '../components/Copilot.jsx'

function KpiStrip({ graph }) {
  const k = graph?.nodes?.[0]?.result?.kpis || {}
  const items = [
    { l: 'Containment', v: pct(k.containment_rate) },
    { l: 'Detection', v: pct(k.detection_rate) },
    { l: 'Time to resolve', v: `${Math.round(k.mean_time_to_resolve_s || 0)}s` },
    { l: 'Consequences', v: (graph?.totals?.downstream_consequences ?? 0) },
  ]
  return <div className="stat-row" style={{ marginBottom: 12 }}>{items.map((x, i) => <div className="stat" key={i}><div className="v">{x.v}</div><div className="l">{x.l}</div></div>)}</div>
}

export default function DecisionMode() {
  const { selected } = useStore()
  const [graph, setGraph] = useState(null)
  const [sel, setSel] = useState(null)
  useEffect(() => { setGraph(null); setSel(null) }, [selected?.id])

  return (
    <>
      <div className="mode-head">
        <h2>Decision Intelligence</h2>
        <p>Here’s the recommended move — then explore the alternatives and stress-test it yourself.</p>
      </div>
      <div className="grid">
        <div className="col">
          <div className="card"><div className="card-title">Scenario</div><ScenarioPicker /></div>
        </div>
        <div className="col">
          {!selected && <div className="card"><div className="empty">Pick a scenario to see the recommended decision.</div></div>}
          {selected && (
            <>
              <DecisionStudio key={'ds-' + selected.id} />
              <Copilot key={'cp-' + selected.id} />
              <WhatIf key={selected.id} onRun={g => { setGraph(g); setSel(null) }} />
              {graph && (
                <>
                  <div className="card">
                    <div className="card-title">Cascade &amp; node inspector</div>
                    <KpiStrip graph={graph} />
                    <CascadeGraph graph={graph} mode="decision" selectedId={sel} onSelect={setSel} />
                    <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                      <NodeInspector graph={graph} selectedId={sel} />
                    </div>
                  </div>
                  <div className="card"><div className="card-title">Risk timeline<span className="tag">sequence &amp; intervention</span></div><RiskTimeline graph={graph} /></div>
                </>
              )}
              <MonteCarloPanel />
            </>
          )}
        </div>
      </div>
    </>
  )
}
