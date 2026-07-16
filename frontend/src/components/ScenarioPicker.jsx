import React from 'react'
import { useStore } from '../store.jsx'

export default function ScenarioPicker() {
  const { scenarios, scenarioId, setScenarioId } = useStore()
  if (!scenarios.length) return <div className="hint">No scenarios registered for this domain.</div>
  return (
    <div className="col" style={{ gap: 8 }}>
      {scenarios.map(s => (
        <button key={s.id} className={`scn ${scenarioId === s.id ? 'on' : ''}`} onClick={() => setScenarioId(s.id)}>
          <b>{s.name}</b>
          <span>{s.description}</span>
        </button>
      ))}
    </div>
  )
}
