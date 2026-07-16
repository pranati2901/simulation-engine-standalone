import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store.jsx'

export default function Library() {
  const { allScenarios, domains, favorites, toggleFav, openScenario } = useStore()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('all')
  const [favsOnly, setFavsOnly] = useState(false)

  const shown = useMemo(() => allScenarios.filter(s => {
    if (favsOnly && !favorites.has(s.id)) return false
    if (cat !== 'all' && s.domainKey !== cat) return false
    if (q && !(`${s.name} ${s.description}`.toLowerCase().includes(q.toLowerCase()))) return false
    return true
  }), [allScenarios, favsOnly, favorites, cat, q])

  return (
    <>
      <div className="mode-head"><h2>Scenario Library</h2><p><b>{allScenarios.length} tested scenarios</b> across <b>{domains.length} industries</b> — open one to analyse, or author a new one.</p></div>

      <div className="lib-bar">
        <input className="lib-search" placeholder="Search scenarios…" value={q} onChange={e => setQ(e.target.value)} />
        <select className="select" value={cat} onChange={e => setCat(e.target.value)}>
          <option value="all">All categories</option>
          {domains.map(d => <option key={d.key} value={d.key}>{d.name}</option>)}
        </select>
        <button className={`btn ${favsOnly ? 'btn-primary' : ''}`} onClick={() => setFavsOnly(f => !f)}>★ Favourites</button>
      </div>

      <div className="lib-grid">
        <button className="lib-card lib-new" onClick={() => navigate('/training')}>
          <div style={{ fontSize: 24 }}>＋</div>
          <b>New scenario</b>
          <span>Describe it in plain English — AI builds it</span>
        </button>
        {shown.map(s => (
          <div key={s.id} className="lib-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span className="pill pill-muted">{s.domainName?.split(' ')[0]}</span>
              <button className="favbtn" onClick={() => toggleFav(s.id)} title="Favourite" style={{ color: favorites.has(s.id) ? 'var(--amber)' : 'var(--border)' }}>★</button>
            </div>
            <b style={{ fontSize: 13.5, margin: '8px 0 4px' }}>{s.name}</b>
            <span style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.5, flex: 1 }}>{s.description}</span>
            <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} onClick={() => openScenario(s.domainKey, s.id)}>Open</button>
          </div>
        ))}
        {!shown.length && <div className="hint" style={{ padding: 20 }}>No scenarios match.</div>}
      </div>
    </>
  )
}
