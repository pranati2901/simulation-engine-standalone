/**
 * JillaHackLab — slide-in drawer overlay for HackLab.
 *
 * The original HackLab layout stays untouched.
 * Jilla is a drawer that slides in from the right when you click the FAB.
 * She guides you step-by-step through the story. Click "Done" and
 * the message advances. Close the drawer to go back to hacking.
 */
import { useCallback, useEffect, useRef, useState } from "react";

interface HackCommand { cmd: string; note?: string }
interface HackPhase { name: string; objective: string; what: string; commands: HackCommand[] }
interface Mission {
  name: string; subtitle: string; brief: string; color: string;
  appName: string; appHost: string; flag: string; creds?: string;
  phases: HackPhase[];
}

interface Props {
  scenarioId: string;
  mission: Mission;
  completed: number;
  totalObjectives: number;
  onComplete: (phaseIdx: number) => void;
}

interface Msg {
  id: number;
  type: "story" | "instruction" | "reaction" | "user" | "complete";
  text: string;
  commands?: HackCommand[];
  phaseIdx?: number;
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

const INTROS: Record<string, string[]> = {
  "scn-wannacry-w1": [
    "Hey, I'm **Jilla**. I'll walk you through this hack step by step.",
    "**Mercy Regional Hospital** runs a patient portal with an injectable login and a forgotten database backup. Same sloppy security that let WannaCry through the NHS.",
    "Your target is `target-w1`. Let's start with recon — figure out what's running.",
  ],
  "scn-r5-phishing": [
    "Hey, I'm **Jilla**. Let me walk you through this one.",
    "**MediumCorp Financial's** SecureMail has a weak mailbox. Brute it, log in, find the diagnostics tool, and turn it into a command shell.",
    "Your target is `target-r5`. Let's map what we're dealing with.",
  ],
  "scn-c5-edr": [
    "Hey, I'm **Jilla**. This one's interesting.",
    "**GlobalTech's** EDR is down. The admin console is exposed and half the admins share `Welcome2024!`. Password spray, get in, use the runbook.",
    "Your target is `target-c5`. Let's go.",
  ],
};

const NARRATIONS: Record<string, Record<string, string>> = {
  "scn-wannacry-w1": {
    "Recon": "First things first — run an **nmap** scan to see what's exposed. Then check **robots.txt** — admins accidentally reveal hidden paths all the time.",
    "Find the exposure": "Now look for files that shouldn't be there. Try pulling `db_backup.sql`. If it's there, someone made a very expensive mistake.",
    "Exploit — SQL injection": "The login form doesn't sanitize inputs. Try `' OR '1'='1' --` as the username. This technique has been breaking systems since the 90s.",
    "Capture": "You're in. Grab the flag from the patient records. In the real world, this is where millions of medical records get stolen.",
  },
  "scn-r5-phishing": {
    "Recon": "Run **nmap** and curl the landing page. We're looking for SecureMail's login surface.",
    "Initial access": "Use **hydra** with rockyou.txt against user **jdoe**. In real REvil campaigns, this exact technique got them into hundreds of organizations.",
    "Foothold": "Log in properly and grab a session cookie. We need authenticated access.",
    "Execute & loot": "SecureMail's diagnostics tool doesn't sanitize input. Try `127.0.0.1;cat /flag` — that semicolon chains your command. Classic injection.",
  },
  "scn-c5-edr": {
    "Recon": "The EDR is blind. Let's see what's exposed. Run **nmap** against `target-c5`.",
    "Password spray": "Multiple admin accounts, one shared password. Create a users file and hit it with **hydra**. The password is `Welcome2024!`.",
    "Admin access": "One of them worked. Log in and grab the session cookie.",
    "Remote exec & loot": "The admin console has a runbook that runs commands on remote systems. Try `cat /flag` through it.",
  },
};

const REACTIONS: Record<string, Record<string, string>> = {
  "scn-wannacry-w1": {
    "Recon": "Good. You found the web server and robots.txt. Now let's see if they left something they shouldn't have...",
    "Find the exposure": "A full database dump on the web root. In a real pentest, that's a critical finding. Now let's use that knowledge to bypass the login.",
    "Exploit — SQL injection": "You're past the login. SQL injection worked because they concatenated user input directly into the query. OWASP Top 10 for 20 years, still works.",
    "Capture": "**Flag captured.** Every step used techniques that are decades old. The defenses are well-known. They just weren't implemented.",
  },
  "scn-r5-phishing": {
    "Recon": "SecureMail on port 80. Standard login form. Let's find the weak password...",
    "Initial access": "**jdoe / Password1.** Takes hydra about 30 seconds. This is the #1 way ransomware operators get initial access.",
    "Foothold": "You're in jdoe's inbox. Now let's find something exploitable inside the app...",
    "Execute & loot": "**Flag captured.** From brute-forced mailbox to remote code execution. Never trust user input in OS-interacting features.",
  },
  "scn-c5-edr": {
    "Recon": "Admin console found. Web-based on port 80. Let's spray that password...",
    "Password spray": "**alice.chen** fell. `Welcome2024!` — the exact pattern Conti used. Depressingly predictable.",
    "Admin access": "You're admin. EDR is still down. Nobody knows you're here. This is exactly how the Kaseya breach happened.",
    "Remote exec & loot": "**Flag captured.** You owned the admin console. In a real attack, this is where ransomware deployment begins.",
  },
};

export default function JillaHackLab({ scenarioId, mission, completed, totalObjectives, onComplete }: Props) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [unread, setUnread] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const seqRef = useRef(0);
  const initDone = useRef(false);
  const currentPhaseRef = useRef(0);

