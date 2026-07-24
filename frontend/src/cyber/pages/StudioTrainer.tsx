import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { StudioGrade, StudioProcedure, StudioProcStep } from "../api/types";

type Action = { step_id: string; action: string };

export default function StudioTrainer() {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const domain = sp.get("domain") || "generic";
  const system = sp.get("system") || "System";
  const fault = sp.get("fault") || "none";
  const title = sp.get("title") || "";

  const [proc, setProc] = useState<StudioProcedure | null>(null);
  const [loading, setLoading] = useState(true);
  const [actions, setActions] = useState<Action[]>([]);
  const [grade, setGrade] = useState<StudioGrade | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [fault, title]);
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [grade]);

  async function load() {
    setLoading(true); setActions([]); setGrade(null);
    try {
      const r = await api.studioProcedure({ domain, system, fault, title });
      setProc(r.procedure);
    } catch (e) { alert("Failed to load procedure: " + e); }
    finally { setLoading(false); }
  }

  // re-grade authoritatively on every action
  useEffect(() => {
    if (!proc) return;
    api.studioGrade({ procedure: proc, actions }).then(setGrade).catch(() => {});
  }, [actions, proc]);

  const steps = proc?.steps ?? [];
  const doneSet = useMemo(() => new Set((grade?.log ?? []).filter((l) => l.ok && !l.skipped).map((l) => l.step_id)), [grade]);
  const statusOf = (s: StudioProcStep) =>
    doneSet.has(s.id) ? "done" : s.requires.every((r) => doneSet.has(r)) ? "next" : "blocked";
  const nextId = useMemo(() => steps.find((s) => statusOf(s) === "next")?.id, [steps, doneSet]);

  const act = (s: StudioProcStep, a: string) => { if (!doneSet.has(s.id)) setActions((x) => [...x, { step_id: s.id, action: a }]); };
  const reset = () => { setActions([]); setGrade(null); };

  const health = grade?.health_pct ?? 42;
  const score = grade?.score ?? 100;
  const gletter = grade?.grade ?? "A";
  const hColor = health >= 70 ? "#22c55e" : health >= 45 ? "#f59e0b" : "#ef4444";

  if (loading) return (
    <div className="card"><div className="center-empty" style={{ padding: "50px 20px" }}>
      <span className="spinner" style={{ width: 26, height: 26 }} />
      <div style={{ marginTop: 12 }}>Authoring the full repair procedure for this fault…</div>
    </div></div>
  );
  if (!proc) return null;

  return (
    <>
      <button className="btn btn-ghost" onClick={() => nav("/studio")} style={{ marginBottom: 12 }}><i className="fa fa-arrow-left" /> Studio</button>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title"><i className="fa fa-graduation-cap" /> {proc.title}
          <span className="scenario-badge badge-purple" style={{ marginLeft: 8 }}>training</span>
          <button className="btn btn-ghost" style={{ marginLeft: "auto", fontSize: 12 }} onClick={reset}><i className="fa fa-rotate-left" /> Reset</button>
        </div>
        <div style={{ fontSize: 13, color: "var(--gc-body)", marginTop: 4 }}>{proc.summary}</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 16, marginTop: 14, alignItems: "center" }}>
          <Gauge label="System health" pct={health} color={hColor} />
          <Gauge label="Progress" pct={steps.length ? ((grade?.performed ?? 0) / steps.length) * 100 : 0} color="var(--gc-accent)" text={`${grade?.performed ?? 0}/${steps.length}`} />
          <div style={{ textAlign: "center" }}>
            <div className="muted" style={{ fontSize: 12 }}>Score</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: hColor }}>{score} · {gletter}</div>
            <div className="muted" style={{ fontSize: 10 }}>{grade?.violations ?? 0} order/safety · {grade?.skips ?? 0} skipped</div>
          </div>
        </div>
        {grade?.complete && (
          <div className="card" style={{ marginTop: 14, borderColor: "rgba(34,197,94,.4)", background: "rgba(34,197,94,.06)" }}>
            <div style={{ fontWeight: 700, color: "#16a34a" }}><i className="fa fa-circle-check" /> System restored — procedure complete!</div>
            <div style={{ fontSize: 12.5, marginTop: 4 }}>{proc.success_criteria}</div>
            <div style={{ fontSize: 12, marginTop: 6 }}>Final score <b>{score} ({gletter})</b> — {grade.summary}</div>
          </div>
        )}
      </div>

      <div className="grid-2" style={{ alignItems: "start", gap: 18 }}>
        {/* steps */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}><i className="fa fa-list-check" /> Repair steps <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>perform in the right order — or experiment</span></div>
          {steps.map((s, i) => {
            const st = statusOf(s);
            const border = st === "done" ? "#22c55e" : s.id === nextId ? "var(--gc-accent)" : "var(--gc-border)";
            return (
              <div key={s.id} style={{ display: "flex", gap: 10, padding: "10px 12px", marginBottom: 8, borderRadius: 10, border: `1px solid ${border}`, background: st === "done" ? "rgba(34,197,94,.05)" : "var(--gc-surface)", opacity: st === "blocked" ? 0.7 : 1 }}>
                <div style={{ width: 26, height: 26, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 12, color: "#fff", background: st === "done" ? "#22c55e" : s.safety ? "#ef4444" : "var(--gc-accent)" }}>
                  {st === "done" ? "✓" : s.safety ? "!" : i + 1}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{s.title}
                    {s.safety && <span className="scenario-badge badge-red" style={{ marginLeft: 6, fontSize: 9 }}>safety</span>}
                    {s.requires.length > 0 && <span className="muted" style={{ fontSize: 10, marginLeft: 6 }}>after {s.requires.join(", ")}</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--gc-body)", marginTop: 2 }}>{s.action}</div>
                  {st !== "done" && (
                    <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                      <button className="btn btn-primary" style={{ fontSize: 11, padding: "5px 10px" }} onClick={() => act(s, "perform")}><i className="fa fa-play" /> Perform</button>
                      <button className="btn btn-ghost" style={{ fontSize: 11, padding: "5px 10px" }} onClick={() => act(s, "skip")}><i className="fa fa-forward-step" /> Skip</button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {proc.common_mistakes.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="builder-label">Common mistakes</div>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--gc-muted)" }}>
                {proc.common_mistakes.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            </div>
          )}
        </div>

        {/* decision log + coach */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 8 }}><i className="fa fa-clock-rotate-left" /> Decision outcomes</div>
            <div ref={logRef} style={{ maxHeight: 180, overflowY: "auto" }}>
              {(!grade || grade.log.length === 0) ? <div className="muted" style={{ fontSize: 13 }}>Perform or skip a step to see what happens.</div>
                : grade.log.map((e, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, padding: "6px 0", borderBottom: "1px solid var(--gc-border)" }}>
                    <span className="muted" style={{ fontFamily: "var(--mono)", fontSize: 11, minWidth: 24 }}>{e.step_id}</span>
                    <span style={{ fontSize: 12, color: e.ok ? "#16a34a" : e.severe ? "#ef4444" : "#f59e0b" }}>{e.text}</span>
                  </div>
                ))}
            </div>
          </div>
          <Coach proc={proc} fault={fault} system={system} doneSet={doneSet} health={health} />
        </div>
      </div>
    </>
  );
}

