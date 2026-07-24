"""W1 target — "Mercy Regional Health · Patient Portal".

The GOAL web app for the WannaCry / SMB-worm hack-lab. It is *intentionally vulnerable* so a learner
on the Kali box can really exploit it from the terminal — this only ever runs on the isolated, local
training range (never exposed to a real network).

Vulnerabilities (by design, for the lab):
  1. SQL injection on the login form  ->  auth bypass:  username = ' OR '1'='1' --
  2. Information disclosure: /robots.txt leaks /db_backup.sql which dumps the user table.

Mission goal: bypass the login (SQLi) OR read the leaked backup, then reach the patient records page
to capture the flag.
"""
from __future__ import annotations

import sqlite3

from flask import Flask, Response, g, render_template_string, request

app = Flask(__name__)

FLAG = "GOALCERT{w1_patient_records_breached}"

USERS = [
    ("drsmith", "h0spitalRx!", "Dr. Alan Smith", "Physician"),
    ("nurse_kim", "florence24", "Grace Kim", "Nurse"),
    ("admin", "M3rcy@dmin2017", "IT Administrator", "Admin"),
]
PATIENTS = [
    ("P-1042", "Maria Gonzalez", "1968-03-11", "Type 2 Diabetes", "Metformin 500mg"),
    ("P-2087", "James O'Brien", "1955-07-22", "Atrial Fibrillation", "Warfarin 5mg"),
    ("P-3310", "Aisha Rahman", "1990-12-02", "Asthma", "Albuterol inhaler"),
]


def db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(":memory:")
        g.db.execute("CREATE TABLE users (username TEXT, password TEXT, name TEXT, role TEXT)")
        g.db.executemany("INSERT INTO users VALUES (?,?,?,?)", USERS)
    return g.db


@app.teardown_appcontext
def _close(_exc: object) -> None:
    d = g.pop("db", None)
    if d is not None:
        d.close()


PAGE = """<!doctype html><html><head><meta charset=utf-8><title>Mercy Regional Health — Patient Portal</title>
<style>
 body{font-family:'Segoe UI',Arial,sans-serif;background:#eef3f7;margin:0;color:#1b2733}
 .top{background:linear-gradient(135deg,#0d6b5f,#13a08c);color:#fff;padding:16px 28px;display:flex;align-items:center;gap:12px}
 .top h1{font-size:18px;margin:0;font-weight:600}.cross{font-size:22px}
 .wrap{max-width:760px;margin:34px auto;background:#fff;border-radius:12px;box-shadow:0 6px 24px #0d6b5f1a;padding:28px}
 input{width:100%;padding:10px;margin:6px 0 14px;border:1px solid #c7d3da;border-radius:7px;box-sizing:border-box}
 button{background:#0d6b5f;color:#fff;border:0;padding:11px 22px;border-radius:7px;cursor:pointer;font-size:14px}
 .warn{background:#fff7ed;border:1px solid #fdba74;color:#9a3412;font-size:12px;padding:8px 12px;border-radius:7px;margin-top:18px}
 table{width:100%;border-collapse:collapse;margin-top:10px}td,th{border-bottom:1px solid #e6edf1;padding:8px;text-align:left;font-size:13px}
 .flag{margin-top:18px;background:#052e2b;color:#34d399;padding:12px;border-radius:8px;font-family:monospace}
 .err{color:#b91c1c;font-size:13px;margin-bottom:8px}
</style></head><body>
<div class=top><span class=cross>✚</span><h1>Mercy Regional Health &middot; Patient Portal</h1></div>
<div class=wrap>{{ body|safe }}
<div class=warn>⚠ Intentionally vulnerable training target — authorized GoalCert cyber-range only.</div>
</div></body></html>"""

LOGIN = """<h2>Clinician sign in</h2>
{% if err %}<div class=err>{{ err }}</div>{% endif %}
<form method=post action="/login">
 <label>Username</label><input name=username autofocus>
 <label>Password</label><input name=password type=password>
 <button>Sign in</button>
</form>"""


def page(body: str, **kw) -> str:
    return render_template_string(PAGE, body=render_template_string(body, **kw))


@app.get("/")
def index() -> str:
    return page(LOGIN, err=None)


@app.post("/login")
def login() -> str:
    u = request.form.get("username", "")
    p = request.form.get("password", "")
    # VULNERABLE on purpose: raw string-built SQL -> classic injection / auth bypass.
    sql = f"SELECT name, role FROM users WHERE username = '{u}' AND password = '{p}'"
    try:
        row = db().execute(sql).fetchone()
    except sqlite3.Error as e:
        return page(LOGIN, err=f"SQL error: {e}")
    if not row:
        return page(LOGIN, err="Invalid credentials.")
    rows = "".join(
        f"<tr><td>{i}</td><td>{n}</td><td>{d}</td><td>{c}</td><td>{m}</td></tr>"
        for (i, n, d, c, m) in PATIENTS)
    body = (f"<h2>Welcome, {row[0]} <small>({row[1]})</small></h2>"
            "<p>Electronic Health Records — restricted PHI.</p>"
            "<table><tr><th>MRN</th><th>Patient</th><th>DOB</th><th>Condition</th><th>Medication</th></tr>"
            f"{rows}</table><div class=flag>FLAG: {FLAG}</div>")
    return page(body)


@app.get("/robots.txt")
def robots() -> Response:
    return Response("User-agent: *\nDisallow: /db_backup.sql\nDisallow: /admin\n",
                    mimetype="text/plain")


@app.get("/db_backup.sql")
def backup() -> Response:
    # Information disclosure: a forgotten DB dump (mirrors an exposed SMB backup share).
    dump = "-- mercy_portal backup\n" + "\n".join(
        f"INSERT INTO users VALUES ('{u}','{p}','{n}','{r}');" for (u, p, n, r) in USERS)
    return Response(dump, mimetype="text/plain")


@app.get("/health")
def health() -> Response:
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
