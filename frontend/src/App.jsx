// App.jsx — the STANDALONE shell only.
//
// Everything in here is chrome: sidebar, topbar, domain picker. None of it ships to the
// hub — the hub supplies its own shell and mounts ScenarioRemoteApp, which renders the
// same pages without this frame (integration plan §0.3).
import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useStore } from './store.jsx'
import Icon from './components/Icon.jsx'
import ScenarioRoutes, { NAV, navFor } from './ScenarioRoutes.jsx'
import { Brand } from './brand.jsx'

export default function App() {
  const { domains, domain, setDomain, engineUp } = useStore()
  const loc = useLocation()
  const active = navFor(loc.pathname)

  return (
    <div data-mode={active.id} className="sc-root sc-shell">
      <aside className="sidebar no-print">
        <div className="side-brand"><Brand /></div>
        <nav className="side-nav">
          {NAV.map(n => (
            <NavLink key={n.id} to={n.to} className={({ isActive }) => isActive ? 'on' : ''} style={{ '--nav': n.color }}>
              <Icon name={n.icon} /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">v0.2 · Operational Intelligence</div>
      </aside>

      <div className="main">
        <header className="topbar2 no-print">
          <div>
            <div className="page-title">{active.title}</div>
            <div className="page-sub">{active.sub}</div>
          </div>
          <div className="spacer" />
          <select className="select" value={domain} onChange={e => setDomain(e.target.value)} disabled={!domains.length}>
            {domains.map(d => <option key={d.key} value={d.key}>{d.name}</option>)}
          </select>
          <div className="avatar" title="Signed-in operator">OP</div>
        </header>

        <main className="page">
          {engineUp === false
            ? <div className="card"><div className="empty">Can’t reach the engine. Start it, then reload.</div></div>
            : <ScenarioRoutes />}
        </main>
      </div>
    </div>
  )
}
