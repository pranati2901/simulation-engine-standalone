import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useLiveSocket } from "../hooks/useLiveSocket";

/* ----------------------------------------------------------------------------
 * GuidedRoom — the guided, multi-user, real-tools walkthrough of a scenario.
 * Backend: POST /api/live/guided/sessions  +  WS /ws/live/{id}  (snapshot.guided).
 * -------------------------------------------------------------------------- */

const ROLE_META: Record<string, { label: string; color: string; icon: string; blurb: string }> = {
  red: { label: "Red Team", color: "#ef4444", icon: "fa-skull", blurb: "Run the attack — real recon tools + the scripted worm." },
  blue: { label: "Blue Team", color: "#3b82f6", icon: "fa-shield-halved", blurb: "Contain, eradicate and recover — bend the worm's growth." },
  soc: { label: "SOC Analyst", color: "#a855f7", icon: "fa-magnifying-glass-chart", blurb: "Watch the funnel — detect, triage and escalate early." },
};
const STATE_COLOR: Record<string, string> = {
  impacted: "#7f1d1d", encrypting: "#b91c1c", infected: "#ef4444", contained: "#3b82f6",
  dormant: "#64748b", recovered: "#22c55e", healthy: "#1e293b",
};

type Sess = { session_id: string; player_id: string; role: string };

export default function GuidedRoom() {
  const { scenarioId = "" } = useParams();
  const nav = useNavigate();
  const storeKey = `gc_guided_${scenarioId}`;
  const [sess, setSess] = useState<Sess | null>(() => {
    try { const r = localStorage.getItem(storeKey); return r ? JSON.parse(r) : null; } catch { return null; }
  });
  const [meta, setMeta] = useState<any>(null);
  const [lab, setLab] = useState<any>(null);

  useEffect(() => { api.guidedScenario(scenarioId).then(setMeta).catch(() => setMeta(null)); }, [scenarioId]);
  useEffect(() => { api.labStatus().then(setLab).catch(() => setLab(null)); }, []);

  const { state, claimRole, guidedTask, setAuto, clearError } = useLiveSocket(sess?.session_id ?? null, sess?.player_id ?? null);
  const claimedRef = useRef(false);
  useEffect(() => {
    if (state.connected && sess?.role && !claimedRef.current) {
      claimedRef.current = true;
      claimRole(sess.role);
    }
  }, [state.connected, sess, claimRole]);

  // Recover from a stale stored session (backend restart / dead id) → "session not found".
  useEffect(() => {
    const e = state.error || "";
    if (e.includes("session not found") || e.includes("re-join") || e.includes("unknown player")) {
      localStorage.removeItem(storeKey);
      claimedRef.current = false;
      setSess(null);
      clearError();
    }
  }, [state.error]);  // eslint-disable-line react-hooks/exhaustive-deps

  function launch(name: string, role: string) {
    api.createGuidedSession({ host_name: name || "operator", scenario_id: scenarioId }).then((r) => {
      const s = { session_id: r.session_id, player_id: r.player_id, role };
      localStorage.setItem(storeKey, JSON.stringify(s));
      claimedRef.current = false;
      setSess(s);
    });
  }
  function quit() { localStorage.removeItem(storeKey); setSess(null); claimedRef.current = false; nav("/"); }

  if (!sess) return <Launch meta={meta} onLaunch={launch} onBack={() => nav("/")} />;
  // Teammate who joined a running session (no seat chosen yet) → pick a role on the EXISTING session.
  if (!sess.role) return <RolePick meta={meta} connected={state.connected} onBack={quit}
    onPick={(role) => { const s2 = { ...sess, role }; localStorage.setItem(storeKey, JSON.stringify(s2)); claimedRef.current = false; setSess(s2); }} />;

  const snap: any = state.snapshot;
  const g = snap?.guided;
  if (!g) {
    return (
      <div style={{ padding: 40, color: "var(--gc-muted)" }}>
        <i className="fa fa-circle-notch fa-spin" /> Spinning up the range and connecting…
        {state.error && <div style={{ color: "#ef4444", marginTop: 10 }}>{state.error}</div>}
      </div>
    );
  }
  return <Room g={g} events={snap.events || []} myRole={sess.role} termUrl={lab?.terminal_url}
    report={snap.report} guidedTask={guidedTask} setAuto={setAuto} onQuit={quit} />;
}

