import { KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import { fmtT, normCmd } from "./shared";

export interface StagedCmd {
  toolId: string;
  params: Record<string, string>;
  command: string;       // the exact command the operator must type
  label: string;         // human tool name (for the prompt)
  targetLabel?: string;  // chosen host/alert, shown as context
}

/* The Kali terminal dock — now interactive. Real tool output (live-fire) + sim command lines stream
   in from the event log; the operator STAGES a tool from the palette, then must TYPE its real command
   here to fire it (Tab autocompletes; `help`/`clear` are built in). That hands-on-keyboard loop is
   the "real hack" feel — no more one-click run. */
export default function Terminal({ events, termUrl, pending, canPlay, onExecute, error, height = 230,
  prompt = "kali@gc-attacker", title = "kali@gc-attacker — terminal", intro, claimMsg = "claim the Red seat to run tools.",
  hint = "stage a tool, then type its command…", inflight = [] }:
  { events: any[]; termUrl?: string | null; pending: StagedCmd | null; canPlay: boolean;
    onExecute: (toolId: string, params: Record<string, string>) => void; error?: string | null; height?: number;
    prompt?: string; title?: string; intro?: ReactNode; claimMsg?: string; hint?: string;
    inflight?: { command: string; label: string; eta_ticks: number }[] }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(true);
  const [input, setInput] = useState("");
  const [scratch, setScratch] = useState<{ cls: string; text: string }[]>([]);  // local echoes (typed/err/sys)
  const [hist, setHist] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);

  // Authoritative output: the same event-derived command/output lines as before (keeps live-fire
  // results updating in place as they stream back from the lab).
  const lines = events.filter((e) => e.kind === "action" || (e.data && (e.data.command || e.data.live_fire)));

  // When a real command actually runs, an event lands → wipe the local scratch (typed hints/errors)
  // so the official output takes over and the dock stays clean.
  const lastSeq = useRef(-1);
  useEffect(() => {
    const max = events.reduce((m, e) => Math.max(m, e.seq ?? -1), -1);
    if (max > lastSeq.current) { lastSeq.current = max; setScratch([]); }
  }, [events]);

  // surface an engine-side rejection (e.g. target no longer valid) as a terminal error line
  useEffect(() => { if (error) setScratch((s) => [...s, { cls: "err", text: error }]); }, [error]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [lines.length, scratch.length, open, pending, inflight.length]);
  useEffect(() => { if (pending && open) inputRef.current?.focus(); }, [pending, open]);

  const echo = (cls: string, text: string) => setScratch((s) => [...s, { cls, text }]);

  const submit = () => {
    const cmd = input.trim();
    setInput("");
    setHistIdx(-1);
    if (!cmd) return;
    setHist((h) => (h[h.length - 1] === cmd ? h : [...h, cmd]));

    if (cmd === "clear") { setScratch([]); return; }
    if (cmd === "whoami") { echo("cmd", cmd); echo("sys", prompt.split("@")[0]); return; }
    if (cmd === "help") {
      echo("cmd", cmd);
      echo("sys", pending
        ? `staged: ${pending.label} — type:  ${pending.command}   (Tab autocompletes)`
        : "stage a tool from the palette on the left, then type its command here. built-ins: help · clear");
      return;
    }
    if (!pending) {
      echo("cmd", cmd);
      echo("err", "no command staged — pick a tool from the palette, then type the command it shows.");
      return;
    }
    if (!canPlay) { echo("cmd", cmd); echo("err", claimMsg); return; }
    if (normCmd(cmd) === normCmd(pending.command)) {
      onExecute(pending.toolId, pending.params);     // output streams back via events; scratch auto-clears
    } else {
      echo("cmd", cmd);
      echo("err", `not quite — type the staged command:  ${pending.command}`);
    }
  };

  const navHist = (dir: number) => {
    if (!hist.length) return;
    const cur = histIdx === -1 ? hist.length : histIdx;
    const idx = Math.max(0, Math.min(hist.length, cur + dir));
    setHistIdx(idx);
    setInput(idx >= hist.length ? "" : hist[idx]);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { e.preventDefault(); submit(); }
    else if (e.key === "Tab") { e.preventDefault(); if (pending) setInput(pending.command); }
    else if (e.key === "ArrowUp") { e.preventDefault(); navHist(-1); }
    else if (e.key === "ArrowDown") { e.preventDefault(); navHist(1); }
  };

  return (
    <div className="term">
      <div className="term-head" onClick={() => setOpen((o) => !o)}>
        <i className={`fa ${open ? "fa-chevron-down" : "fa-chevron-up"}`} />
        <i className="fa fa-terminal" /> {title}
        <span style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          {termUrl && <a href={termUrl} target="_blank" rel="noreferrer" style={{ color: "#22d3ee" }}
            onClick={(e) => e.stopPropagation()}><i className="fa fa-up-right-from-square" /> real shell</a>}
          <span>{lines.length} cmds</span>
        </span>
      </div>
      {open && (
        <div className="term-body" ref={bodyRef} style={{ height }} onClick={() => inputRef.current?.focus()}>
          <div style={{ color: "#64748b" }}>
            {intro ?? <>stage a tool from the palette, then <b style={{ color: "#94a3b8" }}>type its command</b> to run it.</>}
            {" "}Built-ins: <span className="term-cmd">help</span> · <span className="term-cmd">clear</span> · Tab autocompletes.
          </div>
          {lines.map((e, i) => <Line key={i} e={e} />)}
          {scratch.map((l, i) => (
            <div key={"s" + i} className="term-line">
              {l.cls === "cmd" && <span className="term-prompt">{prompt}:~$ </span>}
              <span className={l.cls === "err" ? "term-err" : l.cls === "cmd" ? "term-typed" : "term-sys"}>{l.text}</span>
            </div>
          ))}

          {inflight.map((f, i) => (
            <div key={"if" + i} className="term-line">
              <span className="term-prompt">{prompt}:~$ </span>
              <span className="term-cmd">{f.command}</span>
              <div style={{ color: "#eab308", marginLeft: 4 }}>
                <i className="fa fa-circle-notch fa-spin" /> running {f.label}…{" "}
                {f.eta_ticks > 0 ? `~${f.eta_ticks * 3}s remaining` : "finishing up…"}
              </div>
            </div>
          ))}

          {pending && !inflight.length && (
            <div className="term-stage">
              <i className="fa fa-keyboard" /> type: <span className="term-cmd">{pending.command}</span>
              {pending.targetLabel && <span className="term-target"> · target {pending.targetLabel}</span>}
              <span className="term-tab"> · Tab to autocomplete</span>
            </div>
          )}

          <div className="term-inline">
            <span className="term-prompt">{prompt}:~$</span>
            <input ref={inputRef} className="term-input" value={input} spellCheck={false} autoFocus
              autoComplete="off" autoCorrect="off" autoCapitalize="off"
              placeholder={pending ? "type the staged command…" : (canPlay ? hint : "spectating — " + claimMsg)}
              onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} />
          </div>
        </div>
      )}
    </div>
  );
}