  const addMsg = useCallback((type: Msg["type"], text: string, extra?: Partial<Msg>) => {
    seqRef.current++;
    setMessages(prev => [...prev, { id: seqRef.current, type, text, ...extra }]);
    if (!open && type !== "user") setUnread(prev => prev + 1);
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Intro + first phase (only when drawer opens first time)
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    const intros = INTROS[scenarioId] || INTROS["scn-wannacry-w1"];
    intros.forEach((text, i) => setTimeout(() => addMsg("story", text), i * 1500));
    setTimeout(() => showPhase(0), intros.length * 1500 + 500);
  }, [scenarioId]); // eslint-disable-line react-hooks/exhaustive-deps

  const showPhase = (idx: number) => {
    if (idx >= mission.phases.length) {
      addMsg("complete", "Mission complete. You captured the flag. Head back to the library or keep exploring.");
      return;
    }
    const phase = mission.phases[idx];
    const narr = NARRATIONS[scenarioId]?.[phase.name] || `**${phase.name}** — ${phase.objective}`;
    addMsg("instruction", narr, { commands: phase.commands, phaseIdx: idx });
    currentPhaseRef.current = idx;
  };

  const handleDone = (idx: number) => {
    onComplete(idx);
    const phase = mission.phases[idx];
    const react = REACTIONS[scenarioId]?.[phase.name] || `Done with **${phase.name}**. Moving on.`;
    addMsg("reaction", react);
    setTimeout(() => showPhase(idx + 1), 1200);
  };

