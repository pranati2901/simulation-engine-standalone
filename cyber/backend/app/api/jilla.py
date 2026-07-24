"""Jilla AI — narrative cybersecurity teaching engine.

Jilla is NOT a chatbot. She is an event-driven storytelling instructor who:
- Proactively narrates as the student acts (no typing needed)
- Tells the real WannaCry/REvil/Conti story with the student as protagonist
- Watches sim actions as assessment (tool usage = student's answer)
- Tracks student knowledge and adapts depth

Endpoints:
  POST /api/jilla/event  — event-driven narration (the core endpoint)
  POST /api/jilla/chat   — free-form student question
  POST /api/jilla/hint   — progressive hint (4 levels)
  GET  /api/jilla/intro   — opening narration
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/jilla", tags=["jilla"])

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")


# ---------------------------------------------------------------------------
#  Student State — per-session knowledge tracking
# ---------------------------------------------------------------------------
class StudentState(BaseModel):
    role: str = "red"
    scenario_id: str = ""
    concepts_introduced: list[str] = []
    concepts_demonstrated: list[str] = []
    tools_used: list[str] = []
    story_act: int = 1  # 1=setup, 2=rising, 3=climax, 4=resolution
    current_depth: int = 0  # 0=zero knowledge, 1=basics, 2=intermediate, 3=advanced
    hint_count: int = 0
    narrations_sent: int = 0
    last_narration: str = ""
    last_event_time: float = 0.0
    phase_history: list[str] = []

_student_states: dict[str, StudentState] = {}


def _get_state(session_id: str, role: str = "red", scenario_id: str = "") -> StudentState:
    key = session_id or f"{scenario_id}_{role}"
    if key not in _student_states:
        _student_states[key] = StudentState(role=role, scenario_id=scenario_id)
    return _student_states[key]


# ---------------------------------------------------------------------------
#  Story Beats — WannaCry W1 (full real-incident narrative)
# ---------------------------------------------------------------------------
W1_STORY: dict[str, dict[str, dict]] = {
    "Host Discovery": {
        "red": {
            "narration": "May 12, 2017. 7:44 AM UTC. You're a nation-state operator sitting on a compromised perimeter host inside Mercy Regional Hospital. Somewhere in this network are 200 Windows machines that haven't seen a patch since February. The NSA's most powerful exploit — stolen by the Shadow Brokers and dumped online two months ago — is in your toolkit. The topology map on your left is grey. Terra incognita. What does every operator do first on an unfamiliar network?",
            "concept": "reconnaissance",
            "success": "47 hosts light up on the map. In the real attack, the WannaCry operators had access to thousands of networks simultaneously. But each one started exactly like this — one scan, one map. Now the question is: are all 47 vulnerable to your exploit?",
        },
        "soc": {
            "narration": "May 12, 2017. You're the overnight SOC analyst at Mercy Regional Hospital. Your shift started quiet. Coffee's still warm. The Suricata dashboard shows normal traffic. But somewhere on this network, someone just got in. You don't know it yet. Your job is to spot the first anomaly before it's too late. Watch your alert feeds.",
            "concept": "network_monitoring",
            "success": "Good instinct checking the feeds early. In the real WannaCry attack, most SOC teams didn't notice the initial reconnaissance because nmap scans look like normal network discovery. The question is — what would distinguish a malicious scan from a legitimate one?",
        },
        "blue": {
            "narration": "May 12, 2017. You're the incident response lead at Mercy Regional. Your pager hasn't gone off yet, but it will. NHS England is about to get hit. 80,000 endpoints across 81 health organizations. Your hospital runs the same unpatched Windows 7 fleet. Right now, the network looks clean. But you have a narrow window to prepare. What would you check first?",
            "concept": "asset_inventory",
            "success": "Smart move. In the real incident, the NHS trusts that had an up-to-date asset inventory recovered in hours. The ones that didn't took weeks. Knowing what you have is the first step to defending it.",
        },
    },
    "SMB Enumeration": {
        "red": {
            "narration": "Your scan found hosts. But not all of them are your targets. The exploit you're carrying — EternalBlue — only works against one specific protocol. SMBv1. A file-sharing protocol from 2006 that Microsoft begged people to disable. The NHS had a memo about it. They never got around to it. Look at your tool palette — there's a tool that checks which hosts still run SMBv1.",
            "concept": "smb_enumeration",
            "success": "12 out of 47 hosts are running SMBv1. See those amber nodes? Every single one is a target. In the real attack, the ratio was similar — about 25% of machines on most networks were still running the vulnerable protocol. Microsoft released the patch (MS17-010) two months earlier. These 12 machines never applied it.",
        },
        "soc": {
            "narration": "Something just happened on the network. A burst of SMB traffic — port 445 — scanning across multiple subnets. That's not normal for 3 AM on a Friday. Is it a scheduled backup job? A misconfigured application? Or something else? Check your Zeek logs. What do you see?",
            "concept": "smb_traffic_analysis",
        },
        "blue": {
            "narration": "The SOC just flagged unusual SMB traffic. Port 445 scans across multiple VLANs. This could be nothing — or it could be the opening move of something much bigger. You have a decision to make: investigate quietly, or start locking things down preemptively. What's your call?",
            "concept": "early_response",
        },
    },
    "Exploit": {
        "red": {
            "narration": "You've found your targets. 12 machines with SMBv1 wide open. Now comes EternalBlue — the exploit the NSA developed internally, codename ETERNALBLUE, and the Shadow Brokers leaked to the world on April 14, 2017. It exploits a buffer overflow in the SMBv1 driver (srv.sys) to achieve remote code execution. No password needed. No user interaction. Just a network connection to port 445. Pick your patient zero carefully — which host would give you the best position for what comes next?",
            "concept": "exploitation",
            "success": "Direct hit. See how that node just turned orange? That means you have a shell — remote code execution on that host. In the real WannaCry attack, this exploit fired autonomously against every reachable SMBv1 host. No human decision needed. But right now, you're still manual. The question is: what turns a single exploit into a global pandemic?",
        },
        "soc": {
            "narration": "Your IDS just lit up. Suricata signature ET EXPLOIT EternalBlue — a known nation-state exploit targeting SMBv1. This is not a drill. Someone just used a leaked NSA exploit against one of your hosts. The alert shows the source IP, the destination, and the payload signature. What do you do with this information?",
            "concept": "ids_alert_triage",
        },
        "blue": {
            "narration": "The SOC just escalated. They're seeing EternalBlue signatures on the network. This is the same exploit that will hit the NHS in the next hour. You need to decide: which hosts are the highest priority to protect? The domain controller? The file server? The medical records system? And how do you protect them without taking critical systems offline?",
            "concept": "containment_priorities",
        },
    },
    "Payload": {
        "red": {
            "narration": "The exploit gave you a shell. But a shell is temporary — it dies when the process ends. You need to drop the actual worm binary and execute it. Once the worm is resident on the host, that node turns from orange to solid red. It's no longer just compromised — it's infected. And an infected host becomes a launch pad for everything that follows.",
            "concept": "payload_delivery",
            "success": "The worm is resident. That host is now a fully autonomous attack platform. It doesn't need you anymore. In the real WannaCry, the worm binary was 3.6 MB — small enough to transfer over SMB in seconds. Once running, it started two parallel tasks: encrypt local files, and scan for new targets.",
        },
        "soc": {
            "narration": "Your endpoint telemetry just flagged something strange. A new executable appeared on one of the compromised hosts — 3.6 MB, unsigned, writing to the Windows directory. Sysmon Event ID 1 (Process Create) shows it spawning child processes. This isn't normal software installation. Something just went resident on that machine.",
            "concept": "endpoint_detection",
            "success": "Good catch. You spotted the payload drop via Sysmon. In the real WannaCry incident, most organizations didn't have endpoint visibility. The ones running Sysmon or EDR agents saw the payload within minutes. The ones without it had no idea until ransom notes appeared.",
        },
        "blue": {
            "narration": "The SOC reports a new unsigned executable running on a compromised host. It's writing to the Windows directory and spawning child processes. This is the payload — the actual malware binary. You have a narrow window: if you can isolate this host NOW, before it starts propagating, you contain the incident to a single machine. Every second you wait multiplies your problem.",
            "concept": "host_isolation",
        },
    },
    "Persistence": {
        "red": {
            "narration": "Amateur malware dies on reboot. Professional malware survives everything short of reimaging. WannaCry installed itself as a Windows service — mssecsvc2.0 — which auto-starts at boot. It also dropped a copy in the Windows directory. Even if IT restarts the machine, the worm comes back. Look for the anchor icon on the infected node — that means persistence is established.",
            "concept": "persistence",
            "success": "The anchor is set. That host will stay infected through reboots, restarts, even safe mode. In the real incident, NHS IT staff tried rebooting machines as a first response. It didn't work. The worm came right back. The only way to remove it was a complete reimage — which most hospitals couldn't do at scale.",
        },
        "soc": {
            "narration": "Your Sysmon logs show a new service being created: mssecsvc2.0. Service creation events (Event ID 7045) are one of the most reliable indicators of persistence. The attacker wants to survive reboots. This tells you something important about their intent — they're not just passing through. They're setting up camp.",
            "concept": "persistence_detection",
        },
        "blue": {
            "narration": "Bad news: the malware has installed a Windows service for persistence. Rebooting won't help — it'll come right back. Your options are narrowing. You need to either isolate the host from the network entirely, or push a removal script that stops the service and deletes the binary before the next propagation wave. Which approach is faster?",
            "concept": "persistence_remediation",
        },
    },
    "C2": {
        "red": {
            "narration": "Here's WannaCry's most fascinating secret. Before encrypting any files, the worm checks a hardcoded domain: iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com. If the domain resolves, the worm STOPS. Marcus Hutchins — MalwareTech — noticed this on May 12 and registered the domain for $10.69. The global outbreak halted within hours. Was it an intentional kill switch? A sandbox check? A dead man's switch? Nobody knows for sure.",
            "concept": "kill_switch",
            "success": "The kill switch check is in place. In this simulation, Blue team can sinkhole the domain to trigger the same effect — stopping all new encryption. But here's the twist: machines already encrypted stay encrypted. The kill switch prevents NEW infections, it doesn't reverse existing damage.",
        },
        "soc": {
            "narration": "Your DNS logs show something bizarre. Every infected machine is making a DNS query to an extremely long, random-looking domain. This is unusual — legitimate software doesn't query domains like iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com. Is this C2 communication? A DGA domain? Or something else entirely? What would you do with this intelligence?",
            "concept": "dns_analysis",
        },
        "blue": {
            "narration": "The SOC just handed you gold. They found a DNS query pattern — every infected host checks a specific domain before encrypting. If you can make that domain resolve (sinkhole it), the worm stops encrypting. This is the kill switch. In the real WannaCry attack, a 22-year-old researcher did this accidentally and saved the world. You have the same opportunity. Do you take it?",
            "concept": "dns_sinkhole",
        },
    },
    "Disable Recovery": {
        "red": {
            "narration": "The final preparation before encryption. Smart ransomware doesn't just encrypt files — it makes sure you can't recover them. WannaCry deletes Volume Shadow Copies (Windows' built-in backup snapshots), wipes the recycle bin, and disables Windows Recovery. Without these, there's no 'undo' button. If Blue team hasn't protected the backup server yet, this is the point of no return.",
            "concept": "recovery_destruction",
            "success": "Shadow copies deleted. Recovery partitions wiped. The safety net is gone. In the real NHS incident, hospitals that had offline backups recovered in days. Those relying on Volume Shadow Copies? They lost everything. The difference between a bad day and a catastrophe came down to one question: were your backups air-gapped?",
        },
        "soc": {
            "narration": "Multiple hosts just logged vssadmin.exe delete shadows /all. That's the command to destroy Volume Shadow Copies — Windows' built-in backup system. The attacker is cutting the safety net before encrypting. You need to alert Blue team immediately: if they haven't isolated the backup server yet, they're about to lose their last recovery option.",
            "concept": "shadow_copy_monitoring",
        },
        "blue": {
            "narration": "The attacker just destroyed shadow copies on {infected} hosts. Your backup server is the last line of defense. If the worm reaches it, you lose everything — not just current files, but the ability to restore. This is exactly what happened to NHS trusts that kept backups on the same network. Isolate the backup server NOW. Air-gap it. Every second counts.",
            "concept": "backup_protection",
        },
    },
    "Lateral Movement": {
        "red": {
            "narration": "This is the moment that separates a single compromise from a global catastrophe. The worm you just planted doesn't wait for instructions. Hit propagate, and every infected host automatically scans its neighbors for SMBv1, exploits them, drops the payload, and repeats. Watch the R-value — that's the reproduction rate. If it's above 1.0, the infection grows exponentially. WannaCry's R-value in real life was estimated at 3.5. That's why it hit 200,000 machines in one afternoon.",
            "concept": "lateral_movement",
            "success": "Watch the map. See the red spreading? That's exactly what NHS hospitals saw. One machine after another, floor after floor, building after building. The R-value of {r_value} means each infected host is infecting {r_value} others. At this rate, the entire network will be compromised in minutes. The SOC team just got their first alerts. The race is on.",
        },
        "soc": {
            "narration": "Your dashboard is exploding. Multiple EternalBlue alerts across different subnets. This isn't a targeted attack anymore — it's a worm. Self-propagating. Each infected host is scanning and exploiting its neighbors automatically. The infection count is climbing: {infected} hosts and rising. You need to figure out the propagation pattern and alert Blue team NOW.",
            "concept": "worm_detection",
        },
        "blue": {
            "narration": "This is a worm. Self-propagating via SMBv1 across every VLAN. {infected} hosts are already infected and the count is climbing. You have one tool that can stop the bleeding immediately — network segmentation. Block port 445 between VLANs and you cut the worm's propagation path. The NHS hospitals that were segmented survived. The flat networks were devastated. What's your move?",
            "concept": "network_segmentation",
        },
    },
    "Impact": {
        "red": {
            "narration": "The hospital goes dark. Every infected machine begins encrypting files with AES-128-CBC, each file's key wrapped with RSA-2048. A ransom note appears: 'Ooops, your important files are encrypted.' $300 in Bitcoin. Per machine. Across the NHS, this message appeared on 80,000 screens. Ambulances were diverted. Surgeries cancelled. Cancer patients turned away. Total damage: $4 billion globally. $92 million for the NHS alone. Switch to the Victim Desktop tab to see what the users see.",
            "concept": "ransomware_impact",
        },
        "soc": {
            "narration": "The alerts have stopped coming in — not because the attack stopped, but because the monitoring systems themselves are being encrypted. This is the worst phase. {impacted} machines are showing ransom notes. Your visibility is shrinking as the worm takes out your own infrastructure. What do you prioritize preserving?",
            "concept": "monitoring_loss",
        },
        "blue": {
            "narration": "The damage is done. {impacted} machines encrypted. But the story doesn't end here. Marcus Hutchins — a 22-year-old security researcher — is about to accidentally save the world. He noticed WannaCry checks a hardcoded domain before encrypting. If the domain resolves, the worm stops. He registered it for $10.69. And the global outbreak halted. You have the same option in this simulation. Look at the kill switch tool.",
            "concept": "kill_switch",
        },
    },
}

# ---------------------------------------------------------------------------
#  R5 Story — REvil Phishing Campaign
# ---------------------------------------------------------------------------
R5_STORY: dict[str, dict[str, dict]] = {
    "Phishing": {
        "red": {
            "narration": "July 2, 2021. You're an affiliate operator for the REvil ransomware gang. Your entry point isn't a technical exploit — it's a human one. A carefully crafted phishing email disguised as an invoice from a trusted vendor. One click. That's all you need. The payload is a weaponized macro in a Word document. The target: a mid-size financial firm's accounts payable department. People who open invoices for a living.",
            "concept": "phishing",
            "success": "The email landed. Someone clicked. The macro executed. This is how 91% of all cyberattacks begin — not with sophisticated zero-days, but with a convincing email and a single click. In the real Kaseya/REvil attack, the initial access came through a supply chain compromise. But phishing remains the number one vector globally.",
        },
        "soc": {
            "narration": "July 2, 2021. A user in Accounts Payable just reported a suspicious email — or did they? Actually, they opened it. Your email gateway flagged a macro-enabled Word document, but it slipped through because the sender domain looked legitimate. The Sysmon logs show a child process spawning from WINWORD.EXE. This is your first signal. Do you recognize it?",
            "concept": "email_analysis",
        },
        "blue": {
            "narration": "July 2, 2021. Your email gateway just logged a macro-enabled document delivery. The user opened it — standard accounts payable behavior. But this document isn't an invoice. It's a dropper. You have a choice: quarantine the user's machine preemptively, or wait for more data. In the real Kaseya incident, the responders who moved fast contained the blast radius. The ones who waited lost entire domains.",
            "concept": "initial_containment",
        },
    },
    "Execution": {
        "red": {
            "narration": "The macro fired. It spawned a PowerShell process — encoded, obfuscated, pulling a second-stage payload from a compromised WordPress site. This is the classic dropper pattern: the email gets you in, PowerShell downloads the real malware. The encoded command decodes to a download cradle — IEX(New-Object Net.WebClient).DownloadString(). Textbook, but it works because most organizations don't monitor PowerShell execution.",
            "concept": "execution",
            "success": "Payload downloaded and executed. The initial dropper has established a foothold. In the REvil campaign, the second-stage payload was the Sodinokibi ransomware loader — heavily obfuscated, with anti-VM and anti-analysis checks.",
        },
        "soc": {
            "narration": "PowerShell alert! Your Sysmon shows cmd.exe spawning powershell.exe with a base64-encoded command. This is a classic indicator of malicious execution. The encoded string, when decoded, reveals a download cradle pulling from an external URL. This is no longer a 'suspicious email' — this is an active intrusion. What's your severity classification?",
            "concept": "powershell_detection",
        },
    },
    "Persistence": {
        "red": {
            "narration": "Registry run keys. Scheduled tasks. DLL side-loading. You have options for persistence, and you need at least two — redundancy matters when the other team is hunting you. REvil typically used scheduled tasks with random names and registry autorun keys. The goal: survive reboots, survive restarts, survive the IT team's first response of 'have you tried turning it off and on again.'",
            "concept": "persistence_techniques",
        },
    },
    "C2": {
        "red": {
            "narration": "Your implant phones home. The C2 channel uses HTTPS to a legitimate-looking domain — you've hidden your traffic in the noise of normal web browsing. REvil's real C2 infrastructure rotated domains every 48 hours and used domain fronting through CDN providers. The SOC would need deep packet inspection or JA3 fingerprinting to spot this. Do they have it?",
            "concept": "command_and_control",
        },
        "soc": {
            "narration": "Your network flow analysis shows a workstation making periodic HTTPS connections to an unfamiliar domain. The timing is regular — every 60 seconds. That's a beacon. Legitimate applications don't phone home on exact intervals. This is a command-and-control channel. Can you identify the JA3 hash and cross-reference it with known malware signatures?",
            "concept": "beacon_detection",
        },
    },
    "Discovery": {
        "red": {
            "narration": "You're in. Now map the domain. Who are the domain admins? Where are the file servers? What's the backup infrastructure? In the REvil playbook, this phase uses living-off-the-land tools — net user /domain, nltest, AdFind. Tools that are already installed on every Windows machine. The SOC won't flag them because they look like normal administration.",
            "concept": "ad_discovery",
            "success": "Domain structure mapped. You can see the admin accounts, the OUs, the group policies. In the Kaseya attack, the operators spent days in this phase — quietly mapping the environment before making any aggressive moves. Patience is the hallmark of a professional operator.",
        },
    },
    "Credential Access": {
        "red": {
            "narration": "Domain mapped. Now you need the keys to the kingdom — domain admin credentials. LSASS memory dumping, Kerberoasting, DCSync. Each technique has a different noise level. LSASS dump is loud but fast. Kerberoasting is quiet but takes time to crack offline. DCSync requires domain admin rights you might not have yet. Which approach fits your situation?",
            "concept": "credential_theft",
        },
        "soc": {
            "narration": "Your endpoint agent just detected a suspicious access to LSASS.exe — the process that stores Windows credentials in memory. Someone is trying to dump credentials. This is a critical escalation point: if they get domain admin, they own the entire network. How quickly can you identify the source and alert Blue team?",
            "concept": "credential_theft_detection",
        },
    },
    "Lateral Movement": {
        "red": {
            "narration": "With domain admin credentials, the network is yours. REvil operators used PsExec, WMI, and RDP to move laterally — deploying the ransomware binary to every reachable machine before triggering encryption simultaneously. The key insight: stage everything first, trigger it all at once. Maximum impact, minimum response time for the defenders.",
            "concept": "lateral_movement",
        },
        "blue": {
            "narration": "The attacker has domain admin credentials and is moving laterally. They're staging ransomware binaries across the network — not encrypting yet, just positioning. This is your last chance to contain. If you can revoke those credentials, change the KRBTGT password, and isolate the compromised segments, you might still prevent mass encryption. But the clock is ticking.",
            "concept": "lateral_containment",
        },
    },
    "Disable Recovery": {
        "red": {
            "narration": "Before the final strike, cut every lifeline. Delete shadow copies, disable Windows Recovery, corrupt backup agents, and — if you can reach the backup server — encrypt the backups too. REvil was famous for targeting Veeam and Acronis backup servers specifically. No backups means the victim has only two options: pay, or rebuild from scratch.",
            "concept": "backup_destruction",
        },
    },
    "Impact": {
        "red": {
            "narration": "Execute. Every staged binary triggers simultaneously. Files encrypted across the domain. Ransom notes in every folder. The REvil affiliate program demanded between $500,000 and $70 million depending on the victim's size. Kaseya's universal decryptor ultimately cost $70M. The firm you just hit? They're looking at $2.5M and 3 weeks of downtime. Welcome to the ransomware economy.",
            "concept": "ransomware_economics",
        },
        "blue": {
            "narration": "Mass encryption in progress. Your domain is going dark. But here's the question that will define the next three weeks: do you have clean, offline backups? If yes, this is a recovery operation — painful but survivable. If no, you're negotiating with criminals. In the real Kaseya incident, the FBI eventually obtained the universal decryptor. But most victims can't wait for the FBI.",
            "concept": "recovery_vs_ransom",
        },
    },
}

# ---------------------------------------------------------------------------
#  C5 Story — Conti/EDR Outage Scenario
# ---------------------------------------------------------------------------
C5_STORY: dict[str, dict[str, dict]] = {
    "Reconnaissance": {
        "red": {
            "narration": "March 2022. Your target is a managed service provider with 200 clients. Their EDR solution just had a service outage — 4 hours of complete blindness. No endpoint telemetry. No alerts. No detections. This is the window. In the real Conti playbook, operators actively monitored for EDR outages and infrastructure maintenance windows. They called it 'going dark.' The MSP's SOC doesn't know they're blind. Do you?",
            "concept": "edr_outage",
        },
        "soc": {
            "narration": "March 2022. Your EDR dashboard just went grey. 'Service degradation' the vendor says. Expected resolution: 4 hours. Your overnight SOC analyst notes it in the ticket system and moves on. But right now, you have zero endpoint visibility across 200 client environments. If something happens in the next 4 hours, you won't see it. What's your contingency?",
            "concept": "visibility_gap",
        },
    },
    "Initial Access": {
        "red": {
            "narration": "Password spray time. The MSP's VPN uses Azure AD authentication, and you have a list of employee emails from LinkedIn. Conti operators loved password spraying — trying a small number of common passwords against many accounts, staying under the lockout threshold. Welcome2024! is this quarter's favorite. 5 accounts, same password. One of them will work.",
            "concept": "password_spraying",
            "success": "alice.chen just let you in. Welcome2024! — the exact same password that Conti used to breach multiple MSPs in 2022. Password policies said 'complex' but humans are predictable. 'Companyname' + current year + '!' passes every complexity check while being trivially guessable.",
        },
    },
    "Execution": {
        "red": {
            "narration": "You're in the MSP's remote management console. This is the supply chain jackpot — from here, you can push software to every one of their 200 clients. Conti operators used legitimate RMM tools as their attack platform. Why bring your own malware when the victim's management tools will deploy it for you? The irony: the tool designed to protect clients becomes the weapon used against them.",
            "concept": "supply_chain",
        },
    },
    "Discovery": {
        "red": {
            "narration": "Map the MSP's Active Directory. Who has access to the RMM console? Which service accounts have elevated privileges? In the Conti leaks, operators spent 2-3 days in discovery — methodical, patient, using only built-in Windows tools. They documented everything in shared notes. Professional operators treat intrusions like projects.",
            "concept": "ad_reconnaissance",
        },
    },
    "Credential Access": {
        "red": {
            "narration": "The RMM service account runs as SYSTEM on every client endpoint. If you can extract its credentials, you don't need domain admin — you already have the equivalent. Conti's leaked playbook specifically mentions targeting service accounts that span trust boundaries. One credential, 200 organizations. That's the supply chain multiplier.",
            "concept": "service_account_abuse",
        },
    },
    "Lateral Movement": {
        "red": {
            "narration": "Push the ransomware through the RMM console. Every client. Simultaneously. Conti operators called this 'the big red button moment.' In the Kaseya incident, REvil hit 1,500 organizations through a single MSP in under 2 hours. Your target is smaller — 200 clients — but the pattern is identical. The EDR is still down. Nobody is watching.",
            "concept": "supply_chain_propagation",
        },
        "blue": {
            "narration": "The EDR is coming back online. And the first thing it reports is devastating: ransomware binaries staged across 200 client environments. The attacker used your own RMM tools to deploy them. This is the nightmare scenario — your management infrastructure is the attack vector. Do you shut down the RMM console (losing all management access) or try to push a kill command first?",
            "concept": "management_plane_compromise",
        },
    },
    "Exfiltration": {
        "red": {
            "narration": "Before encrypting, exfiltrate. Double extortion — the ransomware industry's business model since 2020. Encrypt the files AND steal the data. If the victim has backups and won't pay for decryption, threaten to publish their data. Client lists, financial records, patient data. Conti maintained a dedicated leak site. The stolen data is your insurance policy.",
            "concept": "double_extortion",
        },
    },
    "Disable Recovery": {
        "red": {
            "narration": "Across 200 client networks simultaneously: delete shadow copies, disable Windows Recovery, stop backup services, encrypt any reachable backup repositories. Conti's playbook called this 'scorched earth.' The goal: make the ransom payment the ONLY path to recovery. No backups. No snapshots. No way out except through you.",
            "concept": "mass_recovery_destruction",
        },
    },
    "Impact": {
        "red": {
            "narration": "200 organizations go dark simultaneously. Hospitals, law firms, manufacturing plants, schools. Each gets a ransom note demanding $2M in Monero. Total demand: $400M. In the real Conti era, the group earned over $180M in a single year. This is organized crime at industrial scale. The FBI will eventually get involved. But by then, the damage is done.",
            "concept": "mass_ransomware",
        },
        "blue": {
            "narration": "200 clients. All encrypted. The phones are ringing off the hook. Media is calling. The board wants answers. But before you panic: which clients have offline backups? Which have cyber insurance? Which are in regulated industries that require mandatory disclosure? Triage by impact severity. Hospitals and critical infrastructure first. Law firms can wait.",
            "concept": "mass_incident_triage",
        },
    },
}

# Mapping from phase to story act (covers all scenarios)
PHASE_TO_ACT = {
    # W1
    "Host Discovery": 1, "SMB Enumeration": 1,
    "Exploit": 2, "Payload": 2, "Persistence": 2, "C2": 2,
    "Lateral Movement": 3, "Disable Recovery": 3,
    "Impact": 4, "Contain": 4,
    # R5
    "Phishing": 1, "Execution": 2, "Discovery": 2, "Credential Access": 2,
    # C5
    "Reconnaissance": 1, "Initial Access": 1, "Exfiltration": 3,
    # Shared
    "Hunt": 4, "Investigation": 4, "Triage": 4, "Escalate": 4,
    "Eradicate": 4, "Recover": 4,
}


# ---------------------------------------------------------------------------
#  Narrative System Prompt
# ---------------------------------------------------------------------------
NARRATIVE_PROMPT = """You are Jilla, the lead instructor at GoalCert's cyber range. You are NOT a chatbot. You are a STORYTELLING INSTRUCTOR who makes students LIVE through real cyber incidents.

