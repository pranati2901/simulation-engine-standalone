"""R5 — Phishing-to-Encrypt Ransomware Campaign scenario definition.

10-stage attack chain: Phishing → Execution → Persistence → C2 → Discovery →
Credential Harvest → Lateral Movement → Staging → Encryption → Recovery Inhibition.

Setting: MediumCorp — 85-host corporate network with Finance, IT, Servers, DC segments.
Roles: Red (attacker), Victim (social engineering target), SOC (detection), Blue (response).
"""
from __future__ import annotations

SCENARIO_META = {
    "scenario_id": "scn-r5-phish2enc",
    "version": "1.0.0",
    "title": "R5 — Phishing-to-Encrypt Ransomware",
    "family": "ransomware",
    "setting": "MediumCorp Financial Services",
    "role": "SOC Analyst / Incident Responder",
    "estimated_minutes": 45,
    "hard_fail_threshold": 0.80,
    "total_hosts": 85,
}

NETWORK_SEGMENTS = [
    {"id": "seg-finance", "label": "Finance Dept", "host_count": 20},
    {"id": "seg-corp", "label": "Corporate Workstations", "host_count": 35},
    {"id": "seg-it", "label": "IT / Admin", "host_count": 12},
    {"id": "seg-srv", "label": "Servers (FS01, BKP01)", "host_count": 10},
    {"id": "seg-dc", "label": "Domain Controllers", "host_count": 2},
    {"id": "seg-mail", "label": "Mail Gateway", "host_count": 3},
    {"id": "seg-soc", "label": "SOC / Monitoring", "host_count": 3},
]

