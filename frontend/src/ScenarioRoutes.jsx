// ScenarioRoutes.jsx — the page set, shared by BOTH entry points.
//
// The standalone App (App.jsx) and the federated ScenarioRemoteApp render this same table,
// so a page added here appears in both without touching either shell. Chrome (sidebar /
// topbar / domain chooser) lives ONLY in the standalone App — a remote that renders its own
// sidebar shows a duplicate right next to the hub's.
import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
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

export default function ScenarioRoutes({ home = '/dashboard' }) {
  return (
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
  )
}
