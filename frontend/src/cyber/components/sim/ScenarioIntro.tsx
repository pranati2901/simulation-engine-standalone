/**
 * ScenarioIntro — cinematic story briefing before the sim starts.
 *
 * Full-screen dark environment. Jilla narrates the incident backstory
 * with typewriter text. Student picks their role, then enters the sim.
 * Replaces the plain Landing component.
 */
import { useEffect, useRef, useState } from "react";
import { TEAM_META } from "./shared";

interface Props {
  meta: any;
  scenarioId: string;
  onLaunch: (name: string, role: string) => void;
  onBack: () => void;
}

// Scenario story intros — Jilla tells the backstory
// Full narratives per scenario per role — the story changes based on who you are
const SCENARIO_STORIES: Record<string, {
  date: string;
  headline: string;
  roles: Record<string, string[]>;  // role -> array of story paragraphs
}> = {
  "scn-wannacry-w1": {
    date: "MAY 12, 2017 — 07:44 UTC",
    headline: "Operation Tripwire",
    roles: {
      red: [
        "A vulnerability in Windows' SMBv1 protocol — codenamed EternalBlue — was stolen from the NSA and dumped online by the Shadow Brokers two months ago. Microsoft released a patch. Most hospitals didn't apply it.",
        "You are the operator. You've landed on a compromised host inside Mercy Regional Hospital — FIN-WS-014. The worm is loaded. 200 unpatched Windows machines sit on a flat, unsegmented network. Nobody is watching.",
        "Your mission: progress the kill chain. Scan the network. Find SMBv1 hosts. Exploit them. Drop the payload. Propagate. Encrypt. The kill chain that caused $4 billion in global damage starts with your next command.",
        "In the real WannaCry attack, this entire sequence — from first exploit to 200,000 encrypted machines — took less than 24 hours. You're about to learn how.",
      ],
      soc: [
        "It's 3 AM on a Friday night. You're the overnight SOC analyst at Mercy Regional Hospital. The Suricata dashboard shows normal traffic. Your coffee is still warm. It's been a quiet shift.",
        "But something is wrong. Somewhere on this network, an attacker has already compromised a host. FIN-WS-014 in the Finance VLAN is infected with a worm carrying the most powerful exploit ever leaked from a nation-state.",
        "You don't know this yet. Your job is to spot the first anomaly — the first unusual port scan, the first IDS signature, the first Sysmon alert — and escalate before the worm spreads to every machine in the hospital.",
        "In the real WannaCry attack, most SOC teams didn't notice until ransom notes appeared. The ones who caught it early saved their organizations. You have minutes, not hours.",
      ],
      blue: [
        "May 12, 2017. You're the incident response lead at Mercy Regional Hospital. NHS England is about to get hit by the largest ransomware attack in history. 80,000 endpoints. 81 health organizations. $92 million in damage.",
        "Your hospital runs the same unpatched Windows 7 fleet. The same flat network. The same exposed SMBv1. Right now, the network looks clean — but a worm is already dormant on one of your machines.",
        "Your job: contain the blast radius. Segment the VLANs. Protect the backup server. Find the kill switch. Every second you delay, the worm infects another host. Every host it infects costs the hospital $10,000 in recovery.",
        "The NHS hospitals that were network-segmented survived WannaCry. The flat ones were devastated. Which one will yours be?",
      ],
    },
  },
  "scn-r5-phishing": {
    date: "JULY 2, 2021 — 14:30 EST",
    headline: "Phishing to Encrypt",
    roles: {
      red: [
        "You're an affiliate operator for the REvil ransomware gang. The Ransomware-as-a-Service model means you keep 70% of every ransom payment. The toolkit is provided. You just need to get in.",
        "Your target: MediumCorp Financial Services. A mid-size investment firm. Their SecureMail webmail is internet-facing. You have a list of employee usernames from LinkedIn. One of them has a weak password.",
        "The plan: brute-force a mailbox, log in, find a vulnerability inside the app, and turn a weak password into remote code execution. This is the exact playbook that hit 1,500 organizations through Kaseya.",
        "One phishing email. One weak password. One unpatched diagnostics tool. That's the difference between a secure company and a $2.5 million ransom note.",
      ],
      soc: [
        "July 2, 2021. You're the SOC analyst monitoring MediumCorp Financial's environment. The email gateway just logged a spike in failed login attempts against the SecureMail system.",
        "Is it a brute-force attack? A misconfigured client? A user who forgot their password? You need to triage fast. In the real REvil campaigns, the window between initial access and ransomware deployment was sometimes less than 4 hours.",
        "Your tools: Zeek network logs, Suricata IDS, Sysmon endpoint telemetry. The attacker is using legitimate tools — hydra for brute-force, curl for exploitation. Your detections need to spot the behavior, not the tool.",
        "If you catch it here — at the brute-force stage — you save the company. If you miss it, the next alert you see will be a ransom note.",
      ],
      blue: [
        "You're the incident responder at MediumCorp Financial. The SOC just escalated: confirmed unauthorized access to an employee's mailbox via brute-forced credentials.",
        "The attacker is already inside the webmail system. They may have found internal vulnerabilities. Your job: contain before they pivot. Revoke the compromised credentials. Isolate the affected system. Assess the blast radius.",
        "In the real Kaseya/REvil incident, responders who moved in the first 30 minutes contained the breach to a single system. Those who waited lost entire domains.",
        "The clock started when the SOC escalated. Every minute you spend investigating is a minute the attacker spends moving laterally.",
      ],
    },
  },
  "scn-c5-edr": {
    date: "MARCH 15, 2022 — 02:00 UTC",
    headline: "EDR Outage Exploitation",
    roles: {
      red: [
        "GlobalTech MSP manages 200 client organizations. Their EDR vendor just pushed a bad update — 4 hours of complete endpoint blindness. No telemetry. No alerts. No detections. This is your window.",
        "The Conti ransomware group called this 'going dark.' When the watchers are blind, the attackers move. You've been monitoring GlobalTech for weeks, waiting for exactly this moment.",
        "Half the admin accounts share one password: Welcome2024! It passes every complexity policy. A password spray will find a valid login in under 30 seconds. From there, the RMM console gives you push access to every client.",
        "200 organizations. One compromised MSP. Zero endpoint visibility. This is supply chain ransomware at industrial scale.",
      ],
      soc: [
        "2 AM. Your EDR dashboard just went grey. 'Service degradation' the vendor says. Expected resolution: 4 hours. Your overnight analyst notes it in the ticket and moves on.",
        "But you have zero endpoint visibility across 200 client environments. If something happens in the next 4 hours, you won't see it. Your IDS is your only remaining sensor. Your network flow data is all you have.",
        "The Conti group specifically targeted EDR outages as attack windows. Their leaked playbook described the procedure: monitor vendor status pages, hit the MSP during maintenance, spray passwords while nobody's watching.",
        "What contingency do you activate when your primary detection capability goes dark? The answer to that question determines whether 200 organizations get encrypted tonight.",
      ],
      blue: [
        "The EDR is coming back online after a 4-hour outage. And the first thing it reports is devastating: ransomware binaries staged across multiple client environments.",
        "Someone got in during the blind spot. They used the MSP's own admin console to deploy malware to clients. Your own management tools became the attack vector.",
        "You have a decision: shut down the RMM console entirely (losing all management access to 200 clients) or try to push a kill command through the same compromised system. Either choice has consequences.",
        "In the real Conti era, this exact scenario played out dozens of times. The MSPs that had offline backup plans survived. The ones that didn't paid ransoms or went bankrupt.",
      ],
    },
  },
};

