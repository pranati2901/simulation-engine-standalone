import React, { useEffect, useReducer, useRef, useState } from 'react'
import EVWorld from './EVWorld.jsx'
import { HEALTHY, inr } from '../ev/scenarios.js'
import { getProcedure, repairStepsFor, severityOf, inPlaySignals, gradeLetter, CAP } from '../ev/drill.js'
import { RECORDS_KEY } from '../modes/EVRecords.jsx'

// "Fix It Live" — you PLAY inside the twin. Click the faulted asset in the 3-D scene to act on it;
// the world reacts where you clicked. Two phases, one grade: RESPOND (real-time) then REPAIR (field).
const CLOCK = 80

const SIG = {
  'ev:gridLoad': ['Transformer load', '%'], 'ev:transformerTemp': ['Transformer temp', '°C'],
  'ev:loadHeadroom': ['Load headroom', '%'], 'ev:peakDemand': ['Peak demand', 'kW'],
  'ev:bessSoc': ['BESS SoC', '%'], 'ev:bessPower': ['BESS power', 'kW'], 'ev:solarOutput': ['Solar', 'kW'],
  'ev:sessionsActive': ['Active sessions', ''], 'ev:faultedChargers': ['Faulted chargers', ''],
  'ev:chargingPower': ['DC-fast power', 'kW'], 'ev:thermalRunawayRisk': ['Runaway risk', '%'], 'ev:cellTempMax': ['Cell temp max', '°C'],
}
const BOUND = {
  'ev:gridLoad': [10, 110], 'ev:transformerTemp': [40, 102], 'ev:loadHeadroom': [0, 40], 'ev:peakDemand': [0, 800],
  'ev:bessSoc': [0, 100], 'ev:bessPower': [-20, 120], 'ev:solarOutput': [0, 320], 'ev:sessionsActive': [0, 24],
  'ev:faultedChargers': [0, 10], 'ev:chargingPower': [0, 700], 'ev:thermalRunawayRisk': [0, 95], 'ev:cellTempMax': [28, 54],
}
const SCENE_ID = { 'TX-1': 'TX-1', 'BESS-A': 'BESS-A', 'DCFC': 'DCFC-01', 'F-1': 'EMS-1', 'F-2': 'EMS-1', 'GRID': 'TX-1' }
const ASSET_NAME = { 'TX-1': 'Transformer T1', 'BESS-A': 'BESS-A', 'DCFC-01': 'the DC chargers', 'EMS-1': 'the EMS' }
const SIG_ASSET = {
  'ev:gridLoad': 'TX-1', 'ev:transformerTemp': 'TX-1', 'ev:loadHeadroom': 'EMS-1', 'ev:peakDemand': 'TX-1',
  'ev:thermalRunawayRisk': 'BESS-A', 'ev:cellTempMax': 'BESS-A', 'ev:bessSoc': 'BESS-A', 'ev:bessPower': 'BESS-A',
  'ev:faultedChargers': 'DCFC-01', 'ev:chargingPower': 'DCFC-01', 'ev:sessionsActive': 'DCFC-01', 'ev:solarOutput': 'TX-1',
}
const clampSig = (k, v) => { const b = BOUND[k]; return b ? Math.max(b[0], Math.min(b[1], v)) : v }
const clampFrame = (fr) => { for (const k in fr) if (BOUND[k]) fr[k] = clampSig(k, fr[k]) }
const sigVal = (fr, k) => Math.round(fr[k] ?? HEALTHY[k] ?? 0)
const stabColor = (s) => (s >= 70 ? '#34e2b0' : s >= 40 ? '#fbbf24' : '#fb7185')

