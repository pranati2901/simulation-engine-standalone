/**
 * ThreatDossier — classified-document-style intel briefing cards.
 *
 * Styled like real intelligence reports with "CLASSIFIED" watermark,
 * typewriter font, threat actor profiles, and redacted fields.
 */

interface DossierField {
  label: string;
  value: string;
  redacted?: boolean;
}

interface Props {
  title: string;
  classification?: string;
  fields: DossierField[];
  mitreTags?: string[];
  summary?: string;
  onClose: () => void;
  visible: boolean;
}

// Pre-built dossiers for each scenario
export const DOSSIERS: Record<string, {
  title: string;
  classification: string;
  fields: DossierField[];
  mitreTags: string[];
  summary: string;
}> = {
  "scn-wannacry-w1": {
    title: "THREAT ACTOR PROFILE: LAZARUS GROUP",
    classification: "TOP SECRET // NOFORN",
    fields: [
      { label: "Actor Name", value: "Lazarus Group (APT38)" },
      { label: "Aliases", value: "Hidden Cobra, Zinc, Guardians of Peace" },
      { label: "Attribution", value: "Democratic People's Republic of Korea (DPRK)" },
      { label: "Motivation", value: "Financial gain, Espionage, Sabotage" },
      { label: "Active Since", value: "2009 (Sony Pictures hack: 2014)" },
      { label: "Primary Targets", value: "Financial institutions, Healthcare, Critical infrastructure" },
      { label: "Notable Campaigns", value: "Sony Pictures (2014), Bangladesh Bank ($81M, 2016), WannaCry (2017)" },
      { label: "Exploit Used", value: "EternalBlue (MS17-010) — leaked from NSA by Shadow Brokers" },
      { label: "Ransom Demanded", value: "$300-600 USD in Bitcoin per machine" },
      { label: "Total Damage", value: "$4 billion globally, $92 million NHS alone" },
      { label: "Kill Switch Domain", value: "iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea[.]com" },
      { label: "Discovered By", value: "Marcus Hutchins (MalwareTech), age 22" },
      { label: "NSA Internal Codename", value: "[REDACTED]", redacted: true },
      { label: "Shadow Brokers Identity", value: "[REDACTED]", redacted: true },
    ],
    mitreTags: ["T1210", "T1486", "T1490", "T1570", "T1059"],
    summary: "WannaCry (May 12, 2017) was the largest ransomware attack in history, affecting 200,000+ machines across 150 countries in under 24 hours. The worm exploited EternalBlue, a vulnerability in SMBv1, to self-propagate without user interaction. The outbreak was accidentally stopped when researcher Marcus Hutchins registered a hardcoded kill switch domain for $10.69.",
  },
  "scn-r5-phishing": {
    title: "THREAT ACTOR PROFILE: REVIL / SODINOKIBI",
    classification: "SECRET // REL TO FVEY",
    fields: [
      { label: "Actor Name", value: "REvil (Ransomware Evil)" },
      { label: "Aliases", value: "Sodinokibi, Gold Southfield" },
      { label: "Attribution", value: "Russian-speaking cybercriminal group" },
      { label: "Model", value: "Ransomware-as-a-Service (RaaS) — affiliates pay 20-30% cut" },
      { label: "Active Since", value: "April 2019 (successor to GandCrab)" },
      { label: "Primary Targets", value: "MSPs, Legal firms, Manufacturing, Healthcare" },
      { label: "Notable Campaigns", value: "Travelex ($2.3M, 2020), Kaseya ($70M demand, 2021), JBS Foods ($11M, 2021)" },
      { label: "Initial Access", value: "Phishing, RDP brute force, Supply chain compromise" },
      { label: "Double Extortion", value: "Encrypts files AND exfiltrates data for leak leverage" },
      { label: "Estimated Revenue", value: "$100M+ in first year of operations" },
      { label: "Arrested Members", value: "14 suspects identified by FBI (Jan 2022)" },
      { label: "Infrastructure Location", value: "[REDACTED]", redacted: true },
      { label: "Key Affiliate IDs", value: "[REDACTED]", redacted: true },
    ],
    mitreTags: ["T1566", "T1059.001", "T1486", "T1567", "T1078"],
    summary: "REvil pioneered the Ransomware-as-a-Service model, providing affiliate operators with ransomware toolkits in exchange for a percentage of ransom payments. Their Kaseya supply chain attack in July 2021 hit 1,500 organizations through a single MSP vulnerability, demonstrating the devastating multiplier effect of supply chain compromise.",
  },
  "scn-c5-edr": {
    title: "THREAT ACTOR PROFILE: CONTI",
    classification: "SECRET // ORCON",
    fields: [
      { label: "Actor Name", value: "Conti (Wizard Spider)" },
      { label: "Aliases", value: "Wizard Spider, Gold Ulrick, DEV-0193" },
      { label: "Attribution", value: "Russian-based organized cybercrime syndicate" },
      { label: "Structure", value: "Corporate-style organization with HR, developers, negotiators" },
      { label: "Active Since", value: "2020 (evolved from Ryuk ransomware)" },
      { label: "Estimated Revenue", value: "$180 million in 2021 alone" },
      { label: "Primary Targets", value: "Healthcare, MSPs, Government, Critical infrastructure" },
      { label: "Notable Campaigns", value: "Ireland HSE ($20M, 2021), Costa Rica government (2022)" },
      { label: "Playbook Leaked", value: "August 2021 — disgruntled affiliate published internal docs" },
      { label: "Tactic", value: "Target EDR outages as attack windows — 'going dark'" },
      { label: "Supply Chain Focus", value: "Compromise MSPs to hit hundreds of clients simultaneously" },
      { label: "Disbanded", value: "May 2022 (members joined BlackBasta, Royal, BlackCat)" },
      { label: "Internal Chat Logs", value: "[REDACTED]", redacted: true },
    ],
    mitreTags: ["T1078", "T1110", "T1486", "T1490", "T1041"],
    summary: "Conti operated like a Fortune 500 company — with HR departments, salary negotiations, and performance reviews. Their leaked internal playbook revealed methodical attack procedures, including specifically targeting EDR outages as windows of opportunity. After publicly supporting Russia's invasion of Ukraine, a Ukrainian researcher leaked 60,000+ internal chat messages, leading to the group's dissolution.",
  },
};

