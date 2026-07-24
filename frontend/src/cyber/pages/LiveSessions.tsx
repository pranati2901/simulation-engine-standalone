import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { LiveSessionSummary } from "../api/types";

export function storePlayer(sessionId: string, playerId: string) {
  localStorage.setItem(`gc_live_${sessionId}`, playerId);
}
export function loadPlayer(sessionId: string): string | null {
  return localStorage.getItem(`gc_live_${sessionId}`);
}
export function myName(): string {
  return localStorage.getItem("gc_live_name") || "";
}

// Visual metadata for the 3 guided cyber-range scenarios (keyed by guided-scenario id).
const SCN_META: Record<string, { icon: string; color: string; gradient: string; setting: string }> = {
  "scn-wannacry-w1": { icon: "fa-virus", color: "#C8413E", gradient: "linear-gradient(135deg,#C8413E,#E07A3E)", setting: "Mercy Regional Health · 250 hosts" },
  "scn-r5-phishing": { icon: "fa-envelope-open-text", color: "#E07A3E", gradient: "linear-gradient(135deg,#E07A3E,#C8413E)", setting: "MediumCorp Financial · 85 hosts" },
  "scn-c5-edr": { icon: "fa-eye-slash", color: "#5B7FB0", gradient: "linear-gradient(135deg,#5B7FB0,#c084fc)", setting: "GlobalTech Corp · 500 hosts" },
};

export default function LiveSessions() {
  const nav = useNavigate();
  const [name, setName] = useState(myName());

  const { data: sessions } = useQuery<LiveSessionSummary[]>({
    queryKey: ["live-sessions"], queryFn: api.liveSessions, refetchInterval: 3000,
  });
  const { data: guided } = useQuery<any[]>({ queryKey: ["guided"], queryFn: api.guidedScenarios });

  // Launch (host): the guided room handles name + role pick + session creation.
  const goLive = (scenarioId: string) => {
    if (name.trim()) localStorage.setItem("gc_live_name", name.trim());
    nav(`/play/${scenarioId}`);
  };

  const join = async (s: LiveSessionSummary) => {
    const who = name.trim() || window.prompt("Your operator name:")?.trim();
    if (!who) return;
    setName(who); localStorage.setItem("gc_live_name", who);

    // Guided sessions land in the guided walkthrough room (multi-user join → pick a free seat).
    if (s.guided && s.scenario_id) {
      const existing = loadPlayer(s.id);
      const pid = existing ?? (await api.joinLiveSession(s.id, { name: who })).player_id;
      if (!existing) storePlayer(s.id, pid);
      localStorage.setItem(`gc_guided_${s.scenario_id}`, JSON.stringify({ session_id: s.id, player_id: pid, role: null }));
      nav(`/play/${s.scenario_id}`);
      return;
    }

    // Free-form live missions use the classic LiveRoom.
    const existing = loadPlayer(s.id);
    if (existing) { nav(`/live/${s.id}`); return; }
    const r = await api.joinLiveSession(s.id, { name: who });
    storePlayer(s.id, r.player_id);
    nav(`/live/${s.id}`);
  };

  return (
    <>
      <div className="section-header">
        <h1>Live Multiplayer</h1>
        <p>Pick a <b>scenario</b> to go live — teammates then join and choose roles (Red / Blue / SOC, or auto-pilot). Each scenario is a guided, real-tools cyber-range walkthrough.</p>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ flex: "1 1 240px" }}>
            <div className="builder-label">Your operator name</div>
            <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Operator-1" />
          </div>
          <div className="muted" style={{ fontSize: 12, flex: "2 1 300px" }}>
            Launch a scenario below; you'll pick your seat in the room. Empty seats are auto-driven, and
            teammates can join your running session from “Open sessions”.
          </div>
        </div>
      </div>

      {/* GUIDED CYBER-RANGE SCENARIOS */}
      <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-shield-virus" /> Cyber-range scenarios</div>
      <div className="scenario-grid" style={{ marginBottom: 24 }}>
        {(guided ?? []).map((s) => {
          const m = SCN_META[s.id] ?? { icon: "fa-diagram-project", color: "#5B7FB0", gradient: "linear-gradient(135deg,#5B7FB0,#c084fc)", setting: `${s.total_hosts} hosts` };
          return (
            <div key={s.id} className="scenario-card" style={{ cursor: "pointer" }} onClick={() => goLive(s.id)}>
              <div style={{ width: 44, height: 44, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", background: m.gradient, marginBottom: 10 }}>
                <i className={`fa ${m.icon}`} style={{ color: "#fff", fontSize: 18 }} />
              </div>
              <div className="scenario-name">{s.name}</div>
              <div style={{ fontSize: 11, color: m.color, fontWeight: 600, marginBottom: 6 }}>{s.subtitle}</div>
              <div className="scenario-desc">{s.summary}</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)", margin: "8px 0 4px" }}><i className="fa fa-server" /> {m.setting}</div>
              <div className="scenario-meta">
                <div className="meta-item"><i className="fa fa-layer-group" /> {s.phase_count} phases</div>
                <div className="meta-item"><i className="fa fa-users" /> Red · Blue · SOC</div>
                <div className="meta-item"><i className="fa fa-terminal" /> real Kali tools</div>
              </div>
              <div style={{ marginTop: 10 }}>
                <button className="btn btn-danger" style={{ fontSize: 12 }} onClick={(e) => { e.stopPropagation(); goLive(s.id); }}>
                  <i className="fa fa-satellite-dish" /> Go Live
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* OPEN SESSIONS */}
      <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-broadcast-tower" /> Open sessions</div>
      {(sessions ?? []).length === 0 && (
        <div className="center-empty" style={{ fontSize: 14 }}>No live sessions right now. Launch one above.</div>
      )}
      <div className="scenario-grid">
        {(sessions ?? []).map((s) => (
          <div key={s.id} className="scenario-card" onClick={() => join(s)}>
            <div className={`scenario-badge ${s.status === "active" ? "badge-red" : "badge-purple"}`}>
              {s.status === "active" ? "● LIVE" : "LOBBY"}
            </div>
            <div className="scenario-name">{s.scenario_name}</div>
            <div className="scenario-desc">{s.guided ? "Guided walkthrough" : "Live mission"} · Session {s.id}</div>
            <div className="scenario-meta">
              <div className="meta-item"><i className="fa fa-users" /> {s.player_count} player(s)</div>
              {Object.entries(s.roles).map(([r, n]) => (
                <div key={r} className="meta-item"><i className="fa fa-user-tag" /> {r} ×{n}</div>
              ))}
            </div>
            <div style={{ marginTop: 10 }}>
              <button className="btn btn-success" style={{ fontSize: 12 }} onClick={(e) => { e.stopPropagation(); join(s); }}>
                <i className="fa fa-right-to-bracket" /> Join
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
