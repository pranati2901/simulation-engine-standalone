import React, { useEffect, useState } from 'react'
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
import Portfolio from './modes/Portfolio.jsx'
import EVRecords from './modes/EVRecords.jsx'
import EVNetwork from './modes/EVNetwork.jsx'
import Builder from './modes/Builder.jsx'
import Simulation from './modes/Simulation.jsx'
import Assumptions from './modes/Assumptions.jsx'

const NAV = [
  { to: '/simulate', id: 'simulate', label: 'Simulate', icon: 'simulation', color: '#7c3aed', title: 'Mission Control', sub: 'Ask anything — simulate the future' },
  { to: '/network', id: 'network', label: 'Network', icon: 'warroom', color: '#ef4444', title: 'Network Operations', sub: 'Every site, one exposure picture' },
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
  { to: '/records', id: 'records', label: 'Records', icon: 'library', color: '#8b5cf6', title: 'Records', sub: 'Saved simulations — review & export' },
]

// Domain landing — EV is fully built; the others reuse the generic tabs until configured.
const DOMAINS = [
  { id: 'ev', name: 'EV Charging', engine: 'ev', desc: 'Charging networks, energy & fleet', icon: 'simulation', color: '#7c3aed', ready: true },
  { id: 'healthcare', name: 'Healthcare', engine: 'hospital', desc: 'Hospitals, OR & capacity', icon: 'twin', color: '#0891b2' },
  { id: 'railway', name: 'Railway', engine: 'railway', desc: 'Rail operations & delays', icon: 'dashboard', color: '#059669' },
  { id: 'defence', name: 'Defence', engine: 'defence', desc: 'Readiness & response', icon: 'warroom', color: '#6d28d9' },
  { id: 'aerospace', name: 'Aerospace', engine: 'aerospace', desc: 'Fleet & AOG', icon: 'reports', color: '#2563eb' },
]
const EV_NAV_IDS = ['simulate', 'data', 'records']
const GENERIC_NAV_IDS = ['dashboard', 'warroom', 'library', 'builder', 'simulation', 'decision', 'training', 'twin', 'reports', 'assumptions']

function DomainChooser({ onPick }) {
  return (
    <div className="dc">
      <div className="dc-brand">◆ SimCore</div>
      <h1 className="dc-h1">Choose your domain</h1>
      <p className="dc-sub">Pick the operation you want to simulate. EV Charging is fully built; the rest reuse the generic toolkit for now.</p>
      <div className="dc-grid">
        {DOMAINS.map(d => (
          <button key={d.id} className="dc-card" onClick={() => onPick(d)} style={{ '--dc': d.color }}>
            <span className="dc-ic"><Icon name={d.icon} size={26} /></span>
            <b>{d.name}</b>
            <span className="dc-desc">{d.desc}</span>
            <span className={`dc-tag ${d.ready ? '' : 'muted'}`}>{d.ready ? '● Ready' : 'Configure later'}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const { setDomain, engineUp } = useStore()
  const loc = useLocation()
  const [appDomain, setAppDomain] = useState(() => localStorage.getItem('simcore_app_domain') || '')
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('simcore_nav_collapsed') === '1')
  const toggleNav = () => setCollapsed(c => { localStorage.setItem('simcore_nav_collapsed', c ? '0' : '1'); return !c })

  const pickDomain = (d) => { localStorage.setItem('simcore_app_domain', d.id); setAppDomain(d.id) }
  const changeDomain = () => { localStorage.removeItem('simcore_app_domain'); setAppDomain('') }

  useEffect(() => { const d = DOMAINS.find(x => x.id === appDomain); if (d) setDomain(d.engine) }, [appDomain, setDomain])

  if (!appDomain) return <DomainChooser onPick={pickDomain} />

  const dom = DOMAINS.find(d => d.id === appDomain) || DOMAINS[0]
  const ids = appDomain === 'ev' ? EV_NAV_IDS : GENERIC_NAV_IDS
  const navItems = ids.map(id => NAV.find(n => n.id === id)).filter(Boolean)
  const home = appDomain === 'ev' ? '/simulate' : '/dashboard'
  const active = navItems.find(n => loc.pathname.startsWith(n.to)) || navItems[0]

  return (
    <div data-mode={active.id} className={`app ${collapsed ? 'nav-collapsed' : ''}`}>
      <aside className="sidebar no-print">
        <div className="side-brand"><span className="dot">◆</span> <span className="brand-label">SimCore</span></div>
        <button className="side-domain" onClick={changeDomain} title="Change domain">
          <span className="nav-label">{dom.name}</span><span className="dom-swap">⇄</span>
        </button>
        <nav className="side-nav">
          {navItems.map(n => (
            <NavLink key={n.id} to={n.to} title={n.label} className={({ isActive }) => isActive ? 'on' : ''} style={{ '--nav': n.color }}>
              <Icon name={n.icon} /> <span className="nav-label">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">v0.1 · {dom.name}</div>
      </aside>

      <div className="main">
        <header className="topbar2 no-print">
          <button className="collapse-btn" onClick={toggleNav} title="Toggle sidebar">☰</button>
          <div>
            <div className="page-title">{active.title}</div>
            <div className="page-sub">{active.sub}</div>
          </div>
          <div className="spacer" />
          <div className="dom-chip" onClick={changeDomain} title="Change domain">{dom.name} ⇄</div>
          <div className="avatar" title="Signed-in operator">OP</div>
        </header>

        <main className={`page ${active.id === 'simulate' ? 'page-wide' : ''}`}>
          {engineUp === false
            ? <div className="card"><div className="empty">Can’t reach the engine on <span className="mono">:8002</span>. Start it, then reload.</div></div>
            : (
              <Routes>
                <Route path="/" element={<Navigate to={home} replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/simulate" element={<MissionControl />} />
                <Route path="/network" element={<Portfolio />} />
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
                <Route path="/records" element={<EVRecords />} />
                <Route path="/assumptions" element={<Assumptions />} />
                <Route path="*" element={<Navigate to={home} replace />} />
              </Routes>
            )}
        </main>
      </div>
    </div>
  )
}