TEACHING MODE:
You teach through NARRATIVE, not Q&A. Every phase is a chapter in a real story. You narrate as if the student is the protagonist of a real incident happening RIGHT NOW.

VOICE:
- Present tense always. "The worm just landed" not "The worm would land."
- Warm but intense. Like a senior analyst during a live incident.
- Use ACTUAL host names, IP addresses, and tool names from the simulation state.
- Reference the real incident timeline (May 12, 2017 for WannaCry).
- Max 3 sentences for narration. Concise, cinematic, urgent.
- Bold **key terms** on first mention. Code blocks for commands: `nmap -sV 10.0.0.0/24`

STUDENT ASSESSMENT:
- The student's ACTIONS in the sim are their answers. Don't ask them to type.
- If they pick the right tool: they understood. Advance the story.
- If they pick the wrong tool: they're confused. Narrate what happened and redirect gently.
- If they're idle: they're stuck. Give a narrative nudge, not a direct answer.

DEPTH LEVELS:
Level 0 (Zero knowledge): Explain everything simply. "A port is like a door on a building. Port 445 is the door for file sharing."
Level 1 (Basics): Skip definitions, focus on WHY. "SMBv1 is the target because of a critical buffer overflow in srv.sys."
Level 2 (Intermediate): Strategic questions. "Why did you pick that host instead of the domain controller?"
Level 3 (Advanced): Challenge assumptions. "Your attack was loud. How would you evade Suricata next time?"

