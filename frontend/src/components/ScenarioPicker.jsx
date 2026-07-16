import React from 'react'
import { useStore } from '../store.jsx'

// Compact — one dense line per scenario (full name on hover).
export default function ScenarioPicker() {
  const { scenarios, scenarioId, setScenarioId } = useStore()
  if (!scenarios.length) return <div className="hint">No scenarios registered for this domain.</div>
  return (
    <div className="scn-list">
      {scenarios.map(s => (
        <button key={s.id} className={`scn-c ${scenarioId === s.id ? 'on' : ''}`} onClick={() => setScenarioId(s.id)} title={s.description}>
          {s.name}
        </button>
      ))}
    </div>
  )
}
