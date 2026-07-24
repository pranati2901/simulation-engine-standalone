/**
 * InterceptedComms — fake Slack/email from inside the victim organization.
 *
 * Orwell-game-style intercepted communications that update in real-time
 * as the attack progresses. Shows the human side of the incident.
 */
import { useEffect, useRef, useState } from "react";

interface CommMessage {
  id: number;
  channel: string;      // "#general" | "#it-helpdesk" | "#incident-response" | "email"
  sender: string;
  initials: string;
  color: string;         // avatar color
  content: string;
  timestamp: string;
  urgent?: boolean;
}

interface Props {
  sim: any;
  scenarioId: string;
  visible: boolean;
  onClose: () => void;
}

// Pre-built comms keyed by phase
const W1_COMMS: Record<string, CommMessage[]> = {
  "Host Discovery": [
    { id: 1, channel: "#general", sender: "Mike Chen", initials: "MC", color: "#3b82f6",
      content: "Anyone else's computer running slow today? Takes forever to open Outlook.", timestamp: "7:48 AM" },
    { id: 2, channel: "#it-helpdesk", sender: "IT Bot", initials: "IT", color: "#6b7280",
      content: "Ticket #4521 — Slow network performance reported by 3 users in Finance. Assigned to L1.", timestamp: "7:52 AM" },
  ],
  "SMB Enumeration": [
    { id: 3, channel: "#it-helpdesk", sender: "James Park", initials: "JP", color: "#8b5cf6",
      content: "Getting a lot of port 445 traffic in the Zeek logs. Probably just the backup job running early?", timestamp: "8:01 AM" },
    { id: 4, channel: "#general", sender: "Dr. Sarah Chen", initials: "SC", color: "#ec4899",
      content: "Can't access patient records system. Says 'network path not found'. Anyone else?", timestamp: "8:04 AM" },
  ],
  "Exploit": [
    { id: 5, channel: "#it-helpdesk", sender: "James Park", initials: "JP", color: "#8b5cf6",
      content: "Suricata just flagged something — ET EXPLOIT EternalBlue signature. This is... this is real. Escalating NOW.", timestamp: "8:12 AM", urgent: true },
    { id: 6, channel: "#incident-response", sender: "Sarah Williams", initials: "SW", color: "#ef4444",
      content: "All hands. We have a confirmed EternalBlue exploit hit on FIN-WS-014. This is the same exploit from the Shadow Brokers dump. Activating IR playbook.", timestamp: "8:14 AM", urgent: true },
  ],
  "Payload": [
    { id: 7, channel: "#incident-response", sender: "James Park", initials: "JP", color: "#8b5cf6",
      content: "Sysmon shows new process on FIN-WS-014 — mssecsvc2.0. Unsigned binary writing to C:\\Windows. This is the payload.", timestamp: "8:18 AM", urgent: true },
    { id: 8, channel: "#it-helpdesk", sender: "Reception Desk", initials: "RD", color: "#f59e0b",
      content: "We're getting calls from Radiology — their PACS system just went down. Patients waiting for scans.", timestamp: "8:20 AM" },
  ],
  "Persistence": [
    { id: 9, channel: "#incident-response", sender: "Sarah Williams", initials: "SW", color: "#ef4444",
      content: "Tried rebooting FIN-WS-014. Malware came right back. It's installed as a Windows service. We need to reimage.", timestamp: "8:25 AM", urgent: true },
    { id: 10, channel: "#general", sender: "Dr. Raj Patel", initials: "RP", color: "#10b981",
      content: "I'm in the middle of a consultation and I can't pull up medication lists. Is IT working on this?", timestamp: "8:27 AM" },
  ],
  "C2": [
    { id: 11, channel: "#incident-response", sender: "James Park", initials: "JP", color: "#8b5cf6",
      content: "Found something weird in DNS logs. Every infected machine queries the same long domain before encrypting. If the domain resolves, the malware STOPS. Is this a kill switch?", timestamp: "8:32 AM", urgent: true },
    { id: 12, channel: "#incident-response", sender: "Sarah Williams", initials: "SW", color: "#ef4444",
      content: "Get DNS team on the phone NOW. If we can sinkhole that domain, we might stop the encryption.", timestamp: "8:33 AM", urgent: true },
  ],
  "Lateral Movement": [
    { id: 13, channel: "#general", sender: "Nurse Amy", initials: "NA", color: "#f43f5e",
      content: "My computer just showed a weird screen with a lock. Something about Bitcoin? What's happening??", timestamp: "8:38 AM", urgent: true },
    { id: 14, channel: "#incident-response", sender: "Sarah Williams", initials: "SW", color: "#ef4444",
      content: "It's spreading. We're seeing infections across Finance, Radiology, AND Admin. This is a WORM. It's self-propagating through SMB. We need to segment VLANs NOW.", timestamp: "8:40 AM", urgent: true },
    { id: 15, channel: "#it-helpdesk", sender: "IT Bot", initials: "IT", color: "#6b7280",
      content: "⚠️ 47 new tickets in the last 5 minutes. All reporting 'encrypted files' or 'ransom screen'. Queue overloaded.", timestamp: "8:42 AM", urgent: true },
    { id: 16, channel: "#general", sender: "Admin Office", initials: "AO", color: "#6366f1",
      content: "ALL STAFF: Do NOT use your computers. Disconnect from the network. We are experiencing a cybersecurity incident.", timestamp: "8:45 AM", urgent: true },
  ],
  "Disable Recovery": [
    { id: 17, channel: "#incident-response", sender: "James Park", initials: "JP", color: "#8b5cf6",
      content: "Bad news. They're deleting shadow copies. vssadmin.exe running across infected machines. Our backups—", timestamp: "8:48 AM", urgent: true },
    { id: 18, channel: "#incident-response", sender: "Sarah Williams", initials: "SW", color: "#ef4444",
      content: "ISOLATE THE BACKUP SERVER. Pull the network cable physically if you have to. DO IT NOW.", timestamp: "8:48 AM", urgent: true },
  ],
  "Impact": [
    { id: 19, channel: "email", sender: "CEO", initials: "CEO", color: "#1d1530",
      content: "To: Board of Directors\nSubject: URGENT — Cybersecurity Incident\n\nI'm writing to inform you that Mercy Regional is experiencing a significant ransomware attack. Our systems are encrypted. We have activated our incident response plan and engaged external forensic investigators. Patient safety is our top priority. Emergency services remain operational via paper-based procedures.\n\nI will provide an update within 2 hours.", timestamp: "9:15 AM", urgent: true },
    { id: 20, channel: "#general", sender: "HR Department", initials: "HR", color: "#8b5cf6",
      content: "All staff: Please go to paper-based procedures immediately. Patient safety comes first. IT is working to restore systems. Further updates will come via text message.", timestamp: "9:20 AM", urgent: true },
  ],
};

