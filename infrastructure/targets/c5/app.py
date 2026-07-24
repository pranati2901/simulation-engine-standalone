"""C5 target — "GlobalTech Corp · IT Admin Console".

The GOAL web app for the EDR-outage hack-lab. Intentionally vulnerable so a learner on the Kali box
can really exploit it. Isolated training range only.

Vulnerabilities (by design, for the lab):
  1. Password spray: many admins share one weak password  ->  Welcome2024!
        users: alice.chen / bobby.k / carol.diaz / svc_backup / helpdesk
  2. Authenticated "remote runbook" executes commands  ->  models PsExec-style remote exec while the
     EDR is blind:   cmd = id ; cat /flag

Mission goal: password-spray a valid admin, then use the remote runbook to execute commands and read
/flag — exactly what an attacker does during an EDR outage (no endpoint agent to stop them).
"""
from __future__ import annotations

import subprocess

from flask import Flask, Response, redirect, render_template_string, request, session

app = Flask(__name__)
app.secret_key = "globaltech-admin-key"

with open("/flag", "w") as fh:
    fh.write("GOALCERT{c5_domain_admin_during_edr_blindness}\n")

SPRAY_PASSWORD = "Welcome2024!"
ADMINS = {u: SPRAY_PASSWORD for u in
          ("alice.chen", "bobby.k", "carol.diaz", "svc_backup", "helpdesk")}

PAGE = """<!doctype html><html><head><meta charset=utf-8><title>GlobalTech — IT Admin Console</title>
<style>
 body{font-family:'Segoe UI',Arial,sans-serif;background:#0b1220;margin:0;color:#dbe4f0}
 .top{background:#111c30;border-bottom:1px solid #1f3a5f;color:#7dd3fc;padding:14px 26px;display:flex;align-items:center;gap:10px}
 .top h1{font-size:17px;margin:0;font-weight:600;color:#e2e8f0}
 .pill{margin-left:auto;font-size:11px;color:#fca5a5;border:1px solid #7f1d1d;border-radius:20px;padding:3px 10px}
 .wrap{max-width:800px;margin:30px auto;background:#0f1b2e;border:1px solid #1f3a5f;border-radius:12px;padding:26px}
 input{width:100%;padding:10px;margin:6px 0 13px;border:1px solid #24426b;border-radius:7px;box-sizing:border-box;background:#0b1626;color:#e2e8f0}
 button{background:#0284c7;color:#fff;border:0;padding:11px 22px;border-radius:7px;cursor:pointer;font-size:14px}
 .warn{background:#1c1207;border:1px solid #92400e;color:#fbbf24;font-size:12px;padding:8px 12px;border-radius:7px;margin-top:18px}
 pre{background:#060c16;color:#4ade80;padding:12px;border-radius:8px;overflow:auto;font-size:12.5px;border:1px solid #14324f}
 .err{color:#fca5a5;font-size:13px;margin-bottom:8px}.muted{color:#7f93ad;font-size:12px}
</style></head><body>
<div class=top><span>🛠</span><h1>GlobalTech &middot; IT Admin Console</h1><span class=pill>EDR: OFFLINE</span></div>
<div class=wrap>{{ body|safe }}
<div class=warn>⚠ Intentionally vulnerable training target — authorized GoalCert cyber-range only.</div>
</div></body></html>"""

LOGIN = """<h2>Administrator sign in</h2>
<p class=muted>Endpoint protection is undergoing a vendor update. Console access is unrestricted.</p>
{% if err %}<div class=err>{{ err }}</div>{% endif %}
<form method=post action="/login">
 <label>Corporate ID</label><input name=username autofocus>
 <label>Password</label><input name=password type=password>
 <button>Sign in</button>
</form>"""


def page(body: str, **kw) -> str:
    return render_template_string(PAGE, body=render_template_string(body, **kw))


@app.get("/")
def index():
    if session.get("user"):
        return redirect("/console")
    return page(LOGIN, err=None)


@app.post("/login")
def login():
    u = request.form.get("username", "")
    p = request.form.get("password", "")
    if ADMINS.get(u) == p:
        session["user"] = u
        return redirect("/console")
    return page(LOGIN, err="Access denied."), 401


@app.get("/console")
def console():
    u = session.get("user")
    if not u:
        return redirect("/")
    cmd = request.args.get("cmd", "")
    out = ""
    if cmd:
        # VULNERABLE on purpose: runs operator-supplied commands (remote runbook) -> RCE.
        try:
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                 timeout=8).stdout or "(no output)"
        except Exception as e:  # noqa: BLE001
            out = f"error: {e}"
    body = (f"<h2>Remote runbook — signed in as {u}</h2>"
            "<p class=muted>Push a command to managed endpoints (agent-bypass mode while EDR is offline).</p>"
            "<form method=get action='/console'>"
            "<label>Command</label><input name=cmd placeholder='hostname'>"
            "<button>Execute</button></form>"
            + (f"<pre>PS&gt; {cmd}\n{out}</pre>" if cmd else ""))
    return page(body)


@app.get("/health")
def health() -> Response:
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