export default function ScenarioIntro({ meta, scenarioId, onLaunch, onBack }: Props) {
  const [visibleParas, setVisibleParas] = useState(0);
  const [role, setRole] = useState("red");
  const [name, setName] = useState(() => localStorage.getItem("gc_live_name") || "");
  const [ready, setReady] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const story = SCENARIO_STORIES[scenarioId] || SCENARIO_STORIES["scn-wannacry-w1"];
  const paragraphs = story.roles[role] || story.roles.red;

  // Reveal paragraphs one by one — restart when role changes
  useEffect(() => {
    setVisibleParas(0);
    setReady(false);
    let count = 0;
    timerRef.current = setInterval(() => {
      count++;
      setVisibleParas(count);
      if (count >= paragraphs.length) {
        clearInterval(timerRef.current!);
        setTimeout(() => setReady(true), 600);
      }
    }, 2200);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [scenarioId, role, paragraphs.length]);

  const skipToEnd = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setVisibleParas(paragraphs.length);
    setReady(true);
  };

  return (
    <div className="intro-screen" onClick={!ready ? skipToEnd : undefined}>
      {/* Scan-line overlay */}
      <div className="intro-scanlines" />

      {/* Back button */}
      <button className="intro-back" onClick={onBack}>
        <i className="fa fa-arrow-left" /> Back
      </button>

      <div className="intro-content">
        {/* Date stamp */}
        <div className="intro-date">{story.date}</div>

        {/* Headline */}
        <h1 className="intro-headline">{story.headline}</h1>
        <div className="intro-subtitle">{meta?.summary || "Cyber range simulation"}</div>

        {/* Role selection — ABOVE the story so clicking changes the narrative */}
        <div className="intro-section-label" style={{ marginBottom: 10 }}>YOUR PERSPECTIVE</div>
        <div className="intro-roles" style={{ marginBottom: 28 }}>
          {["red", "soc", "blue"].map(r => {
            const m = TEAM_META[r];
            return (
              <button key={r} className={`intro-role${role === r ? " selected" : ""}`}
                onClick={(e) => { e.stopPropagation(); setRole(r); }}
                style={{ "--role-color": m.color } as React.CSSProperties}>
                <div className="intro-role-icon"><i className={`fa ${m.icon}`} /></div>
                <div className="intro-role-name">{m.label}</div>
              </button>
            );
          })}
        </div>

        {/* Story paragraphs — change based on selected role, appear one by one */}
        <div className="intro-story" key={role}>
          {paragraphs.map((p, i) => (
            <p key={`${role}-${i}`} className={`intro-para${i < visibleParas ? " visible" : ""}`}>
              {p}
            </p>
          ))}
        </div>

        {/* Launch button — appears after story finishes */}
        {ready && (
          <div className="intro-launch">
            <div className="intro-name-row">
              <input className="intro-name-input" placeholder="Your name" value={name}
                onChange={e => setName(e.target.value)} onClick={e => e.stopPropagation()} />
              <button className="intro-start-btn" onClick={(e) => { e.stopPropagation(); onLaunch(name, role); }}>
                <i className="fa fa-play" /> Enter the Simulation
              </button>
            </div>
          </div>
        )}

        {/* Skip hint */}
        {!ready && (
          <div className="intro-skip">Click anywhere to skip</div>
        )}
      </div>

      {/* Jilla attribution */}
      <div className="intro-jilla-tag">
        <span className="intro-jilla-dot" /> Briefed by Jilla AI
      </div>
    </div>
  );
}
