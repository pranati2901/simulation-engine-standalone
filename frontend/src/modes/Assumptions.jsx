import React, { useState } from 'react'
import { useStore } from '../store.jsx'
import { getAssumptions, saveAssumptions, resetAssumptions } from '../assumptions.js'

function Row({ label, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 9 }}>
      <span style={{ flex: 1, fontSize: 12.5 }}>{label}</span>
      <span style={{ color: 'var(--muted)' }}>$</span>
      <input className="lib-search" style={{ width: 120, padding: '7px 10px' }} type="number" min="0" value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

export default function Assumptions() {
  const { domains } = useStore()
  const [a, setA] = useState(getAssumptions())
  const [saved, setSaved] = useState(false)
  const upM = (k, v) => setA(x => ({ ...x, money: { ...x.money, [k]: Math.max(0, +v || 0) } }))
  const upC = (k, v) => setA(x => ({ ...x, cost: { ...x.cost, [k]: Math.max(0, +v || 0) } }))
  const save = () => { saveAssumptions(a); setSaved(true); setTimeout(() => setSaved(false), 1600) }
  const reset = () => { resetAssumptions(); setA(getAssumptions()) }
  const COSTS = [['cross', 'Cross-train existing staff'], ['std', 'Hire + standard training'], ['full', 'Full readiness program']]

  return (
    <>
      <div className="mode-head"><h2>Model Assumptions</h2><p>The financial inputs a physics/ops simulation can’t provide — your model, editable. Everything else is computed by the engine.</p></div>
      <div className="grid">
        <div className="col">
          <div className="card">
            <div className="card-title">Impact rate<span className="tag">$ per severity unit</span></div>
            <div className="hint" style={{ marginBottom: 12 }}>What one unit of weighted impact costs, per vertical.</div>
            {domains.map(d => <Row key={d.key} label={d.name} value={a.money[d.key] ?? a.money.default} onChange={v => upM(d.key, v)} />)}
            <Row label="Default (other)" value={a.money.default} onChange={v => upM('default', v)} />
          </div>
        </div>
        <div className="col">
          <div className="card">
            <div className="card-title">Intervention cost<span className="tag">$ per strategy</span></div>
            <div className="hint" style={{ marginBottom: 12 }}>What each readiness investment costs.</div>
            {COSTS.map(([k, label]) => <Row key={k} label={label} value={a.cost[k]} onChange={v => upC(k, v)} />)}
          </div>
          <div className="card">
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={save}>{saved ? '✓ Saved' : 'Save assumptions'}</button>
              <button className="btn" onClick={reset}>Reset to defaults</button>
            </div>
            <div className="hint" style={{ marginTop: 10 }}>Saved in your browser. Every $ figure across the platform recomputes from these — nothing financial is hard-coded.</div>
          </div>
        </div>
      </div>
    </>
  )
}
