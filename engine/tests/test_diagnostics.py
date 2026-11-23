"""Vérification des dépendances incluses (engine.selfcheck)."""

from __future__ import annotations

import json

from statpfe.core import diagnostics
from statpfe.rpc.server import Engine


def _call(e, method):
    return json.loads(json.dumps(e.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method}))))["result"]


def test_selfcheck_exercises_every_dependency():
    r = _call(Engine(), "engine.selfcheck")
    assert r["ok"], r
    keys = [c["key"] for c in r["checks"]]
    assert keys == ["numpy", "scipy", "pandas", "openpyxl", "matplotlib", "python-docx", "reportlab", "sqlite",
                    "config", "temp"]
    assert all(c["version"] for c in r["checks"] if c["key"] not in ("config", "temp"))


def test_info_lists_versions_and_folders():
    info = _call(Engine(), "engine.info")
    assert info["frozen"] is False and info["config_dir"]
    assert set(diagnostics.PACKAGES) <= set(info["dependencies"])


def test_a_broken_dependency_is_reported(monkeypatch):
    def boom():
        raise OSError("bibliothèque native absente")

    monkeypatch.setattr(diagnostics, "CHECKS", [("numpy", "Calcul", boom)] + diagnostics.CHECKS[1:])
    r = diagnostics.selfcheck()
    assert not r["ok"] and r["checks"][0]["detail"] == "OSError: bibliothèque native absente"
    assert all(c["ok"] for c in r["checks"][1:])
