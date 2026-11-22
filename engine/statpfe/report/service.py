"""Point d'entrée des rapports pour le serveur RPC."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from statpfe.errors import StatpfeError, ValidationError
from statpfe.report.build import build
from statpfe.report.checks import run_checks
from statpfe.report.options import FORMATS, clean_options, default_options, templates

META_KEY = "report_options"


class ReportService:
    def __init__(self, project):
        self.p = project

    @staticmethod
    def templates() -> dict[str, Any]:
        return templates()

    def options(self) -> dict[str, Any]:
        existing = sorted(a["id"] for a in self.p.analyses.list())
        row = self.p._conn.execute("SELECT value FROM meta WHERE key = ?", (META_KEY,)).fetchone()
        if row is None:
            return default_options(existing)
        try:
            opts = clean_options(json.loads(row[0]))
        except (ValidationError, ValueError):
            return default_options(existing)
        opts["analyses"] = [i for i in opts["analyses"] if i in existing]
        return opts

    def save_options(self, raw: Any) -> dict[str, Any]:
        opts = clean_options(raw)
        value = json.dumps(opts, ensure_ascii=False, sort_keys=True)
        if value == json.dumps(self.options(), ensure_ascii=False, sort_keys=True):
            return opts  # rien de changé (y compris les options par défaut jamais enregistrées)
        row = self.p._conn.execute("SELECT value FROM meta WHERE key = ?", (META_KEY,)).fetchone()
        if row is None or row[0] != value:
            self.p._conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (META_KEY, value))
            self.p.dirty = True
        return opts

    def check(self, raw: Any) -> dict[str, Any]:
        opts = self.save_options(raw)
        checks = run_checks(self.p, opts)
        try:
            outline = build(self.p, opts, draw=False).outline()
        except StatpfeError:
            outline = []
        return {"options": opts, "checks": checks, "outline": outline}

    def export(self, raw_path: Any, fmt: Any, raw: Any) -> dict[str, Any]:
        if fmt not in FORMATS:
            raise ValidationError("Format d'export inconnu.")
        path = _target(raw_path, fmt)
        opts = self.save_options(raw)
        checks = run_checks(self.p, opts)
        if checks["blocking"]:
            raise ValidationError(f"Export impossible : {checks['blocking']} contrôle(s) bloquant(s). "
                                  "Corrigez-les avant d'exporter.")
        document = build(self.p, opts)
        author = opts["cover"].get("authors", "")
        fd, tmp = tempfile.mkstemp(prefix=".statpfe-rapport-", suffix=f".{fmt}", dir=path.parent)
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            if fmt == "docx":
                from statpfe.report.render_docx import render
            else:
                from statpfe.report.render_pdf import render
            render(document, tmp_path, author)
            mask = os.umask(0)
            os.umask(mask)
            os.chmod(tmp_path, 0o666 & ~mask)  # mkstemp crée le fichier en 0600
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)
        tables = sum(1 for o in document.outline() if o["kind"] == "table")
        figures = sum(1 for o in document.outline() if o["kind"] == "figure")
        self.p._log("rapport", f"Rapport exporté ({FORMATS[fmt]}) : « {path.name} », {len(opts['analyses'])} "
                               f"analyse(s), {tables} tableau(x), {figures} figure(s)",
                    {"format": fmt, "analyses": opts["analyses"], "template": opts["template"]})
        return {"path": str(path), "file_name": path.name, "size": path.stat().st_size, "tables": tables,
                "figures": figures, "checks": checks}


def _target(raw: Any, fmt: str) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise ValidationError("Le chemin du rapport est invalide.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValidationError("Le chemin du rapport doit être un chemin complet.")
    path = path.resolve()
    if path.suffix.lower() != f".{fmt}":
        raise ValidationError(f"Le fichier doit avoir l'extension .{fmt}.")
    if not path.parent.is_dir():
        raise ValidationError(f"Le dossier « {path.parent} » n'existe pas.")
    if path.is_dir():
        raise ValidationError("Le chemin indiqué est un dossier.")
    return path
