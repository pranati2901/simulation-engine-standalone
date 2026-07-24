import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import SocTerminal, { type SocTerminalHandle } from "../components/SocTerminal";
import HospitalMap from "../components/HospitalMap";
import ToolPanel from "../components/tools/ToolPanels";
import { getActiveTools } from "../components/tools/ToolRegistry";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface Option { id: string; text: string }
interface Action { id: string; label: string; quality: string }
interface SceneData {
  index: number; title: string; story: string;
  mitre: { id: string; name: string };
  telemetry: { sev: string; source: string; msg: string }[];
  identify: { prompt: string; options: Option[] };
  micro_teach: string;
}
interface RespondData { selection: string; actions: Action[] }
interface DecisionResult {
  identify_correct: boolean; response_quality: string;
  feedback: { identify_message: string; response_message: string; micro_teach: string };
  network: NetworkState; hard_fail: boolean;
}
interface NetworkState {
  containment_index: number; infected: number; encrypted: number;
  isolated: number; total_hosts: number; backup_destroyed: boolean; infected_ratio: number;
}
interface SessionSnap {
  session_id: string; learner_name: string; scenario_id: string; mode: string; status: string;
  phase: string; scene_index: number; scene_sub: string | null;
  network: NetworkState;
  scores: { detection: number; response: number; containment: number; speed: number; knowledge: number; composite: number };
  outcome: string | null; grade: string | null; passed: boolean | null;
}
interface QuizItem { id: string; question: string; options: { id: string; text: string }[] }
interface FinalResult {
  composite: number; grade: string; passed: boolean; quiz_correct: number; quiz_total: number;
  outcome: string; network: NetworkState;
  dimensions: { detection: number; response: number; containment: number; speed: number; knowledge: number };
  certificate?: { certificate_id: string; verify_code: string; learner_name: string; scenario_title: string; composite_score: number; grade: string; issued_at: string } | null;
}
interface TimelineEntry {
  scene_index: number; title: string; mitre: { id: string; name: string };
  identify_correct: boolean; response_quality: string;
}

const QUALITY_COLOR: Record<string, string> = { optimal: "var(--gc-green)", acceptable: "var(--gc-yellow)", poor: "var(--gc-red)" };

