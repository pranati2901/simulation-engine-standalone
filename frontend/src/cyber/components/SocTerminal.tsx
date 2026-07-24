import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

const THEME = {
  background: "#0a0e16",
  foreground: "#c8d6e5",
  cursor: "#E0A458",
  cursorAccent: "#0a0e16",
  selectionBackground: "#264f78",
  black: "#0a0e16",
  red: "#C8413E",
  green: "#3BA776",
  yellow: "#E6B400",
  blue: "#5B7FB0",
  magenta: "#c084fc",
  cyan: "#22d3a8",
  white: "#c8d6e5",
  brightBlack: "#4E5D73",
  brightRed: "#E07A3E",
  brightGreen: "#3BA776",
  brightYellow: "#E6B400",
  brightBlue: "#5B7FB0",
  brightMagenta: "#c084fc",
  brightCyan: "#22d3a8",
  brightWhite: "#E8EEF6",
};

export interface SocTerminalHandle {
  writeln: (text: string) => void;
  write: (text: string) => void;
  clear: () => void;
  writeAlert: (sev: string, source: string, msg: string) => void;
  writeStage: (index: number, title: string, mitre: string) => void;
  writeStory: (text: string) => void;
  writeFeedback: (correct: boolean, quality: string, msg: string) => void;
  writeNotification: (title: string, color?: string) => void;
}

const SEV_COLORS: Record<string, string> = {
  critical: "\x1b[1;31m", // bold red
  high: "\x1b[38;5;208m", // orange
  medium: "\x1b[33m", // yellow
  low: "\x1b[34m", // blue
  info: "\x1b[90m", // gray
};

const SocTerminal = forwardRef<SocTerminalHandle, { height?: string }>(({ height = "100%" }, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      theme: THEME,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: 13,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: "bar",
      scrollback: 5000,
      disableStdin: true,
      convertEol: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();
    termRef.current = term;
    fitRef.current = fit;

    // Banner
    term.writeln("\x1b[1;36m╔══════════════════════════════════════════════════════════╗\x1b[0m");
    term.writeln("\x1b[1;36m║\x1b[0m  \x1b[1;31mOPERATION TRIPWIRE\x1b[0m — Mercy Regional Health Network SOC   \x1b[1;36m║\x1b[0m");
    term.writeln("\x1b[1;36m║\x1b[0m  \x1b[90mWannaCry Ransomware Worm Simulation · MITRE ATT&CK®\x1b[0m      \x1b[1;36m║\x1b[0m");
    term.writeln("\x1b[1;36m╚══════════════════════════════════════════════════════════╝\x1b[0m");
    term.writeln("");

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      term.dispose();
    };
  }, []);

  useImperativeHandle(ref, () => ({
    writeln: (text: string) => termRef.current?.writeln(text),
    write: (text: string) => termRef.current?.write(text),
    clear: () => termRef.current?.clear(),

    writeAlert: (sev: string, source: string, msg: string) => {
      const t = termRef.current;
      if (!t) return;
      const now = new Date();
      const ts = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
      const sevColor = SEV_COLORS[sev] || "\x1b[90m";
      const sevLabel = sev.toUpperCase().padEnd(8);
      t.writeln(`\x1b[90m${ts}\x1b[0m ${sevColor}${sevLabel}\x1b[0m \x1b[36m[${source}]\x1b[0m ${msg}`);
    },

    writeStage: (index: number, title: string, mitre: string) => {
      const t = termRef.current;
      if (!t) return;
      t.writeln("");
      t.writeln(`\x1b[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m`);
      t.writeln(`\x1b[1;33m  ▶ STAGE ${index + 1}/11: ${title.toUpperCase()}\x1b[0m${mitre ? `  \x1b[38;5;208m[${mitre}]\x1b[0m` : ""}`);
      t.writeln(`\x1b[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m`);
      t.writeln("");
    },

    writeStory: (text: string) => {
      const t = termRef.current;
      if (!t) return;
      t.writeln(`\x1b[3;37m  "${text}"\x1b[0m`);
      t.writeln("");
    },

    writeFeedback: (correct: boolean, quality: string, msg: string) => {
      const t = termRef.current;
      if (!t) return;
      t.writeln("");
      const icon = correct ? "\x1b[1;32m✓\x1b[0m" : "\x1b[1;31m✗\x1b[0m";
      const qColor = quality === "optimal" ? "\x1b[1;32m" : quality === "acceptable" ? "\x1b[33m" : "\x1b[1;31m";
      t.writeln(`  ${icon} Identification: ${correct ? "\x1b[32mCORRECT\x1b[0m" : "\x1b[31mINCORRECT\x1b[0m"}`);
      t.writeln(`  ${icon} Response: ${qColor}${quality.toUpperCase()}\x1b[0m`);
      if (msg) t.writeln(`  \x1b[90m→ ${msg}\x1b[0m`);
      t.writeln("");
    },

    writeNotification: (title: string, color?: string) => {
      const t = termRef.current;
      if (!t) return;
      const c = color || "\x1b[1;36m";
      t.writeln("");
      t.writeln(`${c}╔${"═".repeat(56)}╗\x1b[0m`);
      t.writeln(`${c}║\x1b[0m  ${c}${title.padEnd(54)}\x1b[0m${c}║\x1b[0m`);
      t.writeln(`${c}╚${"═".repeat(56)}╝\x1b[0m`);
      t.writeln("");
    },
  }));

  return (
    <div ref={containerRef} style={{ height, background: "#0a0e16", borderRadius: 8, padding: 4, overflow: "hidden" }} />
  );
});

SocTerminal.displayName = "SocTerminal";
export default SocTerminal;
