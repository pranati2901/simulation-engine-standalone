// ScenarioChat.jsx — customise a scenario by describing the change.
//
// The Trainer already lets you author a drill from a sentence; this is the same idea
// applied to editing. "Add a coolant pump failure downstream of the spindle" comes back
// as a REVISED SPEC the engine validated against its live catalog — not prose.
//
// Nothing here decides what the change does. The model rewrites the spec; the engine
// still computes the cascade. A proposal is inert until the operator hits Apply, and
// applying never touches the original scenario — it registers a variant.
import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const QUICK = [
  'Make this fault harder to contain',
  'Add a preventable downstream consequence',
  'Add a decision gate for the operator',
  'What would make this worse?',
]

export default function ScenarioChat({ scenario, onApplied }) {
  const [msgs, setMsgs] = useState([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [committing, setCommitting] = useState(false)
  // The spec each new instruction builds on. Starts null (= revise the stored scenario);
  // once a proposal is accepted into the conversation, further instructions compound onto
  // it, so "make it worse" then "add a gate" yields one scenario with both changes.
  const [draft, setDraft] = useState(null)
  const endRef = useRef(null)

  // A different scenario is a different conversation. Without this the chat would carry
  // the previous scenario's draft onto the new one and revise the wrong spec.
  useEffect(() => { setMsgs([]); setDraft(null); setQ('') }, [scenario?.id])

  const scrollDown = () => setTimeout(() => endRef.current?.scrollIntoView({ block: 'nearest' }), 50)

  const send = async (instruction) => {
    if (!scenario || busy || !instruction.trim()) return
    setMsgs(m => [...m, { role: 'you', text: instruction }])
    setBusy(true); scrollDown()
    try {
      const r = await api.revise(scenario.id, instruction, draft)
      setMsgs(m => [...m, { role: 'prop', proposal: r }])
      setDraft(r.scenario)
    } catch (e) {
      setMsgs(m => [...m, { role: 'err', text: e.message }])
    } finally { setBusy(false); scrollDown() }
  }

  const apply = async (proposal) => {
    setCommitting(true)
    try {
      const saved = await api.commit(proposal.scenario)
      setMsgs(m => [...m, { role: 'ai', text: `Saved as “${saved.name}”. It's in the library and runnable now — the original is untouched.` }])
      setDraft(null)
      onApplied?.(saved)
    } catch (e) {
      setMsgs(m => [...m, { role: 'err', text: e.message }])
    } finally { setCommitting(false); scrollDown() }
  }

  const discard = () => {
    setDraft(null)
    setMsgs(m => [...m, { role: 'ai', text: 'Discarded. Next change starts from the saved scenario again.' }])
    scrollDown()
  }

  return (
    <div className="card">
      <div className="card-title">
        Customise with AI
        <span className="tag">{draft ? 'draft in progress' : 'edits the spec'}</span>
      </div>

      {!scenario ? (
        <div className="hint">Pick a scenario to customise it.</div>
      ) : (
        <>
          <div className="copilot">
            {!msgs.length && (
              <div className="hint">
                Describe the change you want in plain English. The engine rewrites the scenario’s
                spec and validates it — you approve before anything is saved.
              </div>
            )}
            {msgs.map((m, i) => {
              if (m.role === 'you') return <div key={i} className="cp-msg cp-you">{m.text}</div>
              if (m.role === 'ai') return <div key={i} className="cp-msg cp-ai">{m.text}</div>
              if (m.role === 'err') return <div key={i} className="cp-msg cp-err">{m.text}</div>
              // a proposal
              const p = m.proposal
              const isLive = draft && p.scenario.id === draft.id
              return (
                <div key={i} className="cp-msg sc-prop">
                  <div className="sc-prop-head">
                    <span>{p.scenario.name}</span>
                    <span className="pill pill-violet">{p.scenario.impact_level}</span>
                  </div>
                  <ul className="sc-prop-changes">
                    {p.changes.map((c, j) => <li key={j}>{c}</li>)}
                  </ul>
                  {isLive ? (
                    <div className="sc-prop-acts">
                      <button className="btn btn-primary btn-sm" onClick={() => apply(p)} disabled={committing}>
                        {committing ? <><span className="spin" /> Saving…</> : '✓ Apply'}
                      </button>
                      <button className="btn btn-sm" onClick={discard} disabled={committing}>Discard</button>
                    </div>
                  ) : (
                    <div className="hint">Superseded by a later change.</div>
                  )}
                </div>
              )
            })}
            {busy && <div className="cp-msg cp-ai"><span className="spin spin-dark" /> rewriting the spec…</div>}
            <div ref={endRef} />
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '10px 0' }}>
            {QUICK.map(x => (
              <button key={x} className="chip" onClick={() => send(x)} disabled={busy}>{x}</button>
            ))}
          </div>

          <form className="sc-chat-form" onSubmit={e => { e.preventDefault(); const t = q.trim(); if (t) { send(t); setQ('') } }}>
            <input className="lib-search" placeholder="Describe a change…" value={q}
              onChange={e => setQ(e.target.value)} disabled={busy} />
            <button className="btn btn-primary" disabled={busy || !q.trim()}>Send</button>
          </form>

          {draft && (
            <div className="hint" style={{ marginTop: 8 }}>
              Unsaved draft — further changes build on it. Apply to add it to the library as a new
              scenario; the original is never modified.
            </div>
          )}
        </>
      )}
    </div>
  )
}
