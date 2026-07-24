/**
 * Per-scenario, per-phase narrative text for the guided tutorial.
 * Short and crisp — 2-3 sentences per field.
 */

export interface PhaseNarrative {
  stage: string;           // matches tool.stage in the backend
  name: string;            // "Phase 1: Reconnaissance"
  subtitle: string;        // "Mapping the battlefield"
  briefing: string;        // what this phase is about
  red: string;             // what Red is doing
  soc: string;             // what SOC should watch for
  blue: string;            // what Blue can do
}

export interface ScenarioStory {
  id: string;
  title: string;
  subtitle: string;
  intro: string;           // opening narrative
  setting: string;
  phases: PhaseNarrative[];
}

export const STORIES: Record<string, ScenarioStory> = {
  "scn-wannacry-w1": {
    id: "scn-wannacry-w1",
    title: "Operation Tripwire",
    subtitle: "WannaCry-Style SMB Worm",
    setting: "Mercy Regional Health Network — 250-host hospital",
    intro: "Friday, 16:42. A radiology workstation that nobody patched in months is about to bring down the entire hospital. You're about to experience the anatomy of a ransomware worm — from the attacker's first scan to the last encrypted file.",
    phases: [
      { stage: "Host Discovery", name: "Phase 1: Reconnaissance", subtitle: "Mapping the battlefield",
        briefing: "Every attack starts with discovery. The worm needs to know what's on the network before it can strike.",
        red: "You're scanning the subnet to find live hosts. This is how every real attack begins — quiet, methodical mapping.",
        soc: "Watch Zeek for horizontal scan patterns — one source hitting many destinations on port 445.",
        blue: "No action yet. The scan is happening, but you may not know it." },
      { stage: "SMB Enumeration", name: "Phase 2: Target Selection", subtitle: "Finding the weak links",
        briefing: "Not every host is vulnerable. The worm looks specifically for SMBv1 — a legacy protocol with a critical flaw.",
        red: "You're identifying which hosts still run the vulnerable SMBv1 protocol. These are your targets.",
        soc: "SMB enumeration may generate subtle traffic. Look for connection attempts on port 445 with SMBv1 negotiation.",
        blue: "If you could see this, you'd want to disable SMBv1 everywhere. But detection hasn't happened yet." },
      { stage: "Exploit", name: "Phase 3: Initial Exploitation", subtitle: "The door opens",
        briefing: "EternalBlue. A buffer overflow in SMBv1 that gives the attacker remote code execution — no password, no user interaction needed.",
        red: "Fire the EternalBlue exploit at a vulnerable host. If it works, you have code execution.",
        soc: "This is your loudest signal. Suricata will fire an exploit signature — don't miss it.",
        blue: "If the SOC escalates, you can isolate the exploited host immediately." },
      { stage: "Payload", name: "Phase 4: Payload Delivery", subtitle: "The worm takes hold",
        briefing: "The exploit gave a shell. Now the attacker drops the actual worm binary and runs it.",
        red: "Deploy the worm payload. Once running, this host becomes the launch pad for everything that follows.",
        soc: "Sysmon shows an unsigned executable spawned from an unusual parent process.",
        blue: "If you isolate now, you contain it to one host. Every second of delay multiplies the damage." },
      { stage: "Persistence", name: "Phase 5: Persistence", subtitle: "Surviving the reboot",
        briefing: "Malware that doesn't survive a reboot is amateur. Real worms install themselves as services or auto-run entries.",
        red: "Install a Windows service so the worm auto-starts at boot. Now reimaging is the only way to clean it.",
        soc: "Sysmon Event ID 6/7: new service created. This is a strong persistence indicator.",
        blue: "Simply rebooting won't help. You need to delete the service AND reimage the host." },
      { stage: "C2", name: "Phase 6: Kill-Switch Check", subtitle: "The worm's secret weakness",
        briefing: "WannaCry checks a hardcoded domain before encrypting. If it resolves, the worm stops. This became the famous accidental kill-switch.",
        red: "The worm checks its kill-switch domain. If it's unreachable, it commits to spreading and encrypting.",
        soc: "DNS logs show a query for a newly-seen, suspicious domain. This is a C2 indicator.",
        blue: "Sinkhole the domain! If you register/redirect it before the worm checks, every infected host goes dormant." },
      { stage: "Lateral Movement", name: "Phase 7: Propagation", subtitle: "One becomes many",
        briefing: "This is what makes WannaCry a WORM. It doesn't wait — it automatically scans and exploits every reachable vulnerable host.",
        red: "Unleash the propagation engine. Watch the red zone expand across VLANs in real-time.",
        soc: "Massive 445/tcp traffic spike. Multiple new IDS alerts. The infection is exponential.",
        blue: "SEGMENT NOW. Cut the VLAN boundaries on port 445. This is the single most effective containment action." },
      { stage: "Disable Recovery", name: "Phase 8: Disable Recovery", subtitle: "Cutting the safety net",
        briefing: "Before encrypting, the worm destroys Windows shadow copies and backup catalogs. No rollback. No undo.",
        red: "Delete shadow copies on all infected hosts. If the backup server is also hit, recovery is impossible.",
        soc: "Sysmon shows vssadmin.exe deleting shadow copies — a critical ransomware precursor.",
        blue: "Protect the backup server (BKP-01) NOW. If it survives, you can recover. If not, you're paying ransom." },
      { stage: "Impact", name: "Phase 9: Encryption", subtitle: "The hospital goes dark",
        briefing: "Files are encrypted with AES-128 + RSA-2048. Ransom notes appear. Radiology can't pull images. The ED goes to paper.",
        red: "Deploy the ransomware. Every infected host encrypts its files and shows the ransom note.",
        soc: "Mass file modification alerts. .WNCRY extension. The incident is now undeniable.",
        blue: "Prevention has failed. Focus on containing what remains and assessing backup viability." },
      { stage: "Contain", name: "Phase 10: Containment & Recovery", subtitle: "Picking up the pieces",
        briefing: "The attack is done. Now it's about how fast you recover — and what you learn.",
        red: "Your mission is complete. The outcome depends on how much spread before defenders contained it.",
        soc: "Build the timeline. Document everything. Your analysis feeds the after-action report.",
        blue: "Restore from backups if they survived. Reimage infected hosts. Patch everything. Brief the board." },
    ],
  },

  "scn-r5-phishing": {
    id: "scn-r5-phishing",
    title: "Phishing to Encrypt",
    subtitle: "Human-Operated Ransomware Campaign",
    setting: "MediumCorp — 85-host enterprise, Active Directory domain mediumcorp.local",
    intro: "Tuesday, 09:14. A Finance clerk named j.harper opens what looks like a routine Q4 invoice. There's no exploit here, no zero-day — just a believable email and one click. Over the next hour you'll watch a careful, hands-on-keyboard operator turn that single mistake into a domain-wide ransomware detonation. Every phase is a place the defenders could have broken the chain.",
    phases: [
      { stage: "Phishing", name: "Phase 1: Initial Access", subtitle: "One email, one click",
        briefing: "Human-operated ransomware almost never starts with an exploit — it starts with a person. The attacker just needs one user to open one attachment.",
        red: "Send a believable 'Q4 Invoice' with a macro-enabled attachment to the Finance team. No CVE needed — this is pure social engineering.",
        soc: "Watch the email gateway: a macro-enabled .docm from a look-alike external sender to Finance. Catch it here and nothing else happens.",
        blue: "Nothing to contain yet — the email is in the inbox. This is detection's earliest and cheapest chance." },
      { stage: "Execution", name: "Phase 2: Execution", subtitle: "Enable Content = compromise",
        briefing: "When the user clicks 'Enable Content', the macro runs PowerShell that fetches the real payload. Office spawning a script interpreter is one of the loudest signals in security.",
        red: "Your macro fires a hidden, encoded PowerShell loader. WINWORD → cmd → powershell is the chain that gives you code execution.",
        soc: "Sysmon EID 1: WINWORD.EXE spawning powershell.exe -enc. This is near-zero false positive — triage it FAST.",
        blue: "If the SOC escalates this, isolate FIN-PC07 immediately. Right now you can still stop the entire campaign at host one." },
      { stage: "Persistence", name: "Phase 3: Persistence", subtitle: "Surviving the reboot",
        briefing: "The attacker disguises a scheduled task as a Windows update so the foothold survives logoff and reboot.",
        red: "Register a scheduled task ('WindowsUpdateCheck') that relaunches your loader every 15 minutes. Now a reboot won't save them.",
        soc: "Security 4698 / Sysmon: a new scheduled task launching PowerShell, created outside any change window. Strong persistence indicator.",
        blue: "Cleaning this host now means killing the process AND deleting the task — a reboot alone won't evict the attacker." },
      { stage: "C2", name: "Phase 4: Command & Control", subtitle: "Hands on the keyboard",
        briefing: "An encrypted, cloud-fronted HTTPS beacon turns a script into an intrusion. The operator now drives the attack live, hidden in normal-looking traffic.",
        red: "Open your C2 beacon with jittered HTTPS check-ins. You now have interactive control and stop running canned scripts.",
        soc: "Proxy logs: regular, same-size POSTs with jitter to a newly-seen cloud domain — the classic beacon rhythm.",
        blue: "Sinkhole the C2 domain NOW and the operator loses control — they can't run discovery, dumping or lateral commands without it." },
      { stage: "Discovery", name: "Phase 5: AD Discovery", subtitle: "Mapping the path to Domain Admin",
        briefing: "BloodHound graphs every account, group and trust to reveal the shortest path to Domain Admin — here, an over-privileged service account.",
        red: "Run BloodHound to map Active Directory. It flags svc_backup: a service account that's needlessly in Domain Admins.",
        soc: "DC log 1644: one workstation issuing thousands of LDAP queries in seconds. Bulk AD enumeration is a recon tell.",
        blue: "The attacker is shopping for a path to your servers. Tightening service-account privileges is the structural fix; right now, cut C2 to stall them." },
      { stage: "Credential Access", name: "Phase 6: Credential Theft", subtitle: "Stealing the keys",
        briefing: "Dumping LSASS hands the attacker valid Domain Admin credentials — no cracking, just memory access via a living-off-the-land binary.",
        red: "MiniDump LSASS with comsvcs.dll and extract the svc_backup Domain Admin password. This is your pivot to the whole domain.",
        soc: "Sysmon EID 10: comsvcs.dll accessing lsass.exe memory. Near-certain credential theft — high-confidence alert.",
        blue: "This is your last clean window. Reset svc_backup (and krbtgt) now and the next stage — lateral movement — simply fails." },
      { stage: "Lateral Movement", name: "Phase 7: Lateral Movement", subtitle: "Spreading as an admin",
        briefing: "The attacker moves with VALID credentials, not exploits — to the servers they look exactly like a busy administrator. Patching can't stop this.",
        red: "RDP/PsExec onto FS-01, BKP-01 and DC-01 with svc_backup. Hit the backups first so recovery dies with everything else.",
        soc: "A service account interactively logging into servers it never touches. Anomalous-logon detection (UEBA) is what catches this.",
        blue: "Patching is useless here. Reset the stolen account to kill the spread, and segment user VLANs from the server farm to cap the blast radius." },
      { stage: "Disable Recovery", name: "Phase 8: Inhibit Recovery", subtitle: "Cutting the safety net",
        briefing: "Before encrypting, the attacker deletes shadow copies and stops the backup service — and if they reached BKP-01, offline restore dies too.",
        red: "vssadmin delete shadows + stop the backup agent on every foothold. No 'restore previous version', no easy way out.",
        soc: "Sysmon: vssadmin delete shadows /all across multiple servers. This is the unmistakable 'encryption is imminent' signal.",
        blue: "If BKP-01 isn't yet compromised, air-gap it THIS SECOND. Surviving backups are the difference between recovery and paying the ransom." },
      { stage: "Impact", name: "Phase 9: Encryption", subtitle: "MediumCorp goes dark",
        briefing: "The encryptor is pushed to every controlled host at once. Files become .locked, ransom notes appear, and the business stops.",
        red: "Deploy ransomware to all footholds simultaneously. By the time anyone reads the note, it's already done.",
        soc: "Sysmon EID 11: thousands of files rewritten to .locked across the fleet. Full detonation — the incident is now undeniable.",
        blue: "Prevention has failed. Restore from clean backups if they survived, reimage hosts, reset every credential, and brief leadership." },
    ],
  },

  "scn-c5-edr": {
    id: "scn-c5-edr",
    title: "EDR Outage Exploitation",
    subtitle: "Attacking During Blindness",
    setting: "GlobalTech — 500-host enterprise, Active Directory domain globaltech.com",
    intro: "Friday, 11:47. GlobalTech's EDR vendor just pushed a bad update — every endpoint sensor across 500 machines is offline, and IT is scrambling to roll back. For the next few hours, the organization is blind. A ransomware crew has been watching the vendor's status page, and they're about to walk straight through the front door while no one is looking. This scenario is about defense-in-depth: when your primary control fails, what's left?",
    phases: [
      { stage: "Reconnaissance", name: "Phase 1: Outage Watch", subtitle: "Striking the blind window",
        briefing: "The whole attack is built on timing. With the EDR sensors offline, the most reliable detection control is gone — and the crew knows it.",
        red: "Watch the vendor status page and map GlobalTech's external surface. Silent, external, undetectable — you're just waiting for the green light.",
        soc: "You can't see this. But you SHOULD already be on alert: your EDR is down, which means you're operating blind and need compensating monitoring now.",
        blue: "The EDR outage IS the incident. Stand up Sysmon + log forwarding immediately — don't wait for an alert that your blinded sensors can't generate." },
      { stage: "Initial Access", name: "Phase 2: Initial Access", subtitle: "Spray, then walk in",
        briefing: "No exploit needed. Spray common passwords at the VPN, take the handful that work, and log in like a remote employee.",
        red: "Spray one common password across 200 accounts, then VPN in through a Tor exit with the creds that work. You're inside with a valid login.",
        soc: "Identity is your front line now. Azure AD shows one source hitting many accounts (spray); the VPN log shows a Tor exit + impossible travel. Both are catchable.",
        blue: "Enforce MFA on all remote access NOW — it makes the sprayed passwords useless. Block anonymous/Tor source IPs at the VPN." },
      { stage: "Execution", name: "Phase 3: Execution", subtitle: "The toolkit lands clean",
        briefing: "The attacker drops PsExec and a credential dumper — the exact things EDR is built to block. But it's offline.",
        red: "Stage your toolkit in C:\\ProgramData. On a normal day the EDR kills this instantly; today it lands clean.",
        soc: "If compensating Sysmon is up, EID 11 shows the tool file-writes. If not, this is invisible — which is why standing up Sysmon was priority one.",
        blue: "This is the cost of relying on one control. With Sysmon + WEF live, you see the toolkit drop and can isolate the host before it's used." },
      { stage: "Discovery", name: "Phase 4: AD Discovery", subtitle: "Mapping the path to Domain Admin",
        briefing: "BloodHound graphs the domain to find the shortest path to a Domain Admin account whose token is within reach.",
        red: "Run SharpHound to map every admin account, group and ACL. In a 500-host domain there's always a path to DA.",
        soc: "DC log 1644: thousands of LDAP queries from one workstation. Bulk AD enumeration is a recon tell — easy to miss in the outage chaos.",
        blue: "Tier your admin accounts and remove standing Domain Admin rights — break the graph path the attacker is shopping for." },
      { stage: "Credential Access", name: "Phase 5: Credential Theft", subtitle: "Dumping the master key",
        briefing: "procdump — a signed Microsoft tool — MiniDumps LSASS and hands over a Domain Admin credential. No malware, no exploit.",
        red: "Dump LSASS with the signed procdump binary to extract Domain Admin creds. Signature checks won't flag a legitimate Sysinternals tool.",
        soc: "Sysmon EID 10: procdump opening a handle to lsass.exe. The EDR rule for this is offline — Sysmon is the only thing that catches it.",
        blue: "This is your last clean window. Disable the Domain Admin account and rotate krbtgt NOW — the next stage fails without those creds." },
      { stage: "Lateral Movement", name: "Phase 6: Lateral Movement", subtitle: "Owning the data center",
        briefing: "With a Domain Admin token and PsExec, the attacker authenticates to server after server — 47 logons across 43 hosts in 12 minutes.",
        red: "PsExec across the server farm as Domain Admin. Valid logons, no exploit — patching is irrelevant and the EDR is blind.",
        soc: "Network detection still works: Zeek/NetFlow shows one host fanning out SMB/RDP to dozens of servers. That east-west spray is unmistakable.",
        blue: "Disable the stolen admin account to kill the spread, and segment corporate from the server farm. Credentials still work — but the road is cut." },
      { stage: "Exfiltration", name: "Phase 7: Exfiltration", subtitle: "Steal first, encrypt second",
        briefing: "Modern ransomware is double extortion. The crew uploads 200GB of HR, finance and IP data before encrypting anything.",
        red: "Rclone 200GB of crown-jewel data to mega.nz. Even if their backups are perfect, the threat to leak it keeps the pressure on.",
        soc: "Proxy + DLP light up: a host pushing hundreds of GB to a consumer file-sharing site, classified as confidential data. This is a confirmed breach.",
        blue: "Block file-sharing categories at the egress proxy. If you cut the channel before the upload finishes, you prevent the data breach — timing is everything." },
      { stage: "Disable Recovery", name: "Phase 8: Inhibit Recovery", subtitle: "Cutting the safety net",
        briefing: "vssadmin deletion is fanned out via WMI to every server, and backup agents are stopped — so there's no quick restore.",
        red: "Delete shadow copies fleet-wide and stop backup services. If you reached the backup servers too, even offline recovery is gone.",
        soc: "Sysmon EID 1: vssadmin delete shadows on dozens of servers via WMI. This is the unmistakable 'encryption imminent' signal — escalate instantly.",
        blue: "Air-gap the backup servers THIS SECOND if you haven't. Surviving, immutable backups are the difference between recovery and paying." },
      { stage: "Impact", name: "Phase 9: Encryption", subtitle: "GlobalTech goes dark",
        briefing: "One malicious Group Policy Object pushes the encryptor to every domain-joined host at once. 300+ screens go dark in seconds.",
        red: "Weaponise their own management plane: link a GPO that deploys the encryptor everywhere simultaneously. Maximum impact, minimum time.",
        soc: "Sysmon EID 11: mass encryption across the fleet via a newly-linked GPO. Combined with the earlier exfil, this is both an outage and a breach.",
        blue: "Restore from air-gapped backups if they survived, reimage hosts, reset every credential. Remember: the exfiltrated data is gone regardless." },
    ],
  },
};

export function getStory(scenarioId: string): ScenarioStory | undefined {
  return STORIES[scenarioId];
}

export function getPhase(scenarioId: string, stage: string): PhaseNarrative | undefined {
  return STORIES[scenarioId]?.phases.find(p => p.stage === stage);
}
