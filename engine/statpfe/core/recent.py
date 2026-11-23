"""Liste des projets récents, stockée dans le dossier de configuration de l'utilisateur.

Seuls le chemin, le titre et la date d'ouverture sont conservés : aucune donnée d'étude.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

MAX_RECENT = 10


def config_dir() -> Path:
    override = os.environ.get("STATPFE_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "STATPFE"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "STATPFE"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "statpfe"


def _file() -> Path:
    return config_dir() / "recent-projects.json"


def load() -> list[dict[str, Any]]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    items = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            items.append(
                {
                    "path": item["path"],
                    "title": str(item.get("title", "")),
                    "opened_at": str(item.get("opened_at", "")),
                    "exists": Path(item["path"]).is_file(),
                }
            )
    return items[:MAX_RECENT]


def remember(path: Path, title: str, opened_at: str) -> None:
    items = [i for i in load() if i["path"] != str(path)]
    items.insert(0, {"path": str(path), "title": title, "opened_at": opened_at})
    _store(items)


def forget(path: str) -> None:
    _store([i for i in load() if i["path"] != path])


def _store(items: list[dict[str, Any]]) -> None:
    target = _file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = [{k: i[k] for k in ("path", "title", "opened_at")} for i in items[:MAX_RECENT]]
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        # La liste des projets récents est un confort : son échec ne doit rien bloquer.
        pass
