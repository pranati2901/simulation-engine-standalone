import React, { useEffect, useRef, useState } from 'react'
import EVWorld from '../components/EVWorld.jsx'
import GuidedDrill from '../components/GuidedDrill.jsx'
import { api } from '../api.js'
import { MODEL, assetById, faultsFor, resolveText, engineScenarioFor, loadNetwork } from '../ev/networkModel.js'
import { HEALTHY, HORIZONS, CONDITIONS, buildScenario, buildMonteCarlo, inr, strategiesFor } from '../ev/scenarios.js'
import { SITES, siteToNetwork, siteExposure, siteRisk } from '../ev/sites.js'
import { RECORDS_KEY } from './EVRecords.jsx'

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
  const [netOpen, setNetOpen] = useState(false)
  const [recSaved, setRecSaved] = useState(false)
  const [conds, setConds] = useState([])
  const [openTab, setOpenTab] = useState(null)
  const [optResult, setOptResult] = useState(null)
  const [optBusy, setOptBusy] = useState(false)
  const [multiMode, setMultiMode] = useState(false)
  const [multiSel, setMultiSel] = useState([])
  const [multiInfo, setMultiInfo] = useState(null)
  const [horizon, setHorizon] = useState('now')
  const [siteId, setSiteId] = useState(() => SITES.find(s => MODEL.site.startsWith(s.name))?.id || SITES[0].id)
  const selRef = useRef(null)
  const scenarioRef = useRef(null); scenarioRef.current = scenario

  const groundedAnswer = (scn, q) => {
    setAnswer(null)
    const ctx = `You are the operations copilot for ${scn.facts.site}. Answer ONLY from this simulated result — never invent numbers:\n${JSON.stringify(scn.facts, null, 2)}`
    api.ask(ctx, q).then(rr => setAnswer(rr.answer || fallback(scn.facts))).catch(() => setAnswer(fallback(scn.facts)))
  }

  const buildStrats = (assetId, faultId, hz, conditions = conds) => {
    const list = strategiesFor(assetId, faultId).map(s => {
      const scn = buildScenario(assetId, faultId, { readiness: s.readiness, horizon: hz, conditions })
      return { ...s, scn, exposure: scn.facts.total_exposure_inr }
    })
    const worst = Math.max(1, ...list.map(s => s.exposure))
    const best = list.reduce((a, b) => (b.exposure < a.exposure ? b : a))
    const doNothing = list.find(s => s.key === 'nothing')
    return { list, worst, bestKey: best.key, baseExposure: doNothing.exposure, doNothing }
  }

  const startLive = async (assetId, faultId, q, answerFacts = null) => {
    selRef.current = { assetId, faultId, q }
    const st = buildStrats(assetId, faultId, horizon)
    setStrategies(st)
    setActiveKey('nothing'); setScenario(st.doNothing.scn); setPhase('live'); setIdx(0); setPlaying(true)
    // fault-specific Monte Carlo (120 replays, distribution shaped by the fault)
    const info = buildMonteCarlo(assetId, faultId); setMc(info)
    const facts = answerFacts || { ...st.doNothing.scn.facts, monte_carlo: { runs: info.runs, contained_pct: info.contained_pct } }
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
    setPrompt(q); setPhase('thinking'); setReasonStep(0); setAnswer(null); setScenario(null); setStrategies(null); setMc(null); setOptResult(null); setMultiInfo(null); setOpenTab(null)
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
    setPrompt(q); setPhase('thinking'); setReasonStep(0); setAnswer(null); setScenario(null); setStrategies(null); setMc(null); setOptResult(null); setMultiInfo(null); setOpenTab(null)
    let s = 0
    const iv = setInterval(() => { s++; setReasonStep(s); if (s >= REASONING.length) { clearInterval(iv); startLive(assetId, faultId, q) } }, 430)
  }

  const saveRecord = () => {
    if (!f) return
    const rec = { id: Date.now(), ts: Date.now(), site: MODEL.site, asset: f.asset, fault: f.fault, exposure: f.total_exposure_inr, preventable: f.preventable_pct, best: strategies?.list.find(s => s.key === strategies.bestKey)?.name || '—' }
    try { const cur = JSON.parse(localStorage.getItem(RECORDS_KEY) || '[]'); cur.unshift(rec); localStorage.setItem(RECORDS_KEY, JSON.stringify(cur.slice(0, 50))) } catch { /* ignore */ }
    setRecSaved(true); setTimeout(() => setRecSaved(false), 1600)
  }

  const onSite = (id) => {
    const s = SITES.find(x => x.id === id); if (!s) return
    loadNetwork(siteToNetwork(s)); setSiteId(id)
    if (selRef.current) runFault(selRef.current.assetId, selRef.current.faultId)   // re-run on the new site
  }

  const toggleTab = (t) => setOpenTab(o => (o === t ? null : t))

  const toggleCond = (id) => {
    const n = conds.includes(id) ? conds.filter(x => x !== id) : [...conds, id]
    setConds(n); setOptResult(null)
    const sel = selRef.current; if (!sel) return
    const st = buildStrats(sel.assetId, sel.faultId, horizon, n)
    setStrategies(st); setActiveKey('nothing'); setScenario(st.doNothing.scn); setIdx(0); setPlaying(true)
    groundedAnswer(st.doNothing.scn, `What happens under ${n.length ? n.join(' + ') : 'baseline'} conditions?`)
  }

  const applyOptimum = () => {
    if (!optResult || !selRef.current) return
    const sel = selRef.current
    const scn = buildScenario(sel.assetId, sel.faultId, { readiness: Math.round(optResult.optimal.contain * 100), horizon, conditions: conds })
    setScenario(scn); setActiveKey('optimum'); setIdx(0); setPlaying(true)
    groundedAnswer(scn, 'What happens under the optimised response, and what does it cost?')
  }

  const toggleMulti = (assetId, faultId, label) => {
    const key = `${assetId}:${faultId}`
    setMultiSel(cs => cs.some(x => x.key === key) ? cs.filter(x => x.key !== key) : [...cs, { key, assetId, faultId, label }])
  }

  const runMulti = () => {
    if (multiSel.length < 2) return
    const primary = multiSel[0]
    setPrompt(`${multiSel.length} concurrent faults`); setPhase('thinking'); setReasonStep(0)
    setAnswer(null); setScenario(null); setStrategies(null); setMc(null); setOptResult(null); setMultiInfo(null); setOpenTab(null)
    const miP = api.evMultifault(multiSel.map(m => ({ assetId: m.assetId, faultId: m.faultId })), conds).then(r => { setMultiInfo(r); return r }).catch(() => null)
    let s = 0
    const iv = setInterval(async () => {
      s++; setReasonStep(s)
      if (s >= REASONING.length) {
        clearInterval(iv)
        const mi = await miP
        const cf = mi ? { site: MODEL.site, scenario: `${multiSel.length} concurrent faults`, faults: multiSel.map(m => m.label), combined_exposure_inr: mi.combined_exposure, if_separate_inr: mi.base_exposure, compounding_pct: mi.interaction_pct, breakdown: mi.parts } : null
        startLive(primary.assetId, primary.faultId, `What happens with ${multiSel.length} concurrent faults (${multiSel.map(m => m.label).join(', ')})?`, cf)
      }
    }, 430)
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
    const sel = selRef.current
    if (openTab === 'optimize' && sel && !optResult && !optBusy) {
      setOptBusy(true)
      api.evOptimize(sel.assetId, sel.faultId, conds).then(r => setOptResult(r)).catch(() => {}).finally(() => setOptBusy(false))
    }
  }, [openTab, scenario, optResult, optBusy, conds]) // eslint-disable-line

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
            {faultsFor(a.id).map(fo => {
              const on = multiSel.some(x => x.key === `${a.id}:${fo.id}`)
              return <button key={fo.id} className={`mc-fault-chip ${multiMode && on ? 'on' : ''}`}
                onClick={() => (multiMode ? toggleMulti(a.id, fo.id, `${a.name} · ${fo.label}`) : runFault(a.id, fo.id))}>{fo.label}</button>
            })}
          </div>
        </div>
      ))}
    </div>
  )

  const condChipsJsx = (
    <div className="mc-conds">
      {CONDITIONS.map(c => <button key={c.id} className={`mc-cond ${conds.includes(c.id) ? 'on' : ''}`} onClick={() => toggleCond(c.id)}>{c.label}</button>)}
    </div>
  )

  const RISKCOL = { high: '#fb7185', med: '#fbbf24', low: '#34e2b0' }
  const netRows = SITES.map(s => ({ ...s, exposure: siteExposure(s), risk: siteRisk(s) })).sort((a, b) => b.exposure - a.exposure)
  const netPanelJsx = (
    <div className="mc-net">
      <div className="mc-net-map">
        <svg viewBox="0 0 100 100" style={{ width: '100%', height: 'auto', display: 'block' }}>
          {[20, 40, 60, 80].map(v => <g key={v} stroke="rgba(255,255,255,.08)" strokeWidth="0.2"><line x1={v} y1="4" x2={v} y2="96" /><line x1="4" y1={v} x2="96" y2={v} /></g>)}
          {SITES.map(s => { const risk = siteRisk(s); const r = 2.4 + s.chargers * 0.14; return (
            <g key={s.id} style={{ cursor: 'pointer' }} onClick={() => onSite(s.id)}>
              <circle cx={s.x} cy={s.y} r={r} fill={RISKCOL[risk]} fillOpacity={siteId === s.id ? 0.55 : 0.25} stroke={RISKCOL[risk]} strokeWidth={siteId === s.id ? 1.1 : 0.6} />
              <text x={s.x} y={s.y + r + 2.4} fontSize="2.3" textAnchor="middle" fill="#9fb0d8">{s.name}</text>
            </g>
          ) })}
        </svg>
      </div>
      <div className="mc-net-list">
        {netRows.map(s => (
          <button key={s.id} className={`mc-net-site ${siteId === s.id ? 'on' : ''}`} onClick={() => onSite(s.id)}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: RISKCOL[s.risk], flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize: 12 }}>{s.name}</span>
            <b style={{ fontSize: 12 }}>{inr(s.exposure)}</b>
          </button>
        ))}
      </div>
    </div>
  )

  const strategiesJsx = strategies ? (
    <div className="mc-strat-grid">
      {[...strategies.list].sort((a, b) => a.exposure - b.exposure).map(st => {
        const sv = strategies.baseExposure - st.exposure
        return (
          <button key={st.key} className={`mc-strat ${activeKey === st.key ? 'active' : ''}`} onClick={() => pickStrategy(st)}>
            <div className="mc-strat-h"><b>{st.name}</b>{st.key === strategies.bestKey && <span className="mc-best">BEST</span>}<span className="mc-strat-x">{inr(st.exposure)}</span></div>
            <div className="mc-strat-bar"><div style={{ width: `${100 * st.exposure / strategies.worst}%` }} /></div>
            <div className="mc-strat-m">{st.mech}{sv > 0 && <b style={{ color: '#34e2b0' }}> · saves {inr(sv)}</b>}</div>
          </button>
        )
      })}
    </div>
  ) : null

  const optimizerJsx = optBusy ? (
    <div className="mc-muted"><span className="spin" /> searching response combinations for the optimum…</div>
  ) : optResult ? (
    <div className="mc-opt">
      <div className="mc-opt-note">Searched <b>{optResult.evaluations}</b> lever combinations to minimise <b>total cost</b> (residual damage + cost of responding). The optimum saves <b style={{ color: '#34e2b0' }}>{inr(optResult.savings)}</b> vs doing nothing.</div>
      <div className="mc-opt-levers">
        {optResult.levers.map(l => (
          <div key={l.id} className="mc-opt-lever">
            <div className="mc-opt-ll"><span>{l.label}</span><b>{Math.round(l.value * 100)}%</b></div>
            <div className="mc-opt-bar"><div style={{ width: `${l.value * 100}%` }} /></div>
          </div>
        ))}
      </div>
      <div className="mc-opt-stats">
        <div><b>{inr(optResult.optimal.residual)}</b><span>residual damage</span></div>
        <div><b>{inr(optResult.optimal.action_cost)}</b><span>response cost</span></div>
        <div><b>{inr(optResult.optimal.total)}</b><span>total (optimised)</span></div>
        <div><b style={{ color: '#34e2b0' }}>{inr(optResult.savings)}</b><span>saved vs nothing</span></div>
      </div>
      <button className="mc-save" style={{ marginTop: 12 }} onClick={applyOptimum}>▶ Apply the optimum to the twin</button>
    </div>
  ) : <div className="mc-muted">Computing the optimum…</div>

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
        <div className="mc-assets-t" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span>{multiMode ? 'Pick 2+ faults, then simulate them together' : 'Or pick an asset & fault to simulate'}</span>
          <button className="mc-fault-chip" onClick={() => { setMultiMode(m => !m); setMultiSel([]) }}>{multiMode ? '✓ combining' : '🔀 combine faults'}</button>
        </div>
        {assetPickerJsx}
        {multiMode && (
          <div className="mc-multi-bar">
            {multiSel.map(m => <span key={m.key} className="mc-multi-chip" onClick={() => toggleMulti(m.assetId, m.faultId)}>{m.label} ✕</span>)}
            <button className="mc-new" style={{ marginLeft: 'auto' }} disabled={multiSel.length < 2} onClick={runMulti}>▶ Simulate {multiSel.length || ''} together</button>
          </div>
        )}
        <div className="mc-assets-t" style={{ marginTop: 12 }}>Add operating conditions (worsen the fault)</div>
        {condChipsJsx}
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
        <select className="mc-site" value={siteId} onChange={e => onSite(e.target.value)} title="Switch charging site">
          {SITES.map(s => <option key={s.id} value={s.id}>◉ {s.name}</option>)}
        </select>
        <div className="mc-time">
          <span>⏱ Time Machine</span>
          {Object.entries(HORIZONS).map(([k, v]) => (
            <button key={k} className={horizon === k ? 'on' : ''} onClick={() => onHorizon(k)}>{v.label}</button>
          ))}
        </div>
        {f && answer && <button className="mc-new" onClick={saveRecord}>{recSaved ? '✓ Saved' : '★ Save'}</button>}
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
                ? <>⚠ No action taken — full exposure <b>{inr(activeStrat.exposure)}</b>. Open <b>Strategies</b> below to contain it.</>
                : <>✓ <b>{activeStrat.name}</b> — exposure cut to <b>{inr(activeStrat.exposure)}</b>, saving <b>{inr(saved)}</b> ({Math.round(100 * saved / (strategies.baseExposure || 1))}% less than doing nothing).</>}
            </div>
          )}
          {multiInfo && multiInfo.count > 1 && (
            <div className="mc-compare bad">
              ⚠ <b>{multiInfo.count} concurrent faults</b> — combined exposure <b>{inr(multiInfo.combined_exposure)}</b> (+{multiInfo.interaction_pct}% compounding vs {inr(multiInfo.base_exposure)} if they hit separately).
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
          {condChipsJsx}
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
              <div className="mc-panel-t" style={{ marginTop: 16 }}>Monte Carlo — {mc.runs} runs ⚙</div>
              <div className="mc-mc-head">
                <span><b style={{ color: '#34e2b0' }}>{mc.contained_pct}%</b> contained</span>
                <span><b style={{ color: '#fb7185' }}>{100 - mc.contained_pct}%</b> cascades</span>
              </div>
              <div className="mc-mc-bar">
                <div style={{ width: `${mc.contained_pct}%`, background: '#34e2b0' }} />
                <div style={{ width: `${100 - mc.contained_pct}%`, background: '#fb7185' }} />
              </div>
              {mc.samples?.length > 1 && (() => {
                const bins = new Array(12).fill(0)
                mc.samples.forEach(c => { bins[Math.min(11, Math.floor(c * 12))]++ })
                const max = Math.max(1, ...bins)
                return (
                  <>
                    <div className="mc-mc-hist" title="Distribution of containment across all runs">
                      {bins.map((b, i) => <div key={i} style={{ height: `${Math.max(5, 100 * b / max)}%`, background: i < 4 ? '#fb7185' : i < 8 ? '#fbbf24' : '#34e2b0' }} />)}
                    </div>
                    <div className="mc-mc-axis"><span>◀ cascades</span><span>contained ▶</span></div>
                  </>
                )
              })()}
              <div className="mc-mc-note">The engine replayed this fault <b>{mc.runs} times</b> across varying response readiness — each bar is how many runs landed there. This is the <b>probability</b>, not a single guess.</div>
            </div>
          )}

        </aside>
      </div>

      {scenario && (
        <>
          <div className="mc-tiles">
            <button className={`mc-tile ${openTab === 'optimize' ? 'on' : ''}`} onClick={() => toggleTab('optimize')}>
              <span className="mc-tile-ic">🎯</span>
              <span className="mc-tile-t">Optimizer</span>
              <span className="mc-tile-s">find the best response</span>
            </button>
            <button className={`mc-tile ${openTab === 'strategies' ? 'on' : ''}`} onClick={() => toggleTab('strategies')}>
              <span className="mc-tile-ic">📊</span>
              <span className="mc-tile-t">Strategies</span>
              <span className="mc-tile-s">{strategies?.list.length || 0} preset fixes</span>
            </button>
            <button className={`mc-tile ${openTab === 'repair' ? 'on' : ''}`} onClick={() => toggleTab('repair')}>
              <span className="mc-tile-ic">🔧</span>
              <span className="mc-tile-t">Guided repair</span>
              <span className="mc-tile-s">7-step fix, scored</span>
            </button>
            <button className={`mc-tile ${openTab === 'network' ? 'on' : ''}`} onClick={() => toggleTab('network')}>
              <span className="mc-tile-ic">🗺</span>
              <span className="mc-tile-t">Network</span>
              <span className="mc-tile-s">{SITES.length} sites · switch &amp; compare</span>
            </button>
          </div>
          {openTab === 'optimize' && <div className="mc-tile-body">{optimizerJsx}</div>}
          {openTab === 'strategies' && <div className="mc-tile-body">{strategiesJsx}</div>}
          {openTab === 'repair' && drillScenario && <div className="mc-tile-body"><GuidedDrill key={drillScenario.id} scenario={drillScenario} /></div>}
          {openTab === 'network' && <div className="mc-tile-body">{netPanelJsx}</div>}
        </>
      )}

      {f && (
        <div className="report-print">
          <h1>SimCore — EV Simulation Report</h1>
          <div className="rp-meta">{MODEL.site} · {f.asset} — {f.fault} · {new Date().toLocaleDateString()}</div>
          <table className="rp-tbl"><tbody>
            <tr><td>Total exposure</td><td>{inr(f.total_exposure_inr)}</td></tr>
            <tr><td>Preventable</td><td>{f.preventable_pct}%</td></tr>
            <tr><td>Peak transformer load</td><td>{f.peak_grid_load_pct}%</td></tr>
            <tr><td>Chargers down / sessions dropped</td><td>{f.chargers_down} / {f.sessions_dropped}</td></tr>
            <tr><td>kWh curtailed</td><td>{f.kwh_curtailed}</td></tr>
            {mc && <tr><td>Monte Carlo (contained)</td><td>{mc.contained_pct}% over {mc.runs} runs</td></tr>}
            {f.conditions?.length ? <tr><td>Conditions applied</td><td>{f.conditions.join(', ')}</td></tr> : null}
          </tbody></table>
          <h3>Mitigation strategies</h3>
          <table className="rp-tbl"><thead><tr><th>Strategy</th><th>Exposure</th><th>Saves</th></tr></thead><tbody>
            {strategies?.list.slice().sort((a, b) => a.exposure - b.exposure).map(s => (
              <tr key={s.key}><td>{s.name}</td><td>{inr(s.exposure)}</td><td>{inr(Math.max(0, strategies.baseExposure - s.exposure))}</td></tr>
            ))}
          </tbody></table>
          <h3>Recommended action</h3><p>{f.recommended_action}</p>
          <h3>Copilot summary</h3><p>{answer}</p>
          <div className="rp-foot">Generated by SimCore · the simulation engine is the source of truth.</div>
        </div>
      )}
    </div>
  )
}