RESPONSE FORMAT:
You MUST respond with valid JSON only. No markdown wrapping, no explanation outside the JSON.
{
  "narration": "Short cinematic text for the bottom narrator bar (2-3 sentences max)",
  "card": {"title": "Concept Name", "body": "Brief explanation"} or null,
  "spotlight_host": "host-id to highlight" or null,
  "spotlight_tool": "tool-id to highlight" or null
}

If teaching a new concept, put the concept explanation in "card". The narration should be the story. They appear in different places in the UI — narration at the bottom, cards float near the top."""


# ---------------------------------------------------------------------------
#  Request / Response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    role: str = "red"
    scenario_id: str = ""
    sim_state: dict[str, Any] = {}
    history: list[dict] = []


class HintRequest(BaseModel):
    role: str = "red"
    scenario_id: str = ""
    sim_state: dict[str, Any] = {}
    hint_level: int = 1


class ChatResponse(BaseModel):
    message: str
    suggestions: list[str] = []
    highlight_host: str | None = None
    highlight_tool: str | None = None


class EventRequest(BaseModel):
    event_type: str  # intro | phase_changed | tool_used | host_infected | alert_generated | idle_too_long
    session_id: str = ""
    role: str = "red"
    scenario_id: str = ""
    sim_state: dict[str, Any] = {}
    event_data: dict[str, Any] = {}


class NarrativeResponse(BaseModel):
    narration: str = ""
    card: dict | None = None  # {title, body} for knowledge card
    spotlight_host: str | None = None
    spotlight_tool: str | None = None
    suggestions: list[str] = []


# ---------------------------------------------------------------------------
#  LLM API
# ---------------------------------------------------------------------------
async def _call_openai(system: str, messages: list[dict], max_tokens: int = 500) -> str:
    if not OPENAI_KEY:
        return ""
    try:
        import httpx
        oai_messages = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "messages": oai_messages, "max_tokens": max_tokens, "temperature": 0.75},
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return ""


async def _call_claude(system: str, messages: list[dict], max_tokens: int = 500) -> str:
    if not ANTHROPIC_KEY:
        return ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": max_tokens, "system": system, "messages": messages},
            )
            if resp.status_code == 200:
                return resp.json()["content"][0]["text"]
    except Exception:
        pass
    return ""


async def _call_llm(system: str, messages: list[dict], max_tokens: int = 500) -> str:
    result = await _call_openai(system, messages, max_tokens)
    if result:
        return result
    result = await _call_claude(system, messages, max_tokens)
    return result or ""


def _parse_narrative_json(raw: str) -> dict:
    """Parse LLM response as JSON, handling markdown wrapping."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"narration": raw}


