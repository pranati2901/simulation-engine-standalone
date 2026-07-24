import { useQuery } from "@tanstack/react-query";
import { Radar } from "react-chartjs-2";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { Dashboard as DashboardData } from "../api/types";

const TYPE_COLOR: Record<string, string> = {
  red: "var(--gc-red)", soc: "var(--gc-green)", ics: "var(--gc-orange)",
  cloud: "var(--gc-teal)", blue: "var(--gc-primary)", purple: "var(--gc-purple)",
};

/* layered wave motif used on the gradient cards + banner (echoes the brand artwork) */
function Wave({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 400 90" preserveAspectRatio="none" fill="none" aria-hidden>
      <path d="M0 60 Q100 30 200 55 T400 50 V90 H0 Z" fill="#fff" opacity="0.06" />
      <path d="M0 72 Q120 48 220 66 T400 62 V90 H0 Z" fill="#fff" opacity="0.08" />
    </svg>
  );
}

export default function Dashboard() {
  const nav = useNavigate();
  const { user } = useAuth();
  const { data, isLoading } = useQuery<DashboardData>({ queryKey: ["dashboard"], queryFn: api.dashboard });

  if (isLoading || !data) return <div className="center-empty"><span className="spinner" /> Loading dashboard…</div>;

  const radarLabels = Object.keys(data.readiness);
  const cards = [
    { icon: "fa-bolt", big: data.total_runs, ttl: "Simulations", sub: "runs executed", cta: "History", to: "/reports" },
    { icon: "fa-layer-group", big: data.total_scenarios, ttl: "Scenarios", sub: "in the library", cta: "Browse", to: "/library" },
    { icon: "fa-shield-halved", big: data.avg_blue_score, ttl: "Avg Blue Score", sub: "recent defense", cta: "Insights", to: "/leaderboard" },
    { icon: "fa-triangle-exclamation", big: data.critical_findings, ttl: "Critical Findings", sub: "ransomware / OT impact", cta: "Review", to: "/reports" },
  ];

  return (
    <>
      {/* welcome banner */}
      <div className="gc-banner">
        <Wave className="wave" />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16, position: "relative", zIndex: 1 }}>
          <div>
            <h1>Welcome{user ? `, ${user.name.split(" ")[0]}` : ""}</h1>
            <p>Your GoalCert cyber-range is online. Run a guided red-vs-blue scenario, review after-action reports, or build your own.</p>
          </div>
          <button className="btn" style={{ background: "#fff", color: "var(--gc-primary)", fontWeight: 700, padding: "11px 18px" }}
            onClick={() => nav("/live")}><i className="fa fa-play" /> Launch a Scenario</button>
        </div>
      </div>

      {/* gradient stat cards */}
      <div className="stats-row">
        {cards.map((c) => (
          <div key={c.ttl} className="gc-statcard" onClick={() => nav(c.to)} style={{ cursor: "pointer" }}>
            <Wave className="wave" />
            <div className="ic"><i className={`fa ${c.icon}`} /></div>
            <div className="big">{c.big}</div>
            <div className="ttl">{c.ttl}</div>
            <div className="sub">{c.sub}</div>
            <div className="cta">{c.cta}</div>
          </div>
        ))}
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="fa fa-clock-rotate-left" /> Recent Simulations</div>
            <button className="btn" style={{ fontSize: 11, padding: "5px 11px" }} onClick={() => nav("/library")}>New</button>
          </div>
          {data.recent_runs.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No runs yet — launch one from the library.</div>}
          {data.recent_runs.map((r) => (
            <div key={r.id} onClick={() => nav(`/reports/${r.id}`)}
              style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 0", borderBottom: "1px solid var(--gc-border)", cursor: "pointer" }}>
              <div style={{ width: 9, height: 9, borderRadius: "50%", background: TYPE_COLOR[r.type] || "#888", flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{r.name}</div>
                <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{new Date(r.created_at).toLocaleString()}</div>
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600 }}>
                <span style={{ color: "var(--gc-red)" }}>R {r.red}</span> · <span style={{ color: "var(--gc-primary)" }}>B {r.blue}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-bullseye" /> Team Readiness</div></div>
          <Radar
            data={{
              labels: radarLabels,
              datasets: [{
                label: "Recent runs", data: radarLabels.map((k) => data.readiness[k]),
                backgroundColor: "rgba(73,2,162,.14)", borderColor: "#4902A2",
                pointBackgroundColor: "#4902A2", pointRadius: 3,
              }],
            }}
            options={{
              plugins: { legend: { labels: { color: "#7a7390", font: { size: 11 } } } },
              scales: { r: { suggestedMin: 0, suggestedMax: 100, grid: { color: "rgba(73,2,162,.1)" }, angleLines: { color: "rgba(73,2,162,.1)" }, ticks: { display: false }, pointLabels: { color: "#7a7390", font: { size: 11 } } } },
            }}
            height={220}
          />
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 20 }}>
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-chart-column" /> Threat Coverage (MITRE tactics)</div></div>
          {data.threat_coverage.map((c) => (
            <div key={c.label} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 5 }}>
                <span style={{ fontWeight: 500 }}>{c.label}</span><span style={{ color: "var(--gc-primary)", fontFamily: "var(--mono)", fontWeight: 600 }}>{c.pct}%</span>
              </div>
              <div className="progress-bar"><div className="progress-fill" style={{ width: `${c.pct}%`, background: c.pct > 70 ? "var(--gc-green)" : c.pct > 40 ? "var(--gc-yellow)" : "var(--gc-red)" }} /></div>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="fa fa-bolt" /> Quick Launch</div></div>
          <button className="btn" style={{ justifyContent: "flex-start", gap: 10, width: "100%" }} onClick={() => nav("/live")}>
            <i className="fa fa-satellite-dish" style={{ color: "var(--gc-primary)" }} /> Live guided scenarios (W1 · R5 · C5)
          </button>
          <button className="btn" style={{ justifyContent: "flex-start", gap: 10, width: "100%", marginTop: 10 }} onClick={() => nav("/library")}>
            <i className="fa fa-layer-group" style={{ color: "var(--gc-primary)" }} /> Browse all scenarios
          </button>
          <button className="btn" style={{ justifyContent: "flex-start", gap: 10, width: "100%", marginTop: 10 }} onClick={() => nav("/catalog")}>
            <i className="fa fa-cubes" style={{ color: "var(--gc-primary)" }} /> Explore asset & technique catalog
          </button>
        </div>
      </div>
    </>
  );
}
