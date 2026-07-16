import React, { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import AuthorBox from '../components/AuthorBox.jsx'
import ScenarioPicker from '../components/ScenarioPicker.jsx'
import ScoreCard from '../components/ScoreCard.jsx'
import CascadeGraph from '../components/CascadeGraph.jsx'
import DrillBriefing from '../components/DrillBriefing.jsx'
import AICoach from '../components/AICoach.jsx'

export default function TrainingMode() {
  const { selected, domain } = useStore()
  const [graph, setGraph] = useState(null)
  const [readiness, setReadiness] = useState(88)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const run = async (r) => {
    if (!selected) return
    setBusy(true); setErr(null)
    try { setGraph(await api.runGraph(selected.id, domain, r)) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  // open on a solved, certified example — the trainee lowers competence to see it fail.
  useEffect(() => { setGraph(null); setReadiness(88); if (selected) run(88) }, [selected?.id, domain]) // eslint-disable-line

  return (
    <>
      <div className="mode-head"><h2>Scenario Training</h2><p>Author a drill, set the trainee’s competence, and see how the decision scores.</p></div>
      <div className="grid">
        <div className="col">
          <AuthorBox />
          <div className="card"><div className="card-title">Drill library</div><ScenarioPicker /></div>
        </div>
        <div className="col">
          {!selected && <div className="card"><div className="empty">Author or pick a drill to begin.</div></div>}
          {selected && (
            <>
              <DrillBriefing scenario={selected} />
              <div className="card">
                <div className="card-title">Trainee competence</div>
                <input className="slider" type="range" min="0" max="100" value={readiness} onChange={e => setReadiness(+e.target.value)} />
                <div className="slider-row"><span>Novice</span><b style={{ color: 'var(--text)' }}>{readiness}</b><span>Expert</span></div>
                <button className="btn btn-primary btn-block" style={{ marginTop: 10 }} onClick={() => run(readiness)} disabled={busy}>
                  {busy ? <><span className="spin" /> Scoring…</> : 'Run drill'}
                </button>
                {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
              </div>
              {graph && <ScoreCard graph={graph} />}
              {graph && <AICoach scenario={selected} graph={graph} />}
              {graph && <div className="card"><div className="card-title">What the decision triggered</div><CascadeGraph graph={graph} mode="training" /></div>}
            </>
          )}
        </div>
      </div>
    </>
  )
}