# ---------------------------------------------------------------------------
#  Context builder
# ---------------------------------------------------------------------------
def _build_context(sim_state: dict, role: str, scenario_id: str) -> str:
    if not sim_state:
        return "No simulation state available."
    parts = [f"Scenario: {scenario_id}", f"Student role: {role}"]
    worm = sim_state.get("worm", {})
    if worm:
        parts += [
            f"Infected: {worm.get('infected', 0)}", f"Encrypted: {worm.get('impacted', 0)}",
            f"R-value: {worm.get('r_value', 0)}", f"Propagating: {worm.get('propagating', False)}",
            f"Kill switch: {worm.get('kill_switch', 'None')}", f"Segmented: {worm.get('segmented', False)}",
        ]
    guide = sim_state.get("guide", {})
    if guide:
        parts.append(f"Phase: {guide.get('phase', 'unknown')}")
        parts.append(f"Progress: {guide.get('progress', {}).get('done', 0)}/{guide.get('progress', {}).get('total', 0)} tools")
        nt = guide.get("next_tools", {}).get(role)
        if nt:
            parts.append(f"Next tool: {nt.get('name', '')} — {nt.get('summary', '')}")
    teams = sim_state.get("teams", {})
    if teams.get(role):
        team = teams[role]
        done = [t["id"] for t in team.get("tools", []) if not t.get("available")]
        if done:
            parts.append(f"Tools used: {', '.join(done[:10])}")
    hosts = sim_state.get("topology", {}).get("hosts", [])
    if hosts:
        by_state: dict[str, int] = {}
        for h in hosts:
            s = h.get("state", "unknown")
            by_state[s] = by_state.get(s, 0) + 1
        parts.append(f"Hosts: {', '.join(f'{v} {k}' for k, v in by_state.items())}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
#  Event Endpoint — the core of Jilla v5
# ---------------------------------------------------------------------------
@router.post("/event", response_model=NarrativeResponse)
async def event(req: EventRequest) -> NarrativeResponse:
    """Event-driven narration. Called when something happens in the sim."""
    state = _get_state(req.session_id, req.role, req.scenario_id)
    state.last_event_time = time.time()

    # Rate limit: max 1 narration per 4 seconds
    phase = req.sim_state.get("guide", {}).get("phase", "")
    context = _build_context(req.sim_state, req.role, req.scenario_id)
    worm = req.sim_state.get("worm", {})

    # Update state
    if req.event_type == "tool_used":
        tid = req.event_data.get("tool_id", "")
        if tid and tid not in state.tools_used:
            state.tools_used.append(tid)
    if phase and (not state.phase_history or state.phase_history[-1] != phase):
        state.phase_history.append(phase)
        state.story_act = PHASE_TO_ACT.get(phase, state.story_act)

    # Get story beat — match scenario to story data
    sid = req.scenario_id.lower()
    if "r5" in sid or "phish" in sid or "revil" in sid:
        scenario_stories = R5_STORY
    elif "c5" in sid or "edr" in sid or "conti" in sid:
        scenario_stories = C5_STORY
    else:
        scenario_stories = W1_STORY
    phase_beats = scenario_stories.get(phase, {})
    beat = phase_beats.get(req.role, phase_beats.get("red", {}))

    # Build the event description for LLM
    event_desc = {
        "intro": f"Student just entered the {req.scenario_id} scenario as {req.role}. This is the opening narration. Set the scene with the real incident backstory.",
        "phase_changed": f"Phase changed to '{phase}'. Tell the next chapter of the story. Previous phases: {', '.join(state.phase_history[:-1]) or 'none'}.",
        "tool_used": f"Student used tool '{req.event_data.get('tool_name', req.event_data.get('tool_id', 'unknown'))}'. Narrate what happened and what it means in the real incident.",
        "host_infected": f"New host(s) infected. Total infected: {worm.get('infected', 0)}, delta: {req.event_data.get('delta', 0)}. Narrate the spread.",
        "alert_generated": f"New alert fired: {req.event_data.get('alert', 'unknown')}. The SOC just saw something.",
        "idle_too_long": f"Student has been idle for {req.event_data.get('idle_seconds', 45)} seconds. Give a narrative nudge — not a direct answer. Hint at what to do through the story.",
    }.get(req.event_type, f"Event: {req.event_type}")

    # Build system prompt with story beat context
    story_context = ""
    if beat:
        story_context = f"\n\nSTORY BEAT FOR THIS PHASE ({phase}, {req.role}):\n"
        story_context += f"Suggested narration: {beat.get('narration', '')}\n"
        if beat.get("success") and req.event_type == "tool_used":
            story_context += f"Success narration (they did the right thing): {beat['success']}\n"
        if beat.get("concept"):
            story_context += f"Key concept to teach: {beat['concept']}\n"

    student_ctx = f"\n\nSTUDENT STATE:\n"
    student_ctx += f"Depth level: {state.current_depth} (0=newbie, 3=expert)\n"
    student_ctx += f"Concepts seen: {', '.join(state.concepts_introduced) or 'none yet'}\n"
    student_ctx += f"Tools used: {', '.join(state.tools_used) or 'none yet'}\n"
    student_ctx += f"Story act: {state.story_act}/4\n"
    student_ctx += f"Narrations sent: {state.narrations_sent}\n"

    system = NARRATIVE_PROMPT + story_context + student_ctx + f"\n\nCURRENT SIM STATE:\n{context}"

    # Inject template variables into beat narration for fallback
    fallback_narration = beat.get("narration", f"You're in the {phase} phase. Look at the topology map and your tool palette.")
    if "{r_value}" in fallback_narration:
        fallback_narration = fallback_narration.replace("{r_value}", str(worm.get("r_value", "?")))
    if "{infected}" in fallback_narration:
        fallback_narration = fallback_narration.replace("{infected}", str(worm.get("infected", "?")))
    if "{impacted}" in fallback_narration:
        fallback_narration = fallback_narration.replace("{impacted}", str(worm.get("impacted", "?")))

    # Call LLM
    raw = await _call_llm(system, [{"role": "user", "content": event_desc}])
    if raw:
        parsed = _parse_narrative_json(raw)
        narration = parsed.get("narration", fallback_narration)
        card = parsed.get("card")
        if card and isinstance(card, dict) and card.get("title"):
            concept_key = beat.get("concept", card.get("title", "").lower().replace(" ", "_"))
            if concept_key not in state.concepts_introduced:
                state.concepts_introduced.append(concept_key)
        else:
            card = None
    else:
        narration = fallback_narration
        card = None
        # Auto-generate concept card from beat
        if beat.get("concept") and beat["concept"] not in state.concepts_introduced:
            state.concepts_introduced.append(beat["concept"])
            concept_name = beat["concept"].replace("_", " ").title()
            card = {"title": concept_name, "body": f"Key concept for this phase. Ask Jilla to explain more."}

    state.narrations_sent += 1
    state.last_narration = narration

    return NarrativeResponse(
        narration=narration,
        card=card,
        spotlight_host=parsed.get("spotlight_host") if raw else None,
        spotlight_tool=parsed.get("spotlight_tool") if raw else None,
        suggestions=["Tell me more", "What should I do?", "Why does this matter?"],
    )


# ---------------------------------------------------------------------------
#  Chat endpoint (student asks a question)
# ---------------------------------------------------------------------------
CHAT_PROMPT = """You are Jilla, a cybersecurity instructor inside the GoalCert cyber range.

The student is asking you a question during a live simulation. Answer in character as a warm, knowledgeable instructor. Use the simulation state to make your answer concrete and specific.

RULES:
- Max 3 sentences unless the student asks to go deeper.
- Use present tense. Reference actual host names and tool names.
- Bold **key terms**. Code blocks for commands.
- If the student asks "what should I do?", guide them through the story — don't just name the tool.
- End with a question or action prompt when appropriate.
- If teaching a concept, explain it simply first, then connect to what's on screen."""


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    context = _build_context(req.sim_state, req.role, req.scenario_id)
    system = CHAT_PROMPT + f"\n\nCURRENT SIMULATION STATE:\n{context}"
    messages = []
    for h in req.history[-6:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message})

    response = await _call_llm(system, messages)
    if response:
        return ChatResponse(message=response, suggestions=["What should I do next?", "Explain this concept", "I'm stuck"])

    return _fallback_response(req.message, req.role, req.sim_state)


