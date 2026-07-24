"""WannaCry scenario definition — all 11 scenes + 15 quiz items.

Pure data. No logic. Loaded by the engine at session start.
Each scene contains: story, telemetry, identify task, respond task, scoring weights, effects.
Based on SRS §4, §11, §13.
"""
from __future__ import annotations

SCENARIO_META = {
    "scenario_id": "scn-wannacry-w1",
    "version": "1.0.0",
    "title": "Operation Tripwire: Anatomy of a Ransomware Worm",
    "family": "ransomware-worm",
    "setting": "Mercy Regional Health Network",
    "role": "SOC Analyst (Tier 2)",
    "estimated_minutes": 35,
    "hard_fail_threshold": 0.80,
    "total_hosts": 250,
}

NETWORK_SEGMENTS = [
    {"id": "seg-pacs", "label": "Radiology / PACS", "host_count": 40},
    {"id": "seg-clin", "label": "Clinical Workstations", "host_count": 120},
    {"id": "seg-admin", "label": "Administrative", "host_count": 55},
    {"id": "seg-dc", "label": "Domain Controllers", "host_count": 2},
    {"id": "seg-file", "label": "File Servers", "host_count": 8},
    {"id": "seg-bkp", "label": "Backup", "host_count": 1},
    {"id": "seg-soc", "label": "SOC / Analyst Tools", "host_count": 23},
]

NAMED_NODES = [
    {"id": "RAD-07", "segment": "seg-pacs", "type": "workstation",
     "criticality": "medium", "patched": False, "smbv1": True, "role": "patient-zero"},
    {"id": "BKP-01", "segment": "seg-bkp", "type": "server",
     "criticality": "critical", "patched": True, "smbv1": False, "holds_backup": True},
    {"id": "DC-01", "segment": "seg-dc", "type": "server",
     "criticality": "critical", "patched": True, "smbv1": False},
    {"id": "DC-02", "segment": "seg-dc", "type": "server",
     "criticality": "critical", "patched": True, "smbv1": False},
    {"id": "FS-01", "segment": "seg-file", "type": "server",
     "criticality": "high", "patched": False, "smbv1": True},
]


