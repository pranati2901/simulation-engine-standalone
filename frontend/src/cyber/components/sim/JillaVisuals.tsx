/**
 * JillaVisuals — visual teaching components that go BEYOND text.
 *
 * These render ON the workspace, not in a chat panel:
 * 1. SpotlightGuide — dims screen, highlights target element, "click here"
 * 2. AttackTimeline — horizontal kill chain with "YOU ARE HERE" marker
 * 3. CommandBreakdown — color-coded command flags with hover explanations
 * 4. JillaToast — slide-in notification from Jilla with action button
 */
import { useEffect, useRef, useState } from "react";

/* ============================================================
   1. SPOTLIGHT GUIDE — point at things on screen
   ============================================================ */
interface SpotlightProps {
  target: string;        // CSS selector for the element to highlight
  label: string;         // "Click Nmap to scan the network"
  sublabel?: string;     // extra context
  onDismiss: () => void;
}

export function SpotlightGuide({ target, label, sublabel, onDismiss }: SpotlightProps) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const rafRef = useRef(0);

  // Track element position
  useEffect(() => {
    const track = () => {
      const el = document.querySelector(target);
      if (el) {
        setRect(el.getBoundingClientRect());
      }
      rafRef.current = requestAnimationFrame(track);
    };
    track();
    return () => cancelAnimationFrame(rafRef.current);
  }, [target]);

  if (!rect) return null;

  const pad = 12;
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const rx = rect.width / 2 + pad;
  const ry = rect.height / 2 + pad;

  return (
    <div className="spotlight-overlay" onClick={onDismiss}>
      {/* Dark backdrop with hole */}
      <svg width="100%" height="100%" style={{ position: "fixed", inset: 0, zIndex: 9300 }}>
        <defs>
          <mask id="spotlight-mask">
            <rect width="100%" height="100%" fill="white" />
            <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="black" />
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="rgba(0,0,0,0.7)" mask="url(#spotlight-mask)" />
        {/* Pulsing ring around target */}
        <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none"
          stroke="var(--gc-primary)" strokeWidth="2" className="spotlight-ring" />
        <ellipse cx={cx} cy={cy} rx={rx + 6} ry={ry + 6} fill="none"
          stroke="var(--gc-primary)" strokeWidth="1" opacity="0.4" className="spotlight-ring-outer" />
      </svg>

      {/* Label card positioned near target */}
      <div className="spotlight-card" style={{
        position: "fixed", zIndex: 9310,
        top: rect.bottom + 16, left: Math.max(16, Math.min(cx - 160, window.innerWidth - 340)),
      }}>
        <div className="spotlight-arrow" />
        <div className="spotlight-card-inner">
          <div className="spotlight-label">{label}</div>
          {sublabel && <div className="spotlight-sublabel">{sublabel}</div>}
          <div className="spotlight-hint">Click the highlighted element, or click anywhere to dismiss</div>
        </div>
      </div>
    </div>
  );
}


/* ============================================================
   2. ATTACK TIMELINE — horizontal kill chain with position marker
   ============================================================ */
interface TimelinePhase {
  name: string;
  shortName?: string;
}

interface TimelineProps {
  phases: TimelinePhase[];
  currentIdx: number;
  role: string;
}

export function AttackTimeline({ phases, currentIdx, role }: TimelineProps) {
  if (phases.length === 0) return null;

  const roleColors: Record<string, string> = {
    red: "#ef4444", soc: "#f59e0b", blue: "#3b82f6",
  };
  const color = roleColors[role] || "var(--gc-primary)";

  return (
    <div className="atk-timeline">
      <div className="atk-timeline-track">
        {/* Progress fill */}
        <div className="atk-timeline-fill" style={{
          width: `${((currentIdx + 0.5) / phases.length) * 100}%`,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
        }} />
      </div>
      <div className="atk-timeline-phases">
        {phases.map((p, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <div key={i} className={`atk-phase${done ? " done" : ""}${active ? " active" : ""}`}
              style={{ "--phase-color": active ? color : done ? color + "88" : "var(--gc-muted)" } as React.CSSProperties}>
              <div className="atk-phase-dot">
                {done ? <i className="fa fa-check" style={{ fontSize: 7 }} /> : (i + 1)}
              </div>
              <div className="atk-phase-name">{p.shortName || p.name}</div>
            </div>
          );
        })}
      </div>
      {/* "YOU ARE HERE" indicator */}
      <div className="atk-timeline-marker" style={{
        left: `${((currentIdx + 0.5) / phases.length) * 100}%`,
        borderColor: color,
      }}>
        <span>YOU ARE HERE</span>
      </div>
    </div>
  );
}


/* ============================================================
   3. COMMAND BREAKDOWN — color-coded flags with hover tooltips
   ============================================================ */
interface CmdPart {
  text: string;
  type: "tool" | "flag" | "value" | "target" | "separator";
  tooltip?: string;
}

interface CmdBreakdownProps {
  parts: CmdPart[];
  onCopy?: () => void;
}

