import React, { useEffect, useRef, useState } from 'react'
import EVWorld from '../components/EVWorld.jsx'
import GuidedDrill from '../components/GuidedDrill.jsx'
import { api } from '../api.js'
import { MODEL, assetById, faultsFor, resolveText, engineScenarioFor } from '../ev/networkModel.js'
import { HEALTHY, HORIZONS, buildScenario, inr, strategiesFor } from '../ev/scenarios.js'

const SUGGESTIONS = [
  'What happens if Transformer T1 trips at 5PM?',
  'BESS-A catches fire',
  'A DC fast charger fails',
  'Grid supply is lost',
  'Feeder F-1 overloads at peak',
]
const REASONING = [
  'Reading digital twin…', 'Resolving assets & dependencies…', 'Building simulation graph…',
  'Running Monte Carlo…', 'Testing mitigation strategies…', 'Ranking optimal decisions…', 'Rendering future…',
]
const fallback = (f) => `${f.asset} — ${f.fault}: ~${f.chargers_down} chargers across ${f.stations_affected} station(s) drop, ${f.kwh_curtailed} kWh curtailed. Exposure ${inr(f.total_exposure_inr)} (${f.preventable_pct}% preventable). ${f.recommended_action}`

export default function MissionControl() {
  const [phase, setPhase] = useState('home')
  const [prompt, setPrompt] = useState('')
  const [reasonStep, setReasonStep] = useState(0)
  const [scenario, setScenario] = useState(null)
  const [strategies, setStrategies] = useState(null)
  const [activeKey, setActiveKey] = useState('nothing')
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [answer, setAnswer] = useState(null)
  const [mc, setMc] = useState(null)
  const [repairOpen, setRepairOpen] = useState(false)
  const [horizon, setHorizon] = useState('now')
  const selRef = useRef(null)
  const scenarioRef = useRef(null); scenarioRef.current = scenario

  const groundedAnswer = (scn, q) => {
    setAnswer(null)
    const ctx = `You are the operations copilot for ${scn.facts.site}. Answer ONLY from this simulated result — never invent numbers:\n${JSON.stringify(scn.facts, null, 2)}`
    api.ask(ctx, q).then(rr => setAnswer(rr.answer || fallback(scn.facts))).catch(() => setAnswer(fallback(scn.facts)))
  }

  const buildStrats = (assetId, faultId, hz) => {
    const list = strategiesFor(assetId, faultId).map(s => {
      const scn = buildScenario(assetId, faultId, { readiness: s.readiness, horizon: hz })
      return { ...s, scn, exposure: scn.facts.total_exposure_inr }
    })
    const worst = Math.max(1, ...list.map(s => s.exposure))
    const best = list.reduce((a, b) => (b.exposure < a.exposure ? b : a))
    const doNothing = list.find(s => s.key === 'nothing')
    return { list, worst, bestKey: best.key, baseExposure: doNothing.exposure, doNothing }
  }

  const startLive = async (assetId, faultId, q) => {
    selRef.current = { assetId, faultId, q }
    const st = buildStrats(assetId, faultId, horizon)
    setStrategies(st)
    setActiveKey('nothing'); setScenario(st.doNothing.scn); setPhase('live'); setIdx(0); setPlaying(true); setMc(null)
    // deterministic backend Monte Carlo → real headline confidence
    let facts = st.doNothing.scn.facts
    try {
      const r = await api.monteCarlo(engineScenarioFor(assetId), 'ev')
      const info = { runs: r.iterations, contained_pct: Math.round((r.kpi_stats?.containment_rate?.mean ?? 0) * 100), certified_pct: Math.round((r.certified_rate || 0) * 100) }
      setMc(info); facts = { ...facts, engine_monte_carlo: info }
    } catch { /* fall back to model-only grounding */ }
    groundedAnswer({ facts }, q)
  }

  const onHorizon = (hk) => {
    setHorizon(hk)
    if (!selRef.current) return
    const { assetId, faultId, q } = selRef.current
    const st = buildStrats(assetId, faultId, hk)
    setStrategies(st)
    const act = st.list.find(s => s.key === activeKey) || st.doNothing
    setScenario(act.scn); setIdx(0); setPlaying(true)
    groundedAnswer(act.scn, `At the ${HORIZONS[hk].label} horizon: ${q}`)
  }

  const submit = (text) => {
    const q = (text ?? prompt).trim(); if (!q) return
    setPrompt(q); setPhase('thinking'); setReasonStep(0); setAnswer(null); setScenario(null); setStrategies(null); setMc(null)
    let resolved = resolveText(q) || { assetId: 'TX-1', faultId: 'overload' }
    const planP = api.plan(q, MODEL.assets.map(a => ({ id: a.id, name: a.name, faults: a.faults })))
      .then(p => {
        if (p && p.assetId && assetById(p.assetId)) {
          const fs = faultsFor(p.assetId)
          resolved = { assetId: p.assetId, faultId: fs.some(f => f.id === p.faultId) ? p.faultId : fs[0]?.id }
        }
      }).catch(() => {})
    let s = 0
    const iv = setInterval(() => {
      s++; setReasonStep(s)
      if (s >= REASONING.length) { clearInterval(iv); planP.finally(() => startLive(resolved.assetId, resolved.faultId, q)) }
    }, 430)
  }

  // scoped run — click an asset's fault → guaranteed-accurate simulation (skips the NL planner)
  const runFault = (assetId, faultId) => {
    const a = assetById(assetId)
    const flabel = faultsFor(assetId).find(x => x.id === faultId)?.label || faultId
    const q = `What happens if ${a?.name || assetId} has a ${flabel.toLowerCase()}?`
    setPrompt(q); setPhase('thinking'); setReasonStep(0); setAnswer(null); setScenario(null); setStrategies(null); setMc(null)
    let s = 0
    const iv = setInterval(() => { s++; setReasonStep(s); if (s >= REASONING.length) { clearInterval(iv); startLive(assetId, faultId, q) } }, 430)
  }

  const pickStrategy = (st) => {
    setActiveKey(st.key); setScenario(st.scn); setIdx(0); setPlaying(true)
    groundedAnswer(st.scn, `Under the "${st.name}" strategy, what happens and what is the business impact?`)
  }

  const onAskAI = async (asset) => {
    const facts = scenarioRef.current?.facts
    const ctx = `Asset ${asset?.name} (${asset?.type || ''}) at ${MODEL.site}. Live metrics: ${JSON.stringify(asset?.metrics || [])}.`
      + (facts ? ` Active simulation result: ${JSON.stringify(facts)}` : ' No active simulation running.')
    try { const r = await api.ask(ctx, `Explain ${asset?.name}'s current status and the recommended action.`); return r.answer || 'No status returned.' }
    catch { return 'Copilot unavailable.' }
  }

  useEffect(() => {
    if (!playing || !scenario) return
    let raf, start
    const step = (ts) => { if (!start) start = ts; const p = Math.min(1, (ts - start) / 13000); setIdx(Math.round(p * (scenario.steps.length - 1))); if (p < 1) raf = requestAnimationFrame(step); else setPlaying(false) }
    raf = requestAnimationFrame(step); return () => cancelAnimationFrame(raf)
  }, [playing, scenario])

  const cur = scenario ? scenario.steps[idx] : null
  const live = cur ? cur.live : HEALTHY
  const m = cur ? cur.metrics : { revenueLost: 0, slaPenalty: 0, kwh: 0, sessions: 0 }
  const f = scenario?.facts
  const events = scenario ? scenario.steps.flatMap(s => s.events) : []
  const seek = (t) => { setPlaying(false); setIdx(Math.round((t / scenario.duration) * (scenario.steps.length - 1))) }
  const crisis = cur ? Math.max(0, Math.min(1, Math.max((cur.live['ev:gridLoad'] - 88) / 14, (cur.live['ev:thermalRunawayRisk'] - 40) / 40, cur.metrics.faulted > 0 ? 0.55 : 0))) : 0
  const narr = scenario ? scenario.narration.filter(n => n.t <= (cur?.t ?? 0)) : []
  const stages = scenario ? scenario.sequence.slice(0, scenario.stagesFired).map((s, i) => ({ ...s, n: i + 1 })).filter(s => s.at * scenario.duration <= (cur?.t ?? 0)) : []
  const SCENE_ID = { 'TX-1': 'TX-1', 'BESS-A': 'BESS-A', 'DCFC': 'DCFC-01', 'F-1': 'EMS-1', 'F-2': 'EMS-1', 'GRID': 'TX-1' }
  const focusId = f ? (SCENE_ID[f.assetId] || 'TX-1') : null
  const activeStrat = strategies?.list.find(s => s.key === activeKey)
  const saved = strategies && activeStrat ? strategies.baseExposure - activeStrat.exposure : 0
  const drillScenario = f ? { id: `${f.assetId}:${f.fault}`, name: `${f.fault} — ${f.asset}`, recommended_environment: { actors: [{ name: f.asset }] } } : null

  const assetPickerJsx = (
    <div className="mc-assets">
      {MODEL.assets.map(a => (
        <div key={a.id} className="mc-asset-row">
          <div className="mc-asset-name">{a.name}</div>
          <div className="mc-asset-faults">
            {faultsFor(a.id).map(fo => <button key={fo.id} className="mc-fault-chip" onClick={() => runFault(a.id, fo.id)}>{fo.label}</button>)}
          </div>
        </div>
      ))}
    </div>
  )

  if (phase === 'home') return (
    <div className="mc mc-home">
      <div className="mc-brand">◆ SimCore</div>
      <h1 className="mc-h1">What would you like to simulate today?</h1>
      <div className="mc-prompt">
        <input autoFocus value={prompt} onChange={e => setPrompt(e.target.value)} onKeyDown={e => e.key === 'Enter' && submit()}
          placeholder="What happens if Transformer T1 trips tomorrow at 5PM?" />
        <button onClick={() => submit()}>Simulate →</button>
      </div>
      <div className="mc-sugg">{SUGGESTIONS.map(s => <button key={s} onClick={() => submit(s)}>{s}</button>)}</div>
      <div className="mc-assets-home">
        <div className="mc-assets-t">Or pick an asset &amp; fault — the exact things this twin can simulate</div>
        {assetPickerJsx}
      </div>
      <div className="mc-foot">Simulate Every Decision Before Reality.</div>
    </div>
  )

  if (phase === 'thinking') return (
    <div className="mc mc-home">
      <div className="mc-brand">◆ SimCore</div>
      <div className="mc-think">
        <div className="mc-think-q">“{prompt}”</div>
        {REASONING.map((r, i) => (
          <div key={i} className={`mc-think-row ${i < reasonStep ? 'done' : i === reasonStep ? 'active' : ''}`}><span className="dot" />{r}</div>
        ))}
      </div>
    </div>
  )

  return (
    <div className="mc mc-live">
      <div className="mc-top">
        <div className="mc-brand">◆ SimCore</div>
        <div className="mc-q">“{prompt}”</div>
        <div className="mc-time">
          <span>⏱ Time Machine</span>
          {Object.entries(HORIZONS).map(([k, v]) => (
            <button key={k} className={horizon === k ? 'on' : ''} onClick={() => onHorizon(k)}>{v.label}</button>
          ))}
        </div>
        <button className="mc-new" onClick={() => { setPhase('home'); setPrompt('') }}>＋ New simulation</button>
      </div>

      <div className="mc-body">
        <main className="mc-center">
          <div className="mc-stage">
            <EVWorld live={{ ...live, __stages: stages }} onAskAI={onAskAI} focusId={focusId} height={540} />
            <div className="mc-vignette" style={{ opacity: crisis }} />
            {narr.length > 0 && <div className="mc-narrate">▸ {narr[narr.length - 1].text}</div>}
          </div>
          <div className="mc-metrics">
            <div><div className="v" style={{ color: '#fb7185' }}>{inr(m.revenueLost)}</div><div className="l">revenue lost</div></div>
            <div><div className="v" style={{ color: '#fb7185' }}>{inr(m.slaPenalty)}</div><div className="l">SLA penalty</div></div>
            <div><div className="v">{m.kwh}</div><div className="l">kWh curtailed</div></div>
            <div><div className="v">{m.sessions}</div><div className="l">sessions dropped</div></div>
          </div>
          {strategies && activeStrat && (
            <div className={`mc-compare ${activeKey === 'nothing' ? 'bad' : 'good'}`}>
              {activeKey === 'nothing'
                ? <>⚠ No action taken — full exposure <b>{inr(activeStrat.exposure)}</b>. Pick a strategy on the right to contain it.</>
                : <>✓ <b>{activeStrat.name}</b> — exposure cut to <b>{inr(activeStrat.exposure)}</b>, saving <b>{inr(saved)}</b> ({Math.round(100 * saved / (strategies.baseExposure || 1))}% less than doing nothing).</>}
            </div>
          )}
          <div className="mc-timeline">
            {events.map((e, i) => (
              <button key={i} className={`mc-ev ${e.kind}`} onClick={() => seek(e.t)}>
                <span className="t">+{e.t}m</span><span className="m">{e.msg}</span>
              </button>
            ))}
          </div>
        </main>

        <aside className="mc-right">
          <div className="mc-panel-t">AI Copilot</div>
          {!answer ? <div className="mc-muted"><span className="spin" /> reasoning over the simulation…</div> : <div className="mc-answer">{answer}</div>}
          {f && (
            <div className="mc-facts">
              <div><b>{inr(f.total_exposure_inr)}</b><span>exposure</span></div>
              <div><b>{f.preventable_pct}%</b><span>preventable</span></div>
              {mc ? <div title="Deterministic engine Monte Carlo"><b>{mc.contained_pct}%</b><span>contained · {mc.runs}-run MC ⚙</span></div>
                : <div><b>{f.peak_grid_load_pct}%</b><span>peak load</span></div>}
            </div>
          )}

          {mc && (
            <div className="mc-montecarlo">
              <div className="mc-panel-t" style={{ marginTop: 16 }}>Monte Carlo — {mc.runs} engine runs ⚙</div>
              <div className="mc-mc-head">
                <span><b style={{ color: '#34e2b0' }}>{mc.certified_pct}%</b> contained</span>
                <span><b style={{ color: '#fb7185' }}>{100 - mc.certified_pct}%</b> cascades to blackout</span>
              </div>
              <div className="mc-mc-bar">
                <div style={{ width: `${mc.certified_pct}%`, background: '#34e2b0' }} />
                <div style={{ width: `${100 - mc.certified_pct}%`, background: '#fb7185' }} />
              </div>
              <div className="mc-mc-note">The engine replayed this fault <b>{mc.runs} times</b> across varying response readiness. This is the <b>probability</b> of the outcome — not a single guess.</div>
            </div>
          )}

          {strategies && (
            <>
              <div className="mc-panel-t" style={{ marginTop: 16 }}>Strategies — click to simulate</div>
              {[...strategies.list].sort((a, b) => a.exposure - b.exposure).map(st => {
                const saved = strategies.baseExposure - st.exposure
                return (
                  <button key={st.key} className={`mc-strat ${activeKey === st.key ? 'active' : ''}`} onClick={() => pickStrategy(st)}>
                    <div className="mc-strat-h">
                      <b>{st.name}</b>
                      {st.key === strategies.bestKey && <span className="mc-best">BEST</span>}
                      <span className="mc-strat-x">{inr(st.exposure)}</span>
                    </div>
                    <div className="mc-strat-bar"><div style={{ width: `${100 * st.exposure / strategies.worst}%` }} /></div>
                    <div className="mc-strat-m">{st.mech}{saved > 0 && <b style={{ color: '#34e2b0' }}> · saves {inr(saved)}</b>}</div>
                  </button>
                )
              })}
            </>
          )}
        </aside>
      </div>

      {scenario && (
        <div className="mc-repair">
          <button className="mc-repair-toggle" onClick={() => setRepairOpen(o => !o)}>
            <span>🔧 Guided repair — fix this fault step by step</span>
            <span>{repairOpen ? '▲ hide' : '▼ open'}</span>
          </button>
          {repairOpen && drillScenario && <div className="mc-repair-body"><GuidedDrill key={drillScenario.id} scenario={drillScenario} /></div>}
        </div>
      )}
    </div>
  )
}
