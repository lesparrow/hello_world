"""Vérification des dépendances incluses dans le moteur.

Chaque bibliothèque embarquée (installateur) est réellement utilisée sur un petit exemple :
une bibliothèque présente mais inutilisable (fichier de données manquant dans le paquet,
bibliothèque native absente) est ainsi repérée, sur l'ordinateur de l'utilisateur comme
dans le CI.
"""

from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import time
import zipfile
from importlib import metadata
from typing import Any, Callable

from statpfe.core import recent

PACKAGES = {"numpy": "numpy", "scipy": "scipy", "pandas": "pandas", "openpyxl": "openpyxl",
            "matplotlib": "matplotlib", "python-docx": "docx", "reportlab": "reportlab"}


def versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {"sqlite": sqlite3.sqlite_version}
    for dist, module in PACKAGES.items():
        try:
            out[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            try:  # exécutable autonome : métadonnées parfois absentes, on lit le module
                out[dist] = getattr(__import__(module), "__version__", None)
            except ImportError:
                out[dist] = None
    return out


def _numpy() -> str:
    import numpy as np

    x = np.linalg.solve(np.array([[3.0, 1.0], [1.0, 2.0]]), np.array([9.0, 8.0]))
    assert np.allclose(x, [2.0, 3.0])
    return "algèbre linéaire"


def _scipy() -> str:
    from scipy import stats

    assert abs(stats.t.sf(2.0, 10) - 0.036694) < 1e-5
    assert 0 < stats.nct.sf(2.0, 30, 1.5) < 1  # loi de Student non centrale (puissance)
    return "lois de Student, non centrale"


def _pandas() -> str:
    import pandas as pd

    df = pd.read_csv(io.StringIO("g;note\nA;12,5\nB;9\n"), sep=";", decimal=",")
    assert df["note"].sum() == 21.5
    return "lecture CSV (virgule décimale)"


def _openpyxl() -> str:
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["note", 12.5])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    assert openpyxl.load_workbook(buf).active["B1"].value == 12.5
    return "écriture et lecture Excel"


def _matplotlib() -> str:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    fig = Figure(figsize=(2, 1.5), dpi=50)
    fig.add_subplot().hist([1, 2, 2, 3, 3, 3])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    assert buf.getvalue()[:4] == b"\x89PNG"
    return "figure PNG"


def _docx() -> str:
    import docx

    d = docx.Document()
    d.add_heading("Essai", level=1)
    d.add_table(rows=1, cols=2)
    buf = io.BytesIO()
    d.save(buf)
    assert zipfile.ZipFile(buf).testzip() is None
    return "document Word"


def _reportlab() -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 720, "Écart-type, médiane")
    c.save()
    assert buf.getvalue()[:5] == b"%PDF-"
    return "document PDF"


def _sqlite() -> str:
    con = sqlite3.connect(":memory:")
    con.execute("create table t(x json)")
    con.execute("insert into t values (json_object('a', 1))")
    assert con.execute("select json_extract(x, '$.a') from t").fetchone()[0] == 1
    return "base de projet (JSON)"


def _config_dir() -> str:
    d = recent.config_dir()
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=d, prefix=".essai-", delete=True) as f:
        f.write(b"ok")
    return str(d)


def _temp_dir() -> str:
    with tempfile.TemporaryDirectory(prefix="statpfe-essai-") as d:
        with open(os.path.join(d, "x"), "w", encoding="utf-8") as f:
            f.write("é")
    return "écriture possible"


CHECKS: list[tuple[str, str, Callable[[], str]]] = [
    ("numpy", "Calcul numérique", _numpy),
    ("scipy", "Lois statistiques", _scipy),
    ("pandas", "Tableaux de données", _pandas),
    ("openpyxl", "Fichiers Excel", _openpyxl),
    ("matplotlib", "Graphiques", _matplotlib),
    ("python-docx", "Rapports Word", _docx),
    ("reportlab", "Rapports PDF", _reportlab),
    ("sqlite", "Fichier projet", _sqlite),
    ("config", "Dossier de configuration", _config_dir),
    ("temp", "Dossier temporaire", _temp_dir),
]


def selfcheck() -> dict[str, Any]:
    vers = versions()
    items = []
    for key, label, fn in CHECKS:
        start = time.perf_counter()
        try:
            detail, ok = fn(), True
        except Exception as exc:  # noqa: BLE001 - on rapporte chaque échec sans s'arrêter
            detail, ok = f"{exc.__class__.__name__}: {exc}"[:300], False
        items.append({"key": key, "label": label, "version": vers.get(key), "ok": ok, "detail": detail,
                      "ms": round((time.perf_counter() - start) * 1000)})
    return {"ok": all(i["ok"] for i in items), "checks": items}
