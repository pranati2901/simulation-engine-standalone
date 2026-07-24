"""Live-fire lab integration tests — tool registry, action→tool mapping, and the session hook.

These run WITHOUT Docker: a FakeLab backend stands in for the real Kali range so we can verify the
plumbing (queue → run → attach result → detection) deterministically. The off-by-default test
guarantees the existing simulation is untouched unless a host arms live-fire.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.lab import live_fire as lf
from app.lab import tools as tool_registry
from app.lab.base import CommandResult, LabBackend, LabStatus, LabTarget
from app.live import missions as mp
from app.live import red_playbook as rp
from app.live.manager import manager
from app.main import app


# --------------------------------------------------------------------------- #
#  A no-Docker lab backend that returns canned, deterministic output
# --------------------------------------------------------------------------- #
class FakeLab(LabBackend):
    name = "fake"

    def __init__(self) -> None:
        self._targets = [
            LabTarget("target-web", "Web", "target-web", "linux", "web", ("http",), "c-web"),
            LabTarget("target-files", "Files", "target-files", "linux", "fileserver", ("smb",), "c-files"),
        ]
        self.attacker_calls: list[str] = []

    def status(self) -> LabStatus:
        return LabStatus(self.name, True, True, True, list(self._targets))

    def up(self) -> CommandResult:
        return CommandResult(True)

    def down(self) -> CommandResult:
        return CommandResult(True)

    def targets(self) -> list[LabTarget]:
        return list(self._targets)

    def run_in_attacker(self, command: str, timeout: int = 120) -> CommandResult:
        self.attacker_calls.append(command)
        return CommandResult(True, 0, f"[fake] {command}\n80/tcp open http", command=command)

    def run_in_target(self, target_id: str, command: str, timeout: int = 30) -> CommandResult:
        return CommandResult(True, 0, "5", command=command)  # 5 log lines -> detected


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _red_session():
    scenario = mp.scenario_for("identity_assessment")
    sess, host = manager.create(scenario, scenario.recommended_topology, "H")
    sess.claim_role(host.id, "red")
    sess.start("nation_state")
    return sess, host.id


def _drive(sess, host, action_ids):
    for aid in action_ids:
        ok, reason = sess.execute_red_action(host, aid, None)
        assert ok, f"{aid}: {reason}"


def _action_event(sess, action_id):
    for ev in reversed(sess.events):
        if ev["kind"] == "action" and ev["data"].get("action_id") == action_id:
            return ev
    return None


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- #
#  Tool registry
# --------------------------------------------------------------------------- #
def test_registry_has_one_integrated_per_function_plus_placeholders():
    integrated = tool_registry.integrated_tools()
    # at least nmap / netexec / nikto / impacket / detection
    assert len(integrated) >= 4
    statuses = {t.status for t in tool_registry.TOOLS}
    assert {"integrated", "planned", "provided"} <= statuses     # room to grow + reserved slot
    pub = tool_registry.registry_public()
    assert pub["counts"]["provided"] >= 1                        # the reserved 'we provide' slot
    assert pub["counts"]["planned"] >= 1


def test_integrated_tools_back_real_red_actions():
    for t in tool_registry.integrated_tools():
        for action_id in t.backs:
            if action_id != "*":
                assert action_id in rp.ACTIONS_BY_ID, action_id


# --------------------------------------------------------------------------- #
#  Live-fire mapping + executor (FakeLab)
# --------------------------------------------------------------------------- #
def test_fire_specs_reference_real_actions():
    # A FireSpec backs either a free-form red_playbook action OR a sim-scenario real tool.
    # web.* / exfil.* are the lab's web-exploitation + SMB file-exfil families used by the sim scenarios.
    for f in lf.FIRE_SPECS:
        assert (f.action_id in rp.ACTIONS_BY_ID
                or f.action_id.split(".")[0] in {"web", "exfil"}), f.action_id


def test_run_job_linux_action_is_real_and_detected():
    res = lf.run_job(FakeLab(), "recon.fingerprint")
    assert res["status"] == "done" and res["success"] is True
    assert "nmap" in res["command"] and res["tool"] == "nmap"
    assert res["detected"] is True and res["detection_source"] == "target-logs"


def test_run_job_windows_action_is_gated_on_docker_lab():
    """On a lab with no 'dc' target (Docker), AD actions are gated, not executed."""
    fake = FakeLab()
    res = lf.run_job(fake, "cred.dcsync")
    assert res["status"] == "unavailable" and res["success"] is False
    assert "Windows" in res["output"]
    assert fake.attacker_calls == []          # nothing actually ran on the Docker range


def test_run_job_unmapped_action_is_skipped():
    assert lf.run_job(FakeLab(), "plan.review")["status"] == "skipped"


# --------------------------------------------------------------------------- #
#  Phase 2 — Windows AD lab (FakeAdLab, no real VM)
# --------------------------------------------------------------------------- #
class FakeAdLab(LabBackend):
    name = "windows_ad"

    def __init__(self) -> None:
        self._targets = [LabTarget("dc01", "DC", "10.0.0.10", "windows", "dc",
                                   ("smb", "ldap", "kerberos", "winrm"), "dc01")]
        self.attacker_calls: list[str] = []

    def status(self) -> LabStatus:
        return LabStatus(self.name, True, True, True, list(self._targets))

    def up(self) -> CommandResult: return CommandResult(True)
    def down(self) -> CommandResult: return CommandResult(True)
    def targets(self) -> list[LabTarget]: return list(self._targets)

    def credentials(self) -> dict:
        return {"domain": "GOALCERT", "user": "vagrant", "password": "vagrant"}

    def run_in_attacker(self, command: str, timeout: int = 120) -> CommandResult:
        self.attacker_calls.append(command)
        return CommandResult(True, 0, "Administrator:500:aad3b...:31d6cfe0d16ae931b73c59d7e0c089c0:::\n"
                                       "krbtgt:502:aad3b...:0e1f...:::", command=command)

    def run_in_target(self, target_id: str, command: str, timeout: int = 30) -> CommandResult:
        return CommandResult(True, 0, "3", command=command)  # 3 matching DC events -> detected


def test_ad_action_executes_with_domain_creds_and_detects():
    fake = FakeAdLab()
    res = lf.run_job(fake, "cred.dcsync")
    assert res["status"] == "done" and res["success"] is True
    # real impacket command, rendered with the lab's harvested domain credentials
    assert res["command"] == "impacket-secretsdump -just-dc GOALCERT/vagrant:vagrant@10.0.0.10"
    assert fake.attacker_calls == [res["command"]]
    assert "krbtgt" in res["output"]                       # real-looking secrets dumped
    assert res["detected"] is True and res["detection_source"] == "windows-event-log"


def test_docker_action_gated_on_ad_lab():
    """The web action has no target on the AD lab -> gated, not executed."""
    fake = FakeAdLab()
    res = lf.run_job(fake, "recon.fingerprint")    # needs a 'web' target
    assert res["status"] == "unavailable" and res["success"] is False
    assert fake.attacker_calls == []


def test_manager_selects_windows_ad_backend(monkeypatch):
    from app.lab import manager as lab_manager
    from app.lab.windows_ad_lab import WindowsAdLab
    monkeypatch.setattr("app.core.settings.settings.lab_backend", "windows_ad")
    lab_manager.get_lab.cache_clear()
    try:
        lab = lab_manager.get_lab()
        assert isinstance(lab, WindowsAdLab)
        assert any(t.role == "dc" for t in lab.targets())
        assert lab.credentials()["domain"]              # creds wired from settings
    finally:
        lab_manager.get_lab.cache_clear()               # don't leak the AD backend to other tests


# --------------------------------------------------------------------------- #
#  Session hook — additive, OFF by default
# --------------------------------------------------------------------------- #
def test_off_by_default_does_not_touch_the_simulation():
    sess, host = _red_session()
    _drive(sess, host, ["plan.review", "recon.osint", "recon.fingerprint"])
    assert sess.live_fire is False
    assert sess.pending_fire == []
    ev = _action_event(sess, "recon.fingerprint")
    assert ev is not None and "live_fire" not in ev["data"]


def test_armed_queues_a_real_job_with_a_pending_badge():
    sess, host = _red_session()
    sess.arm_live_fire(True)
    _drive(sess, host, ["plan.review", "recon.osint", "recon.fingerprint"])
    assert len(sess.pending_fire) == 1
    ev = _action_event(sess, "recon.fingerprint")
    assert ev["data"]["live_fire"]["status"] == "queued"
    assert ev["data"]["live_fire"]["tool"] == "nmap"


def test_run_live_fire_executes_and_attaches_result(monkeypatch):
    monkeypatch.setattr("app.lab.manager.get_lab", FakeLab)
    sess, host = _red_session()
    sess.arm_live_fire(True)
    _drive(sess, host, ["plan.review", "recon.osint", "recon.fingerprint"])
    assert sess.pending_fire

    asyncio.run(manager.run_live_fire(sess.id))

    assert sess.pending_fire == []                # drained
    lf_data = _action_event(sess, "recon.fingerprint")["data"]["live_fire"]
    assert lf_data["status"] == "done" and lf_data["success"] is True
    assert "nmap" in lf_data["command"]
    assert lf_data["detected"] is True


# --------------------------------------------------------------------------- #
#  API
# --------------------------------------------------------------------------- #
def test_lab_status_endpoint(client):
    s = client.get("/api/lab/status").json()
    assert s["backend"] == "docker"
    assert "targets" in s and isinstance(s["targets"], list)


def test_lab_tools_endpoint(client):
    j = client.get("/api/lab/tools").json()
    assert j["counts"]["integrated"] >= 4
    assert j["counts"]["provided"] >= 1
    ids = {t["id"] for t in j["tools"]}
    assert {"nmap", "netexec", "impacket"} <= ids


def test_lab_live_fire_map_endpoint(client):
    rows = client.get("/api/lab/live-fire").json()
    assert any(r["tool"] == "nmap" and r["available"] for r in rows)
    assert any(r["available"] is False for r in rows)   # AD actions gated to Phase 2


# --------------------------------------------------------------------------- #
#  Phase 3 — per-session isolated lab pool (multi-tenant)
# --------------------------------------------------------------------------- #
def test_session_lab_pool_isolates_and_caps(monkeypatch):
    from app.lab import pool as poolmod
    built: dict[str, object] = {}

    class FakeDC:
        def __init__(self, compose_file, project="gclab"):
            self.compose_file, self.project = compose_file, project
            self.upped = self.downed = False
            built[project] = self

        def up(self): self.upped = True; return CommandResult(True)
        def down(self): self.downed = True; return CommandResult(True)

    monkeypatch.setattr(poolmod, "DockerComposeLab", FakeDC)
    p = poolmod.SessionLabPool("compose.yml", max_concurrent=2)

    lab_a, err = p.provision("aaa")
    assert err == "" and lab_a.upped and lab_a.project == "gc-aaa"
    assert p.get("aaa") is lab_a

    lab_b, _ = p.provision("bbb")                       # second session -> its OWN isolated project
    assert lab_b.project == "gc-bbb" and lab_b is not lab_a

    lab_c, err_c = p.provision("ccc")                   # over capacity
    assert lab_c is None and "capacity" in err_c

    assert p.teardown("aaa") and built["gc-aaa"].downed  # teardown frees a slot
    lab_c2, err_c2 = p.provision("ccc")
    assert lab_c2 is not None and err_c2 == ""


def test_session_lab_endpoints(client, monkeypatch):
    class FakeLab2:
        def status(self):
            return LabStatus("docker", True, True, True, [], terminal_url="http://localhost:9999")

    class FakePool:
        def __init__(self): self.up_calls, self.down_calls = [], []
        def provision(self, sid): self.up_calls.append(sid); return FakeLab2(), ""
        def teardown(self, sid): self.down_calls.append(sid); return True
        def get(self, sid): return None
        def active(self): return []

    fake = FakePool()
    monkeypatch.setattr("app.api.lab.get_pool", lambda: fake)

    up = client.post("/api/lab/session/sess123/up").json()
    assert up["ok"] is True and up["terminal_url"] == "http://localhost:9999"
    assert fake.up_calls == ["sess123"]

    down = client.post("/api/lab/session/sess123/down").json()
    assert down["ok"] is True and fake.down_calls == ["sess123"]
