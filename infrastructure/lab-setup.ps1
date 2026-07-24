# GoalCert live-fire range — one-time setup (Windows / PowerShell).
# Builds the Kali attacker image, pulls the target images, starts the range, and smoke-tests it.
# Run this ONCE before a demo so everything is cached and starts instantly on the day.
#
#   pwsh infrastructure/lab-setup.ps1
#
param([switch]$Rebuild)

$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot "docker-compose.lab.yml"
$proj = "gclab"   # MUST match the engine's default project (app/lab/docker_lab.py)

function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }

Step 1 "Checking Docker..."
docker version --format '{{.Server.Version}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start Docker Desktop and retry." }
Write-Host "  Docker OK" -ForegroundColor Green

Step 2 "Building the Kali attacker + custom scenario target images (first build pulls ~1GB, then cached)..."
if ($Rebuild) { docker compose -f $compose -p $proj build --no-cache attacker target-w1 target-r5 target-c5 }
else { docker compose -f $compose -p $proj build attacker target-w1 target-r5 target-c5 }

Step 3 "Pulling target images (DVWA web + Samba file server)..."
docker compose -f $compose -p $proj pull target-web target-files

Step 4 "Starting the range..."
docker compose -f $compose -p $proj up -d
Start-Sleep -Seconds 4

Step 5 "Verifying the attacker toolset..."
docker compose -f $compose -p $proj exec -T attacker sh -lc "command -v nmap && command -v nikto && command -v impacket-secretsdump && command -v ttyd && (command -v nxc || echo 'nxc: optional, not present')"

Step 6 "Smoke test — real nmap against the web target..."
docker compose -f $compose -p $proj exec -T attacker sh -lc "nmap -sV -Pn -T4 target-web | tail -n 15"

$dvwa = (docker compose -f $compose -p $proj port target-web 80) -replace '0.0.0.0','localhost'
$term = (docker compose -f $compose -p $proj port attacker 7681) -replace '0.0.0.0','localhost'
$w1 = (docker compose -f $compose -p $proj port target-w1 80) -replace '0.0.0.0','localhost'
$r5 = (docker compose -f $compose -p $proj port target-r5 80) -replace '0.0.0.0','localhost'
$c5 = (docker compose -f $compose -p $proj port target-c5 80) -replace '0.0.0.0','localhost'
Write-Host "`nRange is up." -ForegroundColor Green
Write-Host "  DVWA in a browser:   http://$dvwa  (admin / password, then 'Create / Reset Database')"
Write-Host "  Kali shell (ttyd):   http://$term"
Write-Host "  W1 Patient Portal:   http://$w1   (hack-lab goal: SQLi auth bypass)"
Write-Host "  R5 SecureMail:       http://$r5   (hack-lab goal: brute + command injection)"
Write-Host "  C5 Admin Console:    http://$c5   (hack-lab goal: password spray + RCE)"
Write-Host "  Stop it later:       docker compose -f infrastructure/docker-compose.lab.yml -p gclab down"
Write-Host "  In GoalCert:         Scenario Library -> a scenario -> the inline Kali shell hacks these apps."
