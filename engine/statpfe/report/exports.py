"""Exports complémentaires : tableaux de résultats en Excel et graphiques en images.

Rien n'est recalculé : les valeurs viennent des résultats enregistrés (analyses
et calculs de puissance). Dans le classeur Excel, les nombres restent de vrais
nombres (avec un format d'affichage), pour être retravaillés par l'étudiant.
"""

from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Callable

from statpfe.errors import ValidationError
from statpfe.report import charts
from statpfe.report import theme as themes

NUMBER_FORMATS = {"int": "0", "num": "0.000", "pct": "0.0%", "p": "0.0000", "value": "0.000"}
MAX_ITEMS = 200


def _ids(raw: Any, known: list[int], label: str) -> list[int]:
    if raw is None:
        return known
    if not isinstance(raw, list) or len(raw) > MAX_ITEMS or \
            not all(isinstance(i, int) and not isinstance(i, bool) for i in raw):
        raise ValidationError(f"Liste des {label} invalide.")
    unknown = [i for i in raw if i not in known]
    if unknown:
        raise ValidationError(f"{label.capitalize()} introuvable(s) : {', '.join(map(str, unknown))}.")
    return raw


def _path(raw: Any, extensions: tuple[str, ...]) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise ValidationError("Le chemin du fichier est invalide.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValidationError("Le chemin doit être un chemin complet.")
    path = path.resolve()
    if path.suffix.lower().lstrip(".") not in extensions:
        raise ValidationError("Le fichier doit avoir l'extension " + " ou ".join(f".{e}" for e in extensions) + ".")
    if not path.parent.is_dir():
        raise ValidationError(f"Le dossier « {path.parent} » n'existe pas.")
    if path.is_dir():
        raise ValidationError("Le chemin indiqué est un dossier.")
    return path


def _write_atomic(path: Path, write: Callable[[Path], None]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".statpfe-export-", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        write(tmp_path)
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp_path, 0o666 & ~mask)
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def slug(text: str, max_len: int = 50) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return (s[:max_len].rstrip("-") or "graphique")


def _sources(project, analyses: Any, power: Any) -> list[tuple[str, int, dict[str, Any]]]:
    """(libellé, numéro, enregistrement) des analyses puis des calculs de puissance demandés."""
    a_ids = _ids(analyses, sorted(a["id"] for a in project.analyses.list()), "analyses")
    p_ids = _ids(power, [c["id"] for c in project.power.list()], "calculs de puissance")
    out = [("analyse", i, project.analyses.get(i)) for i in a_ids]
    out += [("puissance", i, project.power.get(i)) for i in p_ids]
    return out


# ---------------------------------------------------------------- Excel

def export_tables(project, raw_path: Any, analyses: Any = None, power: Any = None) -> dict[str, Any]:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    path = _path(raw_path, ("xlsx",))
    sources = _sources(project, analyses, power)
    if not sources:
        raise ValidationError("Aucune analyse ni aucun calcul de puissance à exporter.")
    th = themes.get(themes.DEFAULT_THEME)
    head_fill = PatternFill("solid", fgColor=th.header_fill.lstrip("#"))
    head_font = Font(bold=True, color=th.header_text.lstrip("#"))
    title_font = Font(bold=True, size=13, color=th.primary.lstrip("#"))
    note_font = Font(italic=True, size=9, color="555555")

    wb = Workbook()
    summary = wb.active
    summary.title = "Sommaire"
    summary.append([f"Tableaux de résultats — {project.study.title}"])
    summary["A1"].font = title_font
    summary.append(["Valeurs exportées depuis STATPFE, sans arrondi : le format d'affichage peut être modifié."])
    summary["A2"].font = note_font
    summary.append([])
    summary.append(["Onglet", "Type", "N°", "Titre", "Données"])
    for c in summary[4]:
        c.fill, c.font = head_fill, head_font
    used: set[str] = {"Sommaire"}
    tables_count = 0

    for kind, number, rec in sources:
        res = rec["result"]
        prefix = "A" if kind == "analyse" else "P"
        name = re.sub(r"[\[\]:*?/\\']", " ", f"{prefix}{number} {rec['title']}")[:31].strip()
        base, k = name, 2
        while name in used:
            name = f"{base[:28]}~{k}"
            k += 1
        used.add(name)
        ws = wb.create_sheet(name)
        data_label = (f"{rec.get('dataset_name') or ''} ({rec.get('version_name') or ''})"
                      if kind == "analyse" else "")
        summary.append([name, "Analyse" if kind == "analyse" else "Calcul de puissance", number, rec["title"],
                        data_label])
        ws.append([rec["title"]])
        ws["A1"].font = title_font
        if data_label:
            ws.append([f"Données : {data_label}"])
            ws.cell(ws.max_row, 1).font = note_font
        ws.append([])
        items = res.get("summary") or []
        if items:
            ws.append(["Statistique", "Valeur"])
            for c in ws[ws.max_row]:
                c.fill, c.font = head_fill, head_font
            for it in items:
                ws.append([it["label"], it["value"]])
                cell = ws.cell(ws.max_row, 2)
                if isinstance(it["value"], (int, float)):
                    cell.number_format = NUMBER_FORMATS.get(it.get("kind"), "0.000")
            ws.append([])
            tables_count += 1
        for t in res.get("tables") or []:
            kinds = t.get("kinds") or []
            ws.append([t["title"]])
            ws.cell(ws.max_row, 1).font = Font(bold=True, color=th.primary.lstrip("#"))
            ws.append(list(t["columns"]))
            for c in ws[ws.max_row]:
                c.fill, c.font = head_fill, head_font
                c.alignment = Alignment(wrap_text=True, vertical="top")
            for row in t["rows"]:
                ws.append(list(row))
                for j, v in enumerate(row):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        ws.cell(ws.max_row, j + 1).number_format = NUMBER_FORMATS.get(
                            kinds[j] if j < len(kinds) else "num", "0.000")
            if t.get("note"):
                ws.append([f"Note : {t['note']}"])
                ws.cell(ws.max_row, 1).font = note_font
            ws.append([])
            tables_count += 1
        for col in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = 34 if col == 1 else 16
    for col, width in zip("ABCDE", (32, 20, 6, 60, 30)):
        summary.column_dimensions[col].width = width
    wb.properties.creator = "STATPFE"
    wb.properties.title = f"Tableaux de résultats — {project.study.title}"
    _write_atomic(path, lambda p: wb.save(str(p)))
    project._log("export", f"Tableaux exportés en Excel : « {path.name} », {len(sources)} onglet(s), "
                           f"{tables_count} tableau(x)", {"format": "xlsx"})
    return {"path": str(path), "file_name": path.name, "size": path.stat().st_size, "sheets": len(sources),
            "tables": tables_count}


# ---------------------------------------------------------------- images

def _check_format(fmt: Any) -> str:
    if fmt not in charts.IMAGE_FORMATS:
        raise ValidationError("Format d'image inconnu (png ou svg).")
    return fmt


def _render(chart: dict[str, Any], theme: Any, fmt: str) -> bytes:
    if theme is not None and not isinstance(theme, str):
        raise ValidationError("Thème de couleurs inconnu.")
    return charts.render(chart, theme or themes.DEFAULT_THEME, fmt, dpi=300)


def export_chart(project, raw_path: Any, source: Any, item_id: Any, index: Any, theme: Any = None) -> dict[str, Any]:
    path = _path(raw_path, tuple(charts.IMAGE_FORMATS))
    fmt = path.suffix.lower().lstrip(".")
    if source == "analysis":
        rec = project.analyses.get(item_id)
    elif source == "power":
        rec = project.power.get(item_id)
    else:
        raise ValidationError("Source du graphique inconnue.")
    items = rec["result"].get("charts") or []
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(items):
        raise ValidationError("Graphique introuvable.")
    data = _render(items[index], theme, fmt)
    _write_atomic(path, lambda p: p.write_bytes(data))
    project._log("export", f"Graphique exporté : « {path.name} » ({items[index]['title']})", {"format": fmt})
    return {"path": str(path), "file_name": path.name, "size": path.stat().st_size}


def export_charts(project, raw_dir: Any, fmt: Any, theme: Any = None, analyses: Any = None,
                  power: Any = None) -> dict[str, Any]:
    fmt = _check_format(fmt)
    if not isinstance(raw_dir, str) or not raw_dir.strip() or "\x00" in raw_dir:
        raise ValidationError("Le dossier de destination est invalide.")
    directory = Path(raw_dir).expanduser()
    if not directory.is_absolute() or not directory.is_dir():
        raise ValidationError("Choisissez un dossier existant (chemin complet).")
    files = []
    for kind, number, rec in _sources(project, analyses, power):
        for k, ch in enumerate(rec["result"].get("charts") or [], start=1):
            name = f"{kind}-{number:02d}-graphique-{k:02d}-{slug(ch['title'])}.{fmt}"
            target = directory / name
            data = _render(ch, theme, fmt)
            _write_atomic(target, lambda p, d=data: p.write_bytes(d))
            files.append(name)
    if not files:
        raise ValidationError("Aucun graphique à exporter dans les analyses choisies.")
    project._log("export", f"{len(files)} graphique(s) exporté(s) en {fmt.upper()} dans « {directory} »",
                 {"format": fmt, "count": len(files)})
    return {"directory": str(directory.resolve()), "files": files, "count": len(files)}