# ---------------------------------------------------------------------------
#  11 SCENES
# ---------------------------------------------------------------------------
SCENES: list[dict] = [
    # ---- SCENE 0: Network Discovery ----
    {
        "index": 0,
        "title": "Network Discovery",
        "mitre": {"id": "T1046", "name": "Network Service Discovery"},
        "story": "A burst of connection attempts fans out from a radiology machine, knocking on every door in the subnet. Something is mapping the network.",
        "telemetry": [
            {"sev": "medium", "source": "NetFlow", "msg": "RAD-07: 847 SYN packets to 445/tcp across seg-pacs in 12 seconds"},
            {"sev": "low", "source": "Firewall", "msg": "Rate limit: RAD-07 exceeding 50 conn/s threshold"},
            {"sev": "medium", "source": "IDS", "msg": "Signature: SMB service scan pattern detected from 10.1.40.7"},
        ],
        "identify": {
            "prompt": "What is happening on the wire?",
            "options": [
                {"id": "a", "text": "Routine software update check"},
                {"id": "b", "text": "Network service discovery / scanning", "correct": True},
                {"id": "c", "text": "A user browsing the web"},
                {"id": "d", "text": "Backup replication traffic"},
                {"id": "e", "text": "DHCP lease renewal"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "monitor", "label": "Continue monitoring, gather more data", "quality": "acceptable"},
                {"id": "alert", "label": "Raise alert and begin investigation", "quality": "optimal"},
                {"id": "ignore", "label": "Ignore — probably routine", "quality": "poor"},
                {"id": "reboot", "label": "Reboot the scanning host", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 30000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 0, "infected_delta": 1},
            "acceptable": {"containment_delta": -2, "infected_delta": 1},
            "poor": {"containment_delta": -5, "infected_delta": 3},
        },
        "micro_teach": "Rapid fan-out connection attempts to enumerate reachable hosts is classic discovery behaviour (T1046). Early alerting gives defenders a head start.",
    },

    # ---- SCENE 1: SMB Target Identification ----
    {
        "index": 1,
        "title": "SMB Target Identification",
        "mitre": {"id": "", "name": "Target selection"},
        "story": "The probing settles on machines still speaking an old file-sharing dialect. These are the soft targets.",
        "telemetry": [
            {"sev": "medium", "source": "EDR", "msg": "RAD-07: SMBv1 negotiation attempts to 14 hosts in seg-pacs"},
            {"sev": "low", "source": "Asset DB", "msg": "Query: 14 hosts in seg-pacs have SMBv1 enabled, 12 missing MS17-010"},
            {"sev": "high", "source": "Vuln Scanner", "msg": "CRITICAL: 12 hosts vulnerable to EternalBlue (CVE-2017-0144)"},
        ],
        "identify": {
            "prompt": "Why are these specific hosts being targeted?",
            "options": [
                {"id": "a", "text": "They have weak passwords"},
                {"id": "b", "text": "They run a legacy, unpatched file-sharing service (SMBv1)", "correct": True},
                {"id": "c", "text": "They are connected to the internet"},
                {"id": "d", "text": "They are running antivirus"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "disable-smb", "label": "Begin emergency SMBv1 disable across vulnerable hosts", "quality": "optimal"},
                {"id": "patch-plan", "label": "Schedule patching for next maintenance window", "quality": "acceptable"},
                {"id": "wait", "label": "Wait for more information", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 0},
            "acceptable": {"containment_delta": 0, "infected_delta": 2},
            "poor": {"containment_delta": -8, "infected_delta": 5},
        },
        "micro_teach": "SMBv1 is a legacy protocol with known remote code execution vulnerabilities. Disabling it or patching (MS17-010) closes the attack vector.",
    },

    # ---- SCENE 2: Exploit Vulnerable Host (CRITICAL) ----
    {
        "index": 2,
        "title": "Exploit Vulnerable Host",
        "mitre": {"id": "T1210", "name": "Exploitation of Remote Services"},
        "story": "One of those machines never received the critical update. The worm walks straight through the open door.",
        "telemetry": [
            {"sev": "critical", "source": "EDR", "msg": "RAD-07: EternalBlue exploit payload detected on 445/tcp"},
            {"sev": "high", "source": "SIEM", "msg": "Correlation: known MS17-010 exploit signature matched"},
            {"sev": "critical", "source": "AV", "msg": "RAD-07: Malicious shellcode execution blocked — but secondary payload succeeded"},
        ],
        "identify": {
            "prompt": "What stage of the attack does this telemetry show?",
            "options": [
                {"id": "a", "text": "Phishing email opened"},
                {"id": "b", "text": "Exploitation of a remote service via unpatched vulnerability", "correct": True},
                {"id": "c", "text": "Brute force login attempt"},
                {"id": "d", "text": "DNS tunneling"},
                {"id": "e", "text": "Supply-chain compromise"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "isolate-rad07", "label": "Immediately isolate RAD-07 from the network", "quality": "optimal"},
                {"id": "block-smb-seg", "label": "Block 445/tcp at the segment boundary", "quality": "optimal"},
                {"id": "scan-others", "label": "Scan other hosts for the same vulnerability", "quality": "acceptable"},
                {"id": "wait-confirm", "label": "Wait for AV to confirm remediation", "quality": "poor"},
                {"id": "reboot", "label": "Reboot RAD-07 and hope for the best", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 12, "infected_delta": 2, "isolated_delta": 1},
            "acceptable": {"containment_delta": 4, "infected_delta": 8},
            "poor": {"containment_delta": -15, "infected_delta": 24},
        },
        "micro_teach": "Exploiting a vulnerable network-facing service maps to T1210. Immediate isolation of patient zero and blocking the exploit port are the highest-leverage moves.",
    },

    # ---- SCENE 3: Payload Deployment ----
    {
        "index": 3,
        "title": "Payload Deployment",
        "mitre": {"id": "T1059.003", "name": "Windows Command Shell"},
        "story": "Code lands and runs on the first host. Patient zero is live.",
        "telemetry": [
            {"sev": "high", "source": "EDR", "msg": "RAD-07: cmd.exe spawned by svchost.exe (unusual parent)"},
            {"sev": "high", "source": "Sysmon", "msg": "Process Create: C:\\Windows\\mssecsvc.exe (unsigned, no description)"},
            {"sev": "medium", "source": "EDR", "msg": "RAD-07: New service 'mssecsvc2.0' installed and started"},
        ],
        "identify": {
            "prompt": "What is happening on patient zero?",
            "options": [
                {"id": "a", "text": "A Windows update is installing"},
                {"id": "b", "text": "Malware payload has executed and is establishing itself", "correct": True},
                {"id": "c", "text": "Remote desktop session started"},
                {"id": "d", "text": "Scheduled backup running"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "kill-proc", "label": "Kill the suspicious process and quarantine the executable", "quality": "optimal"},
                {"id": "collect-iocs", "label": "Collect IOCs (hashes, file paths) for threat intel", "quality": "acceptable"},
                {"id": "ignore", "label": "It might be legitimate — monitor passively", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 25},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 1},
            "acceptable": {"containment_delta": 0, "infected_delta": 4},
            "poor": {"containment_delta": -10, "infected_delta": 10},
        },
        "micro_teach": "Distinguishing initial execution from later spread is key. An unusual parent process (svchost → cmd) and unsigned executables are strong indicators of malware deployment (T1059.003).",
    },

    # ---- SCENE 4: Establish Persistence ----
    {
        "index": 4,
        "title": "Establish Persistence",
        "mitre": {"id": "T1059.003", "name": "Windows Command Shell"},
        "story": "It digs in — setting itself to wake up again even after a reboot. Pulling the plug won't be enough.",
        "telemetry": [
            {"sev": "high", "source": "Sysmon", "msg": "Registry: HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run → mssecsvc.exe"},
            {"sev": "medium", "source": "EDR", "msg": "RAD-07: Service 'mssecsvc2.0' set to auto-start"},
            {"sev": "medium", "source": "Sysmon", "msg": "File created: C:\\Windows\\tasksche.exe (hidden, system attributes)"},
        ],
        "identify": {
            "prompt": "What is the malware doing now?",
            "options": [
                {"id": "a", "text": "Scanning for more targets"},
                {"id": "b", "text": "Establishing persistence to survive reboot", "correct": True},
                {"id": "c", "text": "Encrypting files"},
                {"id": "d", "text": "Exfiltrating data"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "remove-persist", "label": "Remove registry keys, disable the service, delete dropped files", "quality": "optimal"},
                {"id": "document", "label": "Document the persistence mechanisms for later cleanup", "quality": "acceptable"},
                {"id": "reboot", "label": "Reboot the host to clear the infection", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 25000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": 3, "infected_delta": 1},
            "acceptable": {"containment_delta": 0, "infected_delta": 3},
            "poor": {"containment_delta": -5, "infected_delta": 6},
        },
        "micro_teach": "Persistence ensures malware survives reboot. Simply rebooting an infected host won't help — the malware will restart. Registry Run keys and auto-start services are classic persistence (T1059.003).",
    },

    # ---- SCENE 5: C2 Callback (CRITICAL) ----
    {
        "index": 5,
        "title": "Command & Control Callback",
        "mitre": {"id": "T1071.001", "name": "Web Protocols"},
        "story": "The host reaches out to the internet, checking in. A single outbound call could be the difference between a contained incident and a headline.",
        "telemetry": [
            {"sev": "high", "source": "Proxy", "msg": "RAD-07: HTTP GET to iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com (known kill-switch domain)"},
            {"sev": "high", "source": "DNS", "msg": "RAD-07: DNS query for suspicious domain — no cached response, first-seen"},
            {"sev": "medium", "source": "Firewall", "msg": "Outbound 80/tcp from RAD-07 to 198.51.100.47 (uncategorized IP)"},
        ],
        "identify": {
            "prompt": "What is this outbound traffic?",
            "options": [
                {"id": "a", "text": "Normal web browsing"},
                {"id": "b", "text": "Command-and-control beaconing over web protocols", "correct": True},
                {"id": "c", "text": "DNS lookup for a software update"},
                {"id": "d", "text": "VPN handshake"},
                {"id": "e", "text": "Printer discovery"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "block-egress", "label": "Block outbound traffic from RAD-07 at the firewall", "quality": "optimal"},
                {"id": "sinkhole", "label": "Sinkhole the C2 domain via DNS", "quality": "optimal"},
                {"id": "monitor-c2", "label": "Monitor the C2 traffic to gather intelligence", "quality": "acceptable"},
                {"id": "ignore", "label": "Probably legitimate — ignore", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 10, "infected_delta": 2},
            "acceptable": {"containment_delta": 2, "infected_delta": 6},
            "poor": {"containment_delta": -12, "infected_delta": 15},
        },
        "micro_teach": "C2 beaconing over HTTP/HTTPS (T1071.001) lets the attacker maintain control. Blocking egress and sinkholing the domain can blunt the campaign. The WannaCry kill-switch domain was a real-world example.",
    },

    # ---- SCENE 6: Lateral Movement (CRITICAL) ----
    {
        "index": 6,
        "title": "Lateral Movement",
        "mitre": {"id": "T1021.002", "name": "SMB/Windows Admin Shares"},
        "story": "It copies itself to a neighbour using trusted file-sharing channels. One machine becomes two.",
        "story_strong": "Because you cut the subnet early, the spread is slower than it could be — but it hasn't stopped. A neighbour just lit up.",
        "story_weak": "The window closed while the alert sat unread. The worm has jumped to a second host — and it's accelerating.",
        "telemetry": [
            {"sev": "high", "source": "EDR", "msg": "Service created on CLIN-22 from RAD-07 session"},
            {"sev": "medium", "source": "NetFlow", "msg": "445/tcp burst: RAD-07 → 14 internal hosts"},
            {"sev": "high", "source": "AD", "msg": "Unusual admin-share write to CLIN-22\\ADMIN$"},
        ],
        "identify": {
            "prompt": "What stage of the attack does this telemetry show?",
            "options": [
                {"id": "a", "text": "Initial access via phishing"},
                {"id": "b", "text": "Lateral movement over admin shares", "correct": True},
                {"id": "c", "text": "Data exfiltration to the internet"},
                {"id": "d", "text": "Privilege escalation on the domain controller"},
                {"id": "e", "text": "Denial of service against file servers"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "isolate-src", "label": "Isolate RAD-07 (source host)", "quality": "optimal"},
                {"id": "segment-block", "label": "Block 445/tcp between clinical subnets", "quality": "optimal"},
                {"id": "reset-creds", "label": "Force reset of compromised service account", "quality": "acceptable"},
                {"id": "wait", "label": "Continue monitoring, take no action", "quality": "poor"},
                {"id": "reboot-all", "label": "Mass-reboot clinical workstations", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 12, "infected_delta": 2, "isolated_delta": 2},
            "acceptable": {"containment_delta": 4, "infected_delta": 8},
            "poor": {"containment_delta": -20, "infected_delta": 40},
        },
        "micro_teach": "Cutting the spread path now is the highest-leverage move. Isolation + port blocking stops propagation via admin shares (T1021.002). This is the critical containment window.",
    },

    # ---- SCENE 7: Repeat Propagation ----
    {
        "index": 7,
        "title": "Repeat Propagation",
        "mitre": {"id": "", "name": "Worm propagation"},
        "story": "Two becomes four. Four becomes sixteen. The curve is bending upward and the clock is now your enemy.",
        "story_strong": "Your early containment is paying off — the spread is slower, but the curve is still climbing. Every minute counts.",
        "story_weak": "It's spreading faster than you can track. The subnet you didn't isolate is now a launch pad for the next wave.",
        "telemetry": [
            {"sev": "critical", "source": "SIEM", "msg": "ALERT: 16 new hosts compromised in last 90 seconds"},
            {"sev": "high", "source": "NetFlow", "msg": "SMB traffic volume 4200% above baseline across seg-clin"},
            {"sev": "critical", "source": "EDR", "msg": "mssecsvc.exe detected on CLIN-03, CLIN-08, CLIN-14, CLIN-22, ADMIN-05..."},
        ],
        "identify": {
            "prompt": "What pattern does this rapid spread demonstrate?",
            "options": [
                {"id": "a", "text": "A user copying files to multiple shares"},
                {"id": "b", "text": "Exponential, worm-like self-propagation across the network", "correct": True},
                {"id": "c", "text": "A scheduled software deployment"},
                {"id": "d", "text": "Network congestion from a backup job"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "emergency-seg", "label": "Emergency network segmentation — isolate all affected subnets", "quality": "optimal"},
                {"id": "selective-iso", "label": "Selectively isolate only confirmed infected hosts", "quality": "acceptable"},
                {"id": "wait-count", "label": "Wait until we have a complete count of infected hosts", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 8, "isolated_delta": 5},
            "acceptable": {"containment_delta": -5, "infected_delta": 35},
            "poor": {"containment_delta": -25, "infected_delta": 80},
        },
        "micro_teach": "Worm growth is exponential. Each minute of delay roughly multiplies the number of infected hosts. Emergency segmentation stops the bleeding even if some hosts are lost.",
    },

    # ---- SCENE 8: Disable Recovery (CRITICAL) ----
    {
        "index": 8,
        "title": "Disable Recovery",
        "mitre": {"id": "T1490", "name": "Inhibit System Recovery"},
        "story": "On infected hosts, the safety nets vanish — recovery points are being wiped so victims can't simply roll back.",
        "telemetry": [
            {"sev": "critical", "source": "Sysmon", "msg": "Process: vssadmin.exe delete shadows /all /quiet — executed on 12 hosts"},
            {"sev": "high", "source": "EDR", "msg": "Volume Shadow Copy Service stopped on CLIN-03, CLIN-08, FS-01"},
            {"sev": "critical", "source": "Backup", "msg": "WARNING: BKP-01 receiving unusual SMB connection attempts from seg-clin"},
        ],
        "identify": {
            "prompt": "What is the malware doing to recovery options?",
            "options": [
                {"id": "a", "text": "Creating system restore points"},
                {"id": "b", "text": "Deleting shadow copies and recovery points to prevent rollback", "correct": True},
                {"id": "c", "text": "Encrypting backup tapes"},
                {"id": "d", "text": "Updating the antivirus definitions"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "protect-bkp", "label": "Immediately isolate BKP-01 (backup server) from the network", "quality": "optimal"},
                {"id": "block-vss", "label": "Block vssadmin.exe execution via application control", "quality": "optimal"},
                {"id": "verify-tapes", "label": "Verify offline backup tapes are intact", "quality": "acceptable"},
                {"id": "ignore-bkp", "label": "The backup server is patched, it should be fine", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 15000, "speed_bonus_points": 30},
        "effects": {
            "optimal": {"containment_delta": 8, "infected_delta": 3},
            "acceptable": {"containment_delta": 2, "infected_delta": 5},
            "poor": {"containment_delta": -15, "infected_delta": 10, "backup_destroyed": True},
        },
        "micro_teach": "Destroying recovery points (T1490) ensures victims cannot simply roll back. Protecting the backup server is the difference between recovery and disaster. Offline/immutable backups survive.",
    },

    # ---- SCENE 9: Encrypt Files ----
    {
        "index": 9,
        "title": "Encrypt Files",
        "mitre": {"id": "T1486", "name": "Data Encrypted for Impact"},
        "story": "Screens across the hospital turn red. Files are being locked. Radiology can't pull images; the ED is going to paper.",
        "telemetry": [
            {"sev": "critical", "source": "EDR", "msg": "Mass file rename detected: *.WNCRY extension on CLIN-03, CLIN-08, FS-01"},
            {"sev": "critical", "source": "File Integrity", "msg": "92% of files on FS-01 modified in last 120 seconds"},
            {"sev": "critical", "source": "Helpdesk", "msg": "17 simultaneous calls: 'my files are locked, ransom note on screen'"},
        ],
        "identify": {
            "prompt": "What is the impact technique being used?",
            "options": [
                {"id": "a", "text": "Data destruction (wiping)"},
                {"id": "b", "text": "Data encrypted for impact — ransomware", "correct": True},
                {"id": "c", "text": "Data exfiltration to external server"},
                {"id": "d", "text": "Denial of service attack on the file server"},
            ],
        },
        "respond": {
            "selection": "single",
            "actions": [
                {"id": "contain-remaining", "label": "Contain remaining clean hosts — prevent further encryption", "quality": "optimal"},
                {"id": "negotiate", "label": "Begin ransom negotiation", "quality": "poor"},
                {"id": "power-off", "label": "Emergency power-off all affected hosts", "quality": "acceptable"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 20000, "speed_bonus_points": 20},
        "effects": {
            "optimal": {"containment_delta": -5, "infected_delta": 5, "encrypted_delta": 15},
            "acceptable": {"containment_delta": -12, "infected_delta": 10, "encrypted_delta": 30},
            "poor": {"containment_delta": -20, "infected_delta": 20, "encrypted_delta": 50},
        },
        "micro_teach": "Mass file encryption (T1486) is the final impact stage. At this point, prevention has failed — the focus shifts to containing what remains and preparing recovery from backups.",
    },

    # ---- SCENE 10: Business Impact ----
    {
        "index": 10,
        "title": "Business Impact",
        "mitre": {"id": "", "name": "Organizational impact"},
        "story": "Morning. The board wants answers. What happened, how far did it get, and how do we make sure it never happens again?",
        "telemetry": [
            {"sev": "high", "source": "CISO", "msg": "Board briefing in 2 hours. Need: root cause, blast radius, recovery timeline."},
            {"sev": "medium", "source": "Legal", "msg": "Patient data involved — breach notification obligations triggered"},
            {"sev": "medium", "source": "Operations", "msg": "ED operating on paper. Radiology downtime: 14 hours and counting."},
        ],
        "identify": {
            "prompt": "What is the most important lesson from this incident?",
            "options": [
                {"id": "a", "text": "Antivirus should have caught everything"},
                {"id": "b", "text": "A single unpatched host with a legacy protocol enabled the entire compromise", "correct": True},
                {"id": "c", "text": "The worm was unstoppable regardless of defenses"},
                {"id": "d", "text": "Better passwords would have prevented this"},
            ],
        },
        "respond": {
            "selection": "multi",
            "actions": [
                {"id": "patch-plan", "label": "Implement emergency patching program for all SMBv1 hosts", "quality": "optimal"},
                {"id": "segment", "label": "Deploy network segmentation between clinical subnets", "quality": "optimal"},
                {"id": "offline-backup", "label": "Establish offline, immutable backup infrastructure", "quality": "optimal"},
                {"id": "egress", "label": "Implement egress filtering and DNS sinkholing", "quality": "acceptable"},
                {"id": "blame", "label": "Blame the IT team for not patching", "quality": "poor"},
            ],
        },
        "scoring": {"identify_points": 100, "response_weights": {"optimal": 100, "acceptable": 60, "poor": 0}, "speed_bonus_max_ms": 30000, "speed_bonus_points": 10},
        "effects": {
            "optimal": {"containment_delta": 5, "infected_delta": 0},
            "acceptable": {"containment_delta": 2, "infected_delta": 0},
            "poor": {"containment_delta": -5, "infected_delta": 0},
        },
        "micro_teach": "Defence-in-depth (patching + segmentation + offline backups + egress filtering) is far stronger than any single control. The root cause was a single unpatched, legacy service — preventable.",
    },
]


# ---------------------------------------------------------------------------
#  QUIZ BANK (15 items, from SRS §13)
# ---------------------------------------------------------------------------
QUIZ_BANK: list[dict] = [
    {"id": "Q1", "objective": "TO-1", "question": "Place the following ransomware-worm stages in the order they typically occur:",
     "options": [
         {"id": "a", "text": "Encrypt files → Lateral movement → Network discovery"},
         {"id": "b", "text": "Network discovery → Exploit → Propagate → Encrypt files"},
         {"id": "c", "text": "Persistence → Encrypt files → Discovery → Exploit"},
         {"id": "d", "text": "C2 callback → Encrypt files → Discovery"},
     ], "correct_id": "b", "rationale": "Worms first find targets, exploit a weakness, spread, and only then deliver impact such as encryption."},

    {"id": "Q2", "objective": "TO-2", "mitre": "T1046", "question": "A host suddenly attempts connections to many neighbours across a subnet. This is most consistent with:",
     "options": [
         {"id": "a", "text": "Routine software update"},
         {"id": "b", "text": "Network service discovery / scanning"},
         {"id": "c", "text": "A user browsing the web"},
         {"id": "d", "text": "Backup replication"},
     ], "correct_id": "b", "rationale": "Rapid fan-out connection attempts to enumerate reachable hosts is classic discovery behaviour (T1046)."},

    {"id": "Q3", "objective": "TO-4", "question": "Why can a single unpatched, legacy file-sharing service be enough to compromise many machines?",
     "options": [
         {"id": "a", "text": "Because it slows the network down"},
         {"id": "b", "text": "Because a remotely exploitable flaw lets code spread machine-to-machine without user action"},
         {"id": "c", "text": "Because users must click a link on every host"},
         {"id": "d", "text": "Because antivirus is never installed on servers"},
     ], "correct_id": "b", "rationale": "Worm-like spread exploits a remote service flaw so no human action is needed at each hop."},

    {"id": "Q4", "objective": "TO-2", "mitre": "T1210", "question": "Telemetry shows exploitation of a remote service on a host missing a critical OS patch. The technique category is:",
     "options": [
         {"id": "a", "text": "Phishing"},
         {"id": "b", "text": "Exploitation of remote services"},
         {"id": "c", "text": "Brute force"},
         {"id": "d", "text": "Supply-chain compromise"},
     ], "correct_id": "b", "rationale": "Exploiting a vulnerable network-facing service maps to T1210."},

    {"id": "Q5", "objective": "TO-4", "question": "Which control most directly prevents the Stage 3 exploitation in this scenario?",
     "options": [
         {"id": "a", "text": "Stronger passwords"},
         {"id": "b", "text": "Applying the security patch / disabling the legacy protocol"},
         {"id": "c", "text": "A longer screensaver timeout"},
         {"id": "d", "text": "More frequent password rotation"},
     ], "correct_id": "b", "rationale": "The exploit depends on an unpatched, legacy SMBv1 service; patching or disabling it closes the door."},

    {"id": "Q6", "objective": "TO-2", "mitre": "T1071.001", "question": "An infected host repeatedly makes small outbound web requests to the same external destination. This is best described as:",
     "options": [
         {"id": "a", "text": "Command-and-control beaconing over web protocols"},
         {"id": "b", "text": "A normal DNS lookup"},
         {"id": "c", "text": "A printer discovery broadcast"},
         {"id": "d", "text": "A VPN handshake"},
     ], "correct_id": "a", "rationale": "Regular small callbacks over HTTP/S to a fixed destination are beaconing (T1071.001)."},

    {"id": "Q7", "objective": "TO-3", "mitre": "T1021.002", "question": "The worm is spreading host-to-host over admin file shares. The single most effective immediate containment action is:",
     "options": [
         {"id": "a", "text": "Email all staff a warning"},
         {"id": "b", "text": "Isolate the source host and block the file-sharing port between segments"},
         {"id": "c", "text": "Increase monitor brightness"},
         {"id": "d", "text": "Schedule a patch for next week"},
     ], "correct_id": "b", "rationale": "Cutting the spread path stops propagation now."},

    {"id": "Q8", "objective": "TO-3", "question": "During exponential propagation, why does response speed matter so much?",
     "options": [
         {"id": "a", "text": "It does not; outcome is fixed"},
         {"id": "b", "text": "Each minute of delay roughly multiplies the number of infected hosts"},
         {"id": "c", "text": "Slower is safer for evidence"},
         {"id": "d", "text": "The worm stops on its own after 10 minutes"},
     ], "correct_id": "b", "rationale": "Worm growth is exponential, so delay compounds."},

    {"id": "Q9", "objective": "TO-2", "mitre": "T1490", "question": "Before encrypting, the malware deletes shadow copies and local recovery points. This technique is:",
     "options": [
         {"id": "a", "text": "Data encrypted for impact"},
         {"id": "b", "text": "Inhibit system recovery"},
         {"id": "c", "text": "Account discovery"},
         {"id": "d", "text": "Input capture"},
     ], "correct_id": "b", "rationale": "Destroying recovery points to prevent rollback is Inhibit System Recovery (T1490)."},

    {"id": "Q10", "objective": "TO-3", "question": "Which measure best ensures the organisation can recover even if encryption succeeds?",
     "options": [
         {"id": "a", "text": "Faster CPUs"},
         {"id": "b", "text": "Offline / immutable backups kept off the production network"},
         {"id": "c", "text": "A second antivirus product"},
         {"id": "d", "text": "Brighter ransom-note fonts"},
     ], "correct_id": "b", "rationale": "Backups isolated from the network survive recovery-inhibition and encryption."},

    {"id": "Q11", "objective": "TO-5", "mitre": "T1486", "question": "Mass file encryption that halts operations maps to which MITRE technique?",
     "options": [
         {"id": "a", "text": "T1486, Data Encrypted for Impact"},
         {"id": "b", "text": "T1046, Network Service Discovery"},
         {"id": "c", "text": "T1071, Application Layer Protocol"},
         {"id": "d", "text": "T1059, Command and Scripting"},
     ], "correct_id": "a", "rationale": "Encrypting data to deny availability is T1486."},

    {"id": "Q12", "objective": "TO-1", "question": "What single property makes this malware a 'worm' rather than ordinary ransomware?",
     "options": [
         {"id": "a", "text": "It shows a ransom note"},
         {"id": "b", "text": "It self-propagates between hosts without user interaction"},
         {"id": "c", "text": "It encrypts files"},
         {"id": "d", "text": "It runs on Windows"},
     ], "correct_id": "b", "rationale": "Self-propagation without user action is the defining worm behaviour."},

    {"id": "Q13", "objective": "TO-5", "question": "Network segmentation reduces ransomware-worm impact primarily because it:",
     "options": [
         {"id": "a", "text": "Speeds up the internet"},
         {"id": "b", "text": "Limits how far the worm can spread laterally"},
         {"id": "c", "text": "Encrypts files faster"},
         {"id": "d", "text": "Removes the need for backups"},
     ], "correct_id": "b", "rationale": "Segmentation contains lateral movement."},

    {"id": "Q14", "objective": "TO-5", "question": "Which combination gives the strongest defence against this class of attack?",
     "options": [
         {"id": "a", "text": "Patching only"},
         {"id": "b", "text": "Backups only"},
         {"id": "c", "text": "Patching + segmentation + offline backups + egress filtering"},
         {"id": "d", "text": "Longer passwords + screensavers"},
     ], "correct_id": "c", "rationale": "Defence-in-depth is far stronger than any single control."},

    {"id": "Q15", "objective": "TO-5", "question": "After containment, what is the correct ordering of recovery priorities?",
     "options": [
         {"id": "a", "text": "Pay ransom first"},
         {"id": "b", "text": "Restore from clean backups, validate integrity, then return systems to service"},
         {"id": "c", "text": "Reconnect everything immediately"},
         {"id": "d", "text": "Delete logs to save space"},
     ], "correct_id": "b", "rationale": "Recovery should rely on verified clean backups and integrity checks before reconnection."},
]


def get_scene(index: int) -> dict:
    """Get a scene definition by index (0-10)."""
    if 0 <= index < len(SCENES):
        return SCENES[index]
    raise ValueError(f"Invalid scene index: {index}")


def get_quiz_subset(count: int = 10) -> list[dict]:
    """Get a subset of quiz items. Default 10 out of 15."""
    import random
    if count >= len(QUIZ_BANK):
        return list(QUIZ_BANK)
    return random.sample(QUIZ_BANK, count)