export default function InterceptedComms({ sim, scenarioId, visible, onClose }: Props) {
  const [messages, setMessages] = useState<CommMessage[]>([]);
  const [activeTab, setActiveTab] = useState<string>("#general");
  const lastPhaseRef = useRef("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Add messages when phase changes
  useEffect(() => {
    const phase = sim?.guide?.phase;
    if (!phase || phase === lastPhaseRef.current) return;
    lastPhaseRef.current = phase;

    const sid = scenarioId.toLowerCase();
    const bank = W1_COMMS; // TODO: add R5/C5 comms
    const phaseMessages = bank[phase] || [];

    if (phaseMessages.length > 0) {
      // Stagger message appearance
      phaseMessages.forEach((msg, i) => {
        setTimeout(() => {
          setMessages(prev => {
            if (prev.find(m => m.id === msg.id)) return prev;
            return [...prev, msg];
          });
        }, i * 1500); // 1.5s between messages
      });
    }
  }, [sim?.guide?.phase, scenarioId]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const tabs = ["#general", "#it-helpdesk", "#incident-response", "email"];
  const filteredMessages = messages.filter(m => m.channel === activeTab);
  const unreadCounts: Record<string, number> = {};
  tabs.forEach(t => { unreadCounts[t] = messages.filter(m => m.channel === t).length; });

  if (!visible) return null;

  return (
    <div className="comms-panel">
      <div className="comms-header">
        <i className="fa fa-satellite-dish" style={{ fontSize: 11, color: "var(--gc-red)" }} />
        <span className="comms-title">INTERCEPTED COMMUNICATIONS</span>
        <span className="comms-badge">CLASSIFIED</span>
        <button className="comms-close" onClick={onClose}>
          <i className="fa fa-times" />
        </button>
      </div>

      {/* Channel tabs */}
      <div className="comms-tabs">
        {tabs.map(t => (
          <button key={t} className={`comms-tab${activeTab === t ? " active" : ""}`}
            onClick={() => setActiveTab(t)}>
            {t === "email" ? <i className="fa fa-envelope" style={{ fontSize: 10 }} /> : <span style={{ color: "var(--gc-muted)" }}>#</span>}
            <span>{t === "email" ? "Email" : t.replace("#", "")}</span>
            {unreadCounts[t] > 0 && <span className="comms-count">{unreadCounts[t]}</span>}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="comms-messages" ref={scrollRef}>
        {filteredMessages.length === 0 && (
          <div className="comms-empty">
            <i className="fa fa-lock" style={{ fontSize: 20, color: "var(--gc-muted)", marginBottom: 8 }} />
            <div>No intercepted messages in this channel yet.</div>
            <div style={{ fontSize: 10, color: "var(--gc-muted)" }}>Messages appear as the incident progresses.</div>
          </div>
        )}
        {filteredMessages.map(msg => (
          <div key={msg.id} className={`comms-msg${msg.urgent ? " urgent" : ""}`}>
            <div className="comms-msg-avatar" style={{ background: msg.color }}>
              {msg.initials}
            </div>
            <div className="comms-msg-body">
              <div className="comms-msg-meta">
                <span className="comms-msg-sender">{msg.sender}</span>
                <span className="comms-msg-time">{msg.timestamp}</span>
              </div>
              <div className="comms-msg-text">{msg.content}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
