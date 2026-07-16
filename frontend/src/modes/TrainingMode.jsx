import React from 'react'
import { useStore } from '../store.jsx'
import AuthorBox from '../components/AuthorBox.jsx'
import ScenarioPicker from '../components/ScenarioPicker.jsx'
import GuidedDrill from '../components/GuidedDrill.jsx'

export default function TrainingMode() {
  const { selected } = useStore()
  return (
    <>
      <div className="mode-head">
        <h2>Train with AI</h2>
        <p>Interactive guided-repair drills, scored on the order you work in — isolate before you touch anything.</p>
      </div>
      <div className="grid">
        <div className="col">
          <AuthorBox />
          <div className="card"><div className="card-title">Drill library</div><ScenarioPicker /></div>
        </div>
        <div className="col">
          {!selected
            ? <div className="card"><div className="empty">Author or pick a drill to begin.</div></div>
            : <GuidedDrill key={selected.id} scenario={selected} />}
        </div>
      </div>
    </>
  )
}
