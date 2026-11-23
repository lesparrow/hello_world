"""Lecture des fichiers sources (CSV, Excel) en tableaux de textes bruts.

Les valeurs sont d'abord lues comme textes, sans aucune conversion automatique :
la détection des types et la conversion sont faites ensuite, de façon explicite
et traçable (statpfe.data.types). Ainsi, un « 007 » ou un « 3,5 » n'est jamais
transformé silencieusement.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from statpfe.errors import ValidationError, StatpfeError

MAX_FILE_SIZE = 200 * 1024 * 1024
CSV_EXTENSIONS = {".csv", ".txt", ".tsv"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
SUPPORTED = CSV_EXTENSIONS | EXCEL_EXTENSIONS
ENCODINGS = ["utf-8", "cp1252", "latin-1"]
DELIMITERS = [";", ",", "\t", "|"]
MOJIBAKE_MARKERS = ("Ã©", "Ã¨", "Ã ", "Ã§", "Ã´", "â€™", "Ã‰")


class SourceError(StatpfeError):
    code = "source"


@dataclass
class ReadOptions:
    encoding: str | None = None  # CSV
    delimiter: str | None = None  # CSV
    sheet: str | None = None  # Excel
    header: bool = True

    @classmethod
    def from_dict(cls, data: Any) -> "ReadOptions":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValidationError("Options de lecture invalides.")
        opts = cls(
            encoding=data.get("encoding"),
            delimiter=data.get("delimiter"),
            sheet=data.get("sheet"),
            header=bool(data.get("header", True)),
        )
        if opts.encoding is not None and opts.encoding not in ENCODINGS:
            raise ValidationError("Encodage non pris en charge.")
        if opts.delimiter is not None and opts.delimiter not in DELIMITERS:
            raise ValidationError("Séparateur non pris en charge.")
        if opts.sheet is not None and not isinstance(opts.sheet, str):
            raise ValidationError("Feuille invalide.")
        return opts

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RawTable:
    """Tableau de textes bruts (None = cellule vide)."""

    frame: pd.DataFrame
    options: ReadOptions
    kind: str
    sheets: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def file_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in CSV_EXTENSIONS:
        return "csv"
    if ext in EXCEL_EXTENSIONS:
        return "excel"
    if ext == ".xls":
        raise SourceError(
            "Les fichiers Excel anciens (.xls) ne sont pas encore pris en charge. "
            "Ouvrez-le dans Excel ou LibreOffice et enregistrez-le au format .xlsx."
        )
    if ext in {".sav", ".zsav", ".por"}:
        raise SourceError("Les fichiers SPSS ne sont pas encore pris en charge (prévu ultérieurement).")
    raise SourceError("Format non pris en charge. Formats acceptés : CSV, TXT, TSV, XLSX.")


def read_source_file(raw_path: Any) -> tuple[Path, bytes]:
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        raise ValidationError("Chemin de fichier invalide.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValidationError("Le chemin du fichier doit être un chemin complet.")
    if not path.is_file():
        raise SourceError(f"Le fichier « {path.name} » est introuvable.")
    file_kind(path)
    size = path.stat().st_size
    if size == 0:
        raise SourceError("Le fichier est vide.")
    if size > MAX_FILE_SIZE:
        raise SourceError("Le fichier dépasse la taille maximale acceptée (200 Mo).")
    try:
        return path, path.read_bytes()
    except OSError as exc:
        raise SourceError(f"Impossible de lire le fichier : {exc.strerror or exc}.") from exc


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse(data: bytes, kind: str, options: ReadOptions) -> RawTable:
    if kind == "csv":
        return _parse_csv(data, options)
    return _parse_excel(data, options)


# ---------------------------------------------------------------------- CSV
def _decode(data: bytes, encoding: str | None) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    if encoding:
        try:
            text = data.decode("utf-8-sig" if encoding == "utf-8" else encoding)
        except UnicodeDecodeError as exc:
            raise SourceError(
                f"Le fichier ne peut pas être lu avec l'encodage {encoding}. Essayez un autre encodage."
            ) from exc
        used = encoding
    else:
        for candidate in ENCODINGS:
            try:
                text = data.decode("utf-8-sig" if candidate == "utf-8" else candidate)
                used = candidate
                break
            except UnicodeDecodeError:
                continue
    if used != "utf-8":
        notes.append(f"Le fichier n'est pas en UTF-8 : il a été lu avec l'encodage {used}.")
    if any(m in text for m in MOJIBAKE_MARKERS):
        notes.append(
            "Certains caractères accentués semblent mal décodés (ex. « Ã© » au lieu de « é »). "
            "Vérifiez l'aperçu et changez d'encodage si nécessaire."
        )
    return text, used, notes


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(DELIMITERS)).delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        counts = {d: first.count(d) for d in DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def _parse_csv(data: bytes, options: ReadOptions) -> RawTable:
    text, encoding, notes = _decode(data, options.encoding)
    delimiter = options.delimiter or _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        rows = [row for row in reader]
    except csv.Error as exc:
        raise SourceError(f"Le fichier CSV est mal formé : {exc}.") from exc
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        raise SourceError("Le fichier ne contient aucune ligne de données.")
    width = max(len(r) for r in rows)
    irregular = sum(1 for r in rows if len(r) != width)
    if irregular:
        notes.append(
            f"{irregular} ligne(s) n'ont pas le même nombre de colonnes que les autres : "
            "les cellules manquantes ont été laissées vides."
        )
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, body = _split_header(rows, options.header, width)
    frame = pd.DataFrame(body, columns=header, dtype=object)
    frame = _clean_frame(frame)
    used = ReadOptions(encoding=encoding, delimiter=delimiter, sheet=None, header=options.header)
    return RawTable(frame=frame, options=used, kind="csv", notes=notes)


# ---------------------------------------------------------------------- Excel
def _cell_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "VRAI" if value else "FAUX"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _parse_excel(data: bytes, options: ReadOptions) -> RawTable:
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException
    import zipfile

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise SourceError("Le fichier Excel est illisible ou endommagé.") from exc
    try:
        sheets = list(wb.sheetnames)
        sheet = options.sheet or sheets[0]
        if sheet not in sheets:
            raise SourceError(f"La feuille « {sheet} » n'existe pas dans ce classeur.")
        rows = [[_cell_text(v) for v in row] for row in wb[sheet].iter_rows(values_only=True)]
    finally:
        wb.close()
    rows = [r for r in rows if any(v is not None for v in r)]
    if not rows:
        raise SourceError(f"La feuille « {sheet} » ne contient aucune donnée.")
    width = max(len(r) for r in rows)
    # Colonnes entièrement vides à droite : ignorées.
    while width > 0 and all(len(r) < width or r[width - 1] is None for r in rows):
        width -= 1
    rows = [(r + [None] * width)[:width] for r in rows]
    header, body = _split_header(rows, options.header, width)
    frame = _clean_frame(pd.DataFrame(body, columns=header, dtype=object))
    notes = []
    if len(sheets) > 1:
        notes.append(f"Le classeur contient {len(sheets)} feuilles ; la feuille « {sheet} » a été lue.")
    used = ReadOptions(encoding=None, delimiter=None, sheet=sheet, header=options.header)
    return RawTable(frame=frame, options=used, kind="excel", sheets=sheets, notes=notes)


# ---------------------------------------------------------------------- en-têtes
def _split_header(rows: list[list], header: bool, width: int) -> tuple[list[str], list[list]]:
    if header:
        names = [(str(v).strip() if v is not None else "") for v in rows[0]]
        body = rows[1:]
    else:
        names = [""] * width
        body = rows
    return unique_names(names), body


def unique_names(names: list[str]) -> list[str]:
    """Noms de colonnes non vides et uniques (V1, V2… pour les colonnes sans nom)."""
    result: list[str] = []
    seen: set[str] = set()
    for i, name in enumerate(names, start=1):
        base = name or f"V{i}"
        candidate, n = base, 2
        while candidate.casefold() in seen:
            candidate = f"{base}_{n}"
            n += 1
        seen.add(candidate.casefold())
        result.append(candidate)
    return result


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Cellules en textes nettoyés ; cellule vide = None (type objet, sans conversion)."""
    out = {}
    for col in frame.columns:
        out[col] = pd.Series(
            [None if v is None or (isinstance(v, float) and v != v) or str(v).strip() == "" else str(v).strip()
             for v in frame[col].tolist()],
            dtype=object, index=frame.index)
    return pd.DataFrame(out, index=frame.index, columns=frame.columns)