export default function TakeCommand({ assetId, faultId, facts, conditions = [], startFrame, onExit }) {
  const proc = getProcedure(assetId, faultId)
  const repair = repairStepsFor(facts?.asset || assetId, facts?.fault || faultId)
  const faultAsset = SCENE_ID[assetId] || 'TX-1'
  const sim = useRef(null)
  const stageRef = useRef(null)
  const [, force] = useReducer((x) => x + 1, 0)
  const [stage, setStage] = useState('brief')
  const [confirmed, setConfirmed] = useState(false)
  const [level, setLevel] = useState(null)
  const [ring, setRing] = useState(null)   // in-world action popover {x,y}
  const [checked, setChecked] = useState([])   // how-to sub-steps ticked off for the current step

  const start = () => {
    const fr = { ...HEALTHY, ...(startFrame || {}) }; clampFrame(fr)
    const ip = inPlaySignals(fr); const inPlay = ip.length ? ip : ['ev:gridLoad', 'ev:transformerTemp']
    sim.current = {
      frame: fr, results: [], repairResults: [], contained: 0, clock: CLOCK, incurred: 0, saved: 0, log: [],
      violations: [], mttr: null, anim: null, handled: new Set(), ended: false, health: 38, loto: false,
      respondSeverity: null, pingCount: 0, narrate: 'Read the twin, then CLICK the glowing asset to act on it.', lastNow: performance.now(), flashUntil: 0,
      inPlay, fullRate: Math.max(400, (facts?.total_exposure_inr || 500000)) / CLOCK,
    }
    setConfirmed(false); setLevel(null); setRing(null); setStage('respond')
  }

  const respondStep = () => (sim.current ? proc.steps.find((st) => !sim.current.results.find((r) => r.id === st.id)) : null)
  const repairStep = () => (sim.current ? repair.find((st) => !sim.current.repairResults.find((r) => r.id === st.id)) : null)

  // reset the how-to checklist (and level/confirm) whenever the active step changes
  const activeStepId = sim.current ? (stage === 'repair' ? repairStep() : respondStep())?.id : null
  useEffect(() => { setChecked([]); setLevel(null); setConfirmed(false) }, [stage, activeStepId])

  useEffect(() => {
    if (stage !== 'respond' && stage !== 'repair') return
    const iv = setInterval(() => {
      const s = sim.current; if (!s || s.ended) return
      const now = performance.now(); let dt = (now - s.lastNow) / 1000; s.lastNow = now; dt = Math.min(0.4, dt)
      if (s.anim) {
        const p = Math.min(1, (now - s.anim.t0) / s.anim.dur)
        for (const k in s.anim.targets) { const { from, to } = s.anim.targets[k]; s.frame[k] = from + (to - from) * p }
        if (p >= 1) (s.anim.repair ? finishRepairAnim(s) : finishAnim(s))
      } else if (stage === 'respond') {
        const drift = Math.min(0.5, 0.05 * (1 - 0.85 * s.contained))
        for (const k of s.inPlay) { if (s.handled.has(k)) continue; const cap = CAP[k] ?? HEALTHY[k]; s.frame[k] += (cap - s.frame[k]) * drift * dt * 4 }
      }
      clampFrame(s.frame)
      if (stage === 'respond') {
        const sev = severityOf(s.frame)
        s.incurred += s.fullRate * sev * dt; s.saved += s.fullRate * (1 - sev) * dt
        if (sev < 0.18 && s.mttr == null && s.results.some((r) => r.status === 'done')) s.mttr = CLOCK - s.clock
        s.clock -= dt
        if (s.clock <= 0 || s.frame['ev:thermalRunawayRisk'] >= 92) return endAll('timeout')
      }
      force()
    }, 170)
    return () => clearInterval(iv)
  }, [stage]) // eslint-disable-line

  const effectLine = (a, st) => {
    let best = null
    for (const k in a.targets) { const d = Math.abs(a.targets[k].to - a.targets[k].from); if (d > 0.5 && (!best || d > best.d)) best = { k, d, from: a.targets[k].from, to: a.targets[k].to } }
    if (!best) return `${st.title} — done`
    const lab = (SIG[best.k] || [best.k, ''])[0], u = (SIG[best.k] || ['', ''])[1]
    return `${st.title} → ${lab} ${Math.round(best.from)}${u}→${Math.round(best.to)}${u}`
  }

  function finishAnim(s) {
    const a = s.anim; const st = proc.steps.find((x) => x.id === a.stepId)
    s.results.push({ id: a.stepId, status: 'done', level: a.level, at: Math.round(CLOCK - s.clock) })
    s.contained = Math.min(0.98, s.contained + (st.w || 0.1))
    for (const k in a.targets) s.handled.add(k)
    const line = effectLine(a, st); s.narrate = '✓ ' + line; s.log.unshift('✓ ' + line); s.anim = null
    setConfirmed(false); setLevel(null)
    if (!respondStep()) toRepair(s)
  }
  function finishRepairAnim(s) {
    const a = s.anim; const st = repair.find((x) => x.id === a.stepId)
    s.repairResults.push({ id: a.stepId, status: 'done', at: Math.round(CLOCK - s.clock) })
    if (st.id === 'loto') s.loto = true
    for (const k of s.inPlay) s.frame[k] += (HEALTHY[k] - s.frame[k]) * Math.min(0.9, (st.heal || 0.1) * 1.7)
    s.health = Math.min(100, s.health + (st.heal || 0.1) * 60 * (a.unsafe ? 0.4 : 1))
    s.narrate = `✓ ${st.title} — done (${Math.round(s.health)}% health)`; s.log.unshift(`✓ ${st.title}`); s.anim = null
    setConfirmed(false)
    if (!repairStep()) endAll('complete')
  }
  const toRepair = (s) => {
    s.respondSeverity = severityOf(s.frame); s.health = 38; s.repairResults = []; s.loto = false; s.anim = null
    s.log.unshift('— Site stabilised. Field repair begins.')
    s.narrate = 'Site stabilised. Now REPAIR: make it safe (LOTO), replace the part, test, sign off.'
    setConfirmed(false); setLevel(null); setRing(null); setStage('repair')
  }

  const endAll = (why) => {
    const s = sim.current; if (!s || s.ended) return; s.ended = true
    const respSev = s.respondSeverity != null ? s.respondSeverity : severityOf(s.frame)
    const respondContain = Math.max(0, 1 - respSev)
    const savedFrac = s.saved / (s.saved + s.incurred || 1)
    const speed = s.mttr == null ? 0 : Math.max(0, 1 - s.mttr / CLOCK)
    const repairPct = (s.health || 0) / 100
    const orderClean = !s.violations.some((v) => v.type === 'order')
    const safetyClean = !s.violations.some((v) => v.type === 'safety')
    const verifyClean = !s.violations.some((v) => v.type === 'verify')
    let score = 28 * respondContain + 20 * savedFrac + 12 * speed + 20 * repairPct + 10 * (orderClean ? 1 : 0) + 10 * (safetyClean && verifyClean ? 1 : 0)
    score = Math.round(Math.max(0, Math.min(100, score)))
    const g = gradeLetter(score, !safetyClean)
    s.final = { why, score, g, respondContain, savedFrac, speed, repairPct, incurred: Math.round(s.incurred), saved: Math.round(s.saved), mttr: s.mttr, orderClean, safetyClean, verifyClean, reachedRepair: s.respondSeverity != null }
    try {
      const rec = { id: Date.now(), ts: Date.now(), type: 'drill', site: facts?.site || '—', asset: facts?.asset || assetId,
        fault: facts?.fault || faultId, grade: g.letter, score, exposure: s.final.incurred, saved: s.final.saved, best: `Grade ${g.letter} · ${g.label}` }
      const cur = JSON.parse(localStorage.getItem(RECORDS_KEY) || '[]'); cur.unshift(rec)
      localStorage.setItem(RECORDS_KEY, JSON.stringify(cur.slice(0, 50)))
    } catch { /* ignore */ }
    const won = why === 'complete' && score >= 55 && safetyClean
    setRing(null); setStage(why === 'abort' ? 'debrief' : won ? 'won' : 'lost')
  }

  // ── handlers (called from the in-world popover) ──
  const diagnose = (st, opt) => {
    const s = sim.current
    if (opt.right) { s.results.push({ id: st.id, status: 'done', at: Math.round(CLOCK - s.clock) }); s.contained = Math.min(0.98, s.contained + st.w); s.pingCount++; s.narrate = `✓ Diagnosed — ${opt.label} is out of band.`; s.log.unshift(`✓ Diagnosed: ${opt.label}`); if (!respondStep()) toRepair(s) }
    else { s.clock = Math.max(2, s.clock - 5); s.narrate = `✗ ${opt.label} is nominal — read the twin again. (−5s)` }
    force()
  }
  const execute = (st) => {
    const s = sim.current
    if (st.requires && !st.requires.every((r) => s.results.find((y) => y.id === r && y.status === 'done'))) {
      const need = proc.steps.find((x) => x.id === st.requires.find((r) => !s.results.find((y) => y.id === r && y.status === 'done')))
      s.violations.push({ type: 'order', msg: `Ran "${st.title}" before "${need?.title || 'its prerequisite'}" — the fault re-tripped.` })
      s.flashUntil = performance.now() + 800
      for (const k of s.inPlay) { const cap = CAP[k] ?? HEALTHY[k]; s.frame[k] += (cap - s.frame[k]) * 0.35 }
      s.contained = Math.max(0, s.contained - 0.06); s.pingCount++; s.narrate = `✗ OUT OF ORDER — re-trip! Do "${need?.title}" first.`; s.log.unshift('✗ Re-trip — out of order'); force(); return
    }
    const opt = st.choose ? st.choose.options[level ?? 1] : null; const mult = opt?.mult ?? 1; const targets = {}
    if (st.effect) { for (const k in st.effect) targets[k] = { from: s.frame[k], to: clampSig(k, s.frame[k] + st.effect[k] * mult) } }
    else { const frac = Math.min(0.85, st.w || 0.35); for (const k of s.inPlay) targets[k] = { from: s.frame[k], to: clampSig(k, s.frame[k] + (HEALTHY[k] - s.frame[k]) * frac) } }
    s.anim = { targets, t0: performance.now(), dur: (st.seconds || 5) * 1000, stepId: st.id, level: opt?.label }
    s.pingCount++; s.narrate = `▸ Executing ${st.title}…`; force()
  }
  const verify = (st) => {
    const s = sim.current
    if (st.verifyWhen === 'stable' && severityOf(s.frame) > 0.35) { s.narrate = '✗ Site is NOT stable yet — verification failed. Keep working the response.'; force(); return }
    s.results.push({ id: st.id, status: 'done', at: Math.round(CLOCK - s.clock) }); s.contained = Math.min(1, s.contained + st.w)
    s.narrate = '✓ Verified — site stabilised.'; s.log.unshift('✓ Verified — stable'); if (!respondStep()) toRepair(s); force()
  }
  const skip = (st) => {
    const s = sim.current
    if (st.safety) s.violations.push({ type: 'safety', msg: `Skipped a SAFETY gate: ${st.title}.` })
    else if (st.kind === 'verify') s.violations.push({ type: 'verify', msg: 'Closed the response without verifying.' })
    s.results.push({ id: st.id, status: 'skipped', at: Math.round(CLOCK - s.clock) }); s.narrate = `– Skipped ${st.title}.`; s.log.unshift(`– Skipped ${st.title}`)
    setConfirmed(false); setLevel(null); if (!respondStep()) toRepair(s); force()
  }
  const performRepair = (st) => {
    const s = sim.current
    if (st.requires && !st.requires.every((r) => s.repairResults.find((x) => x.id === r))) {
      const need = repair.find((x) => x.id === st.requires.find((r) => !s.repairResults.find((y) => y.id === r)))
      s.violations.push({ type: 'order', msg: `Did "${st.title}" before "${need?.title}".` }); s.narrate = `✗ Out of order — do "${need?.title}" first.`; force(); return
    }
    const unsafe = st.physical && !s.loto
    if (unsafe) { s.violations.push({ type: 'safety', msg: `Worked "${st.title}" on a LIVE asset — LOTO not applied.` }); s.flashUntil = performance.now() + 700; s.log.unshift('✗ Worked live — unsafe') }
    const frac = Math.min(0.9, (st.heal || 0.1) * 1.7); const targets = {}
    for (const k of s.inPlay) targets[k] = { from: s.frame[k], to: clampSig(k, s.frame[k] + (HEALTHY[k] - s.frame[k]) * frac) }
    s.anim = { targets, t0: performance.now(), dur: (st.seconds || 3.5) * 1000, stepId: st.id, repair: true, unsafe }
    s.pingCount++; s.narrate = `▸ ${st.title}…`; force()
  }
  const skipRepair = (st) => {
    const s = sim.current
    if (st.safety) s.violations.push({ type: 'safety', msg: 'Skipped LOTO — worked the asset unsafely.' })
    else if (st.verify) s.violations.push({ type: 'verify', msg: 'Closed the work order without verifying the repair.' })
    s.repairResults.push({ id: st.id, status: 'skipped', at: Math.round(CLOCK - s.clock) }); s.narrate = `– Skipped ${st.title}.`; s.log.unshift(`– Skipped ${st.title}`)
    setConfirmed(false); if (!repairStep()) endAll('complete'); force()
  }

  // ═══════════ BRIEFING ═══════════
  if (stage === 'brief') return (
    <div className="tc-overlay">
      <div className="tc-brief">
        <div className="tc-brief-tag">🎮 FIX IT LIVE · THE REPAIR CHALLENGE</div>
        <h1>{facts?.asset || assetId} — {facts?.fault || faultId}</h1>
        <p className="tc-obj">{proc.objective}</p>
        <div className="tc-brief-grid">
          <div><b>{inr(facts?.total_exposure_inr || 0)}</b><span>at risk if you do nothing</span></div>
          <div><b>{CLOCK}s</b><span>to contain the fault</span></div>
          <div><b>{proc.steps.length}+{repair.length}</b><span>respond + repair steps</span></div>
          <div><b>{conditions.length ? conditions.join(', ') : 'baseline'}</b><span>conditions</span></div>
        </div>
        <div className="tc-brief-how">
          <b>You play inside the 3-D twin.</b> The faulted asset glows — <b>click it</b> to act on it, and watch it respond right there.
          First <b>RESPOND</b> in real time to contain the fault before the clock runs out; then <b>REPAIR</b> the hardware (make safe → replace → test → sign off).
          Do it <b>in order</b>, don't skip safety. One grade: containment, ₹ saved, speed, repair quality, order &amp; safety.
        </div>
        <div className="tc-brief-actions">
          <button className="tc-btn tc-primary" onClick={start}>▶ Start the drill</button>
          <button className="tc-btn" onClick={onExit}>Back to simulation</button>
        </div>
      </div>
    </div>
  )

  // ═══════════ WIN / LOSE SPLASH ═══════════
  if (stage === 'won' || stage === 'lost') {
    const F = sim.current.final
    return (
      <div className="tc-overlay">
        <div className={`tc-splash ${stage}`}>
          <div className="tc-splash-ic">{stage === 'won' ? '✅' : '🔴'}</div>
          <h1>{stage === 'won' ? 'SITE SECURED' : 'SITE LOST'}</h1>
          <div className="tc-splash-sub">{stage === 'won' ? 'You contained the fault and closed the repair.' : F.why === 'timeout' ? 'The clock ran out before you stabilised the site.' : !F.safetyClean ? 'A safety gate was breached — automatic fail.' : 'The response fell short.'}</div>
          <div className={`tc-grade tc-${F.g.tone}`} style={{ margin: '18px auto' }}>{F.g.letter}</div>
          <div className="tc-splash-score">{F.score}/100 · saved <b style={{ color: '#34e2b0' }}>{inr(F.saved)}</b></div>
          <button className="tc-btn tc-primary" style={{ marginTop: 20 }} onClick={() => setStage('debrief')}>See full debrief →</button>
        </div>
      </div>
    )
  }

  // ═══════════ DEBRIEF ═══════════
  if (stage === 'debrief') {
    const s = sim.current; const F = s.final
    return (
      <div className="tc-overlay">
        <div className="tc-debrief">
          <div className="tc-brief-tag">DEBRIEF · {F.why === 'timeout' ? 'TIME EXPIRED' : F.why === 'abort' ? 'ENDED EARLY' : 'JOB CLOSED'}</div>
          <div className="tc-grade-row">
            <div className={`tc-grade tc-${F.g.tone}`}>{F.g.letter}</div>
            <div><div className="tc-grade-label">{F.g.label}</div><div className="tc-grade-score">{F.score}<span>/100</span></div></div>
            <div className="tc-grade-money">
              <div><b style={{ color: '#34e2b0' }}>{inr(F.saved)}</b><span>saved vs doing nothing</span></div>
              <div><b style={{ color: '#fb7185' }}>{inr(F.incurred)}</b><span>exposure incurred</span></div>
            </div>
          </div>
          <div className="tc-score-bars">
            {[['Response containment', F.respondContain], ['₹ saved', F.savedFrac], ['Speed', F.speed], ['Repair quality', F.repairPct], ['Order', F.orderClean ? 1 : 0], ['Safety', F.safetyClean && F.verifyClean ? 1 : 0]].map(([l, v]) => (
              <div key={l} className="tc-score-bar"><span>{l}</span><div className="tc-sb-track"><div style={{ width: `${Math.round(v * 100)}%`, background: stabColor(v * 100) }} /></div><b>{Math.round(v * 100)}%</b></div>
            ))}
          </div>
          {!F.reachedRepair && <div className="tc-viols" style={{ borderColor: 'rgba(251,191,36,.3)' }}>⏱ Time ran out during the response — you never reached the repair phase.</div>}
          {s.violations.length > 0 && (
            <div className="tc-viols"><b>⚠ {s.violations.length} violation(s):</b><ul>{s.violations.map((v, i) => <li key={i} className={v.type === 'safety' ? 'crit' : ''}>{v.msg}</li>)}</ul></div>
          )}
          <div className="tc-debrief-steps">
            <div className="tc-ds-head">RESPOND</div>{proc.steps.map((st) => stepRow(st, s.results))}
            <div className="tc-ds-head">REPAIR</div>{repair.map((st) => stepRow(st, s.repairResults))}
          </div>
          <div className="tc-brief-actions">
            <button className="tc-btn tc-primary" onClick={start}>↻ Run it again</button>
            <button className="tc-btn" onClick={onExit}>Back to simulation · grade saved to Records ★</button>
          </div>
        </div>
      </div>
    )
  }

  // ═══════════ PLAYING ═══════════
  const s = sim.current
  const sev = severityOf(s.frame)
  const stability = Math.round((1 - sev) * 100)
  const flash = performance.now() < s.flashUntil
  const clockLow = s.clock < 20
  const isRepair = stage === 'repair'
  const step = isRepair ? repairStep() : respondStep()
  const opt = step?.choose ? step.choose.options[level ?? 1] : null
  const allChecked = !step?.howto?.length || checked.length >= step.howto.length
  const target = step ? (isRepair ? faultAsset : (step.focus || SIG_ASSET[step.targets?.[0]] || faultAsset)) : faultAsset
  const targetName = ASSET_NAME[target] || target
  const prereqOk = !step?.requires || (isRepair ? step.requires.every((r) => s.repairResults.find((x) => x.id === r)) : step.requires.every((r) => s.results.find((x) => x.id === r && x.status === 'done')))

  const sceneStep = step ? {
    asset: target,
    tone: isRepair ? (step.id === 'loto' ? 'locked' : step.kind === 'verify' ? 'done' : 'work')
      : (step.kind === 'diagnose' ? 'focus' : step.kind === 'verify' ? 'done' : step.safety ? 'safe' : 'work'),
    label: `${step.icon} ${step.title} — tap to act`, key: `${stage}:${step.id}:${s.pingCount}`,
  } : null

  const handlePick = (assetId2) => {
    const s2 = sim.current; if (!s2 || s2.anim || !step) return true
    if (assetId2 === target) openRing()
    else { s2.narrate = `👆 That's ${ASSET_NAME[assetId2] || assetId2}. The step is on ${targetName} — click the glowing asset.`; force() }
    return true
  }
  const openRing = () => { const r = stageRef.current?.getBoundingClientRect(); setRing({ x: (r?.width || 640) * 0.5, y: (r?.height || 520) * 0.46 }) }

  const howtoJsx = step?.howto?.length > 0 ? (
    <div className="tc-howto">
      <div className="tc-howto-t"><span>🛠 How to do it</span>{allChecked ? <span className="tc-howto-ok">✓ walked</span> : <span className="tc-howto-c">{checked.length}/{step.howto.length}</span>}</div>
      {step.howto.map((h, i) => (
        <button key={i} className={`tc-howto-i ${checked.includes(i) ? 'on' : ''}`} onClick={() => setChecked((c) => c.includes(i) ? c.filter((x) => x !== i) : [...c, i])}>
          <span className="tc-howto-n">{checked.includes(i) ? '✓' : i + 1}</span><span className="tc-howto-x">{h}</span></button>))}
    </div>
  ) : null

  const actionControls = () => {
    if (!step) return null
    if (!isRepair && step.kind === 'diagnose') return (<>
      {howtoJsx}
      <div className="tc-ring-q">{step.diagnose.prompt}</div>
      {step.diagnose.options.map((o) => (
        <button key={o.signal} className="tc-diag-opt" onClick={() => { diagnose(step, o); setRing(null) }}>
          <span>{o.label}</span><b>{sigVal(s.frame, o.signal)}{(SIG[o.signal] || ['', ''])[1]}</b></button>))}
    </>)
    if (!isRepair && step.kind === 'action') return (<>
      {howtoJsx}
      {step.choose && (<>
        <div className="tc-ring-q">{step.choose.prompt}</div>
        {step.choose.options.map((o, i) => (
          <button key={i} className={`tc-choose-opt ${(level ?? 1) === i ? 'on' : ''}`} onClick={() => setLevel(i)}>
            <span className="tc-co-l">{o.label}</span><span className="tc-co-n">{o.note}</span></button>))}
      </>)}
      {step.safety && <label className="tc-confirm"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> {step.confirm}</label>}
      {!allChecked && <div className="tc-gate">🛠 Tick off the how-to steps to unlock</div>}
      <div className="tc-step-btns">
        <button className="tc-btn tc-primary" disabled={(step.safety && !confirmed) || !allChecked} onClick={() => { execute(step); setRing(null) }}>▶ Do it{opt ? ` · ${opt.label.split(' —')[0]}` : ''}</button>
        <button className="tc-btn" onClick={() => { skip(step); setRing(null) }}>Skip</button>
      </div>
    </>)
    if (!isRepair && step.kind === 'verify') return (<>
      {howtoJsx}
      <div className={`tc-verify-state ${sev <= 0.35 ? 'ok' : 'no'}`}>{sev <= 0.35 ? '✓ Stable — safe to sign off' : '⚠ Not stable yet — verifying will fail'}</div>
      <div className="tc-step-btns">
        <button className="tc-btn tc-primary" onClick={() => { verify(step); setRing(null) }}>✅ Verify</button>
        <button className="tc-btn" onClick={() => { skip(step); setRing(null) }}>Skip</button>
      </div>
    </>)
    return (<>
      {howtoJsx}
      {step.safety && <label className="tc-confirm"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> Confirmed: locked, tagged &amp; zero-energy verified</label>}
      {step.physical && !s.loto && <div className="tc-verify-state no">⚠ Asset still LIVE — apply LOTO first or this logs as unsafe</div>}
      {!allChecked && <div className="tc-gate">🛠 Tick off the how-to steps to unlock</div>}
      <div className="tc-step-btns">
        <button className="tc-btn tc-primary" disabled={(step.safety && !confirmed) || !allChecked} onClick={() => { performRepair(step); setRing(null) }}>{step.kind === 'verify' ? '✅ Verify & close' : '🔧 Perform'}</button>
        <button className="tc-btn" onClick={() => { skipRepair(step); setRing(null) }}>Skip</button>
      </div>
    </>)
  }

  return (
    <div className="tc-overlay tc-play">
      <div className="tc-head">
        <div className="tc-head-l"><span className="tc-live-dot" /> {isRepair ? 'FIELD REPAIR' : 'LIVE RESPONSE'} · {facts?.asset || assetId} — {facts?.fault || faultId}</div>
        <div className="tc-phases">
          <span className={`tc-ph ${!isRepair ? 'on' : 'done'}`}>1 · RESPOND</span><span className="tc-ph-arr">→</span><span className={`tc-ph ${isRepair ? 'on' : ''}`}>2 · REPAIR</span>
        </div>
        {isRepair ? <div className="tc-clock repair">🔧 stabilised</div>
          : <div className={`tc-clock ${clockLow ? 'low' : ''}`}>⏱ {String(Math.floor(Math.max(0, s.clock) / 60))}:{String(Math.floor(Math.max(0, s.clock) % 60)).padStart(2, '0')}</div>}
        <button className="tc-btn tc-abort" onClick={() => endAll('abort')}>■ End drill</button>
      </div>

      <div className="tc-strip">
        {isRepair ? <>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: stabColor(s.health) }}>{Math.round(s.health)}%</div><div className="tc-stat-l">asset health</div><div className="tc-mini"><div style={{ width: `${s.health}%`, background: stabColor(s.health) }} /></div></div>
          <div className="tc-stat"><div className="tc-stat-v">{s.repairResults.length}/{repair.length}</div><div className="tc-stat-l">repair steps</div></div>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: '#34e2b0' }}>✓</div><div className="tc-stat-l">site stabilised</div></div>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: '#34e2b0' }}>{inr(s.saved)}</div><div className="tc-stat-l">saved so far</div></div>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: s.violations.length ? '#fb7185' : '#6b7a99' }}>{s.violations.length}</div><div className="tc-stat-l">violations</div></div>
        </> : <>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: stabColor(stability) }}>{stability}%</div><div className="tc-stat-l">stability</div><div className="tc-mini"><div style={{ width: `${stability}%`, background: stabColor(stability) }} /></div></div>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: '#fb7185' }}>{inr(s.incurred)}</div><div className="tc-stat-l">exposure incurred</div></div>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: '#34e2b0' }}>{inr(s.saved)}</div><div className="tc-stat-l">saved so far</div></div>
          <div className="tc-stat"><div className="tc-stat-v">{Math.round(s.contained * 100)}%</div><div className="tc-stat-l">contained</div></div>
          <div className="tc-stat"><div className="tc-stat-v" style={{ color: s.violations.length ? '#fb7185' : '#6b7a99' }}>{s.violations.length}</div><div className="tc-stat-l">violations</div></div>
        </>}
      </div>

      <div className="tc-body">
        <div className="tc-stage" ref={stageRef}>
          <div className="tc-goal"><span>🎯 {isRepair ? `Repair ${facts?.asset || assetId} to full health` : 'Contain the fault & stabilise the site'}</span><b style={{ color: stabColor(isRepair ? s.health : stability) }}>{isRepair ? Math.round(s.health) : stability}%</b></div>
          <EVWorld live={{ ...s.frame, __step: sceneStep }} onPick={handlePick} focusId={null} height={520} />
          <div className="tc-vignette" style={{ opacity: isRepair ? Math.min(0.4, sev) : sev }} />
          {flash && <div className="tc-retrip">{isRepair ? '⚠ UNSAFE' : '⚡ RE-TRIP'}</div>}
          <div className="tc-narrate">{s.narrate}</div>
          {s.anim && <div className="tc-exec"><span className="spin" /> {isRepair ? 'working…' : 'executing…'}</div>}
          {ring && step && (
            <div className="tc-ring" style={{ left: ring.x, top: ring.y }}>
              <div className="tc-ring-h"><span className="tc-ring-ic">{step.icon}</span><span className="tc-ring-t">{step.title}</span><button className="tc-ring-x" onClick={() => setRing(null)}>✕</button></div>
              {!prereqOk && <div className="tc-req block" style={{ margin: '0 0 8px' }}>⚠ do the earlier step first</div>}
              {actionControls()}
            </div>
          )}
        </div>

        <aside className="tc-panel">
          {step ? (
            <div className={`tc-step ${step.safety ? 'safety' : ''}`}>
              <div className="tc-step-h">
                <span className="tc-step-ic">{step.icon}</span>
                <div><div className="tc-step-t">{step.title}</div><div className="tc-step-b">{step.brief}</div></div>
                <span className="tc-step-kind">{step.kind}{step.safety ? ' · safety' : ''}</span>
              </div>
              <div className="tc-step-detail">{step.detail}</div>
              <div className="tc-step-mech"><b>How it works — </b>{step.mechanism}</div>
              {(step.targets || []).length > 0 && (
                <div className="tc-reads">{step.targets.map((k) => { const [lab, u] = SIG[k] || [k, '']; return (
                  <div key={k} className="tc-read"><span>{lab}</span><b>{sigVal(s.frame, k)}{u}</b></div>) })}</div>
              )}
              <div className="tc-actprompt">
                <div className="tc-actprompt-t">{!prereqOk ? <>⚠ First do the highlighted prerequisite</> : <>👆 Click <b>{targetName}</b> in the twin{step.howto?.length ? <> — you'll walk its <b>{step.howto.length}-step</b> procedure, then it fires</> : ' to act'}</>}</div>
                <button className="tc-actbtn" disabled={!!s.anim} onClick={openRing}>Act on {targetName} →</button>
              </div>
            </div>
          ) : <div className="tc-step"><div className="tc-step-t">{isRepair ? 'Closing job…' : 'Stabilising…'}</div></div>}

          {s.log.length > 0 && (
            <div className="tc-log"><div className="tc-log-t">What just happened</div>{s.log.slice(0, 5).map((l, i) => <div key={i} className={`tc-log-l ${l[0] === '✗' ? 'bad' : l[0] === '–' ? 'muted' : ''}`}>{l}</div>)}</div>
          )}

          <div className="tc-proc">
            <div className="tc-proc-t">{isRepair ? 'Repair procedure' : 'Response procedure'}</div>
            {(isRepair ? repair : proc.steps).map((st, i) => { const r = (isRepair ? s.repairResults : s.results).find((x) => x.id === st.id); const active = st === step; return (
              <div key={st.id} className={`tc-proc-row ${r?.status || ''} ${active ? 'active' : ''}`}>
                <span className="tc-proc-n">{r?.status === 'done' ? '✓' : r?.status === 'skipped' ? '–' : i + 1}</span>
                <span className="tc-proc-l">{st.title}</span>{st.safety && <span className="tc-proc-safe">SAFETY</span>}
              </div>) })}
          </div>
        </aside>
      </div>
    </div>
  )
}

function stepRow(st, results) {
  const r = results.find((x) => x.id === st.id)
  return (
    <div key={st.id} className={`tc-ds ${r?.status || 'missed'}`}>
      <span>{r?.status === 'done' ? '✓' : r?.status === 'skipped' ? '–' : '✗'}</span>
      <span className="tc-ds-t">{st.title}{r?.level ? ` · ${r.level}` : ''}</span>
      <span className="tc-ds-at">{r ? `+${r.at}s` : 'not done'}</span>
    </div>
  )
}
