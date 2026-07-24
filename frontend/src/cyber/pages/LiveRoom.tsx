import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useLiveSocket } from "../hooks/useLiveSocket";
import RedConsole from "../components/RedConsole";
import BlueConsole from "../components/BlueConsole";
import SocConsole from "../components/SocConsole";
import LiveReport from "../components/LiveReport";
import LabPanel from "../components/LabPanel";
import { loadPlayer, storePlayer, myName } from "./LiveSessions";

const ROLE_META: Record<string, { icon: string; color: string; label: string }> = {
  red: { icon: "fa-user-secret", color: "var(--gc-red)", label: "Red Team (Adversary)" },
  blue: { icon: "fa-shield-halved", color: "#5B8CFF", label: "Blue Team (IR)" },
  soc: { icon: "fa-tower-observation", color: "#22d3a8", label: "SOC" },
  mgmt: { icon: "fa-user-tie", color: "#c084fc", label: "Management" },
  ot: { icon: "fa-industry", color: "#f59e0b", label: "OT / Operations" },
  observer: { icon: "fa-eye", color: "var(--gc-muted)", label: "Observer" },
};

export default function LiveRoom() {
  const { sessionId } = useParams();
  const [playerId, setPlayerId] = useState<string | null>(sessionId ? loadPlayer(sessionId) : null);
  const [joinName, setJoinName] = useState(myName());
  const [profile, setProfile] = useState("nation_state");
  const [mission, setMission] = useState("red_team");
  const [chat, setChat] = useState("");
  const [specLens, setSpecLens] = useState<"red" | "blue" | "soc">("red");

  const live = useLiveSocket(sessionId ?? null, playerId);
  const snap = live.state.snapshot;

  const you = useMemo(
    () => snap?.players.find((p) => p.id === playerId) ?? null,
    [snap, playerId],
  );
  const isHost = !!you?.is_host;
  const canPlay = you?.role === "red" || you?.role === "blue" || you?.role === "soc";

  // default the profile selector to whatever the host already set (once started)
  useEffect(() => { if (snap?.operator?.profile) setProfile(snap.operator.profile); }, [snap?.operator?.profile]);
  // non-hosts mirror the host's chosen mission live (in the lobby)
  useEffect(() => { if (snap?.session.mission && !you?.is_host) setMission(snap.session.mission); }, [snap?.session.mission, you?.is_host]);

  const chooseMission = (id: string) => {
    setMission(id);
    live.setMission(id);
    const m = snap?.missions.find((x) => x.id === id);
    if (m) setProfile(m.forced_profile ?? m.recommended_profile);
  };

  if (!sessionId) return null;

  if (!playerId) {
    const doJoin = async () => {
      const who = joinName.trim();
      if (!who) return;
      localStorage.setItem("gc_live_name", who);
      const r = await api.joinLiveSession(sessionId, { name: who });
      storePlayer(sessionId, r.player_id);
      setPlayerId(r.player_id);
    };
    return (
      <div className="card" style={{ maxWidth: 420, margin: "60px auto" }}>
        <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-right-to-bracket" /> Join session {sessionId}</div>
        <div className="builder-label">Your operator name</div>
        <input className="form-input" value={joinName} onChange={(e) => setJoinName(e.target.value)} placeholder="e.g. Operator-2" />
        <button className="btn btn-primary" style={{ marginTop: 12, width: "100%" }} onClick={doJoin} disabled={!joinName.trim()}>Join</button>
      </div>
    );
  }

  if (!snap) return <div className="center-empty"><span className="spinner" /> Connecting to session…</div>;

  const status = snap.session.status;
  const sendChat = () => { if (chat.trim()) { live.chat(chat.trim()); setChat(""); } };

  const PlayersPanel = (
    <div className="card">
      <div className="card-header"><div className="card-title"><i className="fa fa-users" /> Players ({snap.players.length})</div></div>
      {snap.players.map((p) => {
        const m = p.role ? ROLE_META[p.role] : null;
        return (
          <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 8 }}>
            <span className="status-dot" style={{ background: p.connected ? "var(--gc-green)" : "var(--gc-muted)" }} />
            <span style={{ fontWeight: p.id === playerId ? 700 : 400 }}>{p.name}{p.id === playerId ? " (you)" : ""}</span>
            {p.is_host && <span className="tag" style={{ fontSize: 9 }}>HOST</span>}
            {m && <span style={{ marginLeft: "auto", color: m.color, fontSize: 12 }}><i className={`fa ${m.icon}`} /> {p.role}</span>}
          </div>
        );
      })}
    </div>
  );

  const LabSidePanel = (
    <LabPanel isHost={isHost} liveFire={!!snap.session.live_fire} onToggleLiveFire={live.setLiveFire} />
  );

  const ChatPanel = (
    <div className="card">
      <div className="card-header"><div className="card-title"><i className="fa fa-comments" /> Team chat</div></div>
      <div style={{ maxHeight: 160, overflowY: "auto", marginBottom: 8 }}>
        {snap.events.filter((e) => e.kind === "chat").slice(-30).map((e) => (
          <div key={e.seq} style={{ fontSize: 12, marginBottom: 4 }}><b style={{ color: "#9ecbff" }}>{e.title}:</b> {e.message}</div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input className="form-input" value={chat} onChange={(e) => setChat(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendChat()} placeholder="message…" />
        <button className="btn btn-ghost" onClick={sendChat}><i className="fa fa-paper-plane" /></button>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>{snap.scenario.name}</h1>
          <p className="muted" style={{ fontSize: 13 }}>
            <i className="fa fa-bullseye" /> {snap.mission.name} · session {snap.session.id} ·{" "}
            <span style={{ color: status === "active" ? "var(--gc-red)" : status === "completed" ? "var(--gc-green)" : "var(--gc-yellow)" }}>
              {status === "active" ? "● LIVE" : status.toUpperCase()}
            </span> · {live.state.connected ? "connected" : "reconnecting…"}
          </p>
        </div>
        {snap.session.live_fire && (
          <span className="tag" style={{ color: "var(--gc-red)", borderColor: "var(--gc-red)", fontWeight: 700, letterSpacing: 1 }}>
            <i className="fa fa-bolt" /> LIVE-FIRE · REAL TOOLS
          </span>
        )}
      </div>

      {live.state.error && (
        <div className="alert-item" style={{ marginBottom: 14, borderColor: "var(--gc-red)" }} onClick={live.clearError}>
          <div className="alert-icon"><i className="fa fa-triangle-exclamation" style={{ color: "var(--gc-red)" }} /></div>
          <div className="alert-content"><strong>Action rejected</strong><div>{live.state.error}</div></div>
        </div>
      )}

      {status === "lobby" && (
        <div className="grid-2" style={{ alignItems: "start" }}>
          <div style={{ display: "grid", gap: 16 }}>
            {(() => {
              const locked = snap.session.mission_locked;
              const m = locked ? snap.mission : (snap.missions.find((x) => x.id === mission) ?? snap.mission);
              return (
                <div className="card">
                  <div className="card-header"><div className="card-title"><i className="fa fa-bullseye" /> Mission {locked ? "(dedicated)" : isHost ? "" : "(host chooses)"}</div>
                    <span className="tag" style={{ fontSize: 9 }}>{m.klass} · {m.cadence}</span></div>
                  {!locked && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 }}>
                      {snap.missions.map((mi) => (
                        <button key={mi.id} className={"filter-chip" + (mission === mi.id ? " active" : "")} disabled={!isHost}
                          style={{ justifyContent: "flex-start", padding: "8px 10px", fontSize: 11 }}
                          onClick={() => chooseMission(mi.id)} title={mi.tagline}>{mi.name}</button>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize: 12, color: "var(--gc-text)", marginBottom: 6 }}><b>{m.name}.</b> {m.briefing}</div>
                  <div style={{ fontSize: 11, color: "var(--gc-muted)" }}><i className="fa fa-gauge-high" /> Headline: {m.headline_metric}</div>
                  <div style={{ display: "grid", gap: 4, marginTop: 8 }}>
                    {(["red", "soc", "blue"] as const).map((rk) => m.success[rk] && (
                      <div key={rk} style={{ fontSize: 11 }}>
                        <span style={{ color: ROLE_META[rk].color, fontWeight: 600 }}>{rk.toUpperCase()}:</span>{" "}
                        <span style={{ color: "var(--gc-muted)" }}>{m.success[rk]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}
            <div className="card">
              <div className="card-header"><div className="card-title"><i className="fa fa-user-tag" /> Choose your role</div></div>
              <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{snap.scenario.description}</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {snap.roles.map((r) => {
                  const m = ROLE_META[r.id];
                  const mine = you?.role === r.id;
                  const isAuto = snap.auto[r.id];
                  return (
                    <button key={r.id} className={"filter-chip" + (mine ? " active" : "")}
                      style={{ justifyContent: "flex-start", padding: "10px 12px", borderColor: mine ? m.color : undefined, color: mine ? m.color : undefined }}
                      onClick={() => live.claimRole(r.id)}>
                      <i className={`fa ${m.icon}`} style={{ marginRight: 8 }} /> {m.label}
                      {r.interactive
                        ? (isAuto ? <span className="tag" style={{ marginLeft: "auto", fontSize: 9, color: "var(--gc-yellow)" }}>AUTO</span>
                                  : <span className="tag" style={{ marginLeft: "auto", fontSize: 9 }}>PLAYABLE</span>)
                        : <span className="tag" style={{ marginLeft: "auto", fontSize: 9, opacity: 0.6 }}>SOON</span>}
                    </button>
                  );
                })}
              </div>
              <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
                Red, Blue and SOC are all playable — pick a side. <b>Any seat with no operator runs on auto-pilot</b>
                {" "}(deterministic, no AI yet). Mgmt / OT are reserved spectator seats.
              </p>
            </div>

            {isHost && (
              <div className="card">
                <div className="card-header"><div className="card-title"><i className="fa fa-robot" /> Automation (host)</div></div>
                <p className="muted" style={{ fontSize: 11, marginBottom: 10 }}>Force a seat to auto-pilot or to human. Default: auto whenever no human holds the seat.</p>
                {(["red", "soc", "blue"] as const).map((r) => {
                  const auto = snap.auto[r];
                  return (
                    <div key={r} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ width: 60, color: ROLE_META[r].color, fontSize: 13 }}><i className={`fa ${ROLE_META[r].icon}`} /> {r.toUpperCase()}</span>
                      <button className={"filter-chip" + (auto ? " active" : "")} style={{ fontSize: 11 }} onClick={() => live.setAuto(r, true)}><i className="fa fa-robot" /> Auto</button>
                      <button className={"filter-chip" + (!auto ? " active" : "")} style={{ fontSize: 11 }} onClick={() => live.setAuto(r, false)}><i className="fa fa-user" /> Human</button>
                      <button className="filter-chip" style={{ fontSize: 11 }} onClick={() => live.setAuto(r, null)}>Default</button>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="card">
              <div className="card-header"><div className="card-title"><i className="fa fa-user-secret" /> Adversary profile {isHost ? "" : "(host sets this)"}</div></div>
              <div style={{ display: "grid", gap: 8 }}>
                {snap.profiles.map((p) => (
                  <label key={p.id} style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: isHost ? "pointer" : "default", opacity: isHost ? 1 : 0.7 }}>
                    <input type="radio" name="profile" checked={profile === p.id} disabled={!isHost}
                      onChange={() => setProfile(p.id)} style={{ marginTop: 3 }} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{p.name}
                        <span className="tag" style={{ marginLeft: 8, fontSize: 9 }}>budget {p.budget}</span>
                        {p.assumed_breach && <span className="tag" style={{ marginLeft: 4, fontSize: 9 }}>assumed-breach</span>}
                      </div>
                      <div style={{ fontSize: 11.5, color: "var(--gc-muted)" }}>{p.description}</div>
                    </div>
                  </label>
                ))}
              </div>
              {isHost ? (
                <button className="btn btn-primary" style={{ marginTop: 14, width: "100%" }} onClick={() => live.start(profile, mission)}>
                  <i className="fa fa-play" /> Start mission
                </button>
              ) : (
                <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>Waiting for the host to start the operation…</p>
              )}
            </div>
          </div>
          <div style={{ display: "grid", gap: 16 }}>{PlayersPanel}{LabSidePanel}{ChatPanel}</div>
        </div>
      )}

      {status === "completed" && snap.session.match_result && (
        <div className="alert-item success" style={{ marginBottom: 16, borderColor: snap.session.match_result === "red" ? "var(--gc-red)" : "#5B8CFF" }}>
          <div className="alert-icon"><i className="fa fa-flag-checkered" /></div>
          <div className="alert-content">
            <strong>Match over — {snap.session.match_result === "red" ? "Red wins (objective achieved)"
              : snap.session.match_result === "blue" ? "Blue wins (adversary evicted)" : "Concluded"}</strong>
            <div>Red {snap.operator?.final?.total_score ?? snap.operator?.score ?? 0} pts ·
              SOC {snap.soc?.final?.total_score ?? snap.soc?.score ?? 0} pts ·
              Blue {snap.defender?.final?.total_score ?? snap.defender?.score ?? 0} pts</div>
          </div>
        </div>
      )}

      {/* MISSION AFTER-ACTION REPORT — all teams, shown when the match concludes */}
      {status === "completed" && snap.report && <LiveReport report={snap.report} />}

      {status !== "lobby" && snap.operator && (() => {
        const role = you?.role;
        const view = role === "red" || role === "blue" || role === "soc" ? role : specLens;
        return (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16, alignItems: "start" }}>
            <div>
              {!canPlay && (
                <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
                  <span className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>Spectate</span>
                  {(["red", "soc", "blue"] as const).map((r) => (
                    <button key={r} className={"filter-chip" + (view === r ? " active" : "")} onClick={() => setSpecLens(r)}>
                      <i className={`fa ${ROLE_META[r].icon}`} /> {r.toUpperCase()}{snap.auto[r] ? " (auto)" : ""}
                    </button>
                  ))}
                </div>
              )}
              {view === "red"
                ? <RedConsole snapshot={snap} canPlay={canPlay && role === "red"}
                    onAction={(id, t) => live.redAction(id, t)} onConclude={live.conclude} />
                : view === "soc"
                  ? (snap.soc ? <SocConsole snapshot={snap} canPlay={canPlay && role === "soc"}
                      onAction={(id, t) => live.socAction(id, t)} /> : <div className="center-empty">SOC not initialised.</div>)
                  : (snap.defender ? <BlueConsole snapshot={snap} canPlay={canPlay && role === "blue"}
                      onAction={(id, t) => live.blueAction(id, t)} onConclude={live.conclude} />
                      : <div className="center-empty">Defender not initialised.</div>)}
            </div>
            <div style={{ display: "grid", gap: 16 }}>{PlayersPanel}{LabSidePanel}{ChatPanel}</div>
          </div>
        );
      })()}
    </>
  );
}
