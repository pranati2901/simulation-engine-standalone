"""C5 — EDR Outage Exploitation scenario definition.

14-stage attack chain: Human-operated ransomware that exploits a window when EDR is down.
The key twist: defenders are blind (no endpoint telemetry) and must rely on network/auth logs.

Setting: GlobalTech Corp — 500-host enterprise, EDR vendor outage, attacker piggybacks.
"""
from __future__ import annotations

SCENARIO_META = {
    "scenario_id": "scn-c5-edr-outage",
    "version": "1.0.0",
    "title": "C5 — EDR Outage Exploitation",
    "family": "ransomware",
    "setting": "GlobalTech Corp — Enterprise Network",
    "role": "Incident Responder (degraded visibility)",
    "estimated_minutes": 50,
    "hard_fail_threshold": 0.80,
    "total_hosts": 500,
}

NETWORK_SEGMENTS = [
    {"id": "seg-edge", "label": "Edge / VPN Gateway", "host_count": 5},
    {"id": "seg-corp", "label": "Corporate Endpoints", "host_count": 300},
    {"id": "seg-dev", "label": "Dev / Engineering", "host_count": 80},
    {"id": "seg-srv", "label": "Server Farm", "host_count": 60},
    {"id": "seg-dc", "label": "Domain Controllers", "host_count": 4},
    {"id": "seg-data", "label": "Data / File Shares", "host_count": 20},
    {"id": "seg-bkp", "label": "Backup Infrastructure", "host_count": 6},
    {"id": "seg-soc", "label": "SOC / SIEM", "host_count": 10},
    {"id": "seg-cloud", "label": "Cloud (Azure/AWS)", "host_count": 15},
]

