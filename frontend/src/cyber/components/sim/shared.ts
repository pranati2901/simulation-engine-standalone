// Shared helpers + palettes for the immersive scenario workspaces (W1/R5/C5).

export const STATE_COLOR: Record<string, string> = {
  healthy: "#1f8a4c", vulnerable: "#caa019", exploited: "#e07b39", infected: "#e0392b",
  propagating: "#ff5a4d", encrypting: "#b21f1f", impacted: "#111317", dormant: "#5b6b7a",
  contained: "#3b82f6", eradicated: "#22c55e", recovered: "#22c55e",
};
export const STATE_LABEL: Record<string, string> = {
  healthy: "Healthy", vulnerable: "Vulnerable", exploited: "Exploited", infected: "Infected",
  propagating: "Propagating", encrypting: "Encrypting", impacted: "Impacted", dormant: "Dormant",
  contained: "Contained", eradicated: "Eradicated", recovered: "Recovered",
};

export const TEAM_META: Record<string, { label: string; color: string; icon: string; blurb: string }> = {
  red: { label: "Red Team", color: "#ef4444", icon: "fa-skull", blurb: "Run the attack — real recon + the worm." },
  soc: { label: "SOC", color: "#a855f7", icon: "fa-magnifying-glass-chart", blurb: "Watch the funnel — detect, triage, escalate." },
  blue: { label: "Blue Team", color: "#3b82f6", icon: "fa-shield-halved", blurb: "Contain, eradicate, recover." },
  victim: { label: "Victim Desktop", color: "#eab308", icon: "fa-desktop", blurb: "See it from a user's seat." },
};

export const SEV_COLOR: Record<string, string> = {
  critical: "#ef4444", high: "#f59e0b", medium: "#eab308", low: "#60a5fa", info: "#94a3b8",
};

export const ROLE_ICONS = ["fa-desktop", "fa-server", "fa-database", "fa-user-shield", "fa-box-archive",
  "fa-envelope", "fa-network-wired"];
export const HOST_ICON: Record<string, string> = {
  workstation: "fa-desktop", fileserver: "fa-folder-open", database: "fa-database",
  domain_controller: "fa-user-shield", backup: "fa-box-archive", email: "fa-envelope", appserver: "fa-server",
};

export interface SimHost {
  id: string; name: string; vlan: string; role: string; state: string;
  vulnerable: boolean; revealed: boolean; patient_zero: boolean; flags: string[];
}

// Mirror of the engine's _hosts_for filters so tool-workspace forms list valid targets.
export function hostsForFilter(hosts: SimHost[], filter: string): SimHost[] {
  switch (filter) {
    case "exploitable": return hosts.filter((h) => h.vulnerable && h.revealed && ["healthy", "vulnerable"].includes(h.state));
    case "exploited": return hosts.filter((h) => h.state === "exploited");
    case "vulnerable": return hosts.filter((h) => h.vulnerable && ["healthy", "vulnerable"].includes(h.state));
    case "containable": return hosts.filter((h) => ["exploited", "infected", "propagating", "encrypting"].includes(h.state));
    case "impacted": return hosts.filter((h) => h.state === "impacted");
    default: return hosts;
  }
}

export const fmtUSD = (n: number) => (n >= 1000 ? `$${(n / 1000).toFixed(0)}k` : `$${n}`);
export const fmtT = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

// The exact shell command a tool wants the operator to TYPE in the terminal to run it. Every Red
// tool carries a `command_hint`; real tools without one fall back to their fire-action id.
export function toolCommand(tool: any): string {
  if (tool?.command_hint) return tool.command_hint;
  if (tool?.kind === "real") return tool.fire_action ? `run ${tool.fire_action}` : (tool.name || "").toLowerCase();
  return (tool?.name || "").toLowerCase();
}

// Normalised compare so typing is forgiving on case + whitespace, strict on the rest.
export const normCmd = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");
