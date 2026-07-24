/**
 * JillaChat — premium AI cybersecurity tutor chat panel.
 *
 * Glassmorphism sidebar with animated messages, typing indicator,
 * gradient header, spring-animated suggestion chips, progressive hints.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { TEAM_META } from "./shared";

interface Message {
  id: number;
  role: "jilla" | "user";
  content: string;
  suggestions?: string[];
  highlight_host?: string | null;
  highlight_tool?: string | null;
  timestamp: number;
}

interface Props {
  sim: any;
  myRole: string;
  scenarioId: string;
  onHighlightNode?: (hostId: string | null) => void;
  onHighlightTool?: (toolId: string | null) => void;
}

export default function JillaChat({ sim, myRole, scenarioId, onHighlightNode, onHighlightTool }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [hintLevel, setHintLevel] = useState(1);
  const [inputFocused, setInputFocused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastPhaseRef = useRef("");
  const seqRef = useRef(0);
  const initDone = useRef(false);

  const meta = TEAM_META[myRole] || TEAM_META.red;

  const addMessage = useCallback((msg: Omit<Message, "id" | "timestamp">) => {
    seqRef.current++;
    setMessages(prev => [...prev, { ...msg, id: seqRef.current, timestamp: Date.now() }]);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Intro
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    fetch(`/api/jilla/intro?role=${myRole}&scenario_id=${scenarioId}`)
      .then(r => r.json())
      .then(data => addMessage({ role: "jilla", content: data.message, suggestions: data.suggestions }))
      .catch(() => addMessage({
        role: "jilla",
        content: `Hey! I'm **Jilla**, your cyber range instructor.\n\nI can see the simulation state and help you learn. Ask me anything!`,
        suggestions: ["What should I do first?", "Explain this scenario", "Just nudge me"],
      }));
  }, [myRole, scenarioId, addMessage]);

  // Phase transitions
  useEffect(() => {
    const phase = sim?.guide?.phase;
    if (!phase || phase === lastPhaseRef.current) return;
    lastPhaseRef.current = phase;
    setHintLevel(1);
    if (messages.length < 2) return;
    const guide = sim.guide;
    const nextTool = guide?.next_tools?.[myRole];
    addMessage({
      role: "jilla",
      content: `**Phase transition \u2192 ${phase}**\n\nYou're now in the **${phase}** phase.${nextTool ? `\n\nNext suggested tool: **${nextTool.name}**` : ""}`,
      suggestions: ["What should I do?", "Explain this phase", "I'm stuck"],
      highlight_tool: nextTool?.id || null,
    });
  }, [sim?.guide?.phase, myRole, messages.length, addMessage, sim?.guide]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg = text.trim();
    setInput("");
    addMessage({ role: "user", content: userMsg });
    setLoading(true);
    try {
      const history = messages.slice(-6).map(m => ({
        role: m.role === "jilla" ? "assistant" : "user", content: m.content,
      }));
      const resp = await fetch("/api/jilla/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, role: myRole, scenario_id: scenarioId, sim_state: sim || {}, history }),
      });
      const data = await resp.json();
      addMessage({ role: "jilla", content: data.message, suggestions: data.suggestions, highlight_host: data.highlight_host, highlight_tool: data.highlight_tool });
      if (data.highlight_host) onHighlightNode?.(data.highlight_host);
      if (data.highlight_tool) onHighlightTool?.(data.highlight_tool);
    } catch {
      addMessage({ role: "jilla", content: "Sorry, I couldn't process that. Try again?" });
    } finally {
      setLoading(false);
    }
  }, [loading, messages, myRole, scenarioId, sim, addMessage, onHighlightNode, onHighlightTool]);

  const getHint = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch("/api/jilla/hint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: myRole, scenario_id: scenarioId, sim_state: sim || {}, hint_level: hintLevel }),
      });
      const data = await resp.json();
      addMessage({ role: "jilla", content: data.message, suggestions: data.suggestions });
      setHintLevel(prev => Math.min(prev + 1, 4));
    } catch {
      addMessage({ role: "jilla", content: "Hmm, couldn't generate a hint. Try asking me directly!" });
    } finally {
      setLoading(false);
    }
  }, [myRole, scenarioId, sim, hintLevel, addMessage]);

  const handleSuggestion = (text: string) => {
    if (text.toLowerCase().includes("hint") || text.toLowerCase().includes("stuck")) getHint();
    else sendMessage(text);
  };

  // Render markdown fragments
  const renderMd = (text: string, isUser: boolean) =>
    text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={i} style={{ color: isUser ? "#fff" : "var(--gc-text)" }}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`"))
        return <code key={i} className="jilla-code" style={{
          background: isUser ? "rgba(255,255,255,0.15)" : "rgba(73,2,162,0.08)",
          color: isUser ? "#e8d5ff" : "var(--gc-primary)",
        }}>{part.slice(1, -1)}</code>;
      return <span key={i}>{part}</span>;
    });

  // Collapsed rail
  if (collapsed) {
    return (
      <div className="jilla-rail" onClick={() => setCollapsed(false)}>
        <div className="jilla-rail-avatar">J</div>
        <div className="jilla-rail-label">JILLA</div>
        {messages.length > 0 && (
          <div className="jilla-rail-badge">
            {messages.filter(m => m.role === "jilla").length}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="jilla-panel">
      {/* Gradient header */}
      <div className="jilla-header">
        <div className="jilla-avatar-ring">
          <div className="jilla-avatar">J</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="jilla-name">Jilla</div>
          <div className="jilla-subtitle">AI Instructor &middot; {myRole.toUpperCase()}</div>
        </div>
        <button className="jilla-hint-btn" onClick={getHint} disabled={loading} title="Progressive hint">
          <i className="fa fa-lightbulb" /> Hint {hintLevel > 1 && <span className="jilla-hint-level">L{hintLevel}</span>}
        </button>
        <button className="jilla-collapse-btn" onClick={() => setCollapsed(true)}>
          <i className="fa fa-chevron-left" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="jilla-messages">
        {messages.map((msg, idx) => (
          <div key={msg.id} className={`jilla-msg jilla-msg-${msg.role}`}
            style={{ animationDelay: `${Math.min(idx * 0.05, 0.3)}s` }}>
            {msg.role === "jilla" && (
              <div className="jilla-msg-avatar">J</div>
            )}
            <div className={`jilla-bubble jilla-bubble-${msg.role}`}>
              {renderMd(msg.content, msg.role === "user")}
            </div>

            {msg.role === "jilla" && msg.suggestions && msg.suggestions.length > 0 && (
              <div className="jilla-suggestions">
                {msg.suggestions.map((s, i) => (
                  <button key={i} className="jilla-chip" onClick={() => handleSuggestion(s)}
                    disabled={loading} style={{ animationDelay: `${i * 0.08 + 0.15}s` }}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="jilla-msg jilla-msg-jilla jilla-typing-row">
            <div className="jilla-msg-avatar">J</div>
            <div className="jilla-typing">
              <span className="jilla-dot" style={{ animationDelay: "0s" }} />
              <span className="jilla-dot" style={{ animationDelay: "0.15s" }} />
              <span className="jilla-dot" style={{ animationDelay: "0.3s" }} />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className={`jilla-input-wrap${inputFocused ? " focused" : ""}`}>
        <form onSubmit={e => { e.preventDefault(); sendMessage(input); }} className="jilla-input-form">
          <input value={input} onChange={e => setInput(e.target.value)} disabled={loading}
            placeholder="Ask Jilla anything..."
            className="jilla-input"
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)} />
          <button type="submit" disabled={loading || !input.trim()}
            className={`jilla-send${input.trim() ? " active" : ""}`}>
            <i className="fa fa-arrow-up" />
          </button>
        </form>
      </div>
    </div>
  );
}
