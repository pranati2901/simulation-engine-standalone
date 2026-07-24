/**
 * Tool Registry — 20 reusable simulated tool modules for the cyber range.
 *
 * Each tool is a React component that renders a realistic-looking console/UI.
 * Tools are scene-driven: they receive data from the current scenario stage
 * and display contextually relevant information.
 *
 * Tools are grouped by team: Red (attacker), SOC (detection), Blue (response).
 */

export interface ToolDef {
  id: string;
  name: string;
  team: "red" | "soc" | "blue" | "system";
  icon: string;
  description: string;
}

export const TOOL_REGISTRY: ToolDef[] = [
  // Red Team
  { id: "email", name: "Email Simulator", team: "red", icon: "fa-envelope", description: "Phishing campaign management" },
  { id: "powershell", name: "PowerShell Engine", team: "red", icon: "fa-terminal", description: "Command execution & encoded payloads" },
  { id: "rdp", name: "RDP Simulator", team: "red", icon: "fa-desktop", description: "Remote desktop connections" },
  { id: "smb", name: "SMB Propagation", team: "red", icon: "fa-network-wired", description: "File share & lateral movement" },
  { id: "vpn", name: "VPN Gateway", team: "red", icon: "fa-lock", description: "VPN/remote access" },
  { id: "c2", name: "C2 Beacon", team: "red", icon: "fa-satellite-dish", description: "Command & control channel" },
  { id: "ransomware", name: "Ransomware Engine", team: "red", icon: "fa-skull-crossbones", description: "Encryption deployment" },
  { id: "exfil", name: "Exfiltration Module", team: "red", icon: "fa-cloud-upload-alt", description: "Data staging & upload" },

  // SOC
  { id: "siem", name: "SIEM Console", team: "soc", icon: "fa-chart-bar", description: "Alert queue, event correlation" },
  { id: "edr", name: "EDR Console", team: "soc", icon: "fa-virus-slash", description: "Process tree, detections" },
  { id: "hunt", name: "Threat Hunting", team: "soc", icon: "fa-search", description: "IOC search, MITRE mapping" },

  // Blue Team
  { id: "ir", name: "IR Console", team: "blue", icon: "fa-clipboard-list", description: "Incident timeline & actions" },
  { id: "backup", name: "Backup Recovery", team: "blue", icon: "fa-database", description: "Backup status & restore" },
  { id: "firewall", name: "Firewall Console", team: "blue", icon: "fa-shield-alt", description: "Rules & egress filtering" },
  { id: "iam", name: "IAM / MFA", team: "blue", icon: "fa-user-lock", description: "Account management & MFA" },
  { id: "assets", name: "Asset Management", team: "blue", icon: "fa-server", description: "Host inventory & isolation" },

  // Cross-team
  { id: "dns", name: "DNS Manager", team: "blue", icon: "fa-globe", description: "DNS queries & sinkhole" },
  { id: "http", name: "Traffic Analyzer", team: "soc", icon: "fa-exchange-alt", description: "HTTP/HTTPS traffic inspection" },
  { id: "ad", name: "Active Directory", team: "blue", icon: "fa-sitemap", description: "AD operations & queries" },

  // System
  { id: "scoring", name: "Scoring Engine", team: "system", icon: "fa-star", description: "Per-role scores & business impact" },
];

export const TOOLS_BY_ID = Object.fromEntries(TOOL_REGISTRY.map(t => [t.id, t]));

export const TEAM_COLORS: Record<string, string> = {
  red: "var(--gc-red)",
  soc: "#22d3a8",
  blue: "#5B8CFF",
  system: "var(--gc-accent)",
};

/** Which tools are active per scenario scene (tool_id -> scene indices) */
export const SCENARIO_TOOLS: Record<string, Record<string, number[]>> = {
  "scn-wannacry-w1": {
    smb: [0, 1, 6, 7], siem: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], edr: [2, 3, 4, 6, 7, 8, 9],
    hunt: [0, 1, 2, 6], firewall: [5, 6, 7], dns: [5], backup: [8, 9, 10],
    assets: [0, 1, 2, 6, 7, 8, 9, 10], ransomware: [9], ir: [7, 8, 9, 10], scoring: [10],
  },
  "scn-r5-phish2enc": {
    email: [0, 1], powershell: [1, 2], c2: [3], siem: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    edr: [1, 2, 3, 5, 8], hunt: [4, 5], rdp: [6], firewall: [3, 6], iam: [5, 6],
    backup: [7, 8, 9], ir: [6, 7, 8, 9], assets: [4, 5, 6, 7, 8], ransomware: [8],
    ad: [4, 5, 6], scoring: [9],
  },
  "scn-c5-edr-outage": {
    vpn: [1, 2], siem: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    edr: [0], hunt: [3, 4, 5, 6], http: [8], firewall: [2, 6, 8], iam: [1, 2, 5],
    ad: [4, 5, 6], backup: [9, 10, 12], ir: [6, 7, 8, 9, 10, 11, 12],
    assets: [3, 4, 5, 6, 9, 10], ransomware: [10], exfil: [8], dns: [2],
    scoring: [12],
  },
};

export function getActiveTools(scenarioId: string, sceneIndex: number): ToolDef[] {
  const mapping = SCENARIO_TOOLS[scenarioId];
  if (!mapping) return [];
  return TOOL_REGISTRY.filter(t => mapping[t.id]?.includes(sceneIndex));
}
