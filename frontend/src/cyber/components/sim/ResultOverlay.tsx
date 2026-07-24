/**
 * ResultOverlay — modal that appears after each tool execution.
 * Shows: what was done, what happened, consequence, what to do next.
 * Styled to match the GoalCert light purple palette.
 */
import { useEffect, useState } from "react";
import { TEAM_META } from "./shared";

interface ResultData {
  tool_name: string;
  tool_id: string;
  team: string;
  consequence: string;
  next_hint: string;
  teaching_note: string;
  command?: string;
  outcome?: string;
}

interface Props {
  result: ResultData | null;
  onClose: () => void;
  onGoToNext?: (toolId: string) => void;
}

export default function ResultOverlay({ result, onClose, onGoToNext }: Props) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!result) return;
    setProgress(100);
    const start = Date.now();
    const duration = 12000;
    const tick = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(pct);
      if (pct <= 0) { clearInterval(tick); onClose(); }
    }, 50);
    return () => clearInterval(tick);
  }, [result]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!result) return null;

  const meta = TEAM_META[result.team] || TEAM_META.red;

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 2000, display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.35)", backdropFilter: "blur(6px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ width: 520, maxWidth: "92vw", background: "#fff", borderRadius: 16,
        border: `1px solid var(--gc-border)`, overflow: "hidden",
        boxShadow: "0 20px 60px rgba(73,2,162,0.12)" }}>

        {/* Progress bar */}
        <div style={{ height: 3, background: "var(--gc-border)" }}>
          <div style={{ height: "100%", width: `${progress}%`, background: meta.color, transition: "width 0.05s linear" }} />
        </div>

        {/* Header */}
        <div style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 10,
          borderBottom: "1px solid var(--gc-border)" }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: `${meta.color}14`,
            display: "flex", alignItems: "center", justifyContent: "center" }}>
            <i className={`fa ${meta.icon}`} style={{ color: meta.color, fontSize: 14 }} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--gc-text)" }}>{result.tool_name}</div>
            <div style={{ fontSize: 10, color: meta.color, fontWeight: 600, letterSpacing: 1 }}>{result.team.toUpperCase()} TEAM</div>
          </div>
          <button onClick={onClose} style={{ marginLeft: "auto", background: "none", border: "none",
            color: "var(--gc-muted)", cursor: "pointer", fontSize: 16, padding: 4 }}>
            <i className="fa fa-times" />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: "14px 18px", display: "flex", flexDirection: "column", gap: 12 }}>

          {result.consequence && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: meta.color, letterSpacing: 1, marginBottom: 4 }}>
                WHAT HAPPENED
              </div>
              <div style={{ fontSize: 13, color: "var(--gc-text2)", lineHeight: 1.7 }}>{result.consequence}</div>
            </div>
          )}

          {result.command && (
            <div style={{ background: "var(--gc-soft)", borderRadius: 8, padding: "8px 12px", fontFamily: "var(--mono)",
              fontSize: 11.5, color: "var(--gc-primary)", userSelect: "text", cursor: "text",
              border: "1px solid var(--gc-border)" }}>
              <span style={{ color: "var(--gc-muted)" }}>$</span> {result.command}
            </div>
          )}

          {result.teaching_note && (
            <div style={{ background: "var(--gc-soft)", borderRadius: 10, padding: "10px 14px",
              borderLeft: "3px solid var(--gc-primary)" }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--gc-primary)", letterSpacing: 1, marginBottom: 3 }}>
                <i className="fa fa-graduation-cap" style={{ marginRight: 4 }} /> LEARN
              </div>
              <div style={{ fontSize: 12, color: "var(--gc-text2)", lineHeight: 1.7 }}>{result.teaching_note}</div>
            </div>
          )}

          {result.next_hint && (
            <div style={{ background: "rgba(73,2,162,0.04)", borderRadius: 10, padding: "10px 14px",
              borderLeft: `3px solid ${meta.color}` }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: meta.color, letterSpacing: 1, marginBottom: 3 }}>
                <i className="fa fa-arrow-right" style={{ marginRight: 4 }} /> NEXT STEP
              </div>
              <div style={{ fontSize: 12, color: "var(--gc-text2)", lineHeight: 1.7 }}>{result.next_hint}</div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: "10px 18px", borderTop: "1px solid var(--gc-border)",
          display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose} className="btn" style={{ fontSize: 12 }}>
            Dismiss
          </button>
          <button onClick={() => { onClose(); }} className="btn btn-primary" style={{ fontSize: 12 }}>
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