SCENES: list[dict] = [
    # ---- Stage 0: Recon & Weaponize ----
    {
        "index": 0,
        "title": "Recon & Weaponize",
        "mitre": {"id": "T1566.001", "name": "Spear Phishing Attachment"},
        "story": "An attacker profiles MediumCorp's Finance department on LinkedIn. They craft a convincing invoice document armed with a macro payload, spoofing a known vendor's email domain.",
        "telemetry": [
            {"sev": "low", "source": "Email Gateway", "msg": "Inbound email from invoices@vendorsupply.co (external, first-seen domain) to j.harper@mediumcorp.com"},
            {"sev": "info", "source": "Threat Intel", "msg": "Domain vendorsupply.co registered 48 hours ago — disposable infrastructure pattern"},
            {"sev": "low", "source": "Email Gateway", "msg": "Attachment: Q4_Invoice_Final.docm — macro-enabled Office document"},
        ],
        "identify": {
            "prompt": "What is the attacker preparing?",
            "options": [
                {"id": "a", "text": "A DDoS attack against the mail server"},
                {"id": "b", "text": "A spear phishing campaign with a weaponized document", "correct": True},
                {"id": "c", "text": "A brute force attack on VPN credentials"},
                {"id": "d", "text": "A supply chain compromise of a software vendor"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "block-domain", "label": "Block the sender domain at the email gateway", "quality": "optimal"},
                {"id": "quarantine", "label": "Quarantine the email before delivery", "quality": "optimal"},
                {"id": "alert-user", "label": "Send a phishing awareness alert to Finance", "quality": "acceptable"},
                {"id": "monitor", "label": "Monitor but don't intervene yet", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 0},
            "acceptable": {"containment_delta": 0, "infected_delta": 1},
            "poor": {"containment_delta": -5, "infected_delta": 1},
        },
        "micro_teach": "Spear phishing (T1566.001) targets specific individuals with crafted lures. Blocking newly registered sender domains and quarantining macro-enabled attachments are the first line of defense.",
    },

    # ---- Stage 1: User Execution ----
    {
        "index": 1,
        "title": "User Execution",
        "mitre": {"id": "T1204.002", "name": "User Execution: Malicious File"},
        "story": "j.harper in Finance opens the attachment. The document shows a blurred 'protected' preview with an 'Enable Content' button. She clicks it. The macro fires silently.",
        "telemetry": [
            {"sev": "medium", "source": "EDR", "msg": "WINWORD.EXE spawned cmd.exe on FIN-PC07 (j.harper session)"},
            {"sev": "high", "source": "Sysmon", "msg": "Process Create: powershell.exe -enc [Base64] — parent: cmd.exe — grandparent: WINWORD.EXE"},
            {"sev": "medium", "source": "Email Gateway", "msg": "Attachment Q4_Invoice_Final.docm opened by j.harper@mediumcorp.com"},
        ],
        "identify": {
            "prompt": "What has happened on j.harper's workstation?",
            "options": [
                {"id": "a", "text": "A legitimate macro ran a scheduled report"},
                {"id": "b", "text": "A malicious macro executed a PowerShell download cradle", "correct": True},
                {"id": "c", "text": "The user installed unauthorized software"},
                {"id": "d", "text": "An operating system update is running"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "isolate-host", "label": "Immediately isolate FIN-PC07 from the network", "quality": "optimal"},
                {"id": "kill-proc", "label": "Kill the PowerShell process remotely", "quality": "optimal"},
                {"id": "investigate", "label": "Open an investigation ticket and gather more info", "quality": "acceptable"},
                {"id": "ignore", "label": "Probably a false positive — ignore", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 1, "isolated_delta": 1},
            "acceptable": {"containment_delta": 0, "infected_delta": 3},
            "poor": {"containment_delta": -10, "infected_delta": 5},
        },
        "micro_teach": "The process chain WINWORD → cmd → powershell is a classic macro execution chain (T1204.002). Encoded PowerShell from Office is almost never legitimate. Immediate isolation of patient zero is critical.",
    },

    # ---- Stage 2: Establish Persistence ----
    {
        "index": 2,
        "title": "Establish Persistence",
        "mitre": {"id": "T1053.005", "name": "Scheduled Task"},
        "story": "The payload creates a scheduled task that runs every 15 minutes and injects a beacon into a legitimate process. Even if the initial PowerShell is killed, the attacker will regain access.",
        "telemetry": [
            {"sev": "high", "source": "Sysmon", "msg": "Scheduled task created: 'WindowsUpdateCheck' — action: powershell.exe -enc [Base64] — trigger: every 15min"},
            {"sev": "high", "source": "EDR", "msg": "Process injection detected: svchost.exe (PID 4872) loaded unsigned DLL from %TEMP%"},
            {"sev": "medium", "source": "Sysmon", "msg": "File created: C:\\Users\\j.harper\\AppData\\Local\\Temp\\msupdate.dll (unsigned, packed)"},
        ],
        "identify": {
            "prompt": "What is the malware establishing?",
            "options": [
                {"id": "a", "text": "A VPN connection to the attacker's server"},
                {"id": "b", "text": "Persistence via scheduled task and process injection to survive reboot", "correct": True},
                {"id": "c", "text": "A keylogger to capture passwords"},
                {"id": "d", "text": "A cryptocurrency miner"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "remove-task", "label": "Delete the scheduled task and quarantine the DLL", "quality": "optimal"},
                {"id": "reimage", "label": "Begin reimaging FIN-PC07 from clean baseline", "quality": "optimal"},
                {"id": "document", "label": "Document the IOCs for threat hunting across the environment", "quality": "acceptable"},
                {"id": "reboot", "label": "Reboot the workstation to clear the infection", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 1},
            "acceptable": {"containment_delta": 0, "infected_delta": 3},
            "poor": {"containment_delta": -8, "infected_delta": 5},
        },
        "micro_teach": "Scheduled tasks (T1053.005) and process injection (T1055.012) ensure the attacker regains access even after cleanup. Rebooting does NOT remove persistence — you must delete the mechanism.",
    },

    # ---- Stage 3: Command & Control ----
    {
        "index": 3,
        "title": "Command & Control",
        "mitre": {"id": "T1071.001", "name": "Web Protocols"},
        "story": "The injected beacon phones home over HTTPS to a cloud-fronted C2 server. Traffic blends with normal web browsing — short, regular intervals, encrypted payload.",
        "telemetry": [
            {"sev": "medium", "source": "Proxy", "msg": "FIN-PC07: HTTPS POST to cdn-assets-update.azurewebsites.net every 60s (jitter ±15s)"},
            {"sev": "low", "source": "DNS", "msg": "First-seen domain resolution: cdn-assets-update.azurewebsites.net (Azure CDN, legitimate hosting)"},
            {"sev": "medium", "source": "NetFlow", "msg": "FIN-PC07: 847 outbound HTTPS connections in 14 hours — all to same Azure endpoint"},
        ],
        "identify": {
            "prompt": "What is this recurring outbound traffic?",
            "options": [
                {"id": "a", "text": "Normal Windows telemetry to Microsoft"},
                {"id": "b", "text": "C2 beaconing over HTTPS using cloud-fronting to blend with legitimate traffic", "correct": True},
                {"id": "c", "text": "OneDrive file synchronization"},
                {"id": "d", "text": "Automated backup to Azure"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "block-c2", "label": "Block the C2 domain/IP at the proxy and firewall", "quality": "optimal"},
                {"id": "sinkhole", "label": "Sinkhole the domain via internal DNS", "quality": "optimal"},
                {"id": "monitor-c2", "label": "Passively monitor to understand the attacker's playbook", "quality": "acceptable"},
                {"id": "nothing", "label": "It's Azure — probably legitimate", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 10, "infected_delta": 1},
            "acceptable": {"containment_delta": 2, "infected_delta": 4},
            "poor": {"containment_delta": -12, "infected_delta": 8},
        },
        "micro_teach": "Cloud-fronted C2 (T1071.001) hides behind legitimate cloud infrastructure (Azure, AWS). Regular HTTPS beaconing with jitter is hard to distinguish from normal traffic. Blocking the specific domain/IP is the key move.",
    },

    # ---- Stage 4: Internal Discovery ----
    {
        "index": 4,
        "title": "Internal Discovery",
        "mitre": {"id": "T1083", "name": "File and Directory Discovery"},
        "story": "With hands-on-keyboard access, the attacker runs discovery commands: enumerating shares, mapping the domain, finding high-value targets — file servers, backup servers, domain controllers.",
        "telemetry": [
            {"sev": "medium", "source": "Sysmon", "msg": "FIN-PC07: net view /domain executed (domain share enumeration)"},
            {"sev": "medium", "source": "Sysmon", "msg": "FIN-PC07: nltest /dclist:mediumcorp.local (domain controller enumeration)"},
            {"sev": "low", "source": "AD", "msg": "Unusual LDAP queries from FIN-PC07 — full user/group enumeration in 3 minutes"},
        ],
        "identify": {
            "prompt": "What is the attacker doing from the compromised workstation?",
            "options": [
                {"id": "a", "text": "Running a legitimate IT audit"},
                {"id": "b", "text": "Performing internal reconnaissance — mapping the network, shares, and domain structure", "correct": True},
                {"id": "c", "text": "Backing up files to a network share"},
                {"id": "d", "text": "Installing software updates"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "hunt", "label": "Launch a threat hunt across all endpoints for similar discovery commands", "quality": "optimal"},
                {"id": "disable-acct", "label": "Disable j.harper's account to cut attacker access", "quality": "acceptable"},
                {"id": "wait", "label": "Wait for more definitive evidence before acting", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 2},
            "acceptable": {"containment_delta": 0, "infected_delta": 5},
            "poor": {"containment_delta": -8, "infected_delta": 10},
        },
        "micro_teach": "Discovery commands (net view, nltest, LDAP queries) from a Finance workstation are highly anomalous (T1083). This is the 'golden window' — the attacker is mapping targets but hasn't moved yet. Acting here prevents lateral movement.",
    },

    # ---- Stage 5: Credential Harvest ----
    {
        "index": 5,
        "title": "Credential Harvest",
        "mitre": {"id": "T1003.001", "name": "LSASS Memory"},
        "story": "The attacker dumps credentials from memory on the compromised workstation. They find j.harper's domain password and — critically — the svc_backup service account credentials cached from a recent backup job.",
        "telemetry": [
            {"sev": "critical", "source": "EDR", "msg": "LSASS memory access: rundll32.exe → comsvcs.dll MiniDumpWriteDump on FIN-PC07"},
            {"sev": "high", "source": "Sysmon", "msg": "ProcessAccess: rundll32.exe opened lsass.exe with PROCESS_VM_READ (PID 652)"},
            {"sev": "high", "source": "Sysmon", "msg": "File created: C:\\Windows\\Temp\\debug.dmp (14.2 MB — LSASS memory dump)"},
        ],
        "identify": {
            "prompt": "What critical action did the attacker just perform?",
            "options": [
                {"id": "a", "text": "Created a system restore point"},
                {"id": "b", "text": "Dumped credentials from LSASS memory to harvest domain passwords", "correct": True},
                {"id": "c", "text": "Installed a Windows diagnostic tool"},
                {"id": "d", "text": "Exported browser bookmarks"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "reset-creds", "label": "Force password reset for j.harper AND svc_backup immediately", "quality": "optimal"},
                {"id": "isolate", "label": "Isolate FIN-PC07 and block svc_backup from authenticating", "quality": "optimal"},
                {"id": "partial-reset", "label": "Reset only j.harper's password", "quality": "acceptable"},
                {"id": "investigate", "label": "Investigate which credentials were compromised before acting", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 2},
            "acceptable": {"containment_delta": 0, "infected_delta": 8},
            "poor": {"containment_delta": -15, "infected_delta": 15},
        },
        "micro_teach": "LSASS memory dumping (T1003.001) via comsvcs.dll is a well-known credential theft technique. The real danger is service accounts (svc_backup) with broad access. Reset ALL compromised credentials — not just the user's.",
    },

    # ---- Stage 6: Lateral Movement ----
    {
        "index": 6,
        "title": "Lateral Movement",
        "mitre": {"id": "T1021.001", "name": "Remote Desktop Protocol"},
        "story": "Using svc_backup's credentials, the attacker RDPs to FS01 (file server), BKP01 (backup server), and DC01 (domain controller). Three high-value footholds in minutes.",
        "telemetry": [
            {"sev": "critical", "source": "AD", "msg": "svc_backup: RDP logon to FS01 from FIN-PC07 — service accounts should not use RDP"},
            {"sev": "critical", "source": "AD", "msg": "svc_backup: RDP logon to BKP01 from FIN-PC07 (backup server)"},
            {"sev": "critical", "source": "AD", "msg": "svc_backup: RDP logon to DC01 from FIN-PC07 (DOMAIN CONTROLLER)"},
        ],
        "identify": {
            "prompt": "What does this RDP activity indicate?",
            "options": [
                {"id": "a", "text": "Routine IT maintenance via RDP"},
                {"id": "b", "text": "Lateral movement using stolen service account credentials to reach critical infrastructure", "correct": True},
                {"id": "c", "text": "A backup job connecting to remote hosts"},
                {"id": "d", "text": "Automated monitoring checks"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "isolate-all", "label": "Isolate FS01, BKP01, and DC01 from the network immediately", "quality": "optimal"},
                {"id": "disable-svc", "label": "Disable svc_backup account and force-disconnect all sessions", "quality": "optimal"},
                {"id": "block-rdp", "label": "Block RDP at segment boundaries", "quality": "acceptable"},
                {"id": "monitor", "label": "Continue monitoring — need more evidence", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 10, "infected_delta": 3, "isolated_delta": 3},
            "acceptable": {"containment_delta": 0, "infected_delta": 10},
            "poor": {"containment_delta": -20, "infected_delta": 25},
        },
        "micro_teach": "Service accounts using RDP (T1021.001) to domain controllers is a massive red flag. Over-privileged service accounts are the #1 enabler of lateral movement in ransomware campaigns. This is the critical containment window.",
    },

    # ---- Stage 7: Staging & Pre-Impact ----
    {
        "index": 7,
        "title": "Staging & Pre-Impact",
        "mitre": {"id": "T1490", "name": "Inhibit System Recovery"},
        "story": "The attacker stages the ransomware binary on all compromised hosts. Before detonation, they delete shadow copies and disable backup services — cutting off all recovery options.",
        "telemetry": [
            {"sev": "critical", "source": "Sysmon", "msg": "FS01: vssadmin.exe delete shadows /all /quiet — ALL shadow copies deleted"},
            {"sev": "critical", "source": "Sysmon", "msg": "BKP01: sc config 'Veeam Backup Service' start=disabled — backup service disabled"},
            {"sev": "high", "source": "EDR", "msg": "Binary staged: C:\\Windows\\Temp\\svcupdate.exe copied to FS01, BKP01, DC01 via SMB"},
        ],
        "identify": {
            "prompt": "What is the attacker doing before launching the ransomware?",
            "options": [
                {"id": "a", "text": "Creating backups of important files"},
                {"id": "b", "text": "Disabling recovery mechanisms and staging ransomware binaries on all targets", "correct": True},
                {"id": "c", "text": "Patching the servers with security updates"},
                {"id": "d", "text": "Performing a scheduled disk cleanup"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "protect-bkp", "label": "Emergency: disconnect BKP01 from the network before backups are destroyed", "quality": "optimal"},
                {"id": "block-smb", "label": "Block SMB file copy operations between segments", "quality": "optimal"},
                {"id": "restore-shadow", "label": "Attempt to restore shadow copies on unaffected hosts", "quality": "acceptable"},
                {"id": "wait-encrypt", "label": "Wait to see if encryption actually starts", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 3},
            "acceptable": {"containment_delta": 0, "infected_delta": 5},
            "poor": {"containment_delta": -15, "infected_delta": 10, "backup_destroyed": True},
        },
        "micro_teach": "Deleting shadow copies (T1490) and disabling backup services is the point of no return. If backups are destroyed before you protect them, recovery options shrink to 'pay the ransom or rebuild from scratch.'",
    },

    # ---- Stage 8: Encryption ----
    {
        "index": 8,
        "title": "Data Encrypted for Impact",
        "mitre": {"id": "T1486", "name": "Data Encrypted for Impact"},
        "story": "The ransomware detonates. Files across FS01 and compromised workstations are encrypted with .locked extensions. Ransom notes appear on every affected desktop. The finance department is down.",
        "telemetry": [
            {"sev": "critical", "source": "EDR", "msg": "MASS FILE MODIFICATION: svcupdate.exe encrypting files at 200/sec on FS01 — .locked extension"},
            {"sev": "critical", "source": "File Integrity", "msg": "FS01: 94% of files modified in 180 seconds — ransomware pattern confirmed"},
            {"sev": "critical", "source": "Helpdesk", "msg": "12 simultaneous calls: 'Files locked, ransom note on screen, can't work'"},
        ],
        "identify": {
            "prompt": "What is the impact?",
            "options": [
                {"id": "a", "text": "A disk defragmentation operation"},
                {"id": "b", "text": "Ransomware has encrypted files across the file server and workstations", "correct": True},
                {"id": "c", "text": "An automated file compression for storage optimization"},
                {"id": "d", "text": "A data migration to cloud storage"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "contain", "label": "Isolate all affected hosts and prevent further spread", "quality": "optimal"},
                {"id": "declare", "label": "Declare a P1 incident — activate IR plan and notify leadership", "quality": "optimal"},
                {"id": "negotiate", "label": "Begin ransom negotiation", "quality": "poor"},
                {"id": "power-off", "label": "Emergency power-off all affected systems", "quality": "acceptable"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": -5, "infected_delta": 8, "encrypted_delta": 15},
            "acceptable": {"containment_delta": -12, "infected_delta": 15, "encrypted_delta": 30},
            "poor": {"containment_delta": -20, "infected_delta": 25, "encrypted_delta": 45},
        },
        "micro_teach": "Once encryption starts (T1486), prevention has failed. Focus shifts to: 1) contain remaining clean systems, 2) declare incident for coordinated response, 3) assess backup viability for recovery.",
    },

    # ---- Stage 9: Recovery & Lessons ----
    {
        "index": 9,
        "title": "Recovery & Lessons Learned",
        "mitre": {"id": "", "name": "Post-incident"},
        "story": "The dust settles. 60% of the file server is encrypted. Leadership wants answers: what happened, what was the root cause, and what changes prevent a repeat.",
        "telemetry": [
            {"sev": "high", "source": "CISO", "msg": "Board briefing in 3 hours. Need: timeline, blast radius, root cause, recovery plan."},
            {"sev": "medium", "source": "Legal", "msg": "Personal data on FS01 — breach notification assessment required"},
            {"sev": "medium", "source": "Operations", "msg": "Finance dept offline for 6+ hours. Payroll processing deadline is tomorrow."},
        ],
        "identify": {
            "prompt": "What was the root cause of this breach?",
            "options": [
                {"id": "a", "text": "A zero-day exploit in the firewall"},
                {"id": "b", "text": "A phishing email exploiting human error + over-privileged service account enabling full network compromise", "correct": True},
                {"id": "c", "text": "An insider deliberately planted the ransomware"},
                {"id": "d", "text": "A misconfigured cloud storage bucket"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "least-priv", "label": "Implement least-privilege for service accounts — remove RDP access", "quality": "optimal"},
                {"id": "mfa", "label": "Deploy MFA for all remote access (RDP, VPN)", "quality": "optimal"},
                {"id": "immutable-bkp", "label": "Move to immutable, air-gapped backups", "quality": "optimal"},
                {"id": "training", "label": "Mandatory phishing awareness training for Finance", "quality": "acceptable"},
                {"id": "blame", "label": "Terminate j.harper for clicking the email", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 30000, "speed_bonus_points": 10},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 0},
            "acceptable": {"containment_delta": 2, "infected_delta": 0},
            "poor": {"containment_delta": -5, "infected_delta": 0},
        },
        "micro_teach": "Root cause is rarely one thing. It's the chain: phishing + macro execution + over-privileged service account + flat network + online backups. Defense-in-depth (MFA + least privilege + immutable backups + segmentation) breaks multiple links.",
    },
]

QUIZ_BANK: list[dict] = [
    {"id": "R5-Q1", "objective": "TO-1", "question": "What is the most common initial access vector for ransomware campaigns?",
     "options": [{"id": "a", "text": "USB drives"}, {"id": "b", "text": "Phishing emails with malicious attachments"}, {"id": "c", "text": "Exploiting public-facing web servers"}, {"id": "d", "text": "Physical intrusion"}],
     "correct_id": "b", "rationale": "Phishing remains the #1 initial access vector for ransomware, per CISA and Mandiant reports."},
    {"id": "R5-Q2", "objective": "TO-2", "question": "WINWORD.EXE → cmd.exe → powershell.exe -enc. This process chain most likely indicates:",
     "options": [{"id": "a", "text": "A legitimate Office macro"}, {"id": "b", "text": "Malicious macro executing an encoded PowerShell payload"}, {"id": "c", "text": "A Windows update"}, {"id": "d", "text": "An antivirus scan"}],
     "correct_id": "b", "rationale": "Office spawning cmd/PowerShell with encoded commands is a classic macro attack chain (T1204.002 + T1059.001)."},
    {"id": "R5-Q3", "objective": "TO-3", "question": "Why is rebooting insufficient to remove a scheduled task-based persistence mechanism?",
     "options": [{"id": "a", "text": "The task runs before the user logs in"}, {"id": "b", "text": "The scheduled task survives reboot and re-executes the malware automatically"}, {"id": "c", "text": "Rebooting makes the malware stronger"}, {"id": "d", "text": "The antivirus is disabled during reboot"}],
     "correct_id": "b", "rationale": "Scheduled tasks (T1053.005) persist across reboots by design — the OS re-triggers them automatically."},
    {"id": "R5-Q4", "objective": "TO-4", "question": "Cloud-fronted C2 is difficult to detect because:",
     "options": [{"id": "a", "text": "It uses encrypted USB drives"}, {"id": "b", "text": "The traffic goes to legitimate cloud infrastructure (Azure, AWS) and blends with normal HTTPS"}, {"id": "c", "text": "It only runs at night"}, {"id": "d", "text": "It uses custom protocols"}],
     "correct_id": "b", "rationale": "Cloud-fronting (T1071.001) routes C2 through legitimate CDN/cloud hosts, making it hard to blocklist."},
    {"id": "R5-Q5", "objective": "TO-5", "question": "What is the single highest-impact preventive control for this scenario?",
     "options": [{"id": "a", "text": "Faster antivirus updates"}, {"id": "b", "text": "Least-privilege for service accounts (no RDP, minimal scope)"}, {"id": "c", "text": "More monitor screens for the SOC"}, {"id": "d", "text": "Stronger WiFi passwords"}],
     "correct_id": "b", "rationale": "svc_backup's over-privilege (RDP to DC, file server, backup server) enabled the entire lateral movement chain. Least privilege breaks it."},
    {"id": "R5-Q6", "objective": "TO-2", "question": "LSASS memory dumping via comsvcs.dll is categorized as:",
     "options": [{"id": "a", "text": "T1486 — Data Encrypted for Impact"}, {"id": "b", "text": "T1003.001 — OS Credential Dumping: LSASS Memory"}, {"id": "c", "text": "T1046 — Network Service Discovery"}, {"id": "d", "text": "T1059 — Command and Scripting Interpreter"}],
     "correct_id": "b", "rationale": "Accessing LSASS memory to extract credentials maps to T1003.001."},
    {"id": "R5-Q7", "objective": "TO-3", "question": "A service account authenticates via RDP to a domain controller. This should be classified as:",
     "options": [{"id": "a", "text": "Normal backup operation"}, {"id": "b", "text": "Critical: service accounts should never use interactive RDP logon"}, {"id": "c", "text": "Low priority monitoring event"}, {"id": "d", "text": "Routine maintenance"}],
     "correct_id": "b", "rationale": "Service accounts should authenticate only via the services they run, not via interactive RDP. This is a key detection opportunity."},
    {"id": "R5-Q8", "objective": "TO-4", "question": "What makes immutable backups critical against ransomware?",
     "options": [{"id": "a", "text": "They are faster to restore"}, {"id": "b", "text": "They cannot be deleted or encrypted by the attacker even with admin access"}, {"id": "c", "text": "They use less storage space"}, {"id": "d", "text": "They back up more frequently"}],
     "correct_id": "b", "rationale": "Immutable (WORM) backups cannot be modified even with admin credentials, surviving T1490 (Inhibit System Recovery)."},
    {"id": "R5-Q9", "objective": "TO-5", "question": "The correct order of IR priorities when ransomware detonates is:",
     "options": [{"id": "a", "text": "Pay ransom → Restore → Investigate"}, {"id": "b", "text": "Contain → Assess backup viability → Restore from clean backups → Investigate root cause"}, {"id": "c", "text": "Investigate → Write report → Maybe restore"}, {"id": "d", "text": "Power off everything → Call insurance → Wait"}],
     "correct_id": "b", "rationale": "Contain first (stop spread), assess recovery options (are backups intact?), restore, then investigate for lessons learned."},
    {"id": "R5-Q10", "objective": "TO-1", "question": "In this scenario, what was the 'golden window' for defenders?",
     "options": [{"id": "a", "text": "After encryption started"}, {"id": "b", "text": "During internal discovery — before lateral movement — when the attacker was mapping targets but hadn't spread"}, {"id": "c", "text": "After the ransom note appeared"}, {"id": "d", "text": "During the board briefing"}],
     "correct_id": "b", "rationale": "The discovery phase (net view, LDAP queries) is the optimal detection point — the attacker reveals intent but hasn't yet moved to high-value targets."},
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
