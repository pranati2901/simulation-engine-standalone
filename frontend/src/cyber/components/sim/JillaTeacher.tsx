/**
 * JillaTeacher v7 — Jilla comes, teaches, goes.
 *
 * Flow:
 * 1. Sim loads → Jilla slides in, explains what to do
 * 2. After 8s → auto-minimizes to FAB so student can work
 * 3. Student uses a tool → Jilla slides back in, reacts, explains next step
 * 4. After explaining → auto-minimizes again
 * 5. Student clicks FAB anytime → Jilla opens, can ask questions
 *
 * She's a person who comes and goes, not a permanent sidebar.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import PhaseCinematic from "./PhaseCinematic";
import IncidentTicker from "./IncidentTicker";
import { SpotlightGuide, AttackTimeline, JillaToast } from "./JillaVisuals";

interface Props {
  sim: any;
  myRole: string;
  scenarioId: string;
  sessionId?: string;
}

interface JillaMessage {
  id: number;
  type: "story" | "react" | "teach" | "user";
  text: string;
}

function JillaFace({ size = 40, state = "idle" }: { size?: number; state?: "idle" | "thinking" | "speaking" }) {
  const s = size;
  const eyeW = Math.round(s * 0.15), eyeH = Math.round(s * 0.2);
  const eyeTop = Math.round(s * 0.34), eyeGap = Math.round(s * 0.22);
  const mouthW = Math.round(s * 0.25), mouthBot = Math.round(s * 0.2);
  return (
    <div className={`jilla-face-avatar jilla-face-${state}`} style={{ width: s, height: s, minWidth: s }}>
      <div className="jilla-eye jilla-eye-l" style={{ width: eyeW, height: eyeH, top: eyeTop, left: `calc(50% - ${eyeGap}px)` }} />
      <div className="jilla-eye jilla-eye-r" style={{ width: eyeW, height: eyeH, top: eyeTop, left: `calc(50% + ${eyeGap - eyeW}px)` }} />
      <div className="jilla-mouth" style={{ width: mouthW, bottom: mouthBot, left: `calc(50% - ${mouthW / 2}px)` }} />
    </div>
  );
}

/** Draggable FAB — drag Jilla anywhere on screen, click to open */
function DraggableFab({ onClick, unread }: { onClick: () => void; unread: number }) {
  const [pos, setPos] = useState({ x: window.innerWidth - 66, y: window.innerHeight - 66 });
  const dragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const moved = useRef(false);
  const fabRef = useRef<HTMLButtonElement>(null);

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    moved.current = false;
    dragStart.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };
    fabRef.current?.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    moved.current = true;
    const nx = Math.max(0, Math.min(window.innerWidth - 50, e.clientX - dragStart.current.x));
    const ny = Math.max(0, Math.min(window.innerHeight - 50, e.clientY - dragStart.current.y));
    setPos({ x: nx, y: ny });
  };

  const onPointerUp = (e: React.PointerEvent) => {
    dragging.current = false;
    fabRef.current?.releasePointerCapture(e.pointerId);
    // Only open if it was a click, not a drag
    if (!moved.current) onClick();
  };

  return (
    <button ref={fabRef} className="jilla-fab"
      style={{ position: "fixed", left: pos.x, top: pos.y, zIndex: 9000, touchAction: "none", cursor: "grab" }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}>
      <JillaFace size={30} state="idle" />
      {unread > 0 && <span className="jilla-fab-badge">{unread}</span>}
    </button>
  );
}