/* ---------- Launch screen ---------- */
function Launch({ meta, onLaunch, onBack }: { meta: any; onLaunch: (n: string, r: string) => void; onBack: () => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("red");
  return (
    <div style={{ maxWidth: 760, margin: "40px auto", padding: 24 }}>
      <button className="btn" onClick={onBack} style={{ marginBottom: 18 }}><i className="fa fa-arrow-left" /> Scenarios</button>
      <h1 style={{ marginBottom: 4 }}>{meta?.name ?? "Guided Scenario"}</h1>
      <div style={{ color: "var(--gc-muted)", marginBottom: 8 }}>{meta?.subtitle}</div>
      <p style={{ color: "var(--gc-muted)", lineHeight: 1.6 }}>{meta?.summary}</p>
      <div style={{ display: "flex", gap: 14, margin: "16px 0", flexWrap: "wrap", fontSize: 13, color: "var(--gc-muted)" }}>
        <span><i className="fa fa-diagram-project" /> {meta?.phase_count ?? "—"} phases</span>
        <span><i className="fa fa-server" /> {meta?.total_hosts ?? "—"} hosts</span>
        <span><i className="fa fa-terminal" /> real tools in Kali (Docker range)</span>
      </div>

      <div style={{ marginTop: 18, marginBottom: 10, fontWeight: 600 }}>Pick your seat <span style={{ color: "var(--gc-muted)", fontWeight: 400 }}>— the other two are auto-driven</span></div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {Object.entries(ROLE_META).map(([k, m]) => (
          <div key={k} onClick={() => setRole(k)} style={{
            cursor: "pointer", border: `2px solid ${role === k ? m.color : "#33415533"}`,
            borderRadius: 12, padding: 14, background: role === k ? `${m.color}14` : "transparent" }}>
            <div style={{ color: m.color, fontWeight: 700, marginBottom: 6 }}><i className={`fa ${m.icon}`} /> {m.label}</div>
            <div style={{ fontSize: 12, color: "var(--gc-muted)", lineHeight: 1.5 }}>{m.blurb}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        <input className="input" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)}
          style={{ flex: 1, padding: "10px 12px", borderRadius: 8 }} />
        <button className="btn btn-primary" onClick={() => onLaunch(name, role)}>
          <i className="fa fa-play" /> Start walkthrough
        </button>
      </div>
    </div>
  );
}

/* ---------- Role pick for a joining teammate (session already exists) ---------- */
function RolePick({ meta, connected, onPick, onBack }: { meta: any; connected: boolean; onPick: (r: string) => void; onBack: () => void }) {
  return (
    <div style={{ maxWidth: 640, margin: "60px auto", padding: 24, textAlign: "center" }}>
      <h1 style={{ marginBottom: 4 }}>Join: {meta?.name ?? "Scenario"}</h1>
      <div style={{ color: "var(--gc-muted)", marginBottom: 20 }}>
        Pick a free seat — <span style={{ color: connected ? "#22c55e" : "#f59e0b" }}>{connected ? "connected" : "connecting…"}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {Object.entries(ROLE_META).map(([k, m]) => (
          <div key={k} onClick={() => onPick(k)} style={{ cursor: "pointer", border: `2px solid ${m.color}55`, borderRadius: 12, padding: 16 }}>
            <div style={{ color: m.color, fontWeight: 700, marginBottom: 6 }}><i className={`fa ${m.icon}`} /> {m.label}</div>
            <div style={{ fontSize: 12, color: "var(--gc-muted)", lineHeight: 1.5 }}>{m.blurb}</div>
          </div>
        ))}
      </div>
      <button className="btn" onClick={onBack} style={{ marginTop: 18 }}><i className="fa fa-arrow-left" /> Leave</button>
    </div>
  );
}

/* ---------- The room ---------- */
function Room({ g, events, myRole, termUrl, report, guidedTask, setAuto, onQuit }:
  { g: any; events: any[]; myRole: string; termUrl?: string | null; report?: any; guidedTask: (id: string) => void; setAuto: (r: string, v: boolean | null) => void; onQuit: () => void }) {
  const [bannerOpen, setBannerOpen] = useState(true);
  const [termOpen, setTermOpen] = useState(true);
  const phase = g.phase;
  useEffect(() => { setBannerOpen(true); }, [g.phase_idx]);   // re-open banner each new phase

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)", position: "relative" }}>
      <Toaster events={events} />
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "10px 18px", borderBottom: "1px solid #1f2937" }}>
        <button className="btn" onClick={onQuit}><i className="fa fa-arrow-left" /></button>
        <div style={{ fontWeight: 700 }}>{g.scenario.name} <span style={{ color: "var(--gc-muted)", fontWeight: 400 }}>· {g.scenario.subtitle}</span></div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 16, alignItems: "center", fontSize: 13 }}>
          <span style={{ color: "var(--gc-muted)" }}>Phase {g.progress.phase}/{g.progress.total}</span>
          <OutcomeBadge band={g.network.outcome_band} finished={g.finished} outcome={g.outcome} />
          {termUrl
            ? <a className="btn" href={termUrl} target="_blank" rel="noreferrer" style={{ color: "#22d3ee", borderColor: "#22d3ee55" }}><i className="fa fa-terminal" /> Kali terminal</a>
            : <span title="Start the Docker range to get a real shell" style={{ color: "var(--gc-muted)", fontSize: 12 }}><i className="fa fa-terminal" /> Kali offline</span>}
          <span style={{ color: ROLE_META[myRole]?.color }}><i className={`fa ${ROLE_META[myRole]?.icon}`} /> You: {ROLE_META[myRole]?.label}</span>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* progress sidebar */}
        <ProgressSidebar g={g} />

        {/* center */}
        <div style={{ flex: 1, overflowY: "auto", padding: 18, minWidth: 0 }}>
          {bannerOpen && phase && <PhaseBanner phase={phase} onClose={() => setBannerOpen(false)} />}
          <WormMap net={g.network} />
          {phase && <TaskColumns phase={phase} tasks={g.tasks} myRole={myRole} guidedTask={guidedTask} />}
          {g.finished && <ResultCard g={g} report={report} onQuit={onQuit} />}
        </div>
      </div>

      {/* bottom terminal dock */}
      <TerminalDock events={events} open={termOpen} toggle={() => setTermOpen((o) => !o)} />
    </div>
  );
}