  const askJilla = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    setInput("");
    addMsg("user", text.trim());
    setLoading(true);
    try {
      const ph = mission.phases[Math.min(currentPhaseRef.current, mission.phases.length - 1)];
      const resp = await fetch("/api/jilla/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text.trim(), role: "red", scenario_id: scenarioId,
          sim_state: { guide: { phase: ph.name, progress: { done: completed, total: totalObjectives } } },
          history: messages.filter(m => m.type === "user" || m.type === "reaction").slice(-4)
            .map(m => ({ role: m.type === "user" ? "user" : "assistant", content: m.text })),
        }),
      });
      const data = await resp.json();
      addMsg("reaction", data.message);
    } catch { addMsg("reaction", "Couldn't connect. Try again?"); }
    setLoading(false);
  }, [loading, messages, scenarioId, mission, completed, totalObjectives, addMsg]);

  const renderMd = (text: string) =>
    text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="jilla-inline-code">{part.slice(1, -1)}</code>;
      return <span key={i}>{part}</span>;
    });

  const copy = (cmd: string) => navigator.clipboard?.writeText(cmd);

  return (
    <>
      {/* FAB — always visible */}
      {!open && (
        <button className="jilla-fab" onClick={() => { setOpen(true); setUnread(0); }}
          style={{ position: "fixed", bottom: 20, right: 20, zIndex: 9000 }}>
          <JillaFace size={30} state="idle" />
          {unread > 0 && <span className="jilla-fab-badge">{unread}</span>}
        </button>
      )}

      {/* Drawer — slides in from right, overlays the page */}
      {open && (
        <div className="jilla-drawer-overlay" onClick={() => setOpen(false)}>
          <div className="jilla-drawer" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="jilla-guided-header">
              <JillaFace size={36} state={loading ? "thinking" : "idle"} />
              <div style={{ flex: 1 }}>
                <div className="jilla-guided-name">Jilla</div>
                <div className="jilla-guided-status">
                  {loading ? "thinking..." : `${mission.name} · ${completed}/${totalObjectives}`}
                </div>
              </div>
              <button className="jilla-convo-minimize" onClick={() => setOpen(false)}>
                <i className="fa fa-times" />
              </button>
            </div>

            {/* Messages */}
            <div className="jilla-guided-messages" ref={scrollRef}>
              {messages.map(msg => (
                <div key={msg.id} className={`jilla-guided-msg jilla-guided-${msg.type}`}>
                  {msg.type !== "user" && <JillaFace size={26} state={msg.type === "instruction" ? "speaking" : "idle"} />}
                  <div className="jilla-guided-content">
                    <div className={`jilla-guided-bubble${msg.type === "user" ? " user-bubble" : ""}`}>
                      {renderMd(msg.text)}
                    </div>
                    {msg.commands && (
                      <div className="jilla-guided-cmds">
                        {msg.commands.map((c, j) => (
                          <div key={j} className="jilla-guided-cmd">
                            <code>{c.cmd}</code>
                            <button className="jilla-guided-copy" onClick={() => copy(c.cmd)} title="Copy"><i className="fa fa-copy" /></button>
                            {c.note && <div className="jilla-guided-cmd-note">{c.note}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                    {msg.type === "instruction" && msg.phaseIdx !== undefined && completed <= msg.phaseIdx && (
                      <button className="jilla-guided-done-btn" onClick={() => handleDone(msg.phaseIdx!)}>
                        <i className="fa fa-check" /> Done — next step
                      </button>
                    )}
                    {msg.type === "complete" && <div className="jilla-guided-celebration"><span style={{ fontSize: 28 }}>🏁</span></div>}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="jilla-guided-msg jilla-guided-reaction">
                  <JillaFace size={26} state="thinking" />
                  <div className="jilla-convo-typing">
                    <span className="jilla-dot" /><span className="jilla-dot" style={{ animationDelay: "0.15s" }} /><span className="jilla-dot" style={{ animationDelay: "0.3s" }} />
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="jilla-guided-input-area">
              <form onSubmit={e => { e.preventDefault(); askJilla(input); }} className="jilla-convo-form">
                <input value={input} onChange={e => setInput(e.target.value)} disabled={loading}
                  placeholder="Ask Jilla anything..." className="jilla-convo-input" />
                <button type="submit" disabled={loading || !input.trim()}
                  className={`jilla-convo-send${input.trim() ? " active" : ""}`}>
                  <i className="fa fa-arrow-up" />
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
