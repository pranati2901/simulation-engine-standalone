import React from 'react'
import { computeImpact, savingFactor, nodeExposure, money } from '../impact.js'

// The cascade as a time-ordered sequence, with the single best place to intervene marked.
export default function RiskTimeline({ graph }) {
  const nodes = [...(graph?.nodes || [])].sort((a, b) => (a.t_offset_s || 0) - (b.t_offset_s || 0))
  if (!nodes.length) return null
  const { moneyTotal: full, moneyPrev: prev } = computeImpact(graph)
  const avoidable = full * savingFactor(full, prev)
  const domain = graph.domain

  return (
    <div className="timeline">
      {nodes.map((n) => {
        const t = Math.round((n.t_offset_s || 0) / 60)
        const fault = n.node_kind === 'fault'
        return (
          <div className="tl-row" key={n.run_id}>
            <div className="tl-time">{t === 0 ? '0m' : `+${t}m`}</div>
            <div className={`tl-dot ${fault ? 'fault' : ''}`} />
            <div className="tl-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <b>{n.scenario_name}</b>
                <span style={{ color: 'var(--muted)', fontSize: 11.5, whiteSpace: 'nowrap' }}>{money(nodeExposure(domain, n.impact_level))}</span>
              </div>
              {fault && avoidable > 0 && (
                <div className="tl-intervene">⚡ Best place to intervene — up to <b>{money(avoidable)}</b> avoidable if contained here.</div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