export default function JillaTeacher({ sim, myRole, scenarioId, sessionId = "" }: Props) {
  const [messages, setMessages] = useState<JillaMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false); // starts closed, opens after intro
  const [inputFocused, setInputFocused] = useState(false);
  const [unread, setUnread] = useState(0);
  const [cinematicPhase, setCinematicPhase] = useState<{ phase: string; prevPhase?: string } | null>(null);
  const [spotlight, setSpotlight] = useState<{ target: string; label: string; sublabel?: string } | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "info" | "success" | "warning" | "action"; action?: { label: string; onClick: () => void } } | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const prevSimRef = useRef<any>(null);
  const lastEventTick = useRef(0);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const introDone = useRef(false);
  const seqRef = useRef(0);
  const userOpenedManually = useRef(false); // don't auto-close if user opened it

  // ---- Add message + open panel ----
  const addJillaMsg = useCallback((type: JillaMessage["type"], text: string) => {
    seqRef.current++;
    setMessages(prev => [...prev, { id: seqRef.current, type, text }]);
  }, []);

  // Jilla slides in, teaches, then auto-closes after delay
  const jillaAppearsAndTeaches = useCallback((type: JillaMessage["type"], text: string, autoCloseMs = 10000) => {
    addJillaMsg(type, text);
    setPanelOpen(true);
    userOpenedManually.current = false;

    // Auto-close after reading time
    if (autoCloseTimer.current) clearTimeout(autoCloseTimer.current);
    autoCloseTimer.current = setTimeout(() => {
      if (!userOpenedManually.current) {
        setPanelOpen(false);
      }
    }, autoCloseMs);
  }, [addJillaMsg]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // ---- Fire event to backend ----
  const fireEvent = useCallback(async (eventType: string, eventData: Record<string, any> = {}) => {
    lastEventTick.current = sim?.tick || 0;
    setLoading(true);
    try {
      const resp = await fetch("/api/jilla/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: eventType, session_id: sessionId,
          role: myRole, scenario_id: scenarioId,
          sim_state: sim || {}, event_data: eventData,
        }),
      });
      const data = await resp.json();

      // Calculate reading time: ~200 words/min, minimum 8s, max 15s
      const wordCount = (data.narration || "").split(" ").length + ((data.card?.body || "").split(" ").length);
      const readingMs = Math.min(15000, Math.max(8000, (wordCount / 200) * 60 * 1000));

      if (data.narration) {
        jillaAppearsAndTeaches("story", data.narration, readingMs);
      }
      if (data.card && data.card.title && data.card.body) {
        setTimeout(() => {
          addJillaMsg("teach", `**${data.card.title}**\n${data.card.body}`);
        }, 1500);
      }
      // Spotlight the next tool if the API says to
      if (data.spotlight_tool) {
        setTimeout(() => {
          setSpotlight({
            target: `[data-tool-id="${data.spotlight_tool}"], .tool-btn.next-step`,
            label: `Try this tool next`,
            sublabel: data.narration?.slice(0, 80),
          });
        }, 2000);
      }
    } catch { /* silent */ }
    setLoading(false);
  }, [sim, myRole, scenarioId, sessionId, jillaAppearsAndTeaches, addJillaMsg]);

  // ---- Intro: Jilla slides in and explains ----
  useEffect(() => {
    if (introDone.current || !myRole) return;
    introDone.current = true;

    fetch(`/api/jilla/intro?role=${myRole}&scenario_id=${scenarioId}`)
      .then(r => r.json())
      .then(data => {
        if (data.narration) {
          // Jilla appears, introduces herself, then auto-closes
          jillaAppearsAndTeaches("story", data.narration, 12000);
        }
        if (data.card?.body) {
          setTimeout(() => addJillaMsg("teach", data.card.body), 2500);
        }
      })
      .catch(() => {
        jillaAppearsAndTeaches("story", "Hey, I'm Jilla. I'll guide you through this. Look at the tool palette on the left and start with the first available tool.", 8000);
      });
  }, [myRole, scenarioId, jillaAppearsAndTeaches, addJillaMsg]);

  // ---- Event detection: watch sim changes ----
  useEffect(() => {
    const prev = prevSimRef.current;
    prevSimRef.current = sim;
    if (!sim || !prev) return;
    if (sim.tick - lastEventTick.current < 3) return;

    // Phase changed
    const curPhase = sim.guide?.phase;
    const prevPhase = prev.guide?.phase;
    if (curPhase && curPhase !== prevPhase) {
      setCinematicPhase({ phase: curPhase, prevPhase });
      fireEvent("phase_changed", { phase: curPhase, prev_phase: prevPhase });
      return;
    }

    // Tool used
    const curEvents = sim.events || [];
    const prevEvents = prev.events || [];
    if (curEvents.length > prevEvents.length) {
      const newEvts = curEvents.slice(prevEvents.length);
      const toolEvt = newEvts.find((e: any) => e.kind === "action" || e.kind === "response");
      if (toolEvt) {
        fireEvent("tool_used", {
          tool_id: toolEvt.data?.tool_id || "", tool_name: toolEvt.title || "",
          role: toolEvt.role || myRole,
        });
        return;
      }
    }

    // Host infected (batch: only if 2+ new)
    const curInfected = sim.worm?.infected || 0;
    const prevInfected = prev.worm?.infected || 0;
    if (curInfected > prevInfected && curInfected - prevInfected >= 2) {
      fireEvent("host_infected", { count: curInfected, delta: curInfected - prevInfected });
      return;
    }

    // Alert generated
    if ((sim.alerts?.length || 0) > (prev.alerts?.length || 0)) {
      const newAlert = sim.alerts[sim.alerts.length - 1];
      fireEvent("alert_generated", { alert: newAlert?.label, severity: newAlert?.severity });
      return;
    }

    // Blue actions
    if (sim.worm?.segmented && !prev.worm?.segmented) {
      fireEvent("tool_used", { tool_id: "segment", tool_name: "Network Segmentation", role: "blue" });
      return;
    }
    if (sim.worm?.kill_switch === "sinkholed" && prev.worm?.kill_switch !== "sinkholed") {
      fireEvent("tool_used", { tool_id: "sinkhole", tool_name: "Kill Switch Sinkhole", role: "blue" });
      return;
    }

    // Sim finished
    if (sim.finished && !prev.finished) {
      fireEvent("phase_changed", { phase: "Debrief", prev_phase: sim.guide?.phase });
    }
  }, [sim?.tick, fireEvent, myRole]);

  // ---- Idle: if student does nothing for 45s, Jilla nudges ----
  useEffect(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      fireEvent("idle_too_long", { idle_seconds: 45 });
    }, 45000);
    return () => { if (idleTimer.current) clearTimeout(idleTimer.current); };
  }, [sim?.guide?.progress?.done, fireEvent]);

  // ---- Student asks a question ----
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg = text.trim();
    setInput("");
    addJillaMsg("user", userMsg);
    setLoading(true);
    userOpenedManually.current = true; // don't auto-close when student is chatting
    try {
      const history = messages.slice(-8).map(m => ({
        role: m.type === "user" ? "user" : "assistant", content: m.text,
      }));
      const resp = await fetch("/api/jilla/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, role: myRole, scenario_id: scenarioId, sim_state: sim || {}, history }),
      });
      const data = await resp.json();
      addJillaMsg("react", data.message);
    } catch {
      addJillaMsg("react", "Sorry, couldn't process that. Try again?");
    }
    setLoading(false);
  }, [loading, messages, myRole, scenarioId, sim, addJillaMsg]);

  // ---- Keyboard: J to toggle ----
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "j" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const tag = (e.target as HTMLElement).tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        setPanelOpen(prev => {
          if (!prev) userOpenedManually.current = true;
          return !prev;
        });
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // ---- Render markdown ----
  const renderMd = (text: string) =>
    text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`"))
        return <code key={i} className="jilla-inline-code">{part.slice(1, -1)}</code>;
      return <span key={i}>{part}</span>;
    });

  const msgClass = (type: string) => {
    if (type === "story") return "jilla-msg-story";
    if (type === "react") return "jilla-msg-react";
    if (type === "teach") return "jilla-msg-teach";
    if (type === "user") return "jilla-msg-user";
    return "";
  };

  return (
    <>
      {/* News Ticker + Attack Timeline rendered inline in ScenarioWorkspace, not here */}

      {/* Spotlight Guide */}
      {spotlight && (
        <SpotlightGuide
          target={spotlight.target}
          label={spotlight.label}
          sublabel={spotlight.sublabel}
          onDismiss={() => setSpotlight(null)}
        />
      )}

      {/* Toast notification */}
      {toast && (
        <JillaToast
          message={toast.message}
          type={toast.type}
          action={toast.action}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Phase Cinematic */}
      {cinematicPhase && (
        <PhaseCinematic
          phase={cinematicPhase.phase}
          prevPhase={cinematicPhase.prevPhase}
          role={myRole}
          onDismiss={() => setCinematicPhase(null)}
        />
      )}

      {/* ---- Jilla Panel (slides in/out) ---- */}
      {panelOpen && (
        <div className="jilla-convo-panel">
          <div className="jilla-convo-header">
            <JillaFace size={38} state={loading ? "thinking" : "idle"} />
            <div className="jilla-convo-info">
              <div className="jilla-convo-name">Jilla</div>
              <div className="jilla-convo-status">
                {loading ? "thinking..." : `guiding you as ${myRole.toUpperCase()}`}
              </div>
            </div>
            <button className="jilla-convo-minimize" onClick={() => { setPanelOpen(false); userOpenedManually.current = false; }}
              title="Minimize (press J to reopen)">
              <i className="fa fa-chevron-right" />
            </button>
          </div>

          <div className="jilla-convo-messages" ref={scrollRef}>
            {messages.map(msg => (
              <div key={msg.id} className={`jilla-convo-msg ${msgClass(msg.type)}`}>
                {msg.type !== "user" && (
                  <JillaFace size={28} state={msg.type === "story" ? "speaking" : "idle"} />
                )}
                <div className={`jilla-convo-bubble ${msg.type === "user" ? "user-bubble" : ""}`}>
                  {renderMd(msg.text)}
                </div>
              </div>
            ))}

            {loading && (
              <div className="jilla-convo-msg jilla-msg-react">
                <JillaFace size={28} state="thinking" />
                <div className="jilla-convo-typing">
                  <span className="jilla-dot" />
                  <span className="jilla-dot" style={{ animationDelay: "0.15s" }} />
                  <span className="jilla-dot" style={{ animationDelay: "0.3s" }} />
                </div>
              </div>
            )}
          </div>

          <div className="jilla-convo-actions">
            {["What should I do?", "Tell me more", "Why does this matter?"].map(q => (
              <button key={q} className="jilla-convo-chip" onClick={() => sendMessage(q)} disabled={loading}>
                {q}
              </button>
            ))}
          </div>

          <div className={`jilla-convo-input-area${inputFocused ? " focused" : ""}`}>
            <form onSubmit={e => { e.preventDefault(); sendMessage(input); }} className="jilla-convo-form">
              <input value={input} onChange={e => setInput(e.target.value)} disabled={loading}
                placeholder="Ask Jilla anything..."
                className="jilla-convo-input"
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)} />
              <button type="submit" disabled={loading || !input.trim()}
                className={`jilla-convo-send${input.trim() ? " active" : ""}`}>
                <i className="fa fa-arrow-up" />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ---- FAB (draggable, always visible when panel is closed) ---- */}
      {!panelOpen && (
        <DraggableFab onClick={() => { setPanelOpen(true); setUnread(0); userOpenedManually.current = true; }}
          unread={unread} />
      )}
    </>
  );
}
