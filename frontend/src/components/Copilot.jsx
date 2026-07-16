import React, { useEffect, useRef, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { compareInvestments, criticalPath } from '../analysis.js'
import { money } from '../impact.js'

const QUICK = ['Explain the recommendation', 'What happens if we do nothing?', 'Where is the money going?', 'Summarise for the board']

// AI analyst — real Claude call on the engine, grounded in this run's actual numbers.
export default function Copilot() {
  const { selected, domain } = useStore()
  const [ctx, setCtx] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')
  const endRef = useRef(null)

  useEffect(() => {
    if (!selected) return
    let ok = true; setMsgs([]); setCtx(null)
    compareInvestments(selected, domain).then(cmp => {
      if (!ok) return
      const context = `Scenario "${selected.name}" (${domain}). Estimated unmitigated exposure ${money(cmp.full)}, of which ${money(cmp.prevPot)} is avoidable. `
        + `Critical path: ${criticalPath(cmp.worst.graph)}. `
        + `Ranked strategies: ${cmp.ranked.map(r => `${r.name} costs ${money(r.cost)}, avoids ${money(r.saved)}, ${r.roi.toFixed(1)}x ROI, ${Math.round(r.contain * 100)}% success`).join('; ') || 'none beat doing nothing'}.`
      setCtx(context)
      send('Give a 3-sentence executive briefing of this decision.', context, true)
    }).catch(() => {})
    return () => { ok = false }
  }, [selected?.id, domain]) // eslint-disable-line

  const send = async (question, context = ctx, isBrief = false) => {
    if (!context || busy) return
    setBusy(true)
    if (!isBrief) setMsgs(m => [...m, { role: 'you', text: question }])
    try {
      const r = await api.ask(context, question)
      setMsgs(m => [...m, { role: 'ai', text: r.answer, brief: isBrief }])
    } catch (e) { setMsgs(m => [...m, { role: 'ai', text: 'Analyst unavailable: ' + e.message }]) }
    finally { setBusy(false); setTimeout(() => endRef.current?.scrollIntoView({ block: 'nearest' }), 50) }
  }

  return (
    <div className="card">
      <div className="card-title">◆ AI Analyst<span className="tag">grounded in this run</span></div>
      <div className="copilot">
        {msgs.map((m, i) => (
          <div key={i} className={`cp-msg cp-${m.role} ${m.brief ? 'cp-brief' : ''}`}>{busy && i === msgs.length - 1 ? '' : m.text}</div>
        ))}
        {busy && <div className="cp-msg cp-ai"><span className="spin spin-dark" /> thinking…</div>}
        <div ref={endRef} />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '10px 0' }}>
        {QUICK.map(x => <button key={x} className="chip" onClick={() => send(x)} disabled={busy || !ctx}>{x}</button>)}
      </div>
      <form style={{ display: 'flex', gap: 8 }} onSubmit={e => { e.preventDefault(); if (q.trim()) { send(q.trim()); setQ('') } }}>
        <input className="lib-search" style={{ flex: 1 }} placeholder="Ask about this decision…" value={q} onChange={e => setQ(e.target.value)} disabled={!ctx} />
        <button className="btn btn-primary" disabled={busy || !q.trim()}>Ask</button>
      </form>
    </div>
  )
}
