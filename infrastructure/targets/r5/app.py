"""R5 target — "MediumCorp Financial · SecureMail" webmail.

The GOAL web app for the phishing -> human-operated-ransomware hack-lab. Intentionally vulnerable so
a learner on the Kali box can really exploit it. Isolated training range only.

Vulnerabilities (by design, for the lab):
  1. Weak credentials on the webmail login  ->  brute force (hydra):  jdoe / Password1
  2. Authenticated OS command injection in the "mail diagnostics" tool:
        host = 127.0.0.1; cat /flag

Mission goal: brute the webmail login, then use the diagnostics command injection to read /flag
(modelling: phish a user -> get a foothold -> run hands-on-keyboard commands).
"""
from __future__ import annotations

import os
import subprocess

from flask import Flask, Response, redirect, render_template_string, request, session

app = Flask(__name__)
app.secret_key = "securemail-demo-key"

with open("/flag", "w") as fh:
    fh.write("GOALCERT{r5_foothold_command_execution}\n")

# Weak, sprayable mailbox creds (the brute-force target).
MAILBOXES = {"jdoe": "Password1", "afinance": "Summer2024", "mhelp": "welcome1"}

PAGE = """<!doctype html><html><head><meta charset=utf-8><title>SecureMail — MediumCorp Financial</title>
<style>
 body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f1fb;margin:0;color:#241a33}
 .top{background:linear-gradient(135deg,#5b21b6,#7c3aed);color:#fff;padding:15px 26px;display:flex;align-items:center;gap:10px}
 .top h1{font-size:17px;margin:0;font-weight:600}
 .wrap{max-width:780px;margin:32px auto;background:#fff;border-radius:12px;box-shadow:0 6px 24px #5b21b61a;padding:26px}
 input{width:100%;padding:10px;margin:6px 0 13px;border:1px solid #d6cdea;border-radius:7px;box-sizing:border-box}
 button{background:#6d28d9;color:#fff;border:0;padding:11px 22px;border-radius:7px;cursor:pointer;font-size:14px}
 .warn{background:#fff7ed;border:1px solid #fdba74;color:#9a3412;font-size:12px;padding:8px 12px;border-radius:7px;margin-top:18px}
 .mail{border:1px solid #ece6f7;border-radius:8px;padding:12px;margin:10px 0;font-size:13px}
 .from{color:#6d28d9;font-weight:600}.err{color:#b91c1c;font-size:13px;margin-bottom:8px}
 pre{background:#1e1130;color:#c4b5fd;padding:12px;border-radius:8px;overflow:auto;font-size:12.5px}
 a.tool{display:inline-block;margin-top:10px;color:#6d28d9}
</style></head><body>
<div class=top><span>✉</span><h1>SecureMail &middot; MediumCorp Financial</h1></div>
<div class=wrap>{{ body|safe }}
<div class=warn>⚠ Intentionally vulnerable training target — authorized GoalCert cyber-range only.</div>
</div></body></html>"""

LOGIN = """<h2>Sign in to SecureMail</h2>
{% if err %}<div class=err>{{ err }}</div>{% endif %}
<form method=post action="/login">
 <label>Email / username</label><input name=username autofocus>
 <label>Password</label><input name=password type=password>
 <button>Sign in</button>
</form>"""


def page(body: str, **kw) -> str:
    return render_template_string(PAGE, body=render_template_string(body, **kw))


@app.get("/")
def index() -> str:
    if session.get("user"):
        return redirect("/inbox")
    return page(LOGIN, err=None)


@app.post("/login")
def login():
    u = request.form.get("username", "").split("@")[0]
    p = request.form.get("password", "")
    if MAILBOXES.get(u) == p:
        session["user"] = u
        return redirect("/inbox")
    return page(LOGIN, err="Authentication failed."), 401


@app.get("/inbox")
def inbox():
    u = session.get("user")
    if not u:
        return redirect("/")
    body = (f"<h2>{u}@mediumcorp.com — Inbox</h2>"
            "<div class=mail><span class=from>it-support@medıumcorp.com</span><br>"
            "<b>ACTION REQUIRED: Q3 Payroll Adjustment.xlsm</b><br>"
            "Please enable macros and review the attached payroll file before EOD.</div>"
            "<div class=mail><span class=from>security@mediumcorp.com</span><br>"
            "<b>Mail delivery diagnostics</b><br>"
            "If attachments fail to scan, run a connectivity check from the diagnostics tool.</div>"
            "<a class=tool href='/diagnostics'>→ Open mail diagnostics tool</a>")
    return page(body)


@app.get("/diagnostics")
def diagnostics():
    u = session.get("user")
    if not u:
        return redirect("/")
    host = request.args.get("host", "")
    out = ""
    if host:
        # VULNERABLE on purpose: unsanitised shell concatenation -> OS command injection.
        cmd = "ping -c 1 " + host
        try:
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                 timeout=8).stdout or "(no output)"
        except Exception as e:  # noqa: BLE001
            out = f"error: {e}"
    body = ("<h2>Mail server diagnostics</h2>"
            "<p>Check connectivity to a mail relay host.</p>"
            "<form method=get action='/diagnostics'>"
            "<label>Relay host</label><input name=host placeholder='mx1.mediumcorp.com'>"
            "<button>Run check</button></form>"
            + (f"<pre>$ ping -c 1 {host}\n{out}</pre>" if host else ""))
    return page(body)


@app.get("/health")
def health() -> Response:
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