function Gauge({ label, pct, color, text }: { label: string; pct: number; color: string; text?: string }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 5 }}>
        <span className="muted">{label}</span><b style={{ color }}>{text ?? `${Math.round(pct)}%`}</b>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: "var(--gc-border)" }}>
        <div style={{ height: "100%", width: `${Math.max(0, Math.min(100, pct))}%`, borderRadius: 4, background: color, transition: "width .3s" }} />
      </div>
    </div>
  );
}

function Coach({ proc, fault, system, doneSet, health }: { proc: StudioProcedure; fault: string; system: string; doneSet: Set<string>; health: number }) {
  const [msgs, setMsgs] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight; }, [msgs, busy]);

  const send = async (text: string) => {
    const q = text.trim(); if (!q || busy) return;
    const next = [...msgs, { role: "user", content: q }];
    setMsgs(next); setInput(""); setBusy(true);
    try {
      const ctx = { scenario: proc.title, fault, system, procedure_summary: proc.summary,
        steps: proc.steps.map((s) => ({ id: s.id, title: s.title, requires: s.requires, safety: s.safety })),
        completed_steps: [...doneSet], system_health: `${health}%` };
      const r = await api.studioCoach({ messages: next, context: ctx });
      setMsgs((m) => [...m, { role: "assistant", content: r.reply }]);
    } catch { setMsgs((m) => [...m, { role: "assistant", content: "Sorry — coach unavailable." }]); }
    finally { setBusy(false); }
  };

  const suggestions = ["What if I skip the safety isolation?", "Why this step order?", "What's the riskiest mistake here?"];
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column" }}>
      <div className="card-title" style={{ marginBottom: 8 }}><i className="fa fa-comments" /> Training coach</div>
      <div ref={bodyRef} style={{ maxHeight: 240, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8, marginBottom: 8 }}>
        {msgs.length === 0 && (
          <div className="muted" style={{ fontSize: 12.5 }}>
            Ask me anything about this repair — e.g. <i>“what if I skip the isolation step?”</i>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "85%",
            background: m.role === "user" ? "var(--gc-accent)" : "var(--gc-surface)", color: m.role === "user" ? "#fff" : "var(--gc-text)",
            border: m.role === "user" ? "none" : "1px solid var(--gc-border)", borderRadius: 10, padding: "7px 11px", fontSize: 12.5, lineHeight: 1.5 }}>
            {m.content}
          </div>
        ))}
        {busy && <div className="muted" style={{ fontSize: 12 }}><span className="spinner" /> thinking…</div>}
      </div>
      {msgs.length === 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
          {suggestions.map((s) => <button key={s} className="filter-chip" style={{ fontSize: 10.5 }} onClick={() => send(s)}>{s}</button>)}
        </div>
      )}
      <div style={{ display: "flex", gap: 6 }}>
        <input className="form-input" value={input} placeholder="Ask the coach, or explore a what-if…"
          onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)} style={{ flex: 1 }} />
        <button className="btn btn-primary" disabled={busy} onClick={() => send(input)}><i className="fa fa-paper-plane" /></button>
      </div>
    </div>
  );
}
