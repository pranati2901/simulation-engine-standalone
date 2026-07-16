import React, { useState } from 'react'

// The drill as a decision moment — real data from the scenario's decision gate.
export default function DrillBriefing({ scenario }) {
  const g = scenario?.decision_gates?.[0]
  const [reveal, setReveal] = useState(false)
  if (!scenario) return null
  return (
    <div className="card">
      <div className="card-title">Drill briefing<span className={`pill ${(g?.risk_level === 'extreme' || g?.risk_level === 'high') ? 'pill-red' : 'pill-amber'}`} style={{ marginLeft: 'auto' }}>{g?.risk_level || 'high'} risk</span></div>
      <div style={{ fontSize: 13, lineHeight: 1.6 }}>{scenario.description}</div>
      {g && (
        <>
          <div className="drill-q">⚠ {g.name} — what do you do?</div>
          {g.consequence_of_delay && <div className="hint" style={{ marginTop: 6 }}>If you hesitate: {g.consequence_of_delay}</div>}
          {!reveal
            ? <button className="btn btn-block" style={{ marginTop: 12 }} onClick={() => setReveal(true)}>Reveal recommended action</button>
            : <div className="drill-a">✓ {g.correct_action}</div>}
        </>
      )}
    </div>
  )
}