export default function ThreatDossier({ title, classification, fields, mitreTags, summary, onClose, visible }: Props) {
  if (!visible) return null;

  return (
    <div className="dossier-overlay" onClick={onClose}>
      <div className="dossier-card" onClick={e => e.stopPropagation()}>
        {/* CLASSIFIED watermark */}
        <div className="dossier-watermark">CLASSIFIED</div>

        {/* Header */}
        <div className="dossier-header">
          <span>{title}</span>
          <span className="dossier-class">{classification || "CLASSIFIED"}</span>
        </div>

        {/* Fields */}
        <div className="dossier-body">
          {fields.map((f, i) => (
            <div key={i} className="dossier-field">
              <div className="dossier-label">{f.label}</div>
              <div className={`dossier-value${f.redacted ? " redacted" : ""}`}>
                {f.redacted ? "████████████" : f.value}
              </div>
            </div>
          ))}

          {/* MITRE tags */}
          {mitreTags && mitreTags.length > 0 && (
            <div className="dossier-field">
              <div className="dossier-label">MITRE ATT&CK Techniques</div>
              <div className="dossier-tags">
                {mitreTags.map((t, i) => (
                  <span key={i} className="dossier-tag">{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          {summary && (
            <div className="dossier-field">
              <div className="dossier-label">EXECUTIVE SUMMARY</div>
              <div className="dossier-summary">{summary}</div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="dossier-footer">
          <span style={{ fontSize: 9, color: "#837b97" }}>GoalCert Intelligence Division</span>
          <button className="dossier-close-btn" onClick={onClose}>
            Close Briefing
          </button>
        </div>
      </div>
    </div>
  );
}