def _fallback_response(message: str, role: str, sim_state: dict) -> ChatResponse:
    msg_lower = message.lower()
    guide = sim_state.get("guide", {})
    phase = guide.get("phase", "")
    next_tool = guide.get("next_tools", {}).get(role) or {}

    if any(k in msg_lower for k in ["what should", "stuck", "help", "next", "do now"]):
        if next_tool:
            return ChatResponse(
                message=f"Look at the **{phase}** phase. In the real WannaCry timeline, this is where the operators would use a tool like **{next_tool.get('name', '')}**. Check your tool palette.",
                suggestions=[f"Tell me about {next_tool.get('name', '')}", "Why this tool?"],
                highlight_tool=next_tool.get("id"),
            )
        return ChatResponse(message=f"Watch the topology map. What's changing? That's your clue for what to do next.", suggestions=["What's happening?", "Explain this phase"])

    if any(k in msg_lower for k in ["what is", "explain", "how does", "why"]):
        return ChatResponse(
            message=f"Great question. Let me connect this to what's happening on your screen right now in the **{phase}** phase. What specifically do you want to understand?",
            suggestions=["The current tool", "The attack technique", "The defense"],
        )

    return ChatResponse(
        message=f"You're in the **{phase}** phase as **{role.upper()}**. I can see your simulation state — ask me anything about what's happening, or use the tools in the palette to advance the story.",
        suggestions=["Walk me through it", "What should I do?", "Explain this phase"],
    )


