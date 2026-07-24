#!/usr/bin/env bash
# GoalCert live-fire range — one-time setup (macOS / Linux).
# Builds the Kali attacker image, pulls the target images, starts the range, and smoke-tests it.
# Run this ONCE before a demo so everything is cached and starts instantly on the day.
#
#   bash infrastructure/lab-setup.sh           # or:  ./infrastructure/lab-setup.sh
#
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$DIR/docker-compose.lab.yml"
PROJ="gclab"   # MUST match the engine's default project (app/lab/docker_lab.py)
DC="docker compose -f $COMPOSE -p $PROJ"

step() { printf "\n\033[36m[%s] %s\033[0m\n" "$1" "$2"; }

step 1 "Checking Docker..."
if ! docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and retry." >&2; exit 1
fi
echo "  Docker OK"

step 2 "Building the Kali attacker + custom scenario target images (first build pulls ~1GB, then cached)..."
if [ "${1:-}" = "--rebuild" ]; then $DC build --no-cache attacker target-w1 target-r5 target-c5;
else $DC build attacker target-w1 target-r5 target-c5; fi

step 3 "Pulling target images (DVWA web + Samba file server)..."
$DC pull target-web target-files

step 4 "Starting the range..."
$DC up -d
sleep 4

step 5 "Verifying the attacker toolset..."
$DC exec -T attacker sh -lc \
  "command -v nmap && command -v nikto && command -v impacket-secretsdump && command -v ttyd && (command -v nxc || echo 'nxc: optional, not present')"

step 6 "Smoke test — real nmap against the web target..."
$DC exec -T attacker sh -lc "nmap -sV -Pn -T4 target-web | tail -n 15"

DVWA="$($DC port target-web 80 | sed 's/0.0.0.0/localhost/')"
TERM_URL="$($DC port attacker 7681 | sed 's/0.0.0.0/localhost/')"
W1="$($DC port target-w1 80 | sed 's/0.0.0.0/localhost/')"
R5="$($DC port target-r5 80 | sed 's/0.0.0.0/localhost/')"
C5="$($DC port target-c5 80 | sed 's/0.0.0.0/localhost/')"
printf "\n\033[32mRange is up.\033[0m\n"
echo "  DVWA in a browser:  http://$DVWA  (admin / password, then 'Create / Reset Database')"
echo "  Kali shell (ttyd):  http://$TERM_URL"
echo "  W1 Patient Portal:  http://$W1   (hack-lab goal: SQLi auth bypass)"
echo "  R5 SecureMail:      http://$R5   (hack-lab goal: brute + command injection)"
echo "  C5 Admin Console:   http://$C5   (hack-lab goal: password spray + RCE)"
echo "  Stop it later:      docker compose -f infrastructure/docker-compose.lab.yml -p gclab down"
echo "  In GoalCert:        Scenario Library -> a scenario -> the inline Kali shell hacks these apps."
