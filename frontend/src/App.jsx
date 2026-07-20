import React, { useState } from 'react'
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
import MissionControl from './modes/MissionControl.jsx'
import DataLayer from './modes/DataLayer.jsx'
import EVNetwork from './modes/EVNetwork.jsx'
import Builder from './modes/Builder.jsx'
import Simulation from './modes/Simulation.jsx'
import Assumptions from './modes/Assumptions.jsx'

const NAV = [
  { to: '/simulate', id: 'simulate', label: 'Simulate', icon: 'simulation', color: '#7c3aed', title: 'Mission Control', sub: 'Ask anything — simulate the future' },
  { to: '/data', id: 'data', label: 'Data', icon: 'data', color: '#0891b2', title: 'Company Data Layer', sub: 'Connect your systems — grounded, not guessed' },
  { to: '/dashboard', id: 'dashboard', label: 'Dashboard', icon: 'dashboard', color: '#64748b', title: 'Dashboard', sub: 'Your operation at a glance' },
  { to: '/warroom', id: 'warroom', label: 'War Room', icon: 'warroom', color: '#ef4444', title: 'Portfolio War Room', sub: 'Total $ at risk across every vertical' },
  { to: '/ev-network', id: 'ev-network', label: 'EV Network', icon: 'simulation', color: '#0ea5e9', title: 'EV Charging Network', sub: 'Live network twin — stress-test it' },
  { to: '/library', id: 'library', label: 'Library', icon: 'library', color: '#8b5cf6', title: 'Scenario Library', sub: 'Browse and open tested scenarios' },
  { to: '/builder', id: 'builder', label: 'Builder', icon: 'builder', color: '#a855f7', title: 'Scenario Builder', sub: 'Tune the failure web, node by node' },
  { to: '/simulation', id: 'simulation', label: 'Simulation', icon: 'simulation', color: '#ec4899', title: 'Simulation', sub: 'Run the scenario and read the exposure' },
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
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('simcore_nav_collapsed') === '1')
  const toggleNav = () => setCollapsed(c => { localStorage.setItem('simcore_nav_collapsed', c ? '0' : '1'); return !c })

  return (
    <div data-mode={active.id} className={`app ${collapsed ? 'nav-collapsed' : ''}`}>
      <aside className="sidebar no-print">
        <div className="side-brand"><span className="dot">◆</span> <span className="brand-label">SimCore</span></div>
        <nav className="side-nav">
          {NAV.map(n => (
            <NavLink key={n.id} to={n.to} title={n.label} className={({ isActive }) => isActive ? 'on' : ''} style={{ '--nav': n.color }}>
              <Icon name={n.icon} /> <span className="nav-label">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">v0.1 · Operational Intelligence</div>
      </aside>

      <div className="main">
        <header className="topbar2 no-print">
          <button className="collapse-btn" onClick={toggleNav} title="Toggle sidebar">☰</button>
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

        <main className={`page ${active.id === 'simulate' ? 'page-wide' : ''}`}>
          {engineUp === false
            ? <div className="card"><div className="empty">Can’t reach the engine on <span className="mono">:8002</span>. Start it, then reload.</div></div>
            : (
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/simulate" element={<MissionControl />} />
                <Route path="/data" element={<DataLayer />} />
                <Route path="/warroom" element={<WarRoom />} />
                <Route path="/ev-network" element={<EVNetwork />} />
                <Route path="/library" element={<Library />} />
                <Route path="/builder" element={<Builder />} />
                <Route path="/simulation" element={<Simulation />} />
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
