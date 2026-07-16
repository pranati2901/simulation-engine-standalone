import React from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useStore } from './store.jsx'
import Icon from './components/Icon.jsx'
import Dashboard from './modes/Dashboard.jsx'
import Library from './modes/Library.jsx'
import DecisionMode from './modes/DecisionMode.jsx'
import TrainingMode from './modes/TrainingMode.jsx'
import TwinMode from './modes/TwinMode.jsx'
import Reports from './modes/Reports.jsx'
import WarRoom from './modes/WarRoom.jsx'
import Composer from './modes/Composer.jsx'
import Assumptions from './modes/Assumptions.jsx'

const NAV = [
  { to: '/dashboard', id: 'dashboard', label: 'Dashboard', icon: 'dashboard', color: '#64748b', title: 'Dashboard', sub: 'Your operation at a glance' },
  { to: '/warroom', id: 'warroom', label: 'War Room', icon: 'warroom', color: '#ef4444', title: 'Portfolio War Room', sub: 'Total $ at risk across every vertical' },
  { to: '/library', id: 'library', label: 'Library', icon: 'library', color: '#8b5cf6', title: 'Scenario Library', sub: 'Browse and open tested scenarios' },
  { to: '/compose', id: 'compose', label: 'Compose', icon: 'compose', color: '#a855f7', title: 'Scenario Composer', sub: 'Collide two faults into one picture' },
  { to: '/decision', id: 'decision', label: 'Decision', icon: 'decision', color: '#3b82f6', title: 'Decision Intelligence', sub: 'Model levers, compare fixes, decide' },
  { to: '/training', id: 'training', label: 'Training', icon: 'training', color: '#22c55e', title: 'Scenario Training', sub: 'Author and score drills' },
  { to: '/twin', id: 'twin', label: 'Twin', icon: 'twin', color: '#f59e0b', title: 'Twin Intelligence', sub: 'Find the weak point before it fails' },
  { to: '/reports', id: 'reports', label: 'Reports', icon: 'reports', color: '#06b6d4', title: 'Reports', sub: 'Board-ready summaries & evidence' },
  { to: '/assumptions', id: 'assumptions', label: 'Assumptions', icon: 'assumptions', color: '#6b7280', title: 'Model Assumptions', sub: 'Cost & impact rates — your inputs' },
]

export default function App() {
  const { domains, domain, setDomain, engineUp } = useStore()
  const loc = useLocation()
  const active = NAV.find(n => loc.pathname.startsWith(n.to)) || NAV[0]

  return (
    <div data-mode={active.id} className="app">
      <aside className="sidebar no-print">
        <div className="side-brand"><span className="dot">◆</span> SimCore</div>
        <nav className="side-nav">
          {NAV.map(n => (
            <NavLink key={n.id} to={n.to} className={({ isActive }) => isActive ? 'on' : ''} style={{ '--nav': n.color }}>
              <Icon name={n.icon} /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">v0.1 · Operational Intelligence</div>
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
            ? <div className="card"><div className="empty">Can’t reach the engine on <span className="mono">:8002</span>. Start it, then reload.</div></div>
            : (
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/warroom" element={<WarRoom />} />
                <Route path="/library" element={<Library />} />
                <Route path="/compose" element={<Composer />} />
                <Route path="/decision" element={<DecisionMode />} />
                <Route path="/training" element={<TrainingMode />} />
                <Route path="/twin" element={<TwinMode />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/assumptions" element={<Assumptions />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            )}
        </main>
      </div>
    </div>
  )
}
