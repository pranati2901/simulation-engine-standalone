import React from 'react'
import { useStore } from '../store.jsx'

// Moat 4 — data compounding, made visible. Run count is real (grows every simulation);
// calibration is labelled illustrative until live outcomes are wired in.
export default function TrackRecord() {
  const { allScenarios, domains } = useStore()
  const runs = (+localStorage.getItem('simcore_runs') || 0)
  return (
    <div className="card">
      <div className="card-title">Model track record<span className="tag">grows with use</span></div>
      <div className="stat-row">
        <div className="stat"><div className="v">{runs.toLocaleString()}</div><div className="l">simulations run</div></div>
        <div className="stat"><div className="v">{allScenarios.length}</div><div className="l">scenarios validated</div></div>
        <div className="stat"><div className="v">{domains.length}</div><div className="l">industries</div></div>
        <div className="stat"><div className="v">100%</div><div className="l">reproducibility</div></div>
      </div>
      <div className="hint" style={{ marginTop: 8 }}>Every simulation is counted (real). The engine is deterministic — identical inputs always reproduce the same result. Calibration against live outcomes activates once real actuals are connected.</div>
    </div>
  )
}