export function CommandBreakdown({ parts, onCopy }: CmdBreakdownProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const fullCmd = parts.map(p => p.text).join("");

  const typeColors: Record<string, string> = {
    tool: "#22d3ee",     // cyan
    flag: "#a78bfa",     // purple
    value: "#fbbf24",    // amber
    target: "#34d399",   // green
    separator: "#64748b",
  };

  return (
    <div className="cmd-breakdown">
      <div className="cmd-breakdown-code">
        <span style={{ color: "#ef4444", marginRight: 4 }}>$</span>
        {parts.map((p, i) => (
          <span key={i}
            className={`cmd-part${hoveredIdx === i ? " hovered" : ""}`}
            style={{ color: typeColors[p.type] || "#cbd5e1" }}
            onMouseEnter={() => setHoveredIdx(i)}
            onMouseLeave={() => setHoveredIdx(null)}>
            {p.text}
            {hoveredIdx === i && p.tooltip && (
              <span className="cmd-tooltip">{p.tooltip}</span>
            )}
          </span>
        ))}
        {onCopy && (
          <button className="cmd-copy" onClick={onCopy} title="Copy command">
            <i className="fa fa-copy" />
          </button>
        )}
      </div>
      {/* Legend */}
      <div className="cmd-legend">
        <span><span className="cmd-legend-dot" style={{ background: typeColors.tool }} /> tool</span>
        <span><span className="cmd-legend-dot" style={{ background: typeColors.flag }} /> flag</span>
        <span><span className="cmd-legend-dot" style={{ background: typeColors.value }} /> value</span>
        <span><span className="cmd-legend-dot" style={{ background: typeColors.target }} /> target</span>
      </div>
    </div>
  );
}

// Helper: parse common commands into parts
export function parseCommand(cmd: string): CmdPart[] {
  const parts: CmdPart[] = [];
  const tokens = cmd.split(/(\s+)/);
  let isFirst = true;

  for (const token of tokens) {
    if (/^\s+$/.test(token)) {
      parts.push({ text: token, type: "separator" });
      continue;
    }
    if (isFirst) {
      parts.push({ text: token, type: "tool", tooltip: getToolTooltip(token) });
      isFirst = false;
    } else if (token.startsWith("-")) {
      parts.push({ text: token, type: "flag", tooltip: getFlagTooltip(token) });
    } else if (/^[\d./:]+$/.test(token) || token.includes("target-")) {
      parts.push({ text: token, type: "target", tooltip: "Target host or address" });
    } else {
      parts.push({ text: token, type: "value", tooltip: "Parameter value" });
    }
  }
  return parts;
}

function getToolTooltip(tool: string): string {
  const tips: Record<string, string> = {
    nmap: "Network mapper — discovers hosts and open ports",
    hydra: "Password brute-force tool — tries many passwords fast",
    curl: "HTTP client — sends web requests from the command line",
    sqlmap: "SQL injection automation — finds and exploits SQLi vulnerabilities",
    netexec: "Network execution tool — enumerates SMB, checks credentials",
    gobuster: "Directory brute-forcer — finds hidden web paths",
    nikto: "Web vulnerability scanner — checks for common misconfigurations",
  };
  return tips[tool.toLowerCase()] || `Command: ${tool}`;
}

function getFlagTooltip(flag: string): string {
  const tips: Record<string, string> = {
    "-sV": "Service version detection — identifies what's running on each port",
    "-sS": "SYN scan — stealthy half-open scan",
    "-O": "OS fingerprinting — detects the operating system",
    "-p": "Port specification — which ports to scan",
    "-l": "Login/username — the account to try",
    "-P": "Password list file — wordlist for brute force",
    "-L": "Username list file — multiple accounts to try",
    "-s": "Silent mode — suppress progress output",
    "-X": "HTTP method — POST, PUT, DELETE etc",
    "-c": "Cookie file — use saved session cookies",
    "-b": "Send cookies — attach cookies to request",
    "-u": "URL target — the web address to test",
    "--data": "POST body — form data to send",
    "--batch": "Non-interactive — auto-answer prompts",
    "--dump": "Extract data — dump database contents",
  };
  return tips[flag] || `Flag: ${flag}`;
}


/* ============================================================
   4. JILLA TOAST — slide-in action notification
   ============================================================ */
interface ToastProps {
  message: string;
  action?: { label: string; onClick: () => void };
  type?: "info" | "success" | "warning" | "action";
  onDismiss: () => void;
  autoDismissMs?: number;
}

export function JillaToast({ message, action, type = "info", onDismiss, autoDismissMs = 8000 }: ToastProps) {
  useEffect(() => {
    const t = setTimeout(onDismiss, autoDismissMs);
    return () => clearTimeout(t);
  }, [onDismiss, autoDismissMs]);

  const typeStyles: Record<string, { border: string; icon: string }> = {
    info: { border: "var(--gc-primary)", icon: "fa-circle-info" },
    success: { border: "#16a34a", icon: "fa-check-circle" },
    warning: { border: "#f59e0b", icon: "fa-triangle-exclamation" },
    action: { border: "#ea580c", icon: "fa-hand-pointer" },
  };
  const s = typeStyles[type];

  return (
    <div className="jilla-toast" style={{ borderLeftColor: s.border }}>
      <i className={`fa ${s.icon}`} style={{ color: s.border, fontSize: 14, flexShrink: 0 }} />
      <div className="jilla-toast-text">{message}</div>
      {action && (
        <button className="jilla-toast-action" onClick={action.onClick}
          style={{ color: s.border, borderColor: s.border }}>
          {action.label}
        </button>
      )}
      <button className="jilla-toast-close" onClick={onDismiss}>
        <i className="fa fa-times" />
      </button>
    </div>
  );
}