function Line({ e }: { e: any }) {
  const lf = e.data?.live_fire;
  const cmd = e.data?.command;
  const result = e.data?.result;          // simulated output for sim/act tools (no real lab fire)
  return (
    <div className="term-line">
      <span style={{ color: "#475569" }}>[{fmtT(e.t)}] </span>
      {lf ? (
        <>
          <span className="term-cmd">$ {lf.command || `${lf.tool} (${lf.function})`}</span>
          {lf.status === "queued" && <span style={{ color: "#eab308" }}> · running {lf.tool}…</span>}
          {lf.output && <pre className="term-out">{lf.output}</pre>}
          {lf.detected && <div style={{ color: "#f59e0b" }}><i className="fa fa-eye" /> DETECTED — {lf.detection_evidence}</div>}
          {lf.status === "unavailable" && <div style={{ color: "#64748b" }}>{lf.output}</div>}
        </>
      ) : (
        <>
          {cmd
            ? <span className="term-cmd">$ {cmd}</span>
            : <span style={{ color: "#cbd5e1" }}>{e.title}</span>}
          {cmd && result && <pre className="term-out">{`> ${result}`}</pre>}
          {e.message && !cmd && <span style={{ color: "#64748b" }}> — {e.message}</span>}
        </>
      )}
    </div>
  );
}