SCENES: list[dict] = [
    # ---- Stage 0: EDR Outage ----
    {
        "index": 0,
        "title": "EDR Platform Outage",
        "mitre": {"id": "", "name": "Precondition — visibility loss"},
        "story": "Friday 14:00. Your EDR vendor pushes a faulty update. Agents across the fleet crash. 80% of your endpoint visibility goes dark. You're flying blind.",
        "telemetry": [
            {"sev": "critical", "source": "EDR Platform", "msg": "ALERT: 412/500 agents offline — vendor confirms faulty update deployment"},
            {"sev": "high", "source": "SOC Manager", "msg": "EDR vendor ETA for fix: 24-48 hours. We are operating with degraded visibility."},
            {"sev": "medium", "source": "Sysmon", "msg": "Sysmon still operational on 500 hosts — but no central EDR correlation"},
        ],
        "identify": {
            "prompt": "What is the immediate security risk of this EDR outage?",
            "options": [
                {"id": "a", "text": "No risk — antivirus still works"},
                {"id": "b", "text": "Massive visibility gap — attackers who are monitoring for this will exploit the window", "correct": True},
                {"id": "c", "text": "Users will be inconvenienced by slow computers"},
                {"id": "d", "text": "The network will go offline"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "alt-monitoring", "label": "Activate alternative monitoring: increase Sysmon/NetFlow/Auth log alerting", "quality": "optimal"},
                {"id": "threat-brief", "label": "Issue threat brief to SOC: heightened alert, manual triage of auth anomalies", "quality": "optimal"},
                {"id": "wait-vendor", "label": "Wait for vendor fix — nothing we can do", "quality": "poor"},
                {"id": "disable-remote", "label": "Temporarily disable external VPN/RDP access until EDR is restored", "quality": "acceptable"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 30000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 0},
            "acceptable": {"containment_delta": 2, "infected_delta": 0},
            "poor": {"containment_delta": -10, "infected_delta": 0},
        },
        "micro_teach": "EDR outages create opportunity windows for attackers. Sophisticated groups actively monitor vendor status pages and social media for outage signals. Alternative detection sources (Sysmon, auth logs, NetFlow) become critical.",
    },

    # ---- Stage 1: Password Spray ----
    {
        "index": 1,
        "title": "Password Spray Attack",
        "mitre": {"id": "T1110.003", "name": "Password Spraying"},
        "story": "Within 2 hours of the outage, your Azure AD logs show a spike in failed logins across 200 accounts — same 3 passwords tried against every account. An attacker is probing for weak credentials.",
        "telemetry": [
            {"sev": "high", "source": "Azure AD", "msg": "200 failed logins in 15 minutes — source: 3 residential IP addresses (VPN/proxy)"},
            {"sev": "medium", "source": "Azure AD", "msg": "Pattern: same password tried once per account (spray, not brute force)"},
            {"sev": "high", "source": "Azure AD", "msg": "5 successful logins detected among the 200 attempts — accounts with weak passwords"},
        ],
        "identify": {
            "prompt": "What is this authentication pattern?",
            "options": [
                {"id": "a", "text": "Users forgetting their passwords on a Friday"},
                {"id": "b", "text": "Password spray attack — testing common passwords across many accounts", "correct": True},
                {"id": "c", "text": "A brute force attack on one account"},
                {"id": "d", "text": "Normal SSO behavior"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "block-ips", "label": "Block the source IPs and reset the 5 compromised accounts", "quality": "optimal"},
                {"id": "mfa-enforce", "label": "Emergency MFA enforcement for all accounts", "quality": "optimal"},
                {"id": "lockout", "label": "Enable account lockout after 3 failures", "quality": "acceptable"},
                {"id": "monitor", "label": "Monitor the successful logins but don't act yet", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 1},
            "acceptable": {"containment_delta": 2, "infected_delta": 5},
            "poor": {"containment_delta": -10, "infected_delta": 10},
        },
        "micro_teach": "Password spraying (T1110.003) avoids lockouts by trying few passwords per account. Without EDR, Azure AD/auth logs are your only visibility. The 5 successful logins are your immediate priority — reset them NOW.",
    },

    # ---- Stage 2: Initial Access via VPN ----
    {
        "index": 2,
        "title": "VPN Access Established",
        "mitre": {"id": "T1133", "name": "External Remote Services"},
        "story": "An attacker uses one of the compromised accounts to establish a VPN connection from an unusual geographic location. They're inside the network.",
        "telemetry": [
            {"sev": "high", "source": "VPN Gateway", "msg": "VPN connection: m.chen@globaltech.com from 185.220.100.x (Tor exit node) — first login from this location"},
            {"sev": "medium", "source": "GeoIP", "msg": "m.chen last logged in from Sydney, AU. Current connection from Eastern Europe."},
            {"sev": "low", "source": "VPN Gateway", "msg": "Session duration: 47 minutes and counting — no MFA challenge (legacy policy)"},
        ],
        "identify": {
            "prompt": "What does this VPN connection indicate?",
            "options": [
                {"id": "a", "text": "m.chen is traveling internationally"},
                {"id": "b", "text": "Attacker using compromised credentials via Tor to access the corporate network", "correct": True},
                {"id": "c", "text": "A VPN configuration test by IT"},
                {"id": "d", "text": "An automated backup connection"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "kill-vpn", "label": "Terminate the VPN session and disable m.chen's account", "quality": "optimal"},
                {"id": "block-tor", "label": "Block all Tor exit node IPs at the VPN gateway", "quality": "optimal"},
                {"id": "contact-user", "label": "Call m.chen to verify if they're traveling", "quality": "acceptable"},
                {"id": "allow", "label": "Could be legitimate travel — allow the connection", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 10, "infected_delta": 1, "isolated_delta": 1},
            "acceptable": {"containment_delta": 2, "infected_delta": 5},
            "poor": {"containment_delta": -12, "infected_delta": 15},
        },
        "micro_teach": "Impossible travel (Sydney → Eastern Europe in hours) via a Tor exit node is a strong indicator of compromised credentials (T1133). Without MFA, stolen passwords give direct network access. Kill the session immediately.",
    },

    # ---- Stage 3: Custom Tooling Deployed ----
    {
        "index": 3,
        "title": "Custom Tooling Deployed",
        "mitre": {"id": "T1059.001", "name": "PowerShell"},
        "story": "With EDR down, the attacker deploys custom tools freely. PowerShell scripts, a renamed PsExec, and a credential dumping tool — all would normally trigger EDR alerts but now land silently.",
        "telemetry": [
            {"sev": "medium", "source": "Sysmon", "msg": "ENG-WS12: powershell.exe downloading from paste.ee — encoded script execution"},
            {"sev": "low", "source": "Sysmon", "msg": "ENG-WS12: svcmgr.exe created in C:\\ProgramData\\ (renamed PsExec — hash mismatch)"},
            {"sev": "info", "source": "Note", "msg": "EDR would normally flag both events. Currently blind on this endpoint."},
        ],
        "identify": {
            "prompt": "Why are these events especially dangerous right now?",
            "options": [
                {"id": "a", "text": "PowerShell is always dangerous"},
                {"id": "b", "text": "Normally EDR would detect and block these tools — the outage means the attacker operates freely without endpoint alerts", "correct": True},
                {"id": "c", "text": "Sysmon is unreliable"},
                {"id": "d", "text": "The tools are legitimate IT administration utilities"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "hunt-sysmon", "label": "Use Sysmon logs to hunt for the tool hashes and deployment patterns across all hosts", "quality": "optimal"},
                {"id": "block-paste", "label": "Block paste.ee and similar paste sites at the proxy", "quality": "acceptable"},
                {"id": "applocker", "label": "Emergency AppLocker policy: block unsigned executables in ProgramData", "quality": "optimal"},
                {"id": "nothing", "label": "Without EDR we can't do anything — wait for restoration", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 3},
            "acceptable": {"containment_delta": 0, "infected_delta": 8},
            "poor": {"containment_delta": -15, "infected_delta": 20},
        },
        "micro_teach": "EDR dependency is a single point of failure. When it's down, Sysmon + application whitelisting (AppLocker/WDAC) become your only endpoint defense. The lesson: defense-in-depth means not relying on any one tool.",
    },

    # ---- Stage 4: AD Reconnaissance ----
    {
        "index": 4,
        "title": "Active Directory Reconnaissance",
        "mitre": {"id": "T1087.002", "name": "Domain Account Discovery"},
        "story": "The attacker runs BloodHound-style queries against Active Directory, mapping every admin account, group membership, and trust relationship. They know more about your AD than most of your IT staff.",
        "telemetry": [
            {"sev": "medium", "source": "AD", "msg": "Bulk LDAP queries from ENG-WS12: 14,000 objects enumerated in 4 minutes"},
            {"sev": "medium", "source": "AD", "msg": "Queries include: Domain Admins, Enterprise Admins, AdminSDHolder, GPO links"},
            {"sev": "low", "source": "NetFlow", "msg": "ENG-WS12 → DC01: sustained LDAP traffic (port 389) for 8 minutes"},
        ],
        "identify": {
            "prompt": "What is the attacker mapping?",
            "options": [
                {"id": "a", "text": "Printer locations in Active Directory"},
                {"id": "b", "text": "The entire AD attack path — admin accounts, group memberships, and privilege escalation routes", "correct": True},
                {"id": "c", "text": "Email distribution lists for phishing"},
                {"id": "d", "text": "File share permissions for auditing"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "isolate", "label": "Isolate ENG-WS12 and investigate the account's recent activity", "quality": "optimal"},
                {"id": "audit", "label": "Review which accounts have Domain Admin — begin reducing over-privilege", "quality": "acceptable"},
                {"id": "wait", "label": "LDAP queries are normal — continue monitoring", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 3},
            "acceptable": {"containment_delta": 0, "infected_delta": 8},
            "poor": {"containment_delta": -10, "infected_delta": 15},
        },
        "micro_teach": "Bulk LDAP enumeration (T1087.002) from a workstation is a strong recon indicator. BloodHound-style attacks map the shortest path to Domain Admin. Detecting this early gives you time to reduce privileges before exploitation.",
    },

    # ---- Stage 5: Credential Theft (LSASS) ----
    {
        "index": 5,
        "title": "Credential Theft — LSASS Dump",
        "mitre": {"id": "T1003.001", "name": "LSASS Memory"},
        "story": "With local admin obtained via an unpatched privilege escalation, the attacker dumps LSASS on the compromised endpoint. Domain admin credentials are harvested. EDR would catch this instantly — but it's down.",
        "telemetry": [
            {"sev": "critical", "source": "Sysmon", "msg": "ProcessAccess: procdump.exe opened lsass.exe (PID 648) with PROCESS_VM_READ on ENG-WS12"},
            {"sev": "high", "source": "Sysmon", "msg": "File created: C:\\Windows\\Temp\\lsass_dump.dmp (18.7 MB)"},
            {"sev": "info", "source": "Note", "msg": "EDR signature 'Credential Dumping via ProcDump' would fire here — currently offline"},
        ],
        "identify": {
            "prompt": "What did the attacker just accomplish?",
            "options": [
                {"id": "a", "text": "Created a crash dump for debugging"},
                {"id": "b", "text": "Dumped LSASS memory to extract domain admin credentials — EDR would have caught this", "correct": True},
                {"id": "c", "text": "Ran a memory diagnostic test"},
                {"id": "d", "text": "Generated a performance report"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "reset-all-admin", "label": "Emergency: reset ALL domain admin passwords and krbtgt (twice)", "quality": "optimal"},
                {"id": "isolate-ws12", "label": "Isolate ENG-WS12 and all systems m.chen has accessed", "quality": "optimal"},
                {"id": "partial", "label": "Reset only the one admin account found on this host", "quality": "acceptable"},
                {"id": "wait", "label": "We don't know which creds were taken — wait for forensics", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 10, "infected_delta": 5},
            "acceptable": {"containment_delta": 2, "infected_delta": 15},
            "poor": {"containment_delta": -20, "infected_delta": 30},
        },
        "micro_teach": "LSASS dumping (T1003.001) is the most common credential theft technique. Without EDR, Sysmon ProcessAccess events are your only signal. Reset all privileged credentials — assume the worst. Don't wait for forensics to tell you what was stolen.",
    },

    # ---- Stage 6: Lateral Movement ----
    {
        "index": 6,
        "title": "Lateral Movement — Enterprise Spread",
        "mitre": {"id": "T1021.002", "name": "SMB/Windows Admin Shares"},
        "story": "With domain admin credentials, the attacker spreads rapidly. PsExec-style remote execution hits 40+ servers in the server farm. They're building footholds everywhere — file servers, database servers, cloud connectors.",
        "telemetry": [
            {"sev": "critical", "source": "AD", "msg": "Domain Admin account: 47 authentication events across 43 unique hosts in 12 minutes"},
            {"sev": "critical", "source": "NetFlow", "msg": "Lateral SMB traffic (445/tcp): ENG-WS12 → 43 hosts in seg-srv and seg-data"},
            {"sev": "high", "source": "Sysmon", "msg": "Service installed: 'PSEXESVC' on SRV-DB01, SRV-APP03, SRV-FILE01 (PsExec pattern)"},
        ],
        "identify": {
            "prompt": "What is happening across the server farm?",
            "options": [
                {"id": "a", "text": "A software deployment via SCCM"},
                {"id": "b", "text": "Massive lateral movement — the attacker is using Domain Admin to compromise the entire server infrastructure", "correct": True},
                {"id": "c", "text": "Routine backup operations"},
                {"id": "d", "text": "A network scan by the vulnerability management team"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "segment", "label": "Emergency network segmentation — isolate server farm from corporate network", "quality": "optimal"},
                {"id": "disable-da", "label": "Disable the compromised Domain Admin account", "quality": "optimal"},
                {"id": "selective", "label": "Selectively isolate the 3 most critical servers (DB, File, App)", "quality": "acceptable"},
                {"id": "wait", "label": "We need to understand the scope before acting", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 15, "isolated_delta": 10},
            "acceptable": {"containment_delta": 0, "infected_delta": 30},
            "poor": {"containment_delta": -25, "infected_delta": 80},
        },
        "micro_teach": "47 authentications to 43 hosts in 12 minutes via Domain Admin + PSEXESVC service creation is textbook PsExec lateral movement (T1021.002). This is the critical window — every minute of delay adds 3-5 more compromised hosts.",
    },

    # ---- Stage 7: Data Discovery ----
    {
        "index": 7,
        "title": "Sensitive Data Discovery",
        "mitre": {"id": "T1083", "name": "File and Directory Discovery"},
        "story": "On the file servers, the attacker enumerates sensitive directories — HR records, financial data, customer PII, intellectual property. They're building a target list for exfiltration.",
        "telemetry": [
            {"sev": "high", "source": "File Audit", "msg": "SRV-FILE01: 12,000 file access events in 8 minutes from Domain Admin session"},
            {"sev": "high", "source": "File Audit", "msg": "Directories accessed: \\\\FS01\\HR-Confidential, \\\\FS01\\Finance-Reports, \\\\FS01\\Customer-PII"},
            {"sev": "medium", "source": "DLP", "msg": "Sensitive data markers detected in accessed files: SSN patterns, credit card numbers"},
        ],
        "identify": {
            "prompt": "What is the attacker preparing for?",
            "options": [
                {"id": "a", "text": "A legitimate audit of file share permissions"},
                {"id": "b", "text": "Data staging for exfiltration — identifying the most valuable data to steal before encryption", "correct": True},
                {"id": "c", "text": "A search for a specific lost document"},
                {"id": "d", "text": "Reorganizing the file share structure"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "isolate-fs", "label": "Isolate SRV-FILE01 from the network immediately", "quality": "optimal"},
                {"id": "revoke-shares", "label": "Revoke Domain Admin access to all file shares", "quality": "optimal"},
                {"id": "dlp-block", "label": "Enable DLP blocking mode for all sensitive data categories", "quality": "acceptable"},
                {"id": "monitor", "label": "Continue monitoring — file access is normal for admin accounts", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 3},
            "acceptable": {"containment_delta": 0, "infected_delta": 8},
            "poor": {"containment_delta": -10, "infected_delta": 15},
        },
        "micro_teach": "Data discovery (T1083) before exfiltration is a hallmark of double extortion ransomware. The attacker steals first, encrypts second — so even paying the ransom doesn't prevent the data leak. This is your last chance to prevent data theft.",
    },

    # ---- Stage 8: Data Exfiltration ----
    {
        "index": 8,
        "title": "Data Exfiltration",
        "mitre": {"id": "T1048.003", "name": "Exfiltration Over Alternative Protocol"},
        "story": "The attacker stages 200GB of sensitive data and exfiltrates it to cloud storage using rclone — a legitimate file sync tool. Traffic blends with normal cloud uploads.",
        "telemetry": [
            {"sev": "critical", "source": "Proxy", "msg": "SRV-FILE01: 200GB uploaded to mega.nz over 4 hours via rclone.exe (unusual binary in C:\\Temp)"},
            {"sev": "high", "source": "DLP", "msg": "ALERT: 200GB outbound data transfer exceeds baseline by 40x — destination: mega.nz"},
            {"sev": "medium", "source": "NetFlow", "msg": "Sustained 12 Mbps outbound from SRV-FILE01 to cloud storage IPs"},
        ],
        "identify": {
            "prompt": "What has the attacker accomplished?",
            "options": [
                {"id": "a", "text": "A legitimate cloud backup operation"},
                {"id": "b", "text": "Exfiltration of 200GB of sensitive corporate data to attacker-controlled cloud storage", "correct": True},
                {"id": "c", "text": "A software deployment to cloud servers"},
                {"id": "d", "text": "Normal file synchronization with OneDrive"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "block-egress", "label": "Block all outbound traffic to file-sharing/cloud storage sites at the proxy", "quality": "optimal"},
                {"id": "notify-legal", "label": "Notify legal team — this is now a data breach, notification obligations triggered", "quality": "optimal"},
                {"id": "block-mega", "label": "Block mega.nz specifically", "quality": "acceptable"},
                {"id": "ignore", "label": "The data is already gone — focus on other things", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 3},
            "acceptable": {"containment_delta": 0, "infected_delta": 5},
            "poor": {"containment_delta": -8, "infected_delta": 8},
        },
        "micro_teach": "rclone (T1048.003) is a favorite exfiltration tool because it's a legitimate utility. 200GB to mega.nz is double extortion preparation — they'll threaten to publish if ransom isn't paid. Legal notification must start NOW.",
    },

    # ---- Stage 9: Recovery Disabled ----
    {
        "index": 9,
        "title": "Recovery Mechanisms Disabled",
        "mitre": {"id": "T1490", "name": "Inhibit System Recovery"},
        "story": "Across all compromised servers, the attacker deletes shadow copies, disables backup agents, and corrupts the backup catalog. Your safety net is being cut.",
        "telemetry": [
            {"sev": "critical", "source": "Sysmon", "msg": "vssadmin delete shadows /all /quiet — executed on 43 hosts simultaneously"},
            {"sev": "critical", "source": "Backup", "msg": "Backup agent service stopped and disabled on BKP-SRV01, BKP-SRV02"},
            {"sev": "critical", "source": "Backup", "msg": "Backup catalog corrupted — last valid restore point: 6 hours ago (before attack)"},
        ],
        "identify": {
            "prompt": "What is the attacker eliminating?",
            "options": [
                {"id": "a", "text": "Temporary files to free up disk space"},
                {"id": "b", "text": "All recovery mechanisms — shadow copies, backup agents, and backup catalogs", "correct": True},
                {"id": "c", "text": "Old log files for compliance"},
                {"id": "d", "text": "Cached credentials from memory"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "offline-bkp", "label": "Emergency: disconnect offline/tape backup infrastructure from the network", "quality": "optimal"},
                {"id": "snapshot-clean", "label": "Take snapshots of all clean systems NOW before encryption starts", "quality": "optimal"},
                {"id": "try-restore", "label": "Attempt to restore the backup catalog from the 6-hour-old copy", "quality": "acceptable"},
                {"id": "accept", "label": "Focus on containment, backups are a secondary concern", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 5},
            "acceptable": {"containment_delta": 2, "infected_delta": 8},
            "poor": {"containment_delta": -15, "infected_delta": 10, "backup_destroyed": True},
        },
        "micro_teach": "T1490 (Inhibit System Recovery) is the point of no return. If offline/tape backups survive, recovery is possible. If they're destroyed, you're choosing between paying the ransom and rebuilding from scratch. Protect backups FIRST.",
    },

    # ---- Stage 10: Ransomware Deployment ----
    {
        "index": 10,
        "title": "Enterprise Ransomware Deployment",
        "mitre": {"id": "T1486", "name": "Data Encrypted for Impact"},
        "story": "The ransomware detonates simultaneously across 300+ hosts. Group Policy is used to push the payload enterprise-wide. Screens go dark across every department.",
        "telemetry": [
            {"sev": "critical", "source": "AD", "msg": "New GPO deployed: 'Windows Update Service' — pushes svcupdate.exe to all domain-joined hosts"},
            {"sev": "critical", "source": "Sysmon", "msg": "MASS FILE MODIFICATION: 300+ hosts encrypting at 500 files/sec — .LOCKED extension"},
            {"sev": "critical", "source": "Helpdesk", "msg": "ALL LINES RINGING: 'Everything is locked, ransom note on screen, can't access anything'"},
        ],
        "identify": {
            "prompt": "How did the attacker achieve enterprise-wide encryption so quickly?",
            "options": [
                {"id": "a", "text": "The ransomware is a worm that self-propagated"},
                {"id": "b", "text": "They used Group Policy (GPO) to push the ransomware to all domain-joined hosts simultaneously", "correct": True},
                {"id": "c", "text": "Each user clicked a phishing link independently"},
                {"id": "d", "text": "A cloud service pushed the update"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "kill-gpo", "label": "Delete the malicious GPO immediately and force gpupdate", "quality": "optimal"},
                {"id": "isolate-dc", "label": "Isolate domain controllers to prevent further GPO propagation", "quality": "optimal"},
                {"id": "declare-p0", "label": "Declare P0 incident — activate business continuity plan", "quality": "acceptable"},
                {"id": "shutdown-all", "label": "Emergency shutdown of all remaining systems", "quality": "acceptable"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": -10, "infected_delta": 30, "encrypted_delta": 80},
            "acceptable": {"containment_delta": -20, "infected_delta": 50, "encrypted_delta": 150},
            "poor": {"containment_delta": -35, "infected_delta": 100, "encrypted_delta": 250},
        },
        "micro_teach": "Using GPO for ransomware deployment is a technique seen in sophisticated operations (Ryuk, LockBit). With Domain Admin access, the attacker controls Group Policy — which controls every domain-joined machine. This is why protecting the DC is paramount.",
    },

    # ---- Stage 11: Ransom Demand ----
    {
        "index": 11,
        "title": "Ransom Demand & Data Leak Threat",
        "mitre": {"id": "", "name": "Double extortion"},
        "story": "A ransom note appears: $5M in Bitcoin. Plus a dark web link showing 10 sample files from the stolen data — customer PII, financial records. 'Pay in 72 hours or we publish everything.'",
        "telemetry": [
            {"sev": "critical", "source": "Threat Intel", "msg": "Ransom note references dark web leak site — 10 sample files already published"},
            {"sev": "critical", "source": "Legal", "msg": "Sample files contain customer PII — mandatory breach notification triggered (GDPR 72h, NDB 30d)"},
            {"sev": "high", "source": "Finance", "msg": "Ransom demand: $5M USD in Bitcoin — 72-hour deadline"},
        ],
        "identify": {
            "prompt": "What type of ransomware operation is this?",
            "options": [
                {"id": "a", "text": "Commodity ransomware — encrypt and demand"},
                {"id": "b", "text": "Double extortion — data stolen AND encrypted, with public leak threat for additional pressure", "correct": True},
                {"id": "c", "text": "A prank — no real data was stolen"},
                {"id": "d", "text": "A penetration test that went too far"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "legal-breach", "label": "Engage legal + breach notification process — GDPR 72h clock starts now", "quality": "optimal"},
                {"id": "negotiate", "label": "Engage ransomware negotiator to buy time while restoring from backups", "quality": "acceptable"},
                {"id": "pay", "label": "Pay the ransom immediately", "quality": "poor"},
                {"id": "ignore", "label": "Ignore the demand and hope they don't publish", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 30000, "speed_bonus_points": 15},
        "effects": {
            "optimal": {"containment_delta": 3, "infected_delta": 0},
            "acceptable": {"containment_delta": 0, "infected_delta": 0},
            "poor": {"containment_delta": -5, "infected_delta": 0},
        },
        "micro_teach": "Double extortion means paying the ransom doesn't solve the data leak. Breach notification obligations (GDPR 72h, NDB) start when you become aware of the stolen PII. Engaging a negotiator buys time while you assess backup-based recovery.",
    },

    # ---- Stage 12: Recovery & Lessons ----
    {
        "index": 12,
        "title": "Recovery & Lessons Learned",
        "mitre": {"id": "", "name": "Post-incident"},
        "story": "Three weeks later. Systems are being rebuilt. The board wants a root cause analysis and a prevention plan. The EDR vendor has apologized. The CISO is updating the crisis playbook.",
        "telemetry": [
            {"sev": "high", "source": "CISO", "msg": "Board presentation: root cause, timeline, cost impact, prevention roadmap"},
            {"sev": "medium", "source": "Insurance", "msg": "Cyber insurance claim filed — estimated total cost: $12M (recovery + legal + notification + lost revenue)"},
            {"sev": "medium", "source": "HR", "msg": "Mandatory security awareness training scheduled for all employees"},
        ],
        "identify": {
            "prompt": "What was the fundamental failure that enabled this attack?",
            "options": [
                {"id": "a", "text": "The EDR vendor's faulty update"},
                {"id": "b", "text": "Single point of failure in detection (EDR dependency) + lack of MFA + over-privileged accounts + no network segmentation", "correct": True},
                {"id": "c", "text": "m.chen's weak password was the only problem"},
                {"id": "d", "text": "The attackers were too sophisticated to stop"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "depth", "label": "Implement defense-in-depth: no single tool failure should blind the entire SOC", "quality": "optimal"},
                {"id": "mfa", "label": "Mandatory MFA for all remote access and privileged accounts", "quality": "optimal"},
                {"id": "segment", "label": "Network segmentation + microsegmentation for critical infrastructure", "quality": "optimal"},
                {"id": "immutable", "label": "Air-gapped, immutable backup infrastructure with regular restore testing", "quality": "optimal"},
                {"id": "fire-vendor", "label": "Switch EDR vendors (doesn't address the root cause)", "quality": "acceptable"},
                {"id": "nothing", "label": "We have insurance — we'll just pay next time", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 30000, "speed_bonus_points": 10},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 0},
            "acceptable": {"containment_delta": 2, "infected_delta": 0},
            "poor": {"containment_delta": -5, "infected_delta": 0},
        },
        "micro_teach": "The root cause is never one thing. It's the chain: EDR dependency + no MFA + weak passwords + over-privileged accounts + flat network + online backups. Defense-in-depth breaks multiple links. Switching vendors alone fixes nothing.",
    },
]

QUIZ_BANK: list[dict] = [
    {"id": "C5-Q1", "question": "Why do attackers specifically target periods when EDR is down?",
     "options": [{"id": "a", "text": "Computers run faster without EDR"}, {"id": "b", "text": "Endpoint detection and response is the primary tool that catches attacker tools and behaviors — without it, they operate freely"}, {"id": "c", "text": "EDR outages improve internet speed"}, {"id": "d", "text": "EDR outages disable firewalls"}],
     "correct_id": "b", "rationale": "EDR is the primary behavioral detection layer. When it's down, credential dumping, lateral movement, and tool deployment go undetected."},
    {"id": "C5-Q2", "question": "Password spraying differs from brute force in that it:",
     "options": [{"id": "a", "text": "Uses stronger passwords"}, {"id": "b", "text": "Tries few passwords across many accounts to avoid lockout"}, {"id": "c", "text": "Only targets administrator accounts"}, {"id": "d", "text": "Requires physical access"}],
     "correct_id": "b", "rationale": "Spraying avoids lockout by staying under the threshold per account (T1110.003)."},
    {"id": "C5-Q3", "question": "'Impossible travel' in authentication logs refers to:",
     "options": [{"id": "a", "text": "Traveling faster than sound"}, {"id": "b", "text": "A user authenticating from two geographically distant locations within an impossibly short time"}, {"id": "c", "text": "A user traveling without their laptop"}, {"id": "d", "text": "A VPN disconnection"}],
     "correct_id": "b", "rationale": "Impossible travel is a strong indicator of credential compromise — the real user and the attacker are in different places."},
    {"id": "C5-Q4", "question": "Why is defense-in-depth important for endpoint monitoring?",
     "options": [{"id": "a", "text": "It makes the network faster"}, {"id": "b", "text": "No single tool should be a single point of failure — Sysmon, AppLocker, and NetFlow provide coverage when EDR fails"}, {"id": "c", "text": "It's cheaper than a single good tool"}, {"id": "d", "text": "Regulators require exactly three monitoring tools"}],
     "correct_id": "b", "rationale": "If your entire detection capability depends on one tool and it goes down, you're blind. Multiple overlapping layers ensure coverage."},
    {"id": "C5-Q5", "question": "What makes double extortion ransomware more dangerous than traditional ransomware?",
     "options": [{"id": "a", "text": "It encrypts files twice"}, {"id": "b", "text": "Data is stolen before encryption — paying the ransom doesn't prevent the data leak"}, {"id": "c", "text": "It targets two companies at once"}, {"id": "d", "text": "It requires two payments"}],
     "correct_id": "b", "rationale": "Double extortion = encrypt + threaten to publish stolen data. Even paying doesn't guarantee data won't be leaked."},
    {"id": "C5-Q6", "question": "Using Group Policy (GPO) to deploy ransomware indicates:",
     "options": [{"id": "a", "text": "The attacker used a zero-day exploit"}, {"id": "b", "text": "The attacker has Domain Admin access — the highest level of compromise in an AD environment"}, {"id": "c", "text": "The ransomware is a worm"}, {"id": "d", "text": "The antivirus signatures are outdated"}],
     "correct_id": "b", "rationale": "GPO deployment requires Domain Admin. It means the attacker controls Active Directory and can push code to every domain-joined machine."},
    {"id": "C5-Q7", "question": "What is the GDPR breach notification deadline?",
     "options": [{"id": "a", "text": "24 hours"}, {"id": "b", "text": "72 hours after becoming aware of a personal data breach"}, {"id": "c", "text": "30 days"}, {"id": "d", "text": "No deadline exists"}],
     "correct_id": "b", "rationale": "GDPR requires notification to the supervisory authority within 72 hours of awareness."},
    {"id": "C5-Q8", "question": "The most critical action when you discover shadow copies are being deleted is:",
     "options": [{"id": "a", "text": "Create new shadow copies"}, {"id": "b", "text": "Immediately disconnect offline/air-gapped backup infrastructure from the network"}, {"id": "c", "text": "Call the backup vendor"}, {"id": "d", "text": "Wait for encryption to finish before assessing"}],
     "correct_id": "b", "rationale": "If offline backups survive, you can recover. If they're connected and compromised, you have no recovery options. Protect backups FIRST."},
    {"id": "C5-Q9", "question": "rclone is commonly used for exfiltration because:",
     "options": [{"id": "a", "text": "It's the fastest file copy tool"}, {"id": "b", "text": "It's a legitimate tool that syncs to cloud storage — traffic blends with normal uploads"}, {"id": "c", "text": "It's pre-installed on Windows"}, {"id": "d", "text": "It cannot be detected by any tool"}],
     "correct_id": "b", "rationale": "rclone (T1048.003) is legitimate and widely used, making its traffic hard to distinguish from authorized cloud uploads."},
    {"id": "C5-Q10", "question": "In this scenario, what was the single most impactful preventive control that was missing?",
     "options": [{"id": "a", "text": "A better EDR product"}, {"id": "b", "text": "MFA on VPN/remote access — it would have blocked the initial access entirely"}, {"id": "c", "text": "Faster computers"}, {"id": "d", "text": "More SOC analysts"}],
     "correct_id": "b", "rationale": "MFA on VPN would have prevented the sprayed credentials from granting network access, stopping the entire attack at step 2."},
]


def get_scene(index: int) -> dict:
    if 0 <= index < len(SCENES):
        return SCENES[index]
    raise ValueError(f"Invalid scene index: {index}")


def get_quiz_subset(count: int = 10) -> list[dict]:
    import random
    if count >= len(QUIZ_BANK):
        return list(QUIZ_BANK)
    return random.sample(QUIZ_BANK, count)
