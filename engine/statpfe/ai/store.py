"""Propositions de l'IA enregistrées dans le projet (traçabilité complète).

Chaque proposition terminée est conservée avec le texte exact transmis au modèle, le
modèle, les réglages et la version des consignes. Elle reste une « proposition » tant
que l'utilisateur ne l'a pas relue et retenue ; seules les propositions retenues
peuvent entrer dans le rapport, toujours signalées comme rédigées avec l'aide d'une IA.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable

from statpfe.ai import guard, prompts
from statpfe.core.timeutil import now_iso
from statpfe.errors import ValidationError

SCHEMA_V6_AI = """
CREATE TABLE IF NOT EXISTS ai_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    task TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    settings TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    messages TEXT NOT NULL,
    context TEXT NOT NULL,
    context_hash TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    text TEXT NOT NULL,
    checks TEXT NOT NULL,
    status TEXT NOT NULL,
    edited INTEGER NOT NULL DEFAULT 0,
    reviewed_at TEXT,
    updated_at TEXT NOT NULL,
    duration REAL
);
CREATE INDEX IF NOT EXISTS ai_texts_analysis ON ai_texts (analysis_id);
"""
STATUSES = {"proposition": "Proposition à vérifier", "retenu": "Retenue après relecture", "ecarte": "Écartée"}
TEXT_MAX = 20_000
MAX_TEXTS = 2000
_COLS = ("id, analysis_id, created_at, task, provider, model, settings, prompt_version, context, context_hash, "
         "raw_text, text, checks, status, edited, reviewed_at, updated_at, duration")


class AiTextStore:
    def __init__(self, conn: sqlite3.Connection, log: Callable[..., None]):
        self._conn = conn
        self._log = log

    def record(self, *, analysis_id: int, analysis_label: str, task: str, settings: dict[str, Any], model: str,
               messages: list[dict[str, str]], context: dict[str, Any], raw_text: str, duration: float) -> int:
        if self.count() >= MAX_TEXTS:
            raise ValidationError(f"Au plus {MAX_TEXTS} propositions de l'IA par projet.")
        text = guard.strip_thinking(raw_text)[:TEXT_MAX]
        checks = guard.check(text, context["text"])
        now = now_iso()
        cur = self._conn.execute(
            "INSERT INTO ai_texts (analysis_id, created_at, task, provider, model, settings, prompt_version, "
            "messages, context, context_hash, raw_text, text, checks, status, edited, updated_at, duration) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposition', 0, ?, ?)",
            (analysis_id, now, task, settings["provider"], model, json.dumps(settings, ensure_ascii=False),
             prompts.PROMPT_VERSION, json.dumps(messages, ensure_ascii=False), context["text"], context["hash"],
             raw_text[:TEXT_MAX * 2], text, json.dumps(checks, ensure_ascii=False), now, duration))
        text_id = int(cur.lastrowid)
        origin = "de Claude (en ligne, via Claude Code)" if settings["provider"] == "claude_code" else "de l'IA locale"
        self._log("ia", f"Proposition {origin} ({prompts.TASKS[task]['label'].lower()}) pour {analysis_label}, "
                        f"modèle {model}", {"ai_text_id": text_id, "analysis_id": analysis_id})
        return text_id

    def list(self, analysis_id: Any = None) -> list[dict[str, Any]]:
        if analysis_id is None:
            rows = self._conn.execute(f"SELECT {_COLS} FROM ai_texts ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(f"SELECT {_COLS} FROM ai_texts WHERE analysis_id = ? ORDER BY id",
                                      (_id(analysis_id),)).fetchall()
        return [_row(r) for r in rows]

    def get(self, text_id: Any) -> dict[str, Any]:
        row = self._conn.execute(f"SELECT {_COLS} FROM ai_texts WHERE id = ?", (_id(text_id),)).fetchone()
        if row is None:
            raise ValidationError("Cette proposition de l'IA n'existe pas.")
        return _row(row)

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM ai_texts").fetchone()[0])

    def check_text(self, text_id: Any, text: Any) -> dict[str, Any]:
        item = self.get(text_id)
        return guard.check(_clean_text(text), item["context"])

    def keep(self, text_id: Any, text: Any, reviewed: Any) -> dict[str, Any]:
        item = self.get(text_id)
        if reviewed is not True:
            raise ValidationError("Confirmez d'abord que vous avez relu et vérifié ce texte.")
        clean = _clean_text(text)
        checks = guard.check(clean, item["context"])
        if checks["empty"]:
            raise ValidationError("Le texte est vide.")
        if checks["unverified"]:
            listed = ", ".join(f"« {n['text']} »" for n in checks["unverified"][:8])
            raise ValidationError(
                f"Le texte contient des nombres qui ne figurent pas dans les résultats calculés : {listed}. "
                "Corrigez-les ou supprimez-les avant de retenir le texte.")
        now = now_iso()
        edited = int(clean != item["text"] or bool(item["edited"]))
        self._conn.execute(
            "UPDATE ai_texts SET text = ?, checks = ?, status = 'retenu', edited = ?, reviewed_at = ?, updated_at = ? "
            "WHERE id = ?", (clean, json.dumps(checks, ensure_ascii=False), edited, now, now, item["id"]))
        self._log("ia", f"Proposition de l'IA n° {item['id']} retenue après relecture"
                        + (" et modification" if edited else ""), {"ai_text_id": item["id"]})
        return self.get(item["id"])

    def discard(self, text_id: Any) -> dict[str, Any]:
        item = self.get(text_id)
        now = now_iso()
        self._conn.execute("UPDATE ai_texts SET status = 'ecarte', updated_at = ? WHERE id = ?", (now, item["id"]))
        self._log("ia", f"Proposition de l'IA n° {item['id']} écartée", {"ai_text_id": item["id"]})
        return self.get(item["id"])

    def delete_for_analysis(self, analysis_id: int) -> None:
        self._conn.execute("DELETE FROM ai_texts WHERE analysis_id = ?", (analysis_id,))

    def kept(self, analysis_id: int) -> list[dict[str, Any]]:
        return [t for t in self.list(analysis_id) if t["status"] == "retenu"]


def _clean_text(text: Any) -> str:
    if not isinstance(text, str):
        raise ValidationError("Texte invalide.")
    clean = text.replace("\r\n", "\n").strip()
    if len(clean) > TEXT_MAX:
        raise ValidationError(f"Le texte dépasse {TEXT_MAX} caractères.")
    return clean


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("Identifiant invalide.")
    return value


def _row(r: tuple) -> dict[str, Any]:
    task = r[3]
    return {"id": r[0], "analysis_id": r[1], "created_at": r[2], "task": task,
            "task_label": prompts.TASKS.get(task, {}).get("label", task), "provider": r[4], "model": r[5],
            "settings": json.loads(r[6]), "prompt_version": r[7], "context": r[8], "context_hash": r[9],
            "raw_text": r[10], "text": r[11], "checks": json.loads(r[12]), "status": r[13],
            "status_label": STATUSES.get(r[13], r[13]), "edited": bool(r[14]), "reviewed_at": r[15],
            "updated_at": r[16], "duration": r[17]}
