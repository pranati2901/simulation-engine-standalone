/**
 * IncidentTicker — CNN-style breaking news crawler showing human impact.
 *
 * Headlines escalate as the attack progresses. GPT generates them
 * from sim events. Shows consequences, not technical details.
 */
import { useEffect, useRef, useState } from "react";

interface Props {
  sim: any;
  scenarioId: string;
}

// Pre-built headlines keyed by phase + infection thresholds
const W1_HEADLINES: Record<string, string[]> = {
  "Host Discovery": [
    "Mercy Regional Hospital IT department reports routine network maintenance",
    "NHS Digital publishes quarterly cybersecurity advisory for healthcare trusts",
  ],
  "SMB Enumeration": [
    "Minor IT service disruptions reported at several NHS trusts",
    "Hospital staff report slow network performance across multiple departments",
  ],
  "Exploit": [
    "BREAKING: Suspicious network activity detected at Mercy Regional Hospital",
    "NHS England monitoring reports of potential cyber incident at healthcare facility",
    "Hospital IT staff report unauthorized access attempts on internal systems",
  ],
  "Payload": [
    "DEVELOPING: Ransomware variant identified on hospital network",
    "Mercy Regional Hospital activates incident response protocol",
    "Patient appointment systems experiencing intermittent outages",
  ],
  "Persistence": [
    "Hospital confirms malware has established persistent access to systems",
    "IT security teams unable to remove infection through standard reboots",
    "NHS trust raises internal alert level to AMBER",
  ],
  "C2": [
    "ANALYSIS: Malware communicates with external command server",
    "Security researchers identify potential kill switch in ransomware code",
    "22-year-old researcher Marcus Hutchins tracks suspicious domain activity",
  ],
  "Lateral Movement": [
    "URGENT: Ransomware spreading rapidly across hospital network",
    "Multiple departments report computer screens displaying ransom demands",
    "Ambulance services begin diverting patients from affected hospitals",
    "BREAKING: NHS England declares major cyber incident across multiple trusts",
    "Emergency departments overwhelmed as digital systems fail across region",
  ],
  "Disable Recovery": [
    "Hospital backup systems compromised in escalating cyber attack",
    "IT teams report inability to restore from automated backup snapshots",
    "CRITICAL: Recovery options narrowing as attackers target backup infrastructure",
  ],
  "Impact": [
    "BREAKING: Mercy Regional Hospital cancels all non-emergency surgeries",
    "Cancer patients turned away as treatment systems go offline",
    "NHS estimates 80,000 endpoints affected across 81 health organizations",
    "UK Government convenes emergency COBRA meeting on NHS cyber attack",
    "Global damage from WannaCry ransomware estimated at $4 billion",
    "LATEST: 150+ countries affected — largest ransomware attack in history",
  ],
};

const R5_HEADLINES: Record<string, string[]> = {
  "Phishing": [
    "Routine business operations continue at MediumCorp Financial Services",
    "Industry report warns of increasing phishing attacks targeting financial sector",
  ],
  "Execution": [
    "MediumCorp IT detects unusual PowerShell activity on employee workstation",
    "Cybersecurity firm reports surge in macro-based malware campaigns",
  ],
  "Lateral Movement": [
    "BREAKING: Major financial services firm confirms data breach",
    "Client data potentially exposed in ransomware attack on financial services provider",
    "SEC investigating cybersecurity incident at registered investment firm",
  ],
  "Impact": [
    "BREAKING: REvil ransomware group demands $2.5M from financial services firm",
    "Trading operations suspended as systems encrypted in ransomware attack",
    "FBI Cyber Division investigating organized ransomware campaign",
  ],
};

const C5_HEADLINES: Record<string, string[]> = {
  "Reconnaissance": [
    "Major EDR vendor reports temporary service degradation affecting customers",
    "Managed service providers advised to monitor systems during EDR outage",
  ],
  "Initial Access": [
    "Cybersecurity advisory: Password spraying attacks targeting MSP platforms increase 300%",
  ],
  "Lateral Movement": [
    "BREAKING: Multiple organizations report simultaneous ransomware infections",
    "Supply chain attack suspected as 200+ companies hit in coordinated cyber assault",
    "CISA issues emergency directive regarding managed service provider compromise",
  ],
  "Impact": [
    "BREAKING: Largest supply chain ransomware attack in history hits 200 organizations",
    "Hospitals, schools, and law firms among victims of coordinated cyber attack",
    "Total ransom demands estimated at $400 million across affected organizations",
    "FBI launches joint investigation with international partners",
  ],
};

export default function IncidentTicker({ sim, scenarioId }: Props) {
  const [headlines, setHeadlines] = useState<string[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const lastPhaseRef = useRef("");
  const tickerRef = useRef<HTMLDivElement>(null);

  // Select headline bank based on scenario
  const getHeadlineBank = (): Record<string, string[]> => {
    const sid = scenarioId.toLowerCase();
    if (sid.includes("r5") || sid.includes("phish")) return R5_HEADLINES;
    if (sid.includes("c5") || sid.includes("edr")) return C5_HEADLINES;
    return W1_HEADLINES;
  };

  // Add headlines when phase changes or infection grows
  useEffect(() => {
    const phase = sim?.guide?.phase;
    if (!phase) return;

    const bank = getHeadlineBank();
    const phaseHeadlines = bank[phase] || [];

    if (phase !== lastPhaseRef.current) {
      lastPhaseRef.current = phase;
      // Add phase headlines that aren't already in the list
      const newOnes = phaseHeadlines.filter(h => !headlines.includes(h));
      if (newOnes.length > 0) {
        setHeadlines(prev => [...prev, ...newOnes]);
      }
    }

    // Add extra headlines based on infection count thresholds
    const infected = sim?.worm?.infected || 0;
    if (infected >= 5 && !headlines.includes("Multiple departments reporting system failures")) {
      setHeadlines(prev => [...prev, "Multiple departments reporting system failures"]);
    }
    if (infected >= 10 && !headlines.includes("URGENT: Hospital declares internal major incident")) {
      setHeadlines(prev => [...prev, "URGENT: Hospital declares internal major incident"]);
    }
    if (infected >= 20 && !headlines.includes("BREAKING: NHS England escalates to national cyber incident")) {
      setHeadlines(prev => [...prev, "BREAKING: NHS England escalates to national cyber incident"]);
    }
  }, [sim?.guide?.phase, sim?.worm?.infected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cycle through headlines
  useEffect(() => {
    if (headlines.length === 0) return;
    const interval = setInterval(() => {
      setCurrentIdx(prev => (prev + 1) % headlines.length);
    }, 6000);
    return () => clearInterval(interval);
  }, [headlines.length]);

  if (headlines.length === 0) return null;

  const isBreaking = headlines[currentIdx]?.startsWith("BREAKING") || headlines[currentIdx]?.startsWith("URGENT");

  return (
    <div className={`incident-ticker${isBreaking ? " breaking" : ""}`}>
      <div className="ticker-label">
        {isBreaking ? "BREAKING" : "NEWS"}
      </div>
      <div className="ticker-content">
        <div className="ticker-track" ref={tickerRef}>
          {headlines.map((h, i) => (
            <span key={i} className="ticker-item">
              <span className="ticker-bullet" />
              {h}
            </span>
          ))}
          {/* Duplicate for seamless loop */}
          {headlines.map((h, i) => (
            <span key={`dup-${i}`} className="ticker-item">
              <span className="ticker-bullet" />
              {h}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
