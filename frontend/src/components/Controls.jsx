import React from 'react'
import { useStore } from '../store.jsx'

// Readiness + Run. Readiness is the one knob the engine truly reasons about: push it low
// and the fault isn't contained, so the preventable branch of the cascade fires.
export default function Controls({ label = 'Run scenario', note }) {
  const { readiness, setReadiness, run, running, selected } = useStore()
  return (
    <div className="card">
      <div className="card-title">Operator readiness</div>
      <input className="slider" type="range" min="0" max="100" value={readiness}
        onChange={e => setReadiness(+e.target.value)} />
      <div className="slider-row"><span>Low</span><b style={{ color: 'var(--text)' }}>{readiness}</b><span>High</span></div>
      <div className="hint" style={{ margin: '8px 0 12px' }}>
        {note || 'Lower readiness = slower response = the fault is less likely to be contained, so more of the cascade fires.'}
      </div>
      <button className="btn btn-primary btn-block" onClick={run} disabled={running || !selected}>
        {running ? <><span className="spin" /> Running…</> : label}
      </button>
    </div>
  )
}
