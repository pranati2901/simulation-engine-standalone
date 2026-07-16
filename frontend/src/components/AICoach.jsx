import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// Real AI coaching on the drill result — grounded in the trainee's actual score/objectives.
export default function AICoach({ scenario, graph }) {
  const [fb, setFb] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!graph || !scenario) return
    const root = graph.nodes?.[0]?.result || {}
    const score = Math.round(root.scores?.operator ?? 0)
    const cert = root.summary?.clearance?.certified
    const objs = (root.objectives?.operator || []).map(o => `${o.met ? 'met' : 'missed'}: ${o.text}`).join('; ')
    const ctx = `Training drill "${scenario.name}". Trainee scored ${score}/100 and was ${cert ? 'certified' : 'not certified'}. Objectives — ${objs}.`
    let ok = true; setBusy(true); setFb(null)
    api.ask(ctx, 'Give two sentences of constructive coaching to the trainee: one thing they did well, one to improve.')
      .then(r => ok && setFb(r.answer)).catch(() => ok && setFb(null)).finally(() => ok && setBusy(false))
    return () => { ok = false }
  }, [graph, scenario?.id])

  return (
    <div className="card">
      <div className="card-title">◆ AI coach<span className="tag">feedback</span></div>
      {busy ? <div className="hint"><span className="spin spin-dark" /> Reviewing the run…</div>
        : <div style={{ fontSize: 12.5, lineHeight: 1.65 }}>{fb || 'Run the drill to get coaching feedback.'}</div>}
    </div>
  )
}