/* ------------------------------------------------------------------ */
/*  Stage Complete Overlay                                             */
/* ------------------------------------------------------------------ */
function StageNotification({ scene, result, onContinue }: {
  scene: SceneData; result: DecisionResult; onContinue: () => void;
}) {
  const qColor = QUALITY_COLOR[result.response_quality] || "var(--gc-muted)";
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center", animation: "fadeIn 0.3s" }}>
      <div style={{ maxWidth: 520, width: "90%", textAlign: "center" }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--gc-muted)", letterSpacing: 3, marginBottom: 8 }}>
          STAGE {scene.index + 1} COMPLETE
        </div>
        <div style={{ fontSize: 28, fontWeight: 800, marginBottom: 4 }}>{scene.title}</div>
        {scene.mitre.id && <div style={{ fontSize: 13, color: "var(--gc-accent)", marginBottom: 20 }}>{scene.mitre.id} — {scene.mitre.name}</div>}

        <div style={{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 20 }}>
          <div style={{ padding: "12px 20px", borderRadius: 10,
            background: result.identify_correct ? "rgba(59,167,118,0.1)" : "rgba(200,65,62,0.1)",
            border: `1px solid ${result.identify_correct ? "var(--gc-green)" : "var(--gc-red)"}` }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: result.identify_correct ? "var(--gc-green)" : "var(--gc-red)" }}>
              {result.identify_correct ? "✓" : "✗"}
            </div>
            <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 4 }}>Identification</div>
          </div>
          <div style={{ padding: "12px 20px", borderRadius: 10,
            background: `${qColor}15`, border: `1px solid ${qColor}` }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: qColor, textTransform: "uppercase" }}>
              {result.response_quality === "optimal" ? "★" : result.response_quality === "acceptable" ? "◉" : "✗"}
            </div>
            <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 4 }}>{result.response_quality}</div>
          </div>
          <div style={{ padding: "12px 20px", borderRadius: 10,
            background: "rgba(224,164,88,0.1)", border: "1px solid var(--gc-accent)" }}>
            <div style={{ fontSize: 24, fontWeight: 800, fontFamily: "var(--mono)", color: "var(--gc-accent)" }}>
              {result.network.containment_index}
            </div>
            <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 4 }}>Containment</div>
          </div>
        </div>

        {result.feedback.micro_teach && (
          <div style={{ fontSize: 13, color: "var(--gc-body)", lineHeight: 1.7, marginBottom: 20, padding: "12px 16px",
            background: "rgba(224,164,88,0.06)", borderRadius: 8, textAlign: "left" }}>
            <span style={{ color: "var(--gc-accent)", fontWeight: 600 }}>KEY INSIGHT: </span>
            {result.feedback.micro_teach}
          </div>
        )}

        {result.hard_fail && (
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--gc-red)", marginBottom: 16, padding: "10px 16px",
            background: "rgba(200,65,62,0.1)", borderRadius: 8, border: "1px solid var(--gc-red)" }}>
            ⚠ CONTAINMENT FAILED — Infection exceeded 80% threshold
          </div>
        )}

        <div style={{ display: "flex", gap: 12, fontSize: 12, justifyContent: "center", marginBottom: 20, color: "var(--gc-muted)" }}>
          <span>Infected: <strong style={{ color: "var(--gc-red)" }}>{result.network.infected}</strong></span>
          <span>Encrypted: <strong style={{ color: "var(--gc-red)" }}>{result.network.encrypted}</strong></span>
          <span>Isolated: <strong style={{ color: "var(--gc-blue)" }}>{result.network.isolated}</strong></span>
          {result.network.backup_destroyed && <span style={{ color: "var(--gc-red)", fontWeight: 700 }}>BACKUP LOST</span>}
        </div>

        <button className="btn btn-primary" style={{ padding: "12px 32px", fontSize: 15 }} onClick={onContinue}>
          {result.hard_fail ? "Proceed to Debrief" : `Continue to Stage ${scene.index + 2} →`}
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */
export default function Tripwire() {
  const { scenarioId } = useParams();
  const [phase, setPhase] = useState<"start" | "briefing" | "playing" | "debrief" | "quiz" | "results">("start");
  const [session, setSession] = useState<SessionSnap | null>(null);
  const [scene, setScene] = useState<SceneData | null>(null);
  const [respond, setRespond] = useState<RespondData | null>(null);
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [showNotification, setShowNotification] = useState(false);
  const [quiz, setQuiz] = useState<QuizItem[]>([]);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [identifyChoice, setIdentifyChoice] = useState("");
  const [selectedActions, setSelectedActions] = useState<string[]>([]);
  const [confidence, setConfidence] = useState(3);
  const [subPhase, setSubPhase] = useState<"observe" | "identify" | "respond">("observe");
  const [name, setName] = useState("");
  const [mode, setMode] = useState("standard");
  const [sceneStartTime, setSceneStartTime] = useState(0);
  const [scenarioTitle, setScenarioTitle] = useState("");
  const [segments, setSegments] = useState<any[]>([]);
  const [timer, setTimer] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const termRef = useRef<SocTerminalHandle>(null);

  const send = useCallback((data: any) => {
    wsRef.current?.send(JSON.stringify(data));
  }, []);

  /* ---- Animate telemetry into terminal ---- */
  const streamTelemetry = useCallback((telemetry: { sev: string; source: string; msg: string }[], delay = 400) => {
    telemetry.forEach((t, i) => {
      setTimeout(() => {
        termRef.current?.writeAlert(t.sev, t.source, t.msg);
      }, i * delay);
    });
  }, []);

  /* ---- WebSocket handler ---- */
  const connect = useCallback((sid: string) => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    // Same-origin — the SimCore dev proxy / gateway routes /ws/* to the cyber backend.
    const ws = new WebSocket(`${proto}//${location.host}/ws/tripwire/${sid}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.session) setSession(msg.session);

      switch (msg.type) {
        case "init":
          setScenarioTitle(msg.scenario?.title || "");
          setSegments(msg.scenario?.segments || []);
          setPhase("briefing");
          break;

        case "scene": {
          const sc = msg.scene as SceneData;
          setScene(sc);
          setRespond(null);
          setDecisionResult(null);
          setShowNotification(false);
          setIdentifyChoice("");
          setSelectedActions([]);
          setSubPhase("observe");
          setSceneStartTime(Date.now());
          setPhase("playing");

          // Start timer for pressure mode
          if (timerRef.current) clearInterval(timerRef.current);
          if (mode === "pressure") {
            setTimer(30); // 30 seconds per scene in pressure mode
            timerRef.current = setInterval(() => {
              setTimer(prev => {
                if (prev <= 1) {
                  if (timerRef.current) clearInterval(timerRef.current);
                  return 0;
                }
                return prev - 1;
              });
            }, 1000);
          } else {
            setTimer(0);
          }

          // Stream into terminal
          termRef.current?.writeStage(sc.index, sc.title, sc.mitre.id);
          termRef.current?.writeStory(sc.story);
          streamTelemetry(sc.telemetry, 600);

          // Auto-advance to identify after telemetry streams
          setTimeout(() => setSubPhase("identify"), sc.telemetry.length * 600 + 500);
          break;
        }

        case "respond_ready":
          setRespond(msg.respond);
          setSubPhase("respond");
          termRef.current?.writeln("\x1b[1;32m  [CONSOLE] Response options available. Choose your defensive action.\x1b[0m");
          break;

        case "decision_result": {
          const r = msg.result as DecisionResult;
          setDecisionResult(r);
          if (timerRef.current) { clearInterval(timerRef.current); setTimer(0); }
          termRef.current?.writeFeedback(r.identify_correct, r.response_quality, r.feedback.micro_teach);
          if (r.hard_fail) {
            termRef.current?.writeNotification("⚠  CONTAINMENT FAILED — HARD FAIL THRESHOLD REACHED", "\x1b[1;31m");
          }
          setShowNotification(true);
          break;
        }

        case "scene_finished":
          if (msg.session.phase === "debrief") {
            send({ action: "get_debrief" });
          }
          break;

        case "debrief":
          setTimeline(msg.timeline);
          termRef.current?.writeNotification("DEBRIEF — Incident Timeline Review", "\x1b[1;36m");
          setPhase("debrief");
          break;

        case "assessment":
          setQuiz(msg.quiz);
          setQuizAnswers({});
          setPhase("quiz");
          break;

        case "results":
          setFinalResult(msg.result);
          setPhase("results");
          break;
      }
    };
    ws.onclose = () => {
      // Auto-reconnect after 2 seconds if session is still in progress
      setTimeout(() => {
        if (wsRef.current === ws) connect(sid);
      }, 2000);
    };
    ws.onerror = () => ws.close();
  }, [send, streamTelemetry]);

  const startSession = async () => {
    if (!name.trim()) return;
    const resp = await fetch("/api/tripwire/sessions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ learner_name: name.trim(), mode, scenario_id: scenarioId || "scn-wannacry-w1" }),
    });
    const data = await resp.json();
    connect(data.session_id);
  };

  useEffect(() => () => {
    const ws = wsRef.current;
    if (ws) { wsRef.current = null; ws.close(); }
  }, []);

  const handleNotificationContinue = () => {
    setShowNotification(false);
    if (decisionResult?.hard_fail || (session?.scene_index ?? 0) >= 10) {
      send({ action: "finish_scene" });
    } else {
      send({ action: "finish_scene" });
      // finish_scene triggers scene_finished which auto-sends start_scene for next
      setTimeout(() => {
        send({ action: "start_scene", scene_index: (session?.scene_index ?? 0) + 1 });
      }, 300);
    }
  };

  /* ================================================================ */
  /*  RENDER                                                           */
  /* ================================================================ */

  /* ---- START ---- */
  if (phase === "start") return (
    <div style={{ maxWidth: 550, margin: "50px auto", textAlign: "center" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-red)", letterSpacing: 3, marginBottom: 8 }}>OPERATION TRIPWIRE</div>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Anatomy of a Ransomware Worm</h1>
      <p style={{ color: "var(--gc-muted)", marginBottom: 28, fontSize: 13 }}>
        Step into the SOC at Mercy Regional Health Network. A WannaCry-style worm is about to sweep through 250 hosts.
        Identify each attack stage. Choose your response. Contain it before the hospital goes dark.
      </p>
      <div className="card" style={{ textAlign: "left", padding: 20 }}>
        <label style={{ fontSize: 11, fontWeight: 600, color: "var(--gc-muted)", display: "block", marginBottom: 4 }}>Analyst Name</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name..."
          style={{ width: "100%", padding: "10px 12px", background: "var(--gc-bg)", border: "1px solid var(--gc-border)", borderRadius: 6, color: "var(--gc-text)", fontSize: 14, marginBottom: 14, fontFamily: "var(--mono)" }}
          onKeyDown={e => e.key === "Enter" && startSession()} />
        <label style={{ fontSize: 11, fontWeight: 600, color: "var(--gc-muted)", display: "block", marginBottom: 4 }}>Difficulty</label>
        <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
          {(["guided", "standard", "pressure"] as const).map(m => (
            <button key={m} onClick={() => setMode(m)}
              className={mode === m ? "btn btn-primary" : "btn"}
              style={{ flex: 1, textTransform: "capitalize", fontSize: 12, padding: "8px 0" }}>
              {m === "guided" ? "🟢 Guided" : m === "standard" ? "🟡 Standard" : "🔴 Pressure"}
            </button>
          ))}
        </div>
        <button className="btn btn-primary" style={{ width: "100%", padding: "12px 0", fontSize: 14 }}
          onClick={startSession} disabled={!name.trim()}>
          Enter the SOC
        </button>
      </div>
    </div>
  );

  /* ---- BRIEFING ---- */
  if (phase === "briefing") return (
    <div style={{ maxWidth: 650, margin: "40px auto" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-red)", letterSpacing: 3, marginBottom: 8 }}>INCOMING ALERT</div>
      <h2 style={{ fontSize: 22, marginBottom: 12 }}>Mission Briefing</h2>
      <div style={{ background: "#0a0e16", borderRadius: 8, padding: 24, fontFamily: "var(--mono)", fontSize: 14, lineHeight: 2, color: "var(--gc-text)", marginBottom: 20, border: "1px solid var(--gc-border)" }}>
        <div style={{ color: "var(--gc-red)", fontWeight: 700, marginBottom: 8 }}>PRIORITY: CRITICAL</div>
        <div style={{ color: "var(--gc-muted)", fontSize: 12, marginBottom: 12 }}>FROM: SOC MANAGER | TO: TIER-2 ANALYST | TIME: 16:42 FRI</div>
        <p style={{ fontStyle: "italic", color: "#c8d6e5" }}>
          "Most of the team has gone home. You are the analyst on call at Mercy Regional.
          A radiology workstation that nobody has patched in months is about to make this the longest night of your career.
          Watch the wire. Name what you see. Act before it spreads."
        </p>
        <div style={{ borderTop: "1px solid var(--gc-border)", marginTop: 16, paddingTop: 12, fontSize: 12, color: "var(--gc-muted)" }}>
          ENVIRONMENT: 250 hosts · 7 segments · Radiology, Clinical, Admin, DC, File Servers, Backup, SOC<br/>
          THREAT: WannaCry-class ransomware worm · SMBv1 exploitation · Self-propagating<br/>
          OBJECTIVE: Identify each attack stage · Contain the outbreak · Protect backup infrastructure
        </div>
      </div>
      <button className="btn btn-primary" style={{ width: "100%", padding: "14px 0", fontSize: 15 }}
        onClick={() => send({ action: "start_scene", scene_index: 0 })}>
        <i className="fa fa-terminal" /> Connect to SOC Console
      </button>
    </div>
  );

  /* ---- PLAYING (main SOC console) ---- */
  if (phase === "playing" && session) return (
    <>
      {showNotification && decisionResult && scene && (
        <StageNotification scene={scene} result={decisionResult} onContinue={handleNotificationContinue} />
      )}

      {/* Status strip */}
      {scene && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 12px", marginBottom: 8, background: "var(--gc-surface)", borderRadius: 6, fontSize: 12 }}>
          <span style={{ fontWeight: 700, color: "var(--gc-red)", letterSpacing: 1, fontSize: 10 }}>STAGE {session.scene_index + 1}</span>
          <span style={{ fontWeight: 600 }}>{scene.title}</span>
          {scene.mitre.id && <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "rgba(224,164,88,.12)", color: "var(--gc-accent)" }}>{scene.mitre.id}</span>}
          <div style={{ flex: 1 }} />
          <span style={{ fontFamily: "var(--mono)", color: session.network.containment_index > 60 ? "var(--gc-green)" : session.network.containment_index > 30 ? "var(--gc-yellow)" : "var(--gc-red)" }}>
            CI: {session.network.containment_index}%
          </span>
          <span style={{ fontFamily: "var(--mono)", color: "var(--gc-red)" }}>INF: {session.network.infected}</span>
          <span style={{ fontFamily: "var(--mono)", color: "var(--gc-blue)" }}>ISO: {session.network.isolated}</span>
          {mode === "pressure" && timer > 0 && (
            <span style={{ fontFamily: "var(--mono)", fontWeight: 700, padding: "2px 8px", borderRadius: 4,
              color: timer <= 10 ? "#fff" : "var(--gc-yellow)",
              background: timer <= 10 ? "var(--gc-red)" : "rgba(230,180,0,0.15)",
              animation: timer <= 5 ? "pulse-red 0.8s infinite" : "none" }}>
              ⏱ {timer}s
            </span>
          )}
        </div>
      )}

      {/* @media handled via minmax — stacks on narrow screens */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(300px, 400px)", gap: 12, height: scene ? "calc(100vh - 140px)" : "calc(100vh - 100px)" }}>
        {/* LEFT: Terminal + Decision Panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, minHeight: 0 }}>
          {/* Terminal */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <SocTerminal ref={termRef} />
          </div>

          {/* Decision Panel (slides in when active) */}
          {subPhase === "identify" && scene && (
            <div style={{ background: "var(--gc-surface)", borderRadius: 8, padding: 14, border: "1px solid var(--gc-accent)", maxHeight: 280, overflowY: "auto" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--gc-accent)", marginBottom: 8 }}>
                <i className="fa fa-search" /> IDENTIFY: {scene.identify.prompt}
              </div>
              {scene.identify.options.map(opt => (
                <label key={opt.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", marginBottom: 4, borderRadius: 6, cursor: "pointer", fontSize: 13,
                  background: identifyChoice === opt.id ? "rgba(224,164,88,0.1)" : "transparent",
                  border: `1px solid ${identifyChoice === opt.id ? "var(--gc-accent)" : "transparent"}` }}
                  onClick={() => setIdentifyChoice(opt.id)}>
                  <input type="radio" name="id" checked={identifyChoice === opt.id} readOnly style={{ accentColor: "var(--gc-accent)" }} />
                  {opt.text}
                </label>
              ))}
              <button className="btn btn-primary" style={{ width: "100%", marginTop: 8, fontSize: 13 }}
                disabled={!identifyChoice}
                onClick={() => {
                  termRef.current?.writeln(`\x1b[36m  [ANALYST] Identified: ${scene.identify.options.find(o => o.id === identifyChoice)?.text}\x1b[0m`);
                  send({ action: "submit_identify", identify_choice: identifyChoice });
                }}>
                Submit Identification
              </button>
            </div>
          )}

          {subPhase === "respond" && respond && (
            <div style={{ background: "var(--gc-surface)", borderRadius: 8, padding: 14, border: "1px solid var(--gc-green)", maxHeight: 280, overflowY: "auto" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--gc-green)", marginBottom: 8 }}>
                <i className="fa fa-shield-alt" /> RESPOND: Choose defensive action{respond.selection === "multi" ? "s" : ""}
              </div>
              {respond.actions.map(act => (
                <label key={act.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", marginBottom: 4, borderRadius: 6, cursor: "pointer", fontSize: 13,
                  background: selectedActions.includes(act.id) ? "rgba(59,167,118,0.1)" : "transparent",
                  border: `1px solid ${selectedActions.includes(act.id) ? "var(--gc-green)" : "transparent"}` }}
                  onClick={() => {
                    if (respond.selection === "multi") {
                      setSelectedActions(prev => prev.includes(act.id) ? prev.filter(a => a !== act.id) : [...prev, act.id]);
                    } else {
                      setSelectedActions([act.id]);
                    }
                  }}>
                  <input type={respond.selection === "multi" ? "checkbox" : "radio"} name="resp"
                    checked={selectedActions.includes(act.id)} readOnly style={{ accentColor: "var(--gc-green)" }} />
                  {act.label}
                </label>
              ))}
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: 11, color: "var(--gc-muted)" }}>
                <span>Confidence:</span>
                <input type="range" min={1} max={5} value={confidence} onChange={e => setConfidence(Number(e.target.value))}
                  style={{ flex: 1, accentColor: "var(--gc-accent)" }} />
                <span style={{ fontFamily: "var(--mono)", color: "var(--gc-text)", minWidth: 20 }}>{confidence}/5</span>
              </div>
              <button className="btn btn-primary" style={{ width: "100%", marginTop: 6, fontSize: 13, background: "var(--gc-green)" }}
                disabled={selectedActions.length === 0}
                onClick={() => {
                  termRef.current?.writeln(`\x1b[32m  [ANALYST] Response: ${selectedActions.join(", ")} (confidence: ${confidence}/5)\x1b[0m`);
                  send({
                    action: "submit_decision", identify_choice: identifyChoice,
                    actions: selectedActions, latency_ms: Date.now() - sceneStartTime,
                    confidence,
                  });
                }}>
                Confirm Response
              </button>
            </div>
          )}

          {subPhase === "observe" && (
            <div style={{ background: "var(--gc-surface)", borderRadius: 8, padding: 12, textAlign: "center", color: "var(--gc-muted)", fontSize: 13 }}>
              <span className="spinner" style={{ width: 12, height: 12, marginRight: 8 }} />
              Telemetry streaming... Analyzing incoming alerts...
            </div>
          )}
        </div>

        {/* RIGHT: Map + Stats */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, minHeight: 0 }}>
          {/* Network Map */}
          <div style={{ background: "var(--gc-card)", borderRadius: 8, padding: 8, border: "1px solid var(--gc-border)" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-muted)", padding: "4px 8px", letterSpacing: 1 }}>
              NETWORK MAP — MERCY REGIONAL
            </div>
            <HospitalMap network={session.network} sceneIndex={session.scene_index} height={360} segments={segments} />
          </div>

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div className="stat-card">
              <div className="stat-label">Containment</div>
              <div className="stat-value" style={{ fontSize: 28, color: session.network.containment_index > 60 ? "var(--gc-green)" : session.network.containment_index > 30 ? "var(--gc-yellow)" : "var(--gc-red)" }}>
                {session.network.containment_index}
              </div>
              <div style={{ height: 4, borderRadius: 2, background: "var(--gc-border)", marginTop: 6 }}>
                <div style={{ height: "100%", borderRadius: 2, width: `${session.network.containment_index}%`,
                  background: session.network.containment_index > 60 ? "var(--gc-green)" : session.network.containment_index > 30 ? "var(--gc-yellow)" : "var(--gc-red)" }} />
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Infected</div>
              <div className="stat-value" style={{ fontSize: 28, color: "var(--gc-red)" }}>{session.network.infected}</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{Math.round(session.network.infected / 250 * 100)}% of network</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Encrypted</div>
              <div className="stat-value" style={{ fontSize: 28, color: "#C8413E" }}>{session.network.encrypted}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Isolated</div>
              <div className="stat-value" style={{ fontSize: 28, color: "var(--gc-blue)" }}>{session.network.isolated}</div>
            </div>
          </div>

          {/* Active Tools */}
          {scene && (() => {
            const activeTools = getActiveTools(session.scenario_id || scenarioId || "scn-wannacry-w1", session.scene_index);
            if (activeTools.length === 0) return null;
            return (
              <div style={{ display: "grid", gap: 6, maxHeight: 280, overflowY: "auto" }}>
                {activeTools.slice(0, 4).map(t => (
                  <ToolPanel key={t.id} tool={t} telemetry={scene.telemetry} sceneIndex={session.scene_index}
                    network={session.network} scenarioId={session.scenario_id || ""} />
                ))}
              </div>
            );
          })()}

          {/* Stage Progress */}
          <div style={{ background: "var(--gc-card)", borderRadius: 8, padding: 10, border: "1px solid var(--gc-border)" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-muted)", marginBottom: 6, letterSpacing: 1 }}>
              KILL CHAIN — STAGE {(session.scene_index ?? 0) + 1}/{session.scores ? 11 : 11}
            </div>
            <div style={{ display: "flex", gap: 3 }}>
              {Array.from({ length: 11 }, (_, i) => (
                <div key={i} title={`Stage ${i + 1}`} style={{ flex: 1, height: 8, borderRadius: 3,
                  background: i < session.scene_index ? "var(--gc-green)" : i === session.scene_index ? "var(--gc-accent)" : "var(--gc-border)",
                  transition: "background 0.3s" }} />
              ))}
            </div>
          </div>

          {/* Scores */}
          <div style={{ background: "var(--gc-card)", borderRadius: 8, padding: 10, border: "1px solid var(--gc-border)" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-muted)", marginBottom: 6, letterSpacing: 1 }}>RUNNING SCORE</div>
            {(["detection", "response", "containment"] as const).map(dim => (
              <div key={dim} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 10, width: 70, color: "var(--gc-muted)", textTransform: "capitalize" }}>{dim}</span>
                <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--gc-border)" }}>
                  <div style={{ height: "100%", borderRadius: 3, width: `${session.scores[dim]}%`,
                    background: session.scores[dim] >= 70 ? "var(--gc-green)" : session.scores[dim] >= 40 ? "var(--gc-yellow)" : "var(--gc-red)", transition: "width 0.5s" }} />
                </div>
                <span style={{ fontSize: 11, fontFamily: "var(--mono)", width: 30, textAlign: "right", color: "var(--gc-text)" }}>{Math.round(session.scores[dim])}</span>
              </div>
            ))}
          </div>

          {/* Backup Status */}
          {session.network.backup_destroyed && (
            <div style={{ background: "rgba(200,65,62,0.1)", border: "1px solid var(--gc-red)", borderRadius: 8, padding: 10, textAlign: "center" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--gc-red)" }}>⚠ BACKUP SERVER COMPROMISED</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>Recovery options severely limited</div>
            </div>
          )}
        </div>
      </div>
    </>
  );

  /* ---- DEBRIEF ---- */
  if (phase === "debrief") return (
    <div style={{ maxWidth: 800, margin: "30px auto" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-accent)", letterSpacing: 3, marginBottom: 6 }}>AFTER-ACTION DEBRIEF</div>
      <h2 style={{ fontSize: 22, marginBottom: 16 }}>Incident Timeline</h2>
      <div style={{ display: "flex", gap: 3, marginBottom: 16 }}>
        {timeline.map((t, i) => (
          <div key={i} style={{ flex: 1, height: 10, borderRadius: 4,
            background: t.identify_correct && t.response_quality === "optimal" ? "var(--gc-green)" : t.identify_correct ? "var(--gc-yellow)" : "var(--gc-red)" }} title={t.title} />
        ))}
      </div>
      {timeline.map((t, i) => (
        <div key={i} className="card" style={{ padding: 12, marginBottom: 6, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, flexShrink: 0,
            background: t.identify_correct && t.response_quality === "optimal" ? "rgba(59,167,118,.15)" : t.identify_correct ? "rgba(230,180,0,.15)" : "rgba(200,65,62,.15)",
            color: t.identify_correct && t.response_quality === "optimal" ? "var(--gc-green)" : t.identify_correct ? "var(--gc-yellow)" : "var(--gc-red)" }}>{i + 1}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{t.title}</div>
            {t.mitre.id && <span style={{ fontSize: 10, color: "var(--gc-accent)" }}>{t.mitre.id}</span>}
          </div>
          <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, fontWeight: 600, background: t.identify_correct ? "rgba(59,167,118,.12)" : "rgba(200,65,62,.12)", color: t.identify_correct ? "var(--gc-green)" : "var(--gc-red)" }}>
            {t.identify_correct ? "✓ ID" : "✗ ID"}
          </span>
          <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, fontWeight: 600, textTransform: "uppercase",
            background: `${QUALITY_COLOR[t.response_quality]}15`, color: QUALITY_COLOR[t.response_quality] }}>{t.response_quality}</span>
        </div>
      ))}
      <button className="btn btn-primary" style={{ width: "100%", marginTop: 14, padding: "12px 0", fontSize: 14 }}
        onClick={() => send({ action: "start_assessment" })}>
        <i className="fa fa-clipboard-check" /> Knowledge Assessment
      </button>
    </div>
  );

  /* ---- QUIZ ---- */
  if (phase === "quiz") return (
    <div style={{ maxWidth: 700, margin: "30px auto" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-accent)", letterSpacing: 3, marginBottom: 6 }}>KNOWLEDGE ASSESSMENT</div>
      <h2 style={{ fontSize: 20, marginBottom: 16 }}>Test Your Understanding</h2>
      {quiz.map((q, qi) => (
        <div key={q.id} className="card" style={{ padding: 14, marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <span style={{ color: "var(--gc-accent)" }}>Q{qi + 1}.</span> {q.question}
          </div>
          {q.options.map(opt => (
            <label key={opt.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", marginBottom: 3, borderRadius: 6, cursor: "pointer", fontSize: 13,
              background: quizAnswers[q.id] === opt.id ? "rgba(224,164,88,.08)" : "transparent",
              border: `1px solid ${quizAnswers[q.id] === opt.id ? "var(--gc-accent)" : "transparent"}` }}
              onClick={() => setQuizAnswers(prev => ({ ...prev, [q.id]: opt.id }))}>
              <input type="radio" name={q.id} checked={quizAnswers[q.id] === opt.id} readOnly style={{ accentColor: "var(--gc-accent)" }} />
              {opt.text}
            </label>
          ))}
        </div>
      ))}
      <button className="btn btn-primary" style={{ width: "100%", padding: "12px 0", fontSize: 14 }}
        disabled={Object.keys(quizAnswers).length < quiz.length}
        onClick={() => send({
          action: "submit_quiz",
          answers: Object.entries(quizAnswers).map(([item_id, response]) => ({ item_id, response })),
        })}>
        Submit ({Object.keys(quizAnswers).length}/{quiz.length})
      </button>
    </div>
  );

  /* ---- RESULTS ---- */
  if (phase === "results" && finalResult && session) return (
    <div style={{ maxWidth: 750, margin: "30px auto" }}>
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: finalResult.passed ? "var(--gc-green)" : "var(--gc-red)", letterSpacing: 3, marginBottom: 6 }}>
          {finalResult.passed ? "SIMULATION COMPLETE" : "RETAKE RECOMMENDED"}
        </div>
        <div style={{ fontSize: 52, fontWeight: 800, fontFamily: "var(--mono)", color: finalResult.passed ? "var(--gc-green)" : "var(--gc-red)" }}>{Math.round(finalResult.composite)}</div>
        <div style={{ fontSize: 17, fontWeight: 600, marginTop: 4 }}>{finalResult.grade}</div>
        <div style={{ fontSize: 13, color: "var(--gc-muted)", marginTop: 6 }}>Outcome: {finalResult.outcome}</div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>
        {(["detection", "response", "containment", "speed", "knowledge"] as const).map(dim => (
          <div key={dim} className="stat-card" style={{ textAlign: "center" }}>
            <div className="stat-value" style={{ fontSize: 26, color: (finalResult.dimensions[dim] ?? 0) >= 70 ? "var(--gc-green)" : (finalResult.dimensions[dim] ?? 0) >= 50 ? "var(--gc-yellow)" : "var(--gc-red)" }}>
              {Math.round(finalResult.dimensions[dim] ?? 0)}
            </div>
            <div className="stat-label" style={{ textTransform: "capitalize" }}>{dim}</div>
            <div style={{ height: 4, borderRadius: 2, background: "var(--gc-border)", marginTop: 6 }}>
              <div style={{ height: "100%", borderRadius: 2, width: `${finalResult.dimensions[dim] ?? 0}%`,
                background: (finalResult.dimensions[dim] ?? 0) >= 70 ? "var(--gc-green)" : (finalResult.dimensions[dim] ?? 0) >= 50 ? "var(--gc-yellow)" : "var(--gc-red)" }} />
            </div>
          </div>
        ))}
      </div>
      <div className="card" style={{ padding: 16, marginBottom: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, textAlign: "center" }}>
          <div><div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--mono)" }}>{finalResult.network.infected}</div><div style={{ fontSize: 10, color: "var(--gc-muted)" }}>Infected</div></div>
          <div><div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--mono)", color: "var(--gc-red)" }}>{finalResult.network.encrypted}</div><div style={{ fontSize: 10, color: "var(--gc-muted)" }}>Encrypted</div></div>
          <div><div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--mono)", color: "var(--gc-blue)" }}>{finalResult.network.isolated}</div><div style={{ fontSize: 10, color: "var(--gc-muted)" }}>Isolated</div></div>
          <div><div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--mono)", color: finalResult.network.backup_destroyed ? "var(--gc-red)" : "var(--gc-green)" }}>{finalResult.network.backup_destroyed ? "LOST" : "SAFE"}</div><div style={{ fontSize: 10, color: "var(--gc-muted)" }}>Backup</div></div>
        </div>
      </div>
      <div className="card" style={{ padding: 14 }}>
        <span style={{ fontWeight: 700, color: "var(--gc-accent)" }}>{finalResult.quiz_correct}/{finalResult.quiz_total}</span>
        <span style={{ color: "var(--gc-muted)" }}> knowledge assessment questions correct ({Math.round(finalResult.quiz_correct / finalResult.quiz_total * 100)}%)</span>
      </div>
      {finalResult.certificate && (
        <div className="card" style={{ padding: 20, marginTop: 12, border: "1px solid var(--gc-green)", background: "rgba(59,167,118,0.04)", textAlign: "center" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-green)", letterSpacing: 2, marginBottom: 6 }}>CERTIFICATE OF COMPLETION</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>{finalResult.certificate.learner_name}</div>
          <div style={{ fontSize: 13, color: "var(--gc-body)", marginBottom: 8 }}>{finalResult.certificate.scenario_title}</div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            Score: <strong style={{ color: "var(--gc-green)" }}>{finalResult.certificate.composite_score}</strong> — {finalResult.certificate.grade}
          </div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 14, fontWeight: 700, color: "var(--gc-accent)", margin: "10px 0", padding: "8px 16px", background: "rgba(224,164,88,0.08)", borderRadius: 6, display: "inline-block" }}>
            {finalResult.certificate.verify_code}
          </div>
          <div style={{ fontSize: 10, color: "var(--gc-muted)" }}>Verification code · Issued {finalResult.certificate.issued_at}</div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
        <button className="btn" style={{ flex: 1, padding: "12px 0" }}
          onClick={() => window.print()}>
          <i className="fa fa-file-pdf" /> Export PDF
        </button>
        <button className="btn btn-primary" style={{ flex: 1, padding: "12px 0" }}
          onClick={() => { setPhase("start"); wsRef.current?.close(); }}>
          <i className="fa fa-redo" /> New Simulation
        </button>
      </div>
    </div>
  );

  return <div style={{ padding: 40, color: "var(--gc-muted)" }}><span className="spinner" /> Loading...</div>;
}
