import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useLiveSocket } from "../hooks/useLiveSocket";
import RedWorkspace from "../components/sim/RedWorkspace";
import SocWorkspace from "../components/sim/SocWorkspace";
import BlueWorkspace from "../components/sim/BlueWorkspace";
import VictimDesktop from "../components/sim/VictimDesktop";
import AarReport from "../components/AarReport";
import GuidePanel from "../components/sim/GuidePanel";
import JillaTeacher from "../components/sim/JillaTeacher";
import ScenarioIntro from "../components/sim/ScenarioIntro";
import IncidentTicker from "../components/sim/IncidentTicker";
import { AttackTimeline } from "../components/sim/JillaVisuals";
import ResultOverlayModal from "../components/sim/ResultOverlay";
import NotificationDock, { NotifyMsg } from "../components/sim/NotificationDock";
import { TEAM_META } from "../components/sim/shared";
import { getPhase } from "../components/sim/StoryData";
import "../components/sim/sim.css";

type Sess = { session_id: string; player_id: string; role: string | null };

export default function ScenarioWorkspace() {
  const { scenarioId = "" } = useParams();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const mode = sp.get("mode") === "practice" ? "practice" : "teach";   // Library=practice, Live=teach
  const key = `gc_guided_${scenarioId}_${mode}`;
  const [sess, setSess] = useState<Sess | null>(null);  // always show intro first
  const [introDone, setIntroDone] = useState(false);   // track if user clicked "Enter"
  const [meta, setMeta] = useState<any>(null);
  const [lab, setLab] = useState<any>(null);
  const [tab, setTab] = useState<string>("red");
  const [recoveryMode, setRecoveryMode] = useState(false);   // post-impact: play any seat to learn IR
  const [resultClosed, setResultClosed] = useState(false);   // dismissed the result overlay to review the range

  useEffect(() => { api.guidedScenario(scenarioId).then(setMeta).catch(() => {}); }, [scenarioId]);
  useEffect(() => { api.labStatus().then(setLab).catch(() => {}); }, []);

  const live = useLiveSocket(sess?.session_id ?? null, sess?.player_id ?? null);
  const claimed = useRef(false);
  useEffect(() => {
    if (live.state.connected && sess?.role && !claimed.current) { claimed.current = true; live.claimRole(sess.role); }
  }, [live.state.connected, sess, live]);

  // A stored session can be stale (backend restarted, or an old session id) → "session not found".
  // Recover by clearing it and returning to the landing screen so a fresh session is created.
  useEffect(() => {
    const e = live.state.error || "";
    if (e.includes("session not found") || e.includes("re-join") || e.includes("unknown player")) {
      localStorage.removeItem(key);
      claimed.current = false;
      setSess(null);
      live.clearError();
    }
  }, [key, live.state.error]);  // eslint-disable-line react-hooks/exhaustive-deps

  // default the active tab to your seat once chosen
  useEffect(() => { if (sess?.role) setTab(sess.role); }, [sess?.role]);

  // Guide: surface the latest tool result (with a teaching consequence) as an overlay.
  // These hooks MUST stay above the early returns below, or the hook order changes between
  // renders once the snapshot arrives (React: "Rendered more hooks than during the previous render").
  const [lastResult, setLastResult] = useState<any>(null);
  const seenGuide = useRef(-1);
  const simEvents: any[] = (live.state.snapshot as any)?.sim?.events ?? [];
  useEffect(() => {
    const fresh = simEvents.filter((e: any) => e.seq > seenGuide.current && e.notify && e.data?.consequence);
    if (fresh.length) {
      seenGuide.current = Math.max(seenGuide.current, ...simEvents.map((e: any) => e.seq));
      const last = fresh[fresh.length - 1];
      setLastResult({
        tool_name: last.title, tool_id: last.data?.tool_id || "", team: last.role,
        consequence: last.data?.consequence || "", next_hint: last.data?.next_hint || "",
        teaching_note: last.data?.teaching_note || "", command: last.data?.command || "",
        outcome: last.message,
      });
    }
  }, [simEvents]);  // eslint-disable-line react-hooks/exhaustive-deps

  function launch(name: string, role: string) {
    // Check if we have an existing session we can reuse
    try {
      const cached = localStorage.getItem(key);
      if (cached) {
        const s = { ...JSON.parse(cached), role };
        localStorage.setItem(key, JSON.stringify(s));
        claimed.current = false; setIntroDone(true); setSess(s);
        return;
      }
    } catch { /* no cached session, create new */ }

    api.createGuidedSession({ host_name: name || "operator", scenario_id: scenarioId, mode }).then((r) => {
      const s = { session_id: r.session_id, player_id: r.player_id, role };
      localStorage.setItem(key, JSON.stringify(s)); claimed.current = false; setIntroDone(true); setSess(s);
    });
  }
  function pickRole(role: string) {
    if (!sess) return;
    const s = { ...sess, role }; localStorage.setItem(key, JSON.stringify(s)); claimed.current = false; setSess(s);
  }
  function quit() { localStorage.removeItem(key); setSess(null); claimed.current = false; nav("/live"); }

  if (!sess) return <ScenarioIntro meta={meta} scenarioId={scenarioId} onLaunch={launch} onBack={() => nav("/live")} />;
  if (!sess.role) return <RolePick meta={meta} connected={live.state.connected} onPick={pickRole} onBack={quit} />;

  const snap: any = live.state.snapshot;
  const sim = snap?.sim;
  if (!sim) {
    return <div style={{ padding: 40, color: "var(--gc-muted)" }}>
      <i className="fa fa-circle-notch fa-spin" /> Spinning up the range…
      {live.state.error && <div style={{ color: "#ef4444", marginTop: 8 }}>{live.state.error}</div>}
    </div>;
  }

  const myRole = sess.role;
  // In the post-impact recovery phase the learner can step into any seat to practice IR.
  const canPlay = (t: string) => recoveryMode || t === myRole;
  const events = sim.events || [];
  const termUrl = lab?.terminal_url;

  // Floating notification feed: the noteworthy events (phase changes, alerts, actions, results).
  const notifyMsgs: NotifyMsg[] = (events as any[])
    .filter((e) => e.notify || ["g_phase", "g_result", "alert", "g_intent"].includes(e.kind))
    .map((e) => ({ id: e.seq, title: e.title, text: e.message, severity: e.severity, t: e.t, role: e.role }));
  const dockStatus = {
    label: sim.guide?.phase ? `Phase: ${sim.guide.phase}` : (meta?.name ?? "Operation Tripwire"),
    detail: sim.finished ? `Concluded — ${sim.outcome}` : `Threat trending: ${sim.worm?.outcome_band}`,
  };

  return (
    <div className="ws-root">
      <ResultOverlayModal result={lastResult} onClose={() => setLastResult(null)} />
      {/* slim top bar — the single nav/control strip for the immersive workspace */}
      <div className="ws-topbar">
        <button className="ws-icon" onClick={quit} title="Back to scenarios"><i className="fa fa-arrow-left" /></button>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{meta?.name ?? "Operation Tripwire"}</div>
        </div>
        <span className={"mode-chip " + mode}>
          <i className={`fa ${mode === "practice" ? "fa-dumbbell" : "fa-graduation-cap"}`} /> {mode === "practice" ? "Practice" : "Teaching"}
        </span>
        <div style={{ display: "flex", gap: 3, marginLeft: 4 }}>
          {["red", "soc", "blue", "victim"].map((t) => {
            const m = TEAM_META[t];
            const st = sim.team_status?.[t];
            return (
              <button key={t} className={"ws-tab" + (tab === t ? " active" : "")} onClick={() => setTab(t)}
                title={st === "you" ? "Your seat" : st === "narrated" ? "Narrated — shown, not acting" : st === "functional" ? "Functional — acting for real" : undefined}>
                <i className={`fa ${m.icon}`} style={{ color: tab === t ? undefined : m.color }} /> <span className="lbl">{m.label}</span>
                {t === myRole && <span className="seat">YOU</span>}
                {st === "narrated" && t !== myRole && <span className="seat" style={{ background: "rgba(0,0,0,.08)" }}>i</span>}
              </button>
            );
          })}
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
          <span style={{ color: "var(--gc-muted)", fontFamily: "var(--mono)", fontSize: 11 }}>t{sim.tick}</span>
          <OutcomeBadge band={sim.worm.outcome_band} finished={sim.finished} outcome={sim.outcome} />
          {termUrl
            ? <a className="ws-icon" href={termUrl} target="_blank" rel="noreferrer" title="Open Kali terminal" style={{ color: "var(--gc-primary)" }}><i className="fa fa-terminal" /></a>
            : <span className="ws-icon" title="Kali offline" style={{ color: "#94a3b8" }}><i className="fa fa-terminal" /></span>}
          {!sim.finished && <button className="btn btn-primary" style={{ padding: "6px 12px" }} onClick={live.conclude}><i className="fa fa-flag-checkered" /> Conclude</button>}
          {sim.finished && resultClosed && <button className="btn" style={{ padding: "6px 12px" }} onClick={() => setResultClosed(false)}><i className="fa fa-file-lines" /> Result</button>}
        </div>
      </div>

      {/* News ticker + attack timeline — inline */}
      <IncidentTicker sim={sim} scenarioId={scenarioId} />
      {sim?.guide?.phase && (
        <AttackTimeline
          phases={["Host Discovery", "SMB Enumeration", "Exploit", "Payload", "Persistence", "C2", "Lateral Movement", "Disable Recovery", "Impact"]
            .map(name => ({ name, shortName: name.length > 12 ? name.slice(0, 10) + "\u2026" : name }))}
          currentIdx={["Host Discovery", "SMB Enumeration", "Exploit", "Payload", "Persistence", "C2", "Lateral Movement", "Disable Recovery", "Impact"]
            .indexOf(sim.guide.phase)}
          role={myRole}
        />
      )}

      {/* recovery-phase banner — Red already won; you're now learning incident response on any seat */}
      {recoveryMode && !sim.finished && (
        <div className="intent-banner" style={{ background: "#eff6ff", borderColor: "#bfdbfe", color: "#1d4ed8" }}>
          <i className="fa fa-shield-halved" /> <b>Recovery phase</b> — Red's attack succeeded. You can now act as <b>any</b> team:
          contain remaining footholds, eradicate the vector, and restore impacted hosts from backup. Hit <b>Conclude</b> when done.
        </div>
      )}

      {/* telegraph reaction-window banners (auto seats other than yours) */}
      {Object.entries(sim.pending_intents || {}).filter(([r]) => r !== myRole).map(([r, i]: any) => (
        <div key={r} className="intent-banner">
          <i className="fa fa-bolt" /> {TEAM_META[r]?.label} will <b>{i.label}</b> in ~{Math.max(0, i.ticks_left) * 3}s — act first to change the outcome.
        </div>
      ))}

      <div className="ws-body" style={{ display: "flex" }}>
        {/* Jilla is FAB-only — no sidebar, see JillaTeacher below */}
        <div style={{ flex: 1, minWidth: 0, overflow: "auto" }}>
          {(() => {
            const st = sim.team_status?.[tab];
            if (tab === "victim" || !st || st !== "narrated") return null;
            const ph = sim.guide ? getPhase(scenarioId, sim.guide.phase) : null;
            const persp = ph ? (tab === "red" ? ph.red : tab === "soc" ? ph.soc : ph.blue) : "";
            const m = TEAM_META[tab];
            return (
              <div style={{ margin: "12px 12px 0", padding: "10px 14px", borderRadius: 12, background: `${m.color}10`,
                border: `1px solid ${m.color}33`, fontSize: 12.5, lineHeight: 1.55, display: "flex", gap: 10 }}>
                <i className="fa fa-circle-info" style={{ color: m.color, marginTop: 2 }} />
                <div>
                  <b style={{ color: m.color }}>{m.label} is narrated here</b> — in this teaching session you're seeing
                  what they'd do, not live actions (only <b>{TEAM_META[myRole]?.label}</b> is functional).
                  {persp && <> <span style={{ color: "var(--gc-muted)" }}>This phase: {persp}</span></>}
                </div>
              </div>
            );
          })()}
          {tab === "red" && <RedWorkspace sim={sim} canPlay={canPlay("red")} runTool={live.runTool} events={events} termUrl={termUrl} error={live.state.error} />}
          {tab === "soc" && <SocWorkspace sim={sim} canPlay={canPlay("soc")} runTool={live.runTool} events={events} />}
          {tab === "blue" && <BlueWorkspace sim={sim} canPlay={canPlay("blue")} runTool={live.runTool} events={events} error={live.state.error} />}
          {tab === "victim" && <VictimDesktop sim={sim} />}
        </div>
      </div>

      {/* Red won (human-paced): offer to step into the defender's seat for the IR lesson, or conclude */}
      {sim.impact_complete && !sim.finished && !recoveryMode && (
        <div style={{ position: "fixed", inset: 0, background: "#000b", zIndex: 80, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="ws-card" style={{ width: 500, textAlign: "center", borderColor: "#ef4444" }}>
            <div style={{ fontSize: 12, color: "var(--gc-muted)", letterSpacing: 1 }}>RED'S MISSION ACCOMPLISHED</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: "#ef4444", margin: "8px 0" }}><i className="fa fa-skull-crossbones" /> Files Encrypted</div>
            <div style={{ fontSize: 13, color: "var(--gc-text2)", lineHeight: 1.65, marginBottom: 16 }}>
              The attack succeeded — but the story isn't over. <b>This is where real defenders earn their pay.</b>{" "}
              Step into the Blue seat to <b style={{ color: "#3b82f6" }}>contain</b> the remaining footholds,{" "}
              <b style={{ color: "#3b82f6" }}>eradicate</b> the vector, and <b style={{ color: "#3b82f6" }}>recover</b> impacted hosts from backups.
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
              <button className="btn btn-primary" onClick={() => { setRecoveryMode(true); setTab("blue"); }}>
                <i className="fa fa-shield-halved" /> See what happens next — work the recovery
              </button>
              <button className="btn" onClick={live.conclude}><i className="fa fa-flag-checkered" /> Conclude &amp; view report</button>
            </div>
          </div>
        </div>
      )}

      {sim.finished && !resultClosed && <FinishOverlay sim={sim} report={snap.report} onQuit={quit} onClose={() => setResultClosed(true)} />}

      <NotificationDock messages={notifyMsgs} status={dockStatus} />
      <JillaTeacher sim={sim} myRole={myRole} scenarioId={scenarioId} />
    </div>
  );
}

/* ---------- landing / role pick ---------- */
const ROLE_NARRATIVES: Record<string, Record<string, string>> = {
  "scn-wannacry-w1": {
    red: "You are the operator. You've landed on a compromised host inside Mercy Regional Hospital — FIN-WS-014. The worm is loaded. 200 unpatched Windows machines sit on a flat, unsegmented network. Your mission: progress the kill chain from reconnaissance to encryption. The attack that caused $4 billion in global damage starts with your next command.",
    soc: "It's 3 AM on a Friday night. You're the overnight SOC analyst at Mercy Regional Hospital. Somewhere on this network, an attacker has already compromised a host. Your job is to spot the first anomaly — the first unusual port scan, the first IDS signature — and escalate before the worm spreads to every machine in the hospital.",
    blue: "You're the incident response lead at Mercy Regional. NHS England is about to get hit by the largest ransomware attack in history. Your hospital runs the same unpatched Windows 7 fleet. Your job: contain the blast radius. Segment the VLANs. Protect the backup server. Find the kill switch. The NHS hospitals that were segmented survived. The flat ones were devastated.",
  },
  "scn-r5-phishing": {
    red: "You're an affiliate operator for the REvil ransomware gang. Your target: MediumCorp Financial's SecureMail. One weak password, one unpatched diagnostics tool — that's the difference between a secure company and a $2.5M ransom note. Brute-force a mailbox, find the vulnerability, get code execution.",
    soc: "The email gateway just logged a spike in failed login attempts against SecureMail. Is it a brute-force attack? A misconfigured client? You need to triage fast. If you catch it at the brute-force stage, you save the company. Miss it, and the next alert is a ransom note.",
    blue: "The SOC just escalated: confirmed unauthorized access to an employee's mailbox via brute-forced credentials. The attacker may have found internal vulnerabilities. Contain before they pivot. Revoke credentials. Isolate the system. The clock started when the SOC called.",
  },
  "scn-c5-edr": {
    red: "GlobalTech MSP's EDR just went dark — 4 hours of zero endpoint visibility across 200 clients. Half the admin accounts share Welcome2024!. You've been waiting for exactly this moment. Password spray, get admin, push ransomware through their own management tools.",
    soc: "2 AM. Your EDR dashboard is grey. 'Service degradation' the vendor says. You have zero endpoint visibility. If something happens in the next 4 hours, you won't see it. What contingency do you activate when your primary detection goes dark?",
    blue: "The EDR is coming back online and the first thing it shows is devastating: ransomware staged across multiple client environments. Someone got in during the blind spot and used your own admin tools. Do you shut down the RMM console or try to push a kill command through it?",
  },
};

function Landing({ meta, scenarioId, onLaunch, onBack }: { meta: any; scenarioId: string; onLaunch: (n: string, r: string) => void; onBack: () => void }) {
  const [name, setName] = useState(localStorage.getItem("gc_live_name") || "");
  const [role, setRole] = useState("red");
  const narratives = ROLE_NARRATIVES[scenarioId] || ROLE_NARRATIVES["scn-wannacry-w1"];
  const narrative = narratives[role] || narratives.red;

  return (
    <div style={{ maxWidth: 720, margin: "48px auto", padding: 24, color: "var(--gc-text)" }}>
      <button className="btn" onClick={onBack} style={{ marginBottom: 16 }}><i className="fa fa-arrow-left" /> Live</button>
      <div style={{ border: "1px solid var(--gc-border)", borderRadius: 12, padding: 20, background: "#fff", marginBottom: 18 }}>
        <div style={{ fontSize: 11, letterSpacing: 1, color: "#f59e0b" }}>INCIDENT OPERATOR CONSOLE</div>
        <h1 style={{ margin: "6px 0" }}>{meta?.name ?? "Operation Tripwire"}</h1>
        <div style={{ color: "var(--gc-muted)", fontSize: 13, lineHeight: 1.7 }}>
          Patient Zero: <b style={{ color: "#b45309" }}>FIN-WS-014</b> · State: <b style={{ color: "#ef4444" }}>Infected</b><br />
          {meta?.summary}
        </div>
      </div>

      <div style={{ fontWeight: 600, marginBottom: 8 }}>Pick your seat</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {["red", "soc", "blue"].map((k) => {
          const m = TEAM_META[k];
          return (
            <div key={k} onClick={() => setRole(k)} style={{ cursor: "pointer", border: `2px solid ${role === k ? m.color : "#33415544"}`,
              borderRadius: 12, padding: 14, background: role === k ? `${m.color}14` : "transparent", transition: "all 0.2s" }}>
              <div style={{ color: m.color, fontWeight: 700 }}><i className={`fa ${m.icon}`} /> {m.label}</div>
              <div style={{ fontSize: 12, color: "var(--gc-muted)", marginTop: 4 }}>{m.blurb}</div>
            </div>
          );
        })}
      </div>

      {/* Narrative that changes per role */}
      <div key={role} style={{ marginTop: 16, padding: 16, borderRadius: 12, background: "var(--gc-soft)",
        borderLeft: `3px solid ${TEAM_META[role]?.color || "var(--gc-primary)"}`,
        fontSize: 13.5, lineHeight: 1.8, color: "var(--gc-text2)",
        animation: "jillaBubbleIn 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)" }}>
        {narrative}
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
        <input className="form-input" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={() => onLaunch(name, role)}><i className="fa fa-play" /> Enter the range</button>
      </div>
    </div>
  );
}

function RolePick({ meta, connected, onPick, onBack }: { meta: any; connected: boolean; onPick: (r: string) => void; onBack: () => void }) {
  return (
    <div style={{ maxWidth: 640, margin: "60px auto", padding: 24, textAlign: "center", color: "var(--gc-text)" }}>
      <h1>Join: {meta?.name ?? "Scenario"}</h1>
      <div style={{ color: "var(--gc-muted)", marginBottom: 18 }}>Pick a free seat — <span style={{ color: connected ? "#22c55e" : "#f59e0b" }}>{connected ? "connected" : "connecting…"}</span></div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {["red", "blue", "soc"].map((k) => {
          const m = TEAM_META[k];
          return (
            <div key={k} onClick={() => onPick(k)} style={{ cursor: "pointer", border: `2px solid ${m.color}55`, borderRadius: 12, padding: 16 }}>
              <div style={{ color: m.color, fontWeight: 700 }}><i className={`fa ${m.icon}`} /> {m.label}</div>
              <div style={{ fontSize: 12, color: "var(--gc-muted)", marginTop: 4 }}>{m.blurb}</div>
            </div>
          );
        })}
      </div>
      <button className="btn" onClick={onBack} style={{ marginTop: 18 }}><i className="fa fa-arrow-left" /> Leave</button>
    </div>
  );
}

function OutcomeBadge({ band, finished, outcome }: { band: string; finished: boolean; outcome: string | null }) {
  const text = finished ? outcome : band;
  const c = text === "Contained" ? "#22c55e" : text === "Degraded" ? "#f59e0b" : "#ef4444";
  return <span style={{ color: c, fontWeight: 700, border: `1px solid ${c}66`, borderRadius: 6, padding: "1px 8px" }}>{text}</span>;
}

/* ---------- finish overlay ---------- */
function FinishOverlay({ sim, report, onQuit, onClose }: { sim: any; report: any; onQuit: () => void; onClose: () => void }) {
  const [showReport, setShowReport] = useState(false);
  const c = sim.outcome === "Contained" ? "#22c55e" : sim.outcome === "Degraded" ? "#f59e0b" : "#ef4444";

  if (showReport && report) {
    return (
      <div style={{ position: "fixed", inset: 0, zIndex: 80, background: "var(--gc-bg)", overflowY: "auto" }}>
        <AarReport report={report} onClose={() => setShowReport(false)} />
        <div className="no-print" style={{ textAlign: "center", paddingBottom: 28 }}>
          <button className="btn btn-primary" onClick={onQuit}><i className="fa fa-rotate-right" /> Back to scenarios</button>
        </div>
      </div>
    );
  }
  return (
    <div style={{ position: "fixed", inset: 0, background: "#000a", zIndex: 80, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="ws-card" style={{ width: 460, textAlign: "center", borderColor: c, position: "relative" }}>
        <button className="btn" onClick={onClose} title="Close — stay in the range" style={{ position: "absolute", top: 8, right: 8, padding: "2px 8px" }}>
          <i className="fa fa-xmark" />
        </button>
        <div style={{ fontSize: 12, color: "var(--gc-muted)" }}>Scenario complete</div>
        <div style={{ fontSize: 30, fontWeight: 800, color: c, margin: "6px 0" }}>{sim.outcome}</div>
        <div style={{ fontSize: 13, color: "var(--gc-text2)", marginBottom: 12 }}>
          {sim.worm.infected} infected · {sim.worm.impacted} impacted · ${(sim.worm.financial_loss / 1000).toFixed(0)}k loss
        </div>
        {report && <div style={{ display: "flex", justifyContent: "center", gap: 20, fontSize: 13, color: "var(--gc-muted)", marginBottom: 14 }}>
          {Object.entries(report.teams || {}).map(([r, t]: any) => <span key={r}>{r.toUpperCase()} {t.score}</span>)}
        </div>}
        <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
          {report && <button className="btn btn-primary" onClick={() => setShowReport(true)}><i className="fa fa-file-lines" /> View full report</button>}
          <button className="btn" onClick={onClose}><i className="fa fa-magnifying-glass" /> Stay &amp; review the range</button>
          <button className="btn" onClick={onQuit}><i className="fa fa-rotate-right" /> Back to scenarios</button>
        </div>
        {report && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 8 }}><i className="fa fa-floppy-disk" /> Saved to Reports &amp; AAR (open it there to view or print as PDF).</div>}
      </div>
    </div>
  );
}
