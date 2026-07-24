/**
 * PhaseCinematic — full-screen chapter title card on phase transitions.
 *
 * Like a game chapter screen: big phase name, MITRE ATT&CK tags,
 * Jilla narration line, scan-line overlay, auto-dismiss after 3.5s.
 */
import { useEffect, useState } from "react";

interface Props {
  phase: string;
  prevPhase?: string;
  role: string;
  mitreTags?: string[];
  subtitle?: string;
  onDismiss: () => void;
}

// MITRE ATT&CK technique IDs by phase
const PHASE_MITRE: Record<string, string[]> = {
  "Host Discovery": ["T1046 Network Service Discovery", "T1018 Remote System Discovery"],
  "SMB Enumeration": ["T1135 Network Share Discovery", "T1049 System Network Connections"],
  "Exploit": ["T1210 Exploitation of Remote Services", "T1190 Exploit Public-Facing Application"],
  "Payload": ["T1105 Ingress Tool Transfer", "T1059 Command and Scripting Interpreter"],
  "Persistence": ["T1543 Create or Modify System Process", "T1547 Boot or Logon Autostart"],
  "C2": ["T1071 Application Layer Protocol", "T1568 Dynamic Resolution"],
  "Lateral Movement": ["T1021 Remote Services", "T1570 Lateral Tool Transfer"],
  "Disable Recovery": ["T1490 Inhibit System Recovery", "T1489 Service Stop"],
  "Impact": ["T1486 Data Encrypted for Impact", "T1491 Defacement"],
  "Phishing": ["T1566 Phishing", "T1204 User Execution"],
  "Execution": ["T1059.001 PowerShell", "T1204.002 Malicious File"],
  "Discovery": ["T1087 Account Discovery", "T1482 Domain Trust Discovery"],
  "Credential Access": ["T1003 OS Credential Dumping", "T1558 Steal or Forge Kerberos Tickets"],
  "Reconnaissance": ["T1595 Active Scanning", "T1592 Gather Victim Host Information"],
  "Initial Access": ["T1078 Valid Accounts", "T1110 Brute Force"],
  "Exfiltration": ["T1041 Exfiltration Over C2 Channel", "T1567 Exfiltration Over Web Service"],
};

const PHASE_SUBTITLES: Record<string, Record<string, string>> = {
  red: {
    "Host Discovery": "Map the terrain. Find your targets.",
    "SMB Enumeration": "Not all hosts are vulnerable. Find the weak ones.",
    "Exploit": "The NSA's most powerful weapon is in your hands.",
    "Payload": "Turn a temporary shell into a permanent foothold.",
    "Persistence": "Survive reboots. Survive the defenders.",
    "C2": "The kill switch that stopped a global pandemic.",
    "Lateral Movement": "One host becomes a hundred. The worm awakens.",
    "Disable Recovery": "Cut the safety net. No going back.",
    "Impact": "The hospital goes dark.",
    "Phishing": "One click. That's all you need.",
    "Execution": "The macro fires. The payload downloads.",
    "Discovery": "Map the domain. Find the crown jewels.",
    "Credential Access": "The keys to the kingdom.",
    "Reconnaissance": "The EDR is blind. The window is open.",
    "Initial Access": "Password spray. Patience pays off.",
    "Exfiltration": "Steal the data. Insurance for the ransom.",
  },
  soc: {
    "Host Discovery": "Something is scanning your network. Can you spot it?",
    "SMB Enumeration": "Unusual SMB traffic at 3 AM. What does it mean?",
    "Exploit": "Suricata just lit up. This is not a drill.",
    "Payload": "A new executable appeared. Unsigned. Suspicious.",
    "Persistence": "Service creation detected. They're setting up camp.",
    "C2": "Periodic HTTPS beacons. Something is phoning home.",
    "Lateral Movement": "Your dashboard is exploding. Multiple alerts.",
    "Disable Recovery": "Shadow copies being deleted across the network.",
    "Impact": "The monitoring systems are going dark.",
    "Phishing": "A macro-enabled document slipped through. Who opened it?",
    "Execution": "PowerShell with base64. Classic dropper pattern.",
  },
  blue: {
    "Host Discovery": "The network looks clean. But for how long?",
    "SMB Enumeration": "SOC flagged unusual traffic. Investigate or lock down?",
    "Exploit": "EternalBlue signatures detected. Protect the critical assets.",
    "Payload": "Malware is resident. Isolate NOW or it spreads.",
    "Persistence": "Rebooting won't help. The worm comes back.",
    "C2": "The kill switch — your chance to stop everything.",
    "Lateral Movement": "It's a worm. Segment the network or lose it all.",
    "Disable Recovery": "The backup server is the last line of defense.",
    "Impact": "The damage is done. Recovery begins.",
  },
};

export default function PhaseCinematic({ phase, prevPhase, role, mitreTags, subtitle, onDismiss }: Props) {
  const [visible, setVisible] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);

  const tags = mitreTags || PHASE_MITRE[phase] || [];
  const sub = subtitle || PHASE_SUBTITLES[role]?.[phase] || PHASE_SUBTITLES.red[phase] || "";

  // Auto-dismiss after 3.5s
  useEffect(() => {
    const t1 = setTimeout(() => setFadeOut(true), 3000);
    const t2 = setTimeout(() => { setVisible(false); onDismiss(); }, 3500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [onDismiss]);

  if (!visible) return null;

  return (
    <div className={`phase-cine${fadeOut ? " fade-out" : ""}`} onClick={() => { setFadeOut(true); setTimeout(onDismiss, 400); }}>
      {/* Scan-line overlay */}
      <div className="phase-cine-scanlines" />

      {/* Phase number */}
      {prevPhase && (
        <div className="phase-cine-prev">
          <i className="fa fa-chevron-right" style={{ fontSize: 8 }} /> FROM: {prevPhase.toUpperCase()}
        </div>
      )}

      {/* Main title */}
      <div className="phase-cine-title">{phase}</div>

      {/* Subtitle */}
      {sub && <div className="phase-cine-sub">{sub}</div>}

      {/* MITRE tags */}
      {tags.length > 0 && (
        <div className="phase-cine-mitre">
          {tags.map((t, i) => (
            <span key={i} style={{ animationDelay: `${0.8 + i * 0.12}s` }}>{t}</span>
          ))}
        </div>
      )}

      {/* Click to skip */}
      <div className="phase-cine-skip">Click anywhere or wait...</div>
    </div>
  );
}