function OutcomeBadge({ band, finished, outcome }: { band: string; finished: boolean; outcome: string | null }) {
  const text = finished ? outcome : band;
  const c = text === "Contained" ? "#22c55e" : text === "Degraded" ? "#f59e0b" : "#ef4444";
  return <span style={{ color: c, fontWeight: 700, border: `1px solid ${c}55`, borderRadius: 6, padding: "2px 8px" }}>{text}</span>;
}

function PhaseBanner({ phase, onClose }: { phase: any; onClose: () => void }) {
  return (
    <div style={{ border: "1px solid #334155", borderLeft: "4px solid #f59e0b", borderRadius: 10, padding: "14px 16px", marginBottom: 16, background: "#0b1220" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 11, color: "#f59e0b", fontWeight: 700, letterSpacing: 1 }}>PHASE {phase.index + 1} · {phase.mitre} · {phase.stage_kind === "real" ? "REAL TOOLS" : "SIMULATED"}</span>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{phase.name}</div>
        <button className="btn" style={{ marginLeft: "auto", padding: "2px 8px" }} onClick={onClose}><i className="fa fa-xmark" /></button>
      </div>
      <p style={{ margin: "8px 0 6px", lineHeight: 1.6 }}>{phase.briefing}</p>
      <div style={{ fontSize: 12, color: "var(--gc-muted)", display: "grid", gap: 3 }}>
        <div><b style={{ color: "#ef4444" }}>Attacker goal:</b> {phase.attacker_goal}</div>
        <div><b style={{ color: "#94a3b8" }}>Victim feels:</b> {phase.victim_experience}</div>
        <div><b style={{ color: "#a855f7" }}>SOC sees:</b> {phase.soc_signal}</div>
      </div>
      {phase.decision_point && (
        <div style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8, background: "#111827", fontSize: 12 }}>
          <b style={{ color: "#f59e0b" }}>{phase.decision_point.id}</b> — {phase.decision_point.prompt}
          <span style={{ color: "var(--gc-muted)" }}> · Inaction: {phase.decision_point.inaction}</span>
        </div>
      )}
    </div>
  );
}

