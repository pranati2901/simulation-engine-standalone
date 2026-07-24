/**
 * TeachingCard — premium glassmorphism teaching cards.
 *
 * 4 variants: concept (explain), action (do this), result (what happened), flow (attack chain).
 * Features: gradient glow border, frosted glass, spring animations, copy buttons.
 */

interface TeachingCardProps {
  type: "concept" | "action" | "result" | "flow";
  title: string;
  body: string;
  step?: { current: number; total: number };
  code?: string;
  diagram?: React.ReactNode;
  status?: "waiting" | "done" | "error";
  statusText?: string;
  onNext?: () => void;
  onDismiss?: () => void;
  onDeepen?: () => void;
  deepenLabel?: string;
  style?: React.CSSProperties;
}

const TYPE_STYLES: Record<string, { icon: string; gradient: string; accent: string; label: string; glow: string }> = {
  concept: { icon: "fa-lightbulb", gradient: "linear-gradient(135deg, #7c3aed, #4902A2)", accent: "var(--gc-primary)", label: "LEARN", glow: "rgba(73,2,162,0.3)" },
  action: { icon: "fa-bolt", gradient: "linear-gradient(135deg, #f59e0b, #ea580c)", accent: "#ea580c", label: "YOUR TURN", glow: "rgba(234,88,12,0.3)" },
  result: { icon: "fa-check-circle", gradient: "linear-gradient(135deg, #22c55e, #16a34a)", accent: "#16a34a", label: "RESULT", glow: "rgba(22,163,74,0.3)" },
  flow: { icon: "fa-route", gradient: "linear-gradient(135deg, #3b82f6, #0284c7)", accent: "#0284c7", label: "ATTACK FLOW", glow: "rgba(2,132,199,0.3)" },
};

export default function TeachingCard({
  type, title, body, step, code, diagram, status, statusText,
  onNext, onDismiss, onDeepen, deepenLabel, style,
}: TeachingCardProps) {
  const t = TYPE_STYLES[type] || TYPE_STYLES.concept;

  return (
    <div className="tc-outer" style={{ "--tc-glow": t.glow, "--tc-accent": t.accent, ...style } as React.CSSProperties}>
      <div className="tc-card">
        {/* Gradient header strip */}
        <div className="tc-header" style={{ background: t.gradient }}>
          <i className={`fa ${t.icon}`} style={{ fontSize: 12 }} />
          <span className="tc-label">{t.label}</span>
          {step && (
            <span className="tc-step">{step.current}/{step.total}</span>
          )}
          {onDismiss && (
            <button onClick={onDismiss} className="tc-close">
              <i className="fa fa-times" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="tc-body">
          <div className="tc-title">{title}</div>

          {diagram && <div style={{ margin: "10px 0" }}>{diagram}</div>}

          <div className="tc-text">
            {body.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, i) => {
              if (part.startsWith("**") && part.endsWith("**"))
                return <strong key={i} style={{ color: "var(--gc-text)" }}>{part.slice(2, -2)}</strong>;
              if (part.startsWith("`") && part.endsWith("`"))
                return <code key={i} className="tc-inline-code" style={{ color: t.accent }}>{part.slice(1, -1)}</code>;
              return <span key={i}>{part}</span>;
            })}
          </div>

          {code && (
            <div className="tc-code-block">
              <span style={{ color: "#ef4444" }}>$</span> {code}
              <button onClick={() => navigator.clipboard.writeText(code)} className="tc-copy">
                <i className="fa fa-copy" />
              </button>
            </div>
          )}

          {status && (
            <div className="tc-status" style={{
              color: status === "done" ? "#16a34a" : status === "error" ? "#ef4444" : "var(--gc-muted)",
            }}>
              {status === "waiting" && <span className="jilla-dot" style={{ width: 6, height: 6 }} />}
              {status === "done" && <i className="fa fa-check-circle" />}
              {status === "error" && <i className="fa fa-times-circle" />}
              {statusText || (status === "waiting" ? "Waiting for you..." : status === "done" ? "Done!" : "Error")}
            </div>
          )}
        </div>

        {/* Footer */}
        {(onNext || onDeepen) && (
          <div className="tc-footer">
            {onDeepen && (
              <button onClick={onDeepen} className="tc-btn tc-btn-secondary">
                {deepenLabel || "Tell me more"}
              </button>
            )}
            {onNext && (
              <button onClick={onNext} className="tc-btn tc-btn-primary" style={{ background: t.gradient }}>
                Next <i className="fa fa-arrow-right" style={{ fontSize: 10 }} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* Mini diagram components for use inside TeachingCard */

export function MiniTopology({ hosts }: { hosts: { id: string; name: string; state: string }[] }) {
  const stateColors: Record<string, string> = {
    healthy: "#16a34a", vulnerable: "#ca8a04", exploited: "#ea580c",
    infected: "#dc2626", impacted: "#111", contained: "#3b82f6",
  };
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", padding: "6px 0" }}>
      {hosts.map(h => (
        <div key={h.id} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: stateColors[h.state] || "#94a3b8",
            display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11 }}>
            <i className="fa fa-desktop" />
          </div>
          <span style={{ fontSize: 8, color: "var(--gc-muted)", maxWidth: 40, overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.name}</span>
        </div>
      ))}
    </div>
  );
}

export function AttackFlowDiagram({ steps }: { steps: { icon: string; label: string; sublabel: string }[] }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "8px 0", overflowX: "auto" }}>
      {steps.map((s, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
            <div className="tc-flow-node" style={{ animationDelay: `${i * 0.12}s` }}>
              <i className={`fa ${s.icon}`} />
            </div>
            <span style={{ fontSize: 8, color: "var(--gc-text)", fontWeight: 600 }}>{s.label}</span>
            <span style={{ fontSize: 7, color: "var(--gc-muted)" }}>{s.sublabel}</span>
          </div>
          {i < steps.length - 1 && (
            <div className="tc-flow-arrow" style={{ animationDelay: `${i * 0.12 + 0.06}s` }} />
          )}
        </div>
      ))}
    </div>
  );
}
