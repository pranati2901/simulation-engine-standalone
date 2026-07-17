// ScenarioRoutes.jsx — the page set, shared by BOTH entry points.
//
// The standalone App and the federated ScenarioRemoteApp render this same table, so a page
// added here appears in both without touching either shell. Chrome (sidebar/topbar) lives
// ONLY in the standalone App — a remote that renders its own sidebar shows a duplicate next
// to the hub's (integration plan §0.3).
import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './modes/Dashboard.jsx'
import Library from './modes/Library.jsx'
import DecisionMode from './modes/DecisionMode.jsx'
import TrainingMode from './modes/TrainingMode.jsx'
import Reports from './modes/Reports.jsx'
import WarRoom from './modes/WarRoom.jsx'
import Builder from './modes/Builder.jsx'
import Simulation from './modes/Simulation.jsx'

// The nav spine. `hub: true` marks the four pages the Integration Hub surfaces in its own
// sidebar; the rest are standalone-only (the hub has its own Overview and portfolio views,
// and a second dashboard inside a remote would just compete with them).
// NOTE `/overview`, not `/dashboard`. The engine mounts its API routers at the ROOT and
// already owns GET /dashboard, so a client route of that name is shadowed by the API:
// loading or refreshing http://engine/dashboard returned the dashboard JSON instead of the
// app. The API can't move (integration plan §1.2 pins the gateway prefix to ""), so the
// client route does. Only bites standalone — the hub mounts us in a MemoryRouter with no
// URL at all — but a route that works in one mount and not the other is a trap.
export const NAV = [
  { to: '/overview',   id: 'dashboard',  label: 'Dashboard',  icon: 'dashboard',  color: '#6d28d9', title: 'Dashboard',            sub: 'Your operation at a glance' },
  { to: '/warroom',    id: 'warroom',    label: 'War Room',   icon: 'warroom',    color: '#e11d48', title: 'Portfolio War Room',   sub: 'Total $ at risk across every vertical' },
  { to: '/library',    id: 'library',    label: 'Library',    icon: 'library',    color: '#7c3aed', title: 'Scenario Library',     sub: 'Browse and open tested scenarios' },
  { to: '/builder',    id: 'builder',    label: 'Builder',    icon: 'builder',    color: '#a855f7', title: 'Scenario Builder',     sub: 'Tune the failure web, or just describe the change', hub: true },
  { to: '/simulation', id: 'simulation', label: 'Simulation', icon: 'simulation', color: '#ec4899', title: 'Simulation',           sub: 'Run the scenario against the twin and read the exposure', hub: true },
  { to: '/decision',   id: 'decision',   label: 'Decision',   icon: 'decision',   color: '#2563eb', title: 'Decision Intelligence', sub: 'Model levers, compare fixes, decide' },
  { to: '/training',   id: 'training',   label: 'Training',   icon: 'training',   color: '#16a34a', title: 'Scenario Training',    sub: 'Author and score drills', hub: true },
  { to: '/reports',    id: 'reports',    label: 'Reports',    icon: 'reports',    color: '#0d9488', title: 'Reports',              sub: 'Board-ready summaries, evidence & assumptions', hub: true },
]

export const navFor = (pathname) => NAV.find(n => pathname.startsWith(n.to)) || NAV[0]

export default function ScenarioRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="/overview" element={<Dashboard />} />
      <Route path="/warroom" element={<WarRoom />} />
      <Route path="/library" element={<Library />} />
      <Route path="/builder" element={<Builder />} />
      <Route path="/simulation" element={<Simulation />} />
      <Route path="/decision" element={<DecisionMode />} />
      <Route path="/training" element={<TrainingMode />} />
      <Route path="/reports" element={<Reports />} />

      {/* Merged pages. Twin folded into Simulation (you simulate a twin's scenario — same
          run, two lenses) and Assumptions into Reports (same category, one toggle). These
          redirects keep old links and any hub deep-link working instead of 404ing. */}
      <Route path="/twin" element={<Navigate to="/simulation" replace />} />
      <Route path="/assumptions" element={<Navigate to="/reports" replace />} />
      <Route path="/dashboard" element={<Navigate to="/overview" replace />} />

      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  )
}
