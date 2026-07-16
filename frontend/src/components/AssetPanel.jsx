import React, { useState } from 'react'

// Real assets straight from the scenario's environment (backend). The one the fault targets
// shows as failing; the rest are at-risk in the blast radius.
export default function AssetPanel({ scenario }) {
  const actors = scenario?.recommended_environment?.actors || []
  const failType = scenario?.steps?.[0]?.target?.value
  const [open, setOpen] = useState(null)
  if (!actors.length) return null
  return (
    <div className="card">
      <div className="card-title">Assets<span className="tag">live status</span></div>
      <div className="asset-grid">
        {actors.map(a => {
          const failing = a.type === failType
          return (
            <button key={a.id} className="asset" onClick={() => setOpen(open === a.id ? null : a.id)}>
              <span className={`asset-dot ${failing ? 'crit' : 'warn'}`} />
              <div style={{ textAlign: 'left', flex: 1, minWidth: 0 }}>
                <b style={{ fontSize: 12.5 }}>{a.name}</b>
                <div className="asset-t">{String(a.type).replace(/_/g, ' ')}</div>
              </div>
              {failing && <span className="pill pill-red">failing</span>}
            </button>
          )
        })}
      </div>
      {open && (() => {
        const a = actors.find(x => x.id === open); const failing = a.type === failType
        return <div className="asset-detail">
          <b>{a.name}</b> — {failing ? 'the fault originates here; it drives the downstream cascade.' : 'in the blast radius — monitor as the cascade propagates.'}
        </div>
      })()}
    </div>
  )
}