function WormMap({ net }: { net: any }) {
  // a representative dot grid (scaled to ~120 cells) coloured by host state
  const cells = 120;
  const scale = (n: number) => Math.round((n / net.total_hosts) * cells);
  const order: [string, number][] = [
    ["impacted", scale(net.impacted)], ["infected", scale(Math.max(0, net.infected - net.impacted - net.dormant))],
    ["dormant", scale(net.dormant)], ["recovered", scale(net.recovered)], ["contained", scale(net.contained)],
  ];
  const dots: string[] = [];
  for (const [st, n] of order) for (let i = 0; i < n && dots.length < cells; i++) dots.push(st);
  while (dots.length < cells) dots.push("healthy");

  const Stat = ({ label, value, color }: { label: string; value: any; color?: string }) => (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 20, fontWeight: 800, color: color || "#e2e8f0" }}>{value}</div>
      <div style={{ fontSize: 10, color: "var(--gc-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
    </div>
  );
  return (
    <div style={{ border: "1px solid #1f2937", borderRadius: 10, padding: 14, marginBottom: 16, background: "#0b1220" }}>
      <div style={{ display: "flex", gap: 22, justifyContent: "space-between", flexWrap: "wrap", marginBottom: 12 }}>
        <Stat label="Infected" value={net.infected} color="#ef4444" />
        <Stat label="Impacted" value={net.impacted} color="#7f1d1d" />
        <Stat label="Contained" value={net.contained} color="#3b82f6" />
        <Stat label="Recovered" value={net.recovered} color="#22c55e" />
        <Stat label="R-value" value={net.r_value} color={net.r_value > 1 ? "#f59e0b" : "#22c55e"} />
        <Stat label="Est. loss" value={`$${(net.financial_loss / 1000).toFixed(0)}k`} color="#f59e0b" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(40, 1fr)", gap: 2 }}>
        {dots.map((st, i) => <div key={i} title={st} style={{ width: "100%", paddingTop: "100%", borderRadius: 2, background: STATE_COLOR[st] }} />)}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 10, fontSize: 11, color: "var(--gc-muted)", flexWrap: "wrap" }}>
        {net.kill_switch_tripped && <span style={{ color: "#64748b" }}><i className="fa fa-power-off" /> kill-switch tripped</span>}
        {net.segmented && <span style={{ color: "#3b82f6" }}><i className="fa fa-network-wired" /> segmented</span>}
        {net.smbv1_patched && <span style={{ color: "#22c55e" }}><i className="fa fa-shield" /> SMBv1 patched</span>}
        {net.recovery_disabled && <span style={{ color: net.backups_safe ? "#22c55e" : "#ef4444" }}><i className="fa fa-database" /> {net.backups_safe ? "offline backups safe" : "recovery disabled"}</span>}
      </div>
    </div>
  );
}

