#!/usr/bin/env python3
"""Authenticate to DVWA headlessly and print a cookie string for sqlmap / curl / hydra.

Usage:  dvwa-auth http://target-web   ->   PHPSESSID=<id>; security=low

Idempotent and boot-tolerant: ensures the DB exists (setup.php), logs in as admin/password, and
selects security=low. DVWA needs a live session + the `security` cookie before its vuln pages are
exploitable, so every real DVWA FireSpec runs this first and passes the result as --cookie.
"""
import re
import sys
import time

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://target-web").rstrip("/")
USER, PWD = "admin", "password"


def _token(html: str) -> str:
    m = (re.search(r"user_token'\s*value='([0-9a-f]+)'", html)
         or re.search(r'name=["\']user_token["\']\s+value=["\']([0-9a-f]+)["\']', html))
    return m.group(1) if m else ""


def main() -> int:
    s = requests.Session()
    last = "no attempt"
    for _ in range(30):                      # DVWA + its mysql can take a while on first boot
        try:
            # 1) make sure the DB exists (first-run setup); needs a session token
            r = s.get(f"{BASE}/setup.php", timeout=5)
            t = _token(r.text)
            if t:
                s.post(f"{BASE}/setup.php",
                       data={"create_db": "Create / Reset Database", "user_token": t}, timeout=20)
            # 2) log in
            r = s.get(f"{BASE}/login.php", timeout=5)
            s.post(f"{BASE}/login.php",
                   data={"username": USER, "password": PWD, "Login": "Login", "user_token": _token(r.text)},
                   timeout=10, allow_redirects=True)
            # 3) confirm
            r = s.get(f"{BASE}/index.php", timeout=5)
            sid = s.cookies.get("PHPSESSID")
            if sid and "login.php" not in r.url:
                print(f"PHPSESSID={sid}; security=low")
                return 0
            last = "not logged in yet"
        except Exception as exc:             # noqa: BLE001 — boot races are expected; retry
            last = str(exc)
        time.sleep(2)
    sys.stderr.write(f"dvwa-auth: giving up — {last}\n")
    print(f"PHPSESSID={s.cookies.get('PHPSESSID') or ''}; security=low")   # best-effort
    return 1


if __name__ == "__main__":
    sys.exit(main())
