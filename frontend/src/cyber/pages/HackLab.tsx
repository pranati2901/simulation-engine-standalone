import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { LabStatus } from "../api/types";
import { HACK_MISSIONS } from "../components/sim/HackLabData";
import NotificationDock, { NotifyMsg } from "../components/sim/NotificationDock";
import "../components/sim/sim.css";

/* HackLab — the Scenario Library experience: a real, terminal-focused hack lab.
   The inline Kali shell (ttyd) is the hero; the left rail carries the MISSION (brief, objectives,
   suggested commands, phases) and a "View app" button for the per-scenario custom DVWA that is the
   goal. No topology visualization, no exact-command gating — free run of the terminal, guided by a
   checklist you advance yourself. */
export default function HackLab() {
  const { scenarioId = "" } = useParams();
  const nav = useNavigate();
  const mission = HACK_MISSIONS[scenarioId];

  const [lab, setLab] = useState<LabStatus | null>(null);
  const [log, setLog] = useState<NotifyMsg[]>([]);
  const seq = useRef(0);
  const startT = useRef(Date.now());
  const pushLog = (title: string, text?: string, severity = "info") =>
    setLog((l) => [...l, { id: ++seq.current, title, text, severity, t: Math.round((Date.now() - startT.current) / 1000) }]);

  // Guided checklist progress (persisted per scenario).
  const doneKey = `gc_hacklab_done_${scenarioId}`;
  const [done, setDone] = useState<Set<number>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem(doneKey) || "[]")); } catch { return new Set(); }
  });
  const persist = (s: Set<number>) => localStorage.setItem(doneKey, JSON.stringify([...s]));

  // Poll the lab so the terminal + "View app" light up when the range comes online.
  useEffect(() => {
    let alive = true;
    const tick = () => api.labStatus().then((s) => { if (alive) setLab(s); }).catch(() => {});
    tick();
    const iv = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  // First mount: announce the mission.
  useEffect(() => {
    if (mission) pushLog(`Mission started: ${mission.name}`, mission.subtitle, "high");
  }, [scenarioId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!mission) {
    return <div style={{ padding: 40 }}>
      Unknown scenario. <button className="btn" onClick={() => nav("/library")}>Back to Library</button>
    </div>;
  }

  const termUrl = lab?.up ? lab?.terminal_url : "";
  const appUrl = lab?.target_urls?.[mission.targetId] || "";
  const totalObjectives = mission.phases.length;
  const completed = mission.phases.filter((_, i) => done.has(i)).length;
  const allDone = completed === totalObjectives;

  const toggle = (i: number, name: string) => {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else { next.add(i); pushLog(`Objective complete: ${name}`, undefined, "medium"); }
      persist(next);
      return next;
    });
  };

  const copy = (cmd: string) => {
    navigator.clipboard?.writeText(cmd).then(
      () => pushLog("Copied to clipboard", cmd, "info"),
      () => pushLog("Copy failed — select & copy manually", cmd, "low"));
  };

  const status = {
    label: allDone ? "All objectives complete 🎉" : `Objective ${completed + 1}/${totalObjectives}: ${mission.phases[Math.min(completed, totalObjectives - 1)].objective}`,
    detail: lab?.up ? "Range online — hack away in the shell." : "Range offline — start it to get the shell.",
  };

  return (
    <div className="ws-root" style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {/* top bar */}
      <div className="ws-topbar">
        <button className="ws-icon" onClick={() => nav("/library")} title="Back to Library"><i className="fa fa-arrow-left" /></button>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{mission.name}</div>
          <div style={{ fontSize: 11, color: mission.color }}>{mission.subtitle}</div>
        </div>
        <span className="mode-chip practice" style={{ marginLeft: 6 }}><i className="fa fa-terminal" /> Hack Lab</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <LabPill lab={lab} />
          {appUrl
            ? <a className="btn" href={appUrl} target="_blank" rel="noreferrer" style={{ padding: "6px 12px" }}><i className="fa fa-window-maximize" /> View app</a>
            : <button className="btn" disabled title="Start the range to open the target app" style={{ padding: "6px 12px", opacity: .55 }}><i className="fa fa-window-maximize" /> View app</button>}
          {termUrl && <a className="btn" href={termUrl} target="_blank" rel="noreferrer" style={{ padding: "6px 12px" }}><i className="fa fa-up-right-from-square" /> Pop out shell</a>}
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* MISSION sidebar */}
        <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid var(--gc-border)", background: "#fff",
          overflowY: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>

          {/* progress */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--gc-muted)", marginBottom: 4 }}>
              <span>Mission progress</span><span>{completed}/{totalObjectives}</span>
            </div>
            <div style={{ height: 6, borderRadius: 3, background: "var(--gc-border)" }}>
              <div style={{ height: "100%", borderRadius: 3, width: `${(completed / totalObjectives) * 100}%`,
                background: mission.gradient, transition: "width .4s" }} />
            </div>
          </div>

          {/* brief */}
          <div className="ws-card" style={{ borderLeft: `3px solid ${mission.color}` }}>
            <h3 style={{ marginTop: 0 }}><i className="fa fa-bullseye" style={{ color: mission.color, marginRight: 6 }} />Mission</h3>
            <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--gc-text2)" }}>{mission.brief}</div>
          </div>

          {/* target */}
          <div className="ws-card">
            <h3 style={{ marginTop: 0 }}><i className="fa fa-server" style={{ marginRight: 6, color: mission.color }} />Target</h3>
            <div style={{ fontSize: 12.5, lineHeight: 1.8 }}>
              <div><b>{mission.appName}</b></div>
              <div style={{ color: "var(--gc-muted)" }}>Host (from Kali): <code style={{ color: mission.color }}>{mission.appHost}</code></div>
              {mission.creds && <div style={{ color: "var(--gc-muted)" }}><i className="fa fa-key" /> {mission.creds}</div>}
              <div style={{ color: "var(--gc-muted)", fontSize: 11 }}>Goal flag: <code>{mission.flag}</code></div>
            </div>
            {appUrl
              ? <a className="btn btn-primary" href={appUrl} target="_blank" rel="noreferrer" style={{ marginTop: 8, width: "100%", justifyContent: "center" }}><i className="fa fa-window-maximize" /> View the app</a>
              : <div style={{ marginTop: 8, fontSize: 11, color: "var(--gc-muted)" }}><i className="fa fa-circle-info" /> Start the range to browse the app.</div>}
          </div>

          {/* phases / objectives / commands */}
          <div className="ws-card">
            <h3 style={{ marginTop: 0 }}><i className="fa fa-list-check" style={{ marginRight: 6, color: mission.color }} />Phases &amp; objectives</h3>
            <div style={{ fontSize: 10.5, color: "var(--gc-muted)", marginBottom: 8 }}>
              <i className="fa fa-keyboard" /> Free run of the shell — these are suggestions, not a script. Tick a phase when you've done it.
            </div>
            {mission.phases.map((ph, i) => {
              const isDone = done.has(i);
              return (
                <div key={i} style={{ marginBottom: 12, paddingBottom: 10, borderBottom: i < mission.phases.length - 1 ? "1px solid #f1edf7" : undefined }}>
                  <label style={{ display: "flex", gap: 8, alignItems: "flex-start", cursor: "pointer" }}>
                    <input type="checkbox" checked={isDone} onChange={() => toggle(i, ph.objective)} style={{ marginTop: 3 }} />
                    <span>
                      <span style={{ fontSize: 9.5, letterSpacing: .5, color: mission.color, fontWeight: 700 }}>PHASE {i + 1} · {ph.name.toUpperCase()}</span>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: isDone ? "var(--gc-muted)" : "var(--gc-text)", textDecoration: isDone ? "line-through" : undefined }}>{ph.objective}</div>
                      <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{ph.what}</div>
                    </span>
                  </label>
                  <div style={{ marginTop: 7, display: "grid", gap: 5 }}>
                    {ph.commands.map((c, j) => (
                      <div key={j} style={{ background: "#0b1020", borderRadius: 7, padding: "6px 8px", border: "1px solid #1e2740" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <code style={{ flex: 1, minWidth: 0, color: "#7dd3fc", fontSize: 11.5, wordBreak: "break-all", fontFamily: "ui-monospace,monospace" }}>{c.cmd}</code>
                          <button className="ws-icon" onClick={() => copy(c.cmd)} title="Copy command"
                            style={{ flexShrink: 0, width: 26, height: 24, color: "#94a3b8" }}><i className="fa fa-copy" /></button>
                        </div>
                        {c.note && <div style={{ fontSize: 10, color: "#64748b", marginTop: 3 }}>{c.note}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            {allDone && (
              <div style={{ marginTop: 6, background: "#052e2b", color: "#34d399", borderRadius: 8, padding: 10, fontSize: 12.5 }}>
                <i className="fa fa-flag-checkered" /> <b>Lab complete!</b> You captured <code style={{ color: "#6ee7b7" }}>{mission.flag}</code>.
              </div>
            )}
          </div>
        </div>

        {/* TERMINAL hero */}
        <div style={{ flex: 1, minWidth: 0, background: "#05080f", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "8px 14px", color: "#94a3b8", fontSize: 12, borderBottom: "1px solid #14213a", display: "flex", alignItems: "center", gap: 8 }}>
            <i className="fa fa-terminal" style={{ color: "#22d3ee" }} /> <b style={{ color: "#cbd5e1" }}>kali@gc-attacker</b>
            <span style={{ color: "#64748b" }}>— real shell · type any command, like a normal terminal</span>
          </div>
          <div style={{ flex: 1, minHeight: 0 }}>
            {termUrl
              ? <iframe title="Kali terminal" src={termUrl} style={{ width: "100%", height: "100%", border: 0, background: "#000" }} />
              : <RangeOffline lab={lab} onRefresh={() => api.labStatus().then(setLab).catch(() => {})} />}
          </div>
        </div>
      </div>

      <NotificationDock messages={log} status={status} accent={mission.color} />
    </div>
  );
}

function LabPill({ lab }: { lab: LabStatus | null }) {
  const up = !!lab?.up;
  const ready = !!lab?.attacker_ready;
  const c = up && ready ? "#22c55e" : up ? "#f59e0b" : "#94a3b8";
  const txt = !lab ? "checking…" : up && ready ? "Range online" : up ? "booting…" : "Range offline";
  return <span style={{ fontSize: 11.5, color: c, border: `1px solid ${c}66`, borderRadius: 6, padding: "2px 9px" }}>
    <i className="fa fa-circle" style={{ fontSize: 7, marginRight: 5, verticalAlign: "middle" }} />{txt}
  </span>;
}

function RangeOffline({ lab, onRefresh }: { lab: LabStatus | null; onRefresh: () => void }) {
  const cmd = "docker compose -f infrastructure/docker-compose.lab.yml -p gclab up -d";
  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", padding: 30 }}>
      <div style={{ maxWidth: 520, color: "#cbd5e1", textAlign: "center" }}>
        <i className="fa fa-plug-circle-xmark" style={{ fontSize: 34, color: "#64748b" }} />
        <h2 style={{ color: "#e2e8f0", marginTop: 14 }}>The Kali range isn't running</h2>
        <p style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.6 }}>
          {lab?.available === false
            ? "Docker isn't installed / reachable on this host. Install Docker Desktop, then start the range:"
            : "Start the local cyber-range (Kali attacker + the custom target apps), then this shell goes live:"}
        </p>
        <pre style={{ textAlign: "left", background: "#0b1020", color: "#7dd3fc", padding: 12, borderRadius: 8,
          fontSize: 12, overflow: "auto", border: "1px solid #1e2740" }}>{cmd}</pre>
        <p style={{ fontSize: 12, color: "#64748b" }}>One-time build: <code>pwsh infrastructure/lab-setup.ps1</code> (macOS/Linux: <code>bash infrastructure/lab-setup.sh</code>)</p>
        <button className="btn btn-primary" onClick={onRefresh} style={{ marginTop: 6 }}><i className="fa fa-rotate-right" /> Re-check</button>
      </div>
    </div>
  );
}