function TaskColumns({ phase, tasks, myRole, guidedTask }:
  { phase: any; tasks: any; myRole: string; guidedTask: (id: string) => void; }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
      {(["red", "soc", "blue"] as const).map((role) => (
        <div key={role} style={{ border: `1px solid ${ROLE_META[role].color}33`, borderRadius: 10, overflow: "hidden" }}>
          <div style={{ padding: "8px 12px", background: `${ROLE_META[role].color}1a`, color: ROLE_META[role].color, fontWeight: 700, fontSize: 13 }}>
            <i className={`fa ${ROLE_META[role].icon}`} /> {ROLE_META[role].label} {role === myRole && <span style={{ fontSize: 10, marginLeft: 6, padding: "1px 6px", borderRadius: 4, background: ROLE_META[role].color, color: "#000" }}>YOU</span>}
          </div>
          <div style={{ padding: 10, display: "grid", gap: 8 }}>
            {(tasks[role] || []).map((t: any) => (
              <TaskCard key={t.id} t={t} mine={role === myRole} color={ROLE_META[role].color} onDo={() => guidedTask(t.id)} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function TaskCard({ t, mine, color, onDo }: { t: any; mine: boolean; color: string; onDo: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: "1px solid #1f2937", borderRadius: 8, padding: "8px 10px", background: t.done ? "#0c1a0c" : "#0b1220", opacity: t.done ? 0.75 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <i className={`fa ${t.done ? "fa-circle-check" : "fa-circle"}`} style={{ color: t.done ? "#22c55e" : "#475569" }} />
        <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{t.label}</span>
        {t.kind === "real_tool" && <span title="real tool" style={{ fontSize: 9, color: "#22d3ee", border: "1px solid #22d3ee55", borderRadius: 4, padding: "0 4px" }}>{t.tool}</span>}
        {t.optional && <span style={{ fontSize: 9, color: "var(--gc-muted)" }}>optional</span>}
        <button className="btn" style={{ padding: "1px 6px", fontSize: 11 }} onClick={() => setOpen((o) => !o)}><i className="fa fa-circle-info" /></button>
      </div>
      {open && (
        <div style={{ fontSize: 11.5, color: "var(--gc-muted)", lineHeight: 1.5, marginTop: 6, display: "grid", gap: 3 }}>
          <div><b style={{ color: "#cbd5e1" }}>Does:</b> {t.does}</div>
          <div><b style={{ color: "#cbd5e1" }}>How:</b> {t.how}</div>
          <div><b style={{ color: "#cbd5e1" }}>Outcome:</b> {t.outcome}</div>
        </div>
      )}
      {mine && !t.done && (
        <button className="btn btn-primary" style={{ marginTop: 8, width: "100%", fontSize: 12, background: color, borderColor: color }} onClick={onDo}>
          <i className={`fa ${t.kind === "real_tool" ? "fa-terminal" : "fa-bolt"}`} /> {t.kind === "real_tool" ? `Run ${t.tool}` : "Do this"}
        </button>
      )}
    </div>
  );
}

function ProgressSidebar({ g }: { g: any }) {
  return (
    <div style={{ width: 240, borderRight: "1px solid #1f2937", overflowY: "auto", padding: 12, flexShrink: 0 }}>
      <div style={{ fontSize: 11, color: "var(--gc-muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>Walkthrough</div>
      <div style={{ fontSize: 12, color: "var(--gc-muted)", marginBottom: 10 }}>
        Phase {g.progress.phase}/{g.progress.total} · {g.progress.phase_done}/{g.progress.phase_total} tasks done
      </div>
      <div style={{ display: "grid", gap: 4 }}>
        {g.phases.map((p: any) => {
          const active = p.state === "active", done = p.state === "done";
          return (
            <div key={p.index} style={{
              display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: 6,
              background: active ? "#1e293b" : "transparent",
              borderLeft: `3px solid ${active ? "#f59e0b" : done ? "#22c55e" : "#334155"}` }}>
              <i className={`fa ${done ? "fa-circle-check" : active ? "fa-circle-dot" : "fa-circle"}`}
                style={{ color: done ? "#22c55e" : active ? "#f59e0b" : "#475569", fontSize: 11 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: active ? 700 : 400, color: active ? "#e2e8f0" : "var(--gc-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.name}</div>
                <div style={{ fontSize: 9, color: "#475569" }}>{p.mitre} · {p.stage_kind}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TerminalDock({ events, open, toggle }: { events: any[]; open: boolean; toggle: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [events.length, open]);
  return (
    <div style={{ borderTop: "1px solid #1f2937", background: "#0a0e1a" }}>
      <div onClick={toggle} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 14px", cursor: "pointer", fontSize: 12, color: "var(--gc-muted)" }}>
        <i className={`fa ${open ? "fa-chevron-down" : "fa-chevron-up"}`} />
        <i className="fa fa-terminal" /> Console &amp; tool output
        <span style={{ marginLeft: "auto" }}>{events.length} events</span>
      </div>
      {open && (
        <div ref={ref} style={{ height: 200, overflowY: "auto", padding: "6px 14px", fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12, lineHeight: 1.5 }}>
          {events.map((e: any, i: number) => <TermLine key={i} e={e} />)}
        </div>
      )}
    </div>
  );
}

function TermLine({ e }: { e: any }) {
  const rc = ROLE_META[e.role]?.color || "#64748b";
  const lf = e.data?.live_fire;
  return (
    <div style={{ marginBottom: 2 }}>
      <span style={{ color: "#475569" }}>[{String(e.t).padStart(3, "0")}s] </span>
      <span style={{ color: rc, textTransform: "uppercase", fontSize: 10 }}>{e.role}</span>{" "}
      <span style={{ color: "#cbd5e1" }}>{e.title}</span>
      {e.message && <span style={{ color: "#64748b" }}> — {e.message}</span>}
      {lf && lf.command && (
        <div style={{ margin: "3px 0 6px 16px", padding: "6px 8px", background: "#0d1424", borderLeft: "2px solid #22d3ee", borderRadius: 4 }}>
          <div style={{ color: "#22d3ee" }}>$ {lf.command}</div>
          {lf.output && <pre style={{ margin: "4px 0 0", color: "#94a3b8", whiteSpace: "pre-wrap", maxHeight: 160, overflow: "auto" }}>{lf.output}</pre>}
          {lf.detected && <div style={{ color: "#f59e0b", marginTop: 3 }}><i className="fa fa-eye" /> DETECTED — {lf.detection_evidence}</div>}
          {lf.status === "queued" && <div style={{ color: "#64748b" }}><i className="fa fa-circle-notch fa-spin" /> running {lf.tool}…</div>}
        </div>
      )}
    </div>
  );
}

/* ---------- toasts ---------- */
function Toaster({ events }: { events: any[] }) {
  const [toasts, setToasts] = useState<any[]>([]);
  const seen = useRef(-1);
  useEffect(() => {
    const fresh = events.filter((e) => e.seq > seen.current && ["g_phase", "g_task", "g_decision", "g_result"].includes(e.kind));
    if (fresh.length) {
      seen.current = Math.max(seen.current, ...events.map((e) => e.seq));
      setToasts((t) => [...t, ...fresh].slice(-4));
      fresh.forEach((f) => setTimeout(() => setToasts((t) => t.filter((x) => x !== f)), 6000));
    }
  }, [events]);
  return (
    <div style={{ position: "absolute", top: 12, right: 12, zIndex: 50, display: "grid", gap: 8, width: 320 }}>
      {toasts.map((e, i) => {
        const c = e.kind === "g_phase" ? "#f59e0b" : e.kind === "g_result" ? "#22c55e" : ROLE_META[e.role]?.color || "#3b82f6";
        return (
          <div key={i} style={{ background: "#0b1220", border: `1px solid ${c}`, borderLeft: `4px solid ${c}`, borderRadius: 8, padding: "10px 12px", boxShadow: "0 6px 20px #0008" }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: c }}>{e.title}</div>
            <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 2, lineHeight: 1.45 }}>{e.message}</div>
          </div>
        );
      })}
    </div>
  );
}

function ResultCard({ g, report, onQuit }: { g: any; report?: any; onQuit: () => void }) {
  const [showAAR, setShowAAR] = useState(false);
  const download = () => {
    const blob = new Blob([JSON.stringify(report ?? g, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `AAR_${g.scenario?.id || "guided"}_${Date.now()}.json`; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div style={{ marginTop: 16, border: "1px solid #334155", borderRadius: 12, padding: 20, textAlign: "center", background: "#0b1220" }}>
      <div style={{ fontSize: 13, color: "var(--gc-muted)" }}>Scenario complete</div>
      <div style={{ fontSize: 28, fontWeight: 800, margin: "6px 0", color: g.outcome === "Contained" ? "#22c55e" : g.outcome === "Degraded" ? "#f59e0b" : "#ef4444" }}>{g.outcome}</div>
      <div style={{ display: "flex", gap: 24, justifyContent: "center", margin: "12px 0", color: "var(--gc-muted)", fontSize: 13 }}>
        <span>Red {g.team_score.red}</span><span>SOC {g.team_score.soc}</span><span>Blue {g.team_score.blue}</span>
        <span>· {g.network.impacted} impacted · ${(g.network.financial_loss / 1000).toFixed(0)}k loss</span>
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
        <button className="btn btn-primary" onClick={onQuit}><i className="fa fa-rotate-right" /> Back to scenarios</button>
        {report && <button className="btn" onClick={() => setShowAAR((o) => !o)}><i className="fa fa-file-lines" /> {showAAR ? "Hide" : "View"} AAR report</button>}
        {report && <button className="btn" onClick={download}><i className="fa fa-download" /> Download AAR</button>}
      </div>
      {report && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 8 }}><i className="fa fa-floppy-disk" /> Saved to Reports &amp; AAR.</div>}
      {showAAR && report && <AARPanel report={report} />}
    </div>
  );
}

function AARPanel({ report }: { report: any }) {
  return (
    <div style={{ textAlign: "left", marginTop: 16, borderTop: "1px solid #1f2937", paddingTop: 14 }}>
      <div style={{ fontWeight: 700, marginBottom: 10 }}>{report.verdict}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        {(["red", "soc", "blue"] as const).map((role) => {
          const t = report.teams?.[role]; const m = ROLE_META[role];
          if (!t) return null;
          return (
            <div key={role} style={{ border: `1px solid ${m.color}33`, borderRadius: 8, padding: 10 }}>
              <div style={{ color: m.color, fontWeight: 700, marginBottom: 6 }}><i className={`fa ${m.icon}`} /> {m.label} · {t.score}</div>
              {(t.findings?.strengths ?? []).map((x: string, i: number) => <div key={`s${i}`} style={{ fontSize: 11, color: "#22c55e", lineHeight: 1.4 }}>+ {x}</div>)}
              {(t.findings?.weaknesses ?? []).map((x: string, i: number) => <div key={`w${i}`} style={{ fontSize: 11, color: "#f59e0b", lineHeight: 1.4 }}>− {x}</div>)}
            </div>
          );
        })}
      </div>
      {(report.recommendations ?? []).length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Recommendations</div>
          {report.recommendations.map((r: string, i: number) => <div key={i} style={{ fontSize: 12, color: "#cbd5e1", marginBottom: 3 }}>• {r}</div>)}
        </div>
      )}
    </div>
  );
}
