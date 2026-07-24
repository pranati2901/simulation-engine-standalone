import { useEffect, useMemo, useRef, useState } from "react";
import { SEV_COLOR } from "./shared";

export interface NotifyMsg {
  id: string | number;
  title: string;
  text?: string;
  severity?: string;   // critical | high | medium | low | info
  t?: number;          // seconds since start (optional)
  role?: string;
}

/* Floating, collapsible notification dock.
   - Collapsed by default to a small bell button (it is NOT always in your face).
   - The current phase / mission status rides a slim pill above the bell.
   - A new message briefly flashes a toast, then folds away; an unread badge keeps the count.
   - Click the bell to open the full, scrollable MESSAGE LOG of everything that has happened — so a
     learner can catch up on "what's going on" at will, then collapse it again.
   Used by both the immersive workspace (Live) and the terminal hack-lab (Library). */
export default function NotificationDock({ messages, status, accent = "#4902A2" }:
  { messages: NotifyMsg[]; status?: { label?: string; detail?: string }; accent?: string }) {
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<NotifyMsg | null>(null);
  const [seen, setSeen] = useState(0);
  const lastId = useRef<string | number | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const latest = messages.length ? messages[messages.length - 1] : null;
  const unread = open ? 0 : Math.max(0, messages.length - seen);

  // Flash a transient toast whenever a genuinely new message arrives (and the log is collapsed).
  useEffect(() => {
    if (!latest || latest.id === lastId.current) return;
    lastId.current = latest.id;
    if (!open) {
      setToast(latest);
      const tm = setTimeout(() => setToast(null), 6000);
      return () => clearTimeout(tm);
    }
  }, [latest, open]);

  // Opening the log marks everything read; keep it pinned to the newest line.
  useEffect(() => {
    if (open) { setSeen(messages.length); setToast(null); }
  }, [open, messages.length]);
  useEffect(() => {
    if (open && bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [open, messages.length]);

  const sev = (s?: string) => SEV_COLOR[s || "info"] || SEV_COLOR.info;
  const ordered = useMemo(() => messages.slice(-200), [messages]);

  return (
    <div style={{ position: "fixed", right: 18, bottom: 18, zIndex: 90, display: "flex",
      flexDirection: "column", alignItems: "flex-end", gap: 8, pointerEvents: "none" }}>

      {/* Expanded message log */}
      {open && (
        <div style={{ pointerEvents: "auto", width: 360, maxWidth: "92vw", background: "#fff",
          border: "1px solid var(--gc-border)", borderRadius: 12, boxShadow: "0 12px 40px #0003",
          overflow: "hidden", display: "flex", flexDirection: "column", maxHeight: "70vh" }}>
          <div style={{ padding: "10px 12px", background: accent, color: "#fff", display: "flex", alignItems: "center", gap: 8 }}>
            <i className="fa fa-bell" />
            <b style={{ fontSize: 13 }}>Mission log</b>
            <span style={{ marginLeft: "auto", fontSize: 11, opacity: 0.85 }}>{messages.length} events</span>
            <button onClick={() => setOpen(false)} title="Collapse"
              style={{ background: "transparent", border: 0, color: "#fff", cursor: "pointer", fontSize: 14 }}>
              <i className="fa fa-chevron-down" />
            </button>
          </div>
          {status?.label && (
            <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--gc-border)", background: `${accent}0c` }}>
              <div style={{ fontSize: 9.5, letterSpacing: 1, color: accent, fontWeight: 700 }}>CURRENT STATUS</div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--gc-text)" }}>{status.label}</div>
              {status.detail && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 2 }}>{status.detail}</div>}
            </div>
          )}
          <div ref={bodyRef} style={{ overflowY: "auto", padding: "8px 10px" }}>
            {ordered.length === 0 && <div style={{ fontSize: 12, color: "var(--gc-muted)", padding: 12, textAlign: "center" }}>No events yet.</div>}
            {ordered.map((m) => (
              <div key={m.id} style={{ display: "flex", gap: 8, padding: "7px 4px", borderBottom: "1px solid #f1edf7" }}>
                <span style={{ width: 6, borderRadius: 3, background: sev(m.severity), flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--gc-text)" }}>{m.title}</div>
                  {m.text && <div style={{ fontSize: 11.5, color: "var(--gc-muted)", lineHeight: 1.5 }}>{m.text}</div>}
                  {m.t != null && <div style={{ fontSize: 9.5, color: "#aab2c0" }}>t+{m.t}s</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transient toast (collapsed state only) */}
      {!open && toast && (
        <div onClick={() => setOpen(true)} style={{ pointerEvents: "auto", cursor: "pointer", width: 320, maxWidth: "88vw",
          background: "#fff", border: "1px solid var(--gc-border)", borderLeft: `4px solid ${sev(toast.severity)}`,
          borderRadius: 10, boxShadow: "0 10px 30px #0003", padding: "9px 12px", transition: "opacity .3s" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--gc-text)" }}>{toast.title}</div>
          {toast.text && <div style={{ fontSize: 11.5, color: "var(--gc-muted)", lineHeight: 1.5, marginTop: 2,
            display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{toast.text}</div>}
          <div style={{ fontSize: 10, color: accent, marginTop: 4 }}>Click to open the mission log →</div>
        </div>
      )}

      {/* Current-status pill (collapsed) — a quiet one-liner, easy to ignore or read */}
      {!open && status?.label && (
        <div onClick={() => setOpen(true)} style={{ pointerEvents: "auto", cursor: "pointer", maxWidth: 320,
          background: "#fff", border: "1px solid var(--gc-border)", borderRadius: 20, padding: "5px 12px",
          fontSize: 11.5, color: "var(--gc-text2)", boxShadow: "0 4px 16px #0002", whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis" }}>
          <i className="fa fa-flag" style={{ color: accent, marginRight: 6 }} />{status.label}
        </div>
      )}

      {/* The bell — toggles the log. Always present but unobtrusive. */}
      <button onClick={() => setOpen((o) => !o)} title="Mission log / notifications"
        style={{ pointerEvents: "auto", position: "relative", width: 46, height: 46, borderRadius: "50%",
          background: accent, color: "#fff", border: 0, cursor: "pointer", boxShadow: "0 6px 20px #4902a255", fontSize: 17 }}>
        <i className={`fa ${open ? "fa-xmark" : "fa-bell"}`} />
        {unread > 0 && (
          <span style={{ position: "absolute", top: -3, right: -3, background: "#ef4444", color: "#fff",
            borderRadius: 10, minWidth: 18, height: 18, fontSize: 10.5, fontWeight: 700, display: "flex",
            alignItems: "center", justifyContent: "center", padding: "0 4px" }}>{unread > 99 ? "99+" : unread}</span>
        )}
      </button>
    </div>
  );
}