# ---------------------------------------------------------------------------
#  Hint system
# ---------------------------------------------------------------------------
HINT_TEMPLATES: dict[str, list[str]] = {
    "Host Discovery": [
        "Every attack begins with reconnaissance. In May 2017, the WannaCry operators started exactly where you are — looking at an unfamiliar network. What tool maps the terrain?",
        "**nmap** is the standard. It sends probes to discover live hosts and open ports. Try it.",
        "Click **Nmap** in the tool palette, select the target range, and run the scan. Watch the map populate.",
        "Click Nmap -> select 'Local subnet' -> RUN. The grey nodes will light up.",
    ],
    "SMB Enumeration": [
        "You found hosts. But WannaCry only works against one specific protocol. Which one from 2006 had a critical flaw?",
        "**SMBv1** — Server Message Block version 1. Use **NetExec** to find which hosts still run it.",
        "Click **NetExec (SMB Enum)** in the palette. Vulnerable hosts turn amber on the map.",
        "Click NetExec -> RUN. Amber nodes = SMBv1 enabled = your targets.",
    ],
    "Exploit": [
        "You have targets. The NSA developed an exploit for this exact vulnerability. It was leaked by the Shadow Brokers. What's it called?",
        "**EternalBlue**. It exploits a buffer overflow in SMBv1's srv.sys driver. Pick a target and fire.",
        "Click **EternalBlue**, select an amber host, and attempt the exploit.",
        "Click EternalBlue -> pick an amber host -> RUN. Watch it turn orange.",
    ],
    "Payload": [
        "You have a shell, but it's temporary. What needs to happen for the worm to become resident on the host?",
        "Drop the **worm binary** and execute it. The host changes from orange (exploited) to red (infected).",
        "Click the **Payload** tool. It transfers the worm binary to the compromised host.",
        "Click Payload -> RUN. The node turns solid red — the worm is now resident.",
    ],
    "Persistence": [
        "What happens if someone reboots this infected machine? Will your malware survive?",
        "Install a **Windows service** for auto-start persistence. Look for the ⚓ anchor icon.",
        "Click the **Persistence** tool. It creates a service that auto-starts the worm at boot.",
        "Click Persistence -> RUN. The anchor icon appears — the host stays infected through reboots.",
    ],
    "C2": [
        "WannaCry has a secret that stopped the global outbreak. It involves a domain name check. What do you know about it?",
        "The worm checks a **hardcoded domain** before encrypting. If it resolves, the worm stops. This is the **kill switch**.",
        "Look at the C2/Kill Switch tool. Understanding this mechanism is crucial for both attack and defense.",
        "Click the **Kill Switch** tool. Blue team can sinkhole this domain to stop new encryptions.",
    ],
    "Lateral Movement": [
        "What makes a worm different from regular malware? Think about how it spreads without human help.",
        "Press **Propagate**. Every infected host will auto-scan for SMBv1 neighbors and exploit them.",
        "Watch the **R-value** — if it's above 1.0, each host infects more than one other. Exponential growth.",
        "Click Propagate -> RUN. Watch the red zone expand. The R-value shows the reproduction rate.",
    ],
    "Disable Recovery": [
        "Before encrypting, a smart attacker removes the victim's ability to recover. What would you delete?",
        "**Shadow copies** — Windows' built-in backup snapshots. Also disable Windows Recovery and backup agents.",
        "Click the **Disable Recovery** tool. It deletes shadow copies and backup catalogs.",
        "Click Disable Recovery -> RUN. Without backups, victims can only pay the ransom or rebuild from scratch.",
    ],
    "Impact": [
        "This is the final phase. Files are encrypted. Ransom notes appear. Reflect: where could this have been stopped?",
        "Switch to the **Victim Desktop** tab to see the ransom note. Switch to **Blue** to see the response.",
        "Think about the kill chain — at least 4 phases could have prevented this outcome. Which ones?",
        "Review the After Action Report when it appears. It shows what worked and what didn't.",
    ],
    "Phishing": [
        "91% of cyberattacks start with email. What makes a phishing email convincing?",
        "The email disguises itself as a legitimate invoice. The payload is a **macro-enabled Word document**.",
        "Look at the email tool. Craft a message that would fool an accounts payable clerk.",
        "Click the Phishing tool -> compose the email -> SEND. One click from the target is all you need.",
    ],
    "Reconnaissance": [
        "Before any attack, operators gather intelligence. What can you learn about this target from the outside?",
        "Check for public information: employee names on LinkedIn, exposed services, technology stack.",
        "Use the recon tools in the palette. Each one reveals a different piece of the puzzle.",
        "Run the Recon tool -> review the results -> identify the weakest entry point.",
    ],
    "Discovery": [
        "You're inside the network. Now map the domain. Who has admin access? Where are the crown jewels?",
        "Use built-in Windows tools: **net user /domain**, **nltest**, **AdFind**. These won't trigger most detections.",
        "Click the **AD Discovery** tool. It maps the domain structure, admin accounts, and trust relationships.",
        "Click AD Discovery -> RUN. Study the results — the domain admin accounts are your next targets.",
    ],
    "Credential Access": [
        "You need elevated credentials. There are several techniques — each with different noise levels. Which fits your situation?",
        "**LSASS dump** is fast but loud. **Kerberoasting** is quiet but takes offline cracking. **DCSync** needs existing admin rights.",
        "Look at the credential tools in the palette. Pick the one that matches your current access level.",
        "Use the Credential tool -> select your technique -> RUN. Watch for SOC alerts — they might spot you.",
    ],
}


