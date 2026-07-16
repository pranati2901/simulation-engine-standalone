import React from 'react'

export default function ScoreCard({ graph }) {
  const root = graph?.nodes?.[0]?.result
  if (!root) return null
  const score = root.scores?.operator ?? 0
  const objectives = root.objectives?.operator || []
  const certified = root.summary?.clearance?.certified
  return (
    <div className="card">
      <div className="card-title">Competency result<span className="tag">scored</span></div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ fontSize: 34, fontWeight: 800, fontFamily: 'var(--display)', lineHeight: 1 }}>
          {Math.round(score)}<span style={{ fontSize: 15, color: 'var(--muted)', fontWeight: 600 }}>/100</span>
        </div>
        <span className={`pill ${certified ? 'pill-green' : 'pill-red'}`}>{certified ? 'CERTIFIED' : 'NOT CERTIFIED'}</span>
      </div>
      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 9 }}>
        {objectives.map((o, i) => (
          <div key={i} style={{ display: 'flex', gap: 9, fontSize: 12.5, alignItems: 'flex-start' }}>
            <span style={{ color: o.met ? 'var(--green)' : 'var(--red)', fontWeight: 800 }}>{o.met ? '✓' : '✗'}</span>
            <span>{o.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
