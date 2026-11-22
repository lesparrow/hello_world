import io
import json
import subprocess
import sys
from pathlib import Path

from statpfe.rpc.server import Engine, serve

ENGINE_DIR = Path(__file__).resolve().parents[1]


def call(engine, method, params=None, req_id=1):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return engine.handle(json.dumps(msg))


def test_full_lifecycle(tmp_path, study):
    e = Engine()
    path = str(tmp_path / "e.statpfe")
    r = call(e, "project.create", {"path": path, "study": study})
    assert r["result"]["study"]["title"] == study["title"]
    assert r["result"]["dirty"] is False
    r = call(e, "project.update_study", {"changes": {"objectives": "X"}})
    assert r["result"]["dirty"] is True
    r = call(e, "project.close", {})
    assert r["error"]["data"]["kind"] == "modifications_non_enregistrees"
    assert call(e, "project.save")["result"]["dirty"] is False
    assert call(e, "project.close")["result"] is None
    assert call(e, "project.current")["result"] is None
    recent = call(e, "app.recent_projects")["result"]
    assert recent[0]["path"].endswith("e.statpfe") and recent[0]["exists"]
    r = call(e, "project.open", {"path": path})
    assert r["result"]["study"]["objectives"] == "X"


def test_only_one_project_at_a_time(tmp_path, study):
    e = Engine()
    call(e, "project.create", {"path": str(tmp_path / "a.statpfe"), "study": study})
    r = call(e, "project.create", {"path": str(tmp_path / "b.statpfe"), "study": study})
    assert r["error"]["data"]["kind"] == "projet_deja_ouvert"


def test_business_error_is_readable(tmp_path):
    r = call(Engine(), "project.create", {"path": str(tmp_path / "a.statpfe"), "study": {}})
    assert r["error"]["code"] == -32000
    assert "titre" in r["error"]["message"]


def test_protocol_errors():
    e = Engine()
    assert e.handle("pas du json")["error"]["code"] == -32700
    assert e.handle(json.dumps({"id": 1, "method": "x"}))["error"]["code"] == -32600
    assert call(e, "inconnue")["error"]["code"] == -32601
    bad = {"jsonrpc": "2.0", "id": 1, "method": "engine.info", "params": [1]}
    assert e.handle(json.dumps(bad))["error"]["code"] == -32602


def test_internal_error_does_not_leak(monkeypatch):
    e = Engine()
    monkeypatch.setitem(e.methods, "engine.info", lambda _: 1 / 0)
    r = call(e, "engine.info")
    assert r["error"]["code"] == -32603
    assert "ZeroDivision" not in r["error"]["message"]


def test_notification_has_no_response():
    assert Engine().handle(json.dumps({"jsonrpc": "2.0", "method": "engine.info"})) is None


def test_serve_loop_and_shutdown_discards_unsaved(tmp_path, study):
    path = str(tmp_path / "e.statpfe")
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "project.create", "params": {"path": path, "study": study}},
        {"jsonrpc": "2.0", "id": 2, "method": "project.update_study", "params": {"changes": {"objectives": "perdu"}}},
    ]
    out = io.StringIO()
    serve(io.StringIO("\n".join(json.dumps(m) for m in lines) + "\n\n"), out)
    responses = [json.loads(l) for l in out.getvalue().splitlines()]
    assert [r["id"] for r in responses] == [1, 2]
    r = call(Engine(), "project.open", {"path": path})
    assert r["result"]["study"]["objectives"] == study["objectives"]


def test_real_subprocess_utf8(tmp_path, study):
    """Le moteur lancé comme le fera l'application : processus séparé, stdio UTF-8."""
    path = str(tmp_path / "étude é.statpfe")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "engine.info"},
        {"jsonrpc": "2.0", "id": 2, "method": "project.create", "params": {"path": path, "study": study}},
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "statpfe"],
        input=("\n".join(json.dumps(r, ensure_ascii=False) for r in requests) + "\n").encode("utf-8"),
        capture_output=True,
        cwd=ENGINE_DIR,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    responses = [json.loads(l) for l in proc.stdout.decode("utf-8").splitlines()]
    assert responses[0]["result"]["name"] == "statpfe-engine"
    assert responses[1]["result"]["study"]["title"] == study["title"]
    assert Path(path).is_file()