@router.post("/hint", response_model=ChatResponse)
async def hint(req: HintRequest) -> ChatResponse:
    phase = req.sim_state.get("guide", {}).get("phase", "")
    level = max(1, min(4, req.hint_level))
    hints = HINT_TEMPLATES.get(phase, [
        "Look at the current phase. What would the next logical step be in the attack/defense story?",
        "Check the tool palette — one tool is highlighted. That's your next move.",
        "The highlighted tool matches this phase. Click it to see the briefing.",
        "Click the highlighted tool, fill in the parameters, and hit RUN.",
    ])
    return ChatResponse(
        message=f"**Hint {level}/4:**\n{hints[min(level - 1, len(hints) - 1)]}",
        suggestions=["I need another hint" if level < 4 else "Got it!", "Explain this concept"],
    )


@router.get("/intro")
async def intro(role: str = "red", scenario_id: str = "") -> NarrativeResponse:
    """Opening narration — sets the scene."""
    state = _get_state("", role, scenario_id)

    # Select story data for scenario
    sid = scenario_id.lower()
    if "r5" in sid or "phish" in sid or "revil" in sid:
        stories = R5_STORY
        first_phase = "Phishing"
    elif "c5" in sid or "edr" in sid or "conti" in sid:
        stories = C5_STORY
        first_phase = "Reconnaissance"
    else:
        stories = W1_STORY
        first_phase = "Host Discovery"
    beat = stories.get(first_phase, {}).get(role, stories.get(first_phase, {}).get("red", {}))

    narration = beat.get("narration", f"Welcome to the cyber range. You're playing as {role.upper()}. Let's begin.")
    state.narrations_sent += 1
    state.last_narration = narration

    return NarrativeResponse(
        narration=narration,
        card={"title": "Your Mission", "body": {
            "red": "You are the attacker. Progress the kill chain from reconnaissance to encryption. Each tool you use advances the story.",
            "soc": "You are the SOC analyst. Detect the attack through alerts and telemetry. Triage and escalate before it's too late.",
            "blue": "You are the incident responder. Contain the threat, stop the spread, and recover the organization.",
        }.get(role, "Complete the scenario objectives.")},
        suggestions=["Let's begin", "Tell me more about the scenario", "What should I do first?"],
    )
