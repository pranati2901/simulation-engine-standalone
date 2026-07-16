import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const GAIN = 65 / 7   // start 35% → 100% if all seven done right

const buildSteps = (asset, fault) => [
  { title: 'Diagnose the fault', desc: `Read the affected telemetry on ${asset} and localise the cause of the ${fault}.` },
  { title: 'Isolate & make safe (LOTO)', desc: 'Apply lockout/tagout and confirm zero energy before opening anything.', safety: true },
  { title: 'Inspect the component', desc: `Open the housing and confirm the failure mode on ${asset}.`, physical: true },
  { title: 'Repair / replace', desc: 'Restore or swap the failed part to serviceable condition per spec.', physical: true },
  { title: 'Recalibrate / set to spec', desc: 'Bring the subsystem back to its set-point and re-reference as needed.', physical: true },
  { title: 'Functional test', desc: 'Restore power, run the asset and confirm it returns to nominal.' },
  { title: 'Verify & sign off', desc: 'Confirm health is restored and close the work order.', verify: true },
]

export default function GuidedDrill({ scenario }) {
  const asset = scenario?.recommended_environment?.actors?.[0]?.name || 'the asset'
  const fault = scenario?.name || 'the fault'
  const steps = buildSteps(asset, fault)

  const [status, setStatus] = useState([])     // 'done' | 'skipped'
  const [loto, setLoto] = useState(false)
  const [health, setHealth] = useState(35)
  const [violations, setViolations] = useState([])
  const [feedback, setFeedback] = useState(null)
  const [fbBusy, setFbBusy] = useState(false)

  const reset = () => { setStatus([]); setLoto(false); setHealth(35); setViolations([]); setFeedback(null) }
  useEffect(() => { reset() }, [scenario?.id]) // eslint-disable-line

  const active = status.length            // index of the current step
  const done = status.length >= steps.length
  const clamp = (v) => Math.max(0, Math.min(100, v))

  const act = (kind) => {
    const i = active; const st = steps[i]; let viol = null; let dh = 0
    if (kind === 'perform') {
      if (st.physical && !loto) { viol = `Worked on ${asset} before isolating it (LOTO).`; dh = 2 }
      else { dh = GAIN }
      if (st.safety) setLoto(true)
      setStatus(s => [...s, 'done'])
    } else {
      if (st.safety) viol = 'Skipped safety isolation (LOTO) entirely.'
      else if (st.verify) viol = 'Closed the job without verifying the fix.'
      dh = viol ? -4 : -1
      setStatus(s => [...s, 'skipped'])
    }
    setHealth(h => clamp(h + dh))
    if (viol) setViolations(v => [...v, viol])
  }

  // AI supervisor feedback once the drill completes
  useEffect(() => {
    if (!done || feedback) return
    const doneN = status.filter(s => s === 'done').length
    const ctx = `Guided repair drill for "${fault}" on ${asset}. Final machine health ${Math.round(health)}%. `
      + `${doneN}/${steps.length} steps performed, ${violations.length} violation(s): ${violations.join('; ') || 'none'}.`
    let ok = true; setFbBusy(true)
    api.ask(ctx, 'You are the maintenance supervisor. Give two sentences: what the technician did well and the single most important thing to fix next time.')
      .then(r => ok && setFeedback(r.answer)).catch(() => ok && setFeedback(null)).finally(() => ok && setFbBusy(false))
    return () => { ok = false }
  }, [done]) // eslint-disable-line

  const safetyViol = violations.some(v => v.toLowerCase().includes('isolat') || v.toLowerCase().includes('loto'))
  const score = clamp(Math.round(health - violations.length * 4))
  const certified = health >= 88 && !safetyViol
  const hColor = health >= 80 ? 'var(--green)' : health >= 50 ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="card">
      <div className="drill-hdr">
        <div>
          <div className="card-title" style={{ margin: 0 }}>◆ Guided repair — {fault}</div>
          <div className="hint" style={{ marginTop: 4 }}>Interactive procedure — perform the steps <b>in order</b>. Safety isolation before any physical work; skipping or re-ordering carries realistic consequences.</div>
        </div>
      </div>

      <div className="drill-stats">
        <div><div className="ds-v" style={{ color: hColor }}>{Math.round(health)}%</div><div className="ds-l">machine health</div></div>
        <div><div className="ds-v">{Math.min(status.length, steps.length)}/{steps.length}</div><div className="ds-l">progress</div></div>
        <div><div className="ds-v" style={{ color: violations.length ? 'var(--red)' : 'var(--muted)' }}>{violations.length}</div><div className="ds-l">violation(s)</div></div>
      </div>
      <div className="bar-track" style={{ margin: '12px 0 16px' }}><div className="bar-fill" style={{ width: `${health}%`, background: hColor, transition: 'width .4s' }} /></div>

      <div className="steps">
        {steps.map((s, i) => {
          const stat = status[i]
          const isActive = i === active && !done
          return (
            <div key={i} className={`step ${stat || ''} ${isActive ? 'active' : ''}`}>
              <div className="step-n">{stat === 'done' ? '✓' : stat === 'skipped' ? '–' : i + 1}</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <b style={{ fontSize: 13 }}>{s.title}</b>
                  {s.safety && <span className="pill pill-red">SAFETY</span>}
                </div>
                <div className="hint" style={{ marginTop: 2 }}>{s.desc}</div>
                {isActive && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button className="btn btn-primary" style={{ padding: '6px 16px' }} onClick={() => act('perform')}>Perform</button>
                    <button className="btn" style={{ padding: '6px 16px' }} onClick={() => act('skip')}>Skip</button>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {done && (
        <div className="drill-done">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 30, fontWeight: 800, fontFamily: 'var(--display)' }}>{score}<span style={{ fontSize: 15, color: 'var(--muted)' }}>/100</span></div>
            <span className={`pill ${certified ? 'pill-green' : 'pill-red'}`}>{certified ? 'CERTIFIED' : safetyViol ? 'FAILED — SAFETY' : 'NOT CERTIFIED'}</span>
            <button className="btn" style={{ marginLeft: 'auto' }} onClick={reset}>↻ Retry drill</button>
          </div>
          <div style={{ marginTop: 12, fontSize: 12.5, lineHeight: 1.6 }}>
            <b>◆ Supervisor feedback:</b> {fbBusy ? <span><span className="spin spin-dark" /> reviewing…</span> : (feedback || 'Complete the drill for feedback.')}
          </div>
        </div>
      )}
    </div>
  )
}
