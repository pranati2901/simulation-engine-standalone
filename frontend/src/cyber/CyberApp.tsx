/**
 * CyberApp — the GoalCert cyber-security platform, mounted inside the SimCore shell.
 *
 * This is the original GoalCert <App> minus its own chrome: no <Layout> (SimCore's
 * sidebar/topbar wrap it) and no login gate (auth is auto — see hooks/useAuth). Its routes
 * keep their original paths; SimCore only renders this tree while the "Cybersecurity"
 * domain is active, so the two engines never collide. All content lives under `.gc-root`
 * so GoalCert's styles stay scoped and can't repaint the SimCore shell.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes, useLocation, useParams, useSearchParams } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import "./index.css";
import "./charts";

import Dashboard from "./pages/Dashboard";
import Catalog from "./pages/Catalog";
import Library from "./pages/Library";
import Launch from "./pages/Launch";
import ActiveSim from "./pages/ActiveSim";
import Builder from "./pages/Builder";
import Leaderboard from "./pages/Leaderboard";
import Reports from "./pages/Reports";
import LiveSessions from "./pages/LiveSessions";
import LiveRoom from "./pages/LiveRoom";
import Tripwire from "./pages/Tripwire";
import GuidedRoom from "./pages/GuidedRoom";
import ScenarioWorkspace from "./pages/ScenarioWorkspace";
import HackLab from "./pages/HackLab";
import Studio from "./pages/Studio";
import StudioRun from "./pages/StudioRun";
import StudioTrainer from "./pages/StudioTrainer";

const qc = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

// Scenarios that have an immersive sim workspace (must match backend sim/tools.py).
const IMMERSIVE = new Set(["scn-wannacry-w1", "scn-r5-phishing", "scn-c5-edr"]);
function Play() {
  const { scenarioId = "" } = useParams();
  const [sp] = useSearchParams();
  if (sp.get("mode") === "practice" && IMMERSIVE.has(scenarioId)) return <HackLab />;
  return IMMERSIVE.has(scenarioId) ? <ScenarioWorkspace /> : <GuidedRoom />;
}

// The immersive workspace (/play) manages its own full-bleed layout; every other page gets the
// standard content padding (mirrors GoalCert's original Layout, which used `.page` for this).
function CyberRoutes() {
  const loc = useLocation();
  const fullBleed = loc.pathname.startsWith("/play");
  return (
    <div className={fullBleed ? "gc-bleed" : "gc-embed"}>
      <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/library" element={<Library />} />
            <Route path="/live" element={<LiveSessions />} />
            <Route path="/live/:sessionId" element={<LiveRoom />} />
            <Route path="/play/:scenarioId" element={<Play />} />
            <Route path="/launch/:scenarioId" element={<Launch />} />
            <Route path="/sim/:runId" element={<ActiveSim />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="/builder" element={<Builder />} />
            <Route path="/studio" element={<Studio />} />
            <Route path="/studio/train" element={<StudioTrainer />} />
            <Route path="/studio/run/:runId" element={<StudioRun />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/reports/:runId" element={<Reports />} />
            <Route path="/sim-edu/:scenarioId" element={<Tripwire />} />
            <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function CyberApp() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <div className="gc-root">
          <CyberRoutes />
        </div>
      </AuthProvider>
    </QueryClientProvider>
  );
}
