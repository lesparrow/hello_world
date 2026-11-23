"""Plan d'analyse : rédigé avant l'analyse finale, verrouillé, versionné.

Le plan passe par des versions numérotées. Une version en « brouillon » se
modifie librement ; une fois « verrouillée », elle ne change plus jamais. Toute
modification ultérieure crée une nouvelle version, qui doit être verrouillée à
son tour avec le motif du changement. L'historique complet reste dans le
projet et dans le rapport.

Une analyse est « prévue au plan » seulement si elle est rattachée, au moment
où elle est lancée, à une analyse d'une version verrouillée : par construction,
elle est donc postérieure au verrouillage. Toute autre analyse est présentée
comme ajoutée hors du plan, après consultation des données.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Callable

from statpfe.core.timeutil import now_iso
from statpfe.errors import ValidationError
from statpfe.stats import catalog

SCHEMA_V5_PLAN = """
CREATE TABLE IF NOT EXISTS plan_versions (
    version INTEGER PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('brouillon', 'verrouille')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    locked_at TEXT,
    change_reason TEXT NOT NULL DEFAULT ''
);
"""

TEXT_MAX = 20_000
SHORT_MAX = 2_000
NAME_MAX = 200
LIST_MAX = 100
ITEMS_MAX = 100
REASON_MAX = 2_000
ITEM_ID = re.compile(r"^A([1-9][0-9]{0,3})$")
ALTERNATIVES = {"two-sided": "bilatéral", "less": "unilatéral (inférieur)", "greater": "unilatéral (supérieur)"}
ROLES = {"principale": "Principale", "secondaire": "Secondaire"}

TEXT_FIELDS = {
    "objectives": "Objectifs",
    "exclusion_criteria": "Critères d'exclusion",
    "missing_values": "Traitement des valeurs manquantes",
    "exploratory": "Analyses exploratoires envisagées",
    "multiplicity": "Tests multiples",
}
FIELD_LABELS = {
    **TEXT_FIELDS,
    "hypotheses": "Hypothèses",
    "primary_variables": "Variables principales",
    "secondary_variables": "Variables secondaires",
    "analyses": "Analyses prévues",
    "alpha": "Seuil de signification",
    "sample_size": "Taille d'échantillon prévue",
    "power_calc": "Calcul de puissance de référence",
}


def empty_plan() -> dict[str, Any]:
    return {"objectives": "", "hypotheses": [], "primary_variables": [], "secondary_variables": [], "analyses": [],
            "exclusion_criteria": "", "missing_values": "", "exploratory": "", "multiplicity": "", "alpha": 0.05,
            "sample_size": None, "power_calc": None}


# ---------------------------------------------------------------------- validation
def _text(raw: Any, label: str, max_len: int = TEXT_MAX) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValidationError(f"« {label} » doit être un texte.")
    raw = raw.strip()
    if len(raw) > max_len:
        raise ValidationError(f"« {label} » ne doit pas dépasser {max_len} caractères.")
    return raw


def _names(raw: Any, label: str, max_count: int = LIST_MAX) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError(f"« {label} » doit être une liste.")
    out: list[str] = []
    for x in raw:
        x = _text(x, label, NAME_MAX)
        if x and x not in out:
            out.append(x)
    if len(out) > max_count:
        raise ValidationError(f"« {label} » : au plus {max_count} éléments.")
    return out


def _opt_int(raw: Any, label: str, lo: int, hi: int) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or not lo <= raw <= hi:
        raise ValidationError(f"« {label} » doit être un entier compris entre {lo} et {hi}.")
    return raw


def clean_plan(raw: Any, known_ids: set[str], power_exists: Callable[[int], bool]) -> dict[str, Any]:
    """Valide le contenu d'un plan reçu de l'interface et attribue les identifiants des nouvelles analyses."""
    if not isinstance(raw, dict):
        raise ValidationError("Plan d'analyse invalide.")
    unknown = set(raw) - set(FIELD_LABELS)
    if unknown:
        raise ValidationError(f"Champ(s) inconnu(s) dans le plan : {', '.join(sorted(unknown))}.")
    out = empty_plan()
    for k, label in TEXT_FIELDS.items():
        out[k] = _text(raw.get(k), label)
    hyps = raw.get("hypotheses") or []
    if not isinstance(hyps, list):
        raise ValidationError("Les hypothèses doivent être une liste.")
    out["hypotheses"] = [h for h in (_text(h, "Hypothèse", SHORT_MAX) for h in hyps) if h]
    if len(out["hypotheses"]) > 50:
        raise ValidationError("Au plus 50 hypothèses.")
    out["primary_variables"] = _names(raw.get("primary_variables"), "Variables principales")
    out["secondary_variables"] = _names(raw.get("secondary_variables"), "Variables secondaires")
    alpha = raw.get("alpha", 0.05)
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0.0001 <= float(alpha) <= 0.2:
        raise ValidationError("Le seuil de signification doit être compris entre 0,0001 et 0,2.")
    out["alpha"] = float(alpha)
    out["sample_size"] = _opt_int(raw.get("sample_size"), "Taille d'échantillon prévue", 1, 1_000_000_000)
    out["power_calc"] = _opt_int(raw.get("power_calc"), "Calcul de puissance", 1, 10**9)
    if out["power_calc"] is not None and not power_exists(out["power_calc"]):
        raise ValidationError("Le calcul de puissance choisi n'existe plus.")

    items = raw.get("analyses") or []
    if not isinstance(items, list) or len(items) > ITEMS_MAX:
        raise ValidationError(f"Au plus {ITEMS_MAX} analyses prévues.")
    numbers = [int(ITEM_ID.match(i).group(1)) for i in known_ids if ITEM_ID.match(i)]
    next_no = max(numbers, default=0) + 1
    seen: set[str] = set()
    for pos, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValidationError("Analyse prévue invalide.")
        label = f"Analyse prévue n° {pos}"
        item_id = item.get("id")
        if item_id in (None, ""):
            item_id = f"A{next_no}"
            next_no += 1
        elif not isinstance(item_id, str) or item_id not in known_ids:
            raise ValidationError(f"{label} : identifiant inconnu.")
        if item_id in seen:
            raise ValidationError(f"{label} : figure deux fois dans le plan.")
        seen.add(item_id)
        method = item.get("method")
        if method not in catalog.METHODS:
            raise ValidationError(f"{label} : choisissez la méthode.")
        roles = {v["name"]: v for v in catalog.METHODS[method]["variables"]}
        variables_in = item.get("variables") or {}
        if not isinstance(variables_in, dict) or set(variables_in) - set(roles):
            raise ValidationError(f"{label} : variables invalides pour cette méthode.")
        variables = {}
        for role, spec in roles.items():
            names = _names(variables_in.get(role), spec["label"], 30 if spec["multiple"] else 1)
            if names:
                variables[role] = names
        hyp = item.get("hypothesis")
        if hyp is not None and (isinstance(hyp, bool) or not isinstance(hyp, int)
                                or not 0 <= hyp < len(out["hypotheses"])):
            raise ValidationError(f"{label} : hypothèse inconnue.")
        role = item.get("role", "principale")
        if role not in ROLES:
            raise ValidationError(f"{label} : rôle inconnu.")
        alt = item.get("alternative", "two-sided")
        if alt not in ALTERNATIVES:
            raise ValidationError(f"{label} : hypothèse alternative inconnue.")
        calc = _opt_int(item.get("power_calc"), "Calcul de puissance", 1, 10**9)
        if calc is not None and not power_exists(calc):
            raise ValidationError(f"{label} : le calcul de puissance choisi n'existe plus.")
        out["analyses"].append({
            "id": item_id, "method": method, "variables": variables, "hypothesis": hyp, "role": role,
            "alternative": alt, "description": _text(item.get("description"), "Description", SHORT_MAX),
            "power_calc": calc,
        })
    return out


def item_variables(item: dict[str, Any]) -> list[str]:
    return [n for names in item.get("variables", {}).values() for n in names]


def describe_item(item: dict[str, Any]) -> str:
    """« A1 · Test t de Welch : score, groupe »."""
    names = item_variables(item)
    return f"{item['id']} · {catalog.METHODS[item['method']]['label']}" + (f" : {', '.join(names)}" if names else "")


def diff(before: dict[str, Any] | None, after: dict[str, Any]) -> list[dict[str, str]]:
    """Différences entre deux versions du plan, pour l'historique et le rapport."""
    if before is None:
        return []
    out: list[dict[str, str]] = []
    for key, label in FIELD_LABELS.items():
        if key == "analyses":
            continue
        if before.get(key) != after.get(key):
            out.append({"field": key, "label": label, "kind": "modifie", "detail": f"{label} modifié(es)"})
    old = {i["id"]: i for i in before.get("analyses", [])}
    new = {i["id"]: i for i in after.get("analyses", [])}
    for i in after.get("analyses", []):
        if i["id"] not in old:
            out.append({"field": "analyses", "label": i["id"], "kind": "ajoute",
                        "detail": f"Analyse ajoutée : {describe_item(i)}"})
        elif old[i["id"]] != i:
            changed = [k for k in ("method", "variables", "hypothesis", "role", "alternative", "description",
                                   "power_calc") if old[i["id"]].get(k) != i.get(k)]
            names = {"method": "méthode", "variables": "variables", "hypothesis": "hypothèse", "role": "rôle",
                     "alternative": "hypothèse alternative", "description": "description",
                     "power_calc": "calcul de puissance"}
            out.append({"field": "analyses", "label": i["id"], "kind": "modifie",
                        "detail": f"Analyse {i['id']} modifiée ({', '.join(names[c] for c in changed)})"})
    for i in before.get("analyses", []):
        if i["id"] not in new:
            out.append({"field": "analyses", "label": i["id"], "kind": "retire",
                        "detail": f"Analyse retirée : {describe_item(i)}"})
    return out


# ---------------------------------------------------------------------- stockage
class PlanStore:
    def __init__(self, conn: sqlite3.Connection, log: Callable[..., None], mark_dirty: Callable[[], None],
                 power_exists: Callable[[int], bool]):
        self._conn = conn
        self._log = log
        self._mark_dirty = mark_dirty
        self._power_exists = power_exists

    # -------------------------------------------------------------- lecture
    def _rows(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT version, status, content, created_at, updated_at, locked_at, change_reason FROM plan_versions "
            "ORDER BY version").fetchall()
        return [{"version": r[0], "status": r[1], "content": json.loads(r[2]), "created_at": r[3],
                 "updated_at": r[4], "locked_at": r[5], "change_reason": r[6]} for r in rows]

    def versions(self) -> list[dict[str, Any]]:
        """Toutes les versions avec, pour chacune, les changements par rapport à la version précédente."""
        rows = self._rows()
        out = []
        prev = None
        for r in rows:
            out.append({**r, "changes": diff(prev["content"] if prev else None, r["content"])})
            prev = r
        return out

    def latest_locked(self) -> dict[str, Any] | None:
        locked = [v for v in self.versions() if v["status"] == "verrouille"]
        return locked[-1] if locked else None

    def first_lock_at(self) -> str | None:
        row = self._conn.execute("SELECT MIN(locked_at) FROM plan_versions WHERE status = 'verrouille'").fetchone()
        return row[0] if row else None

    def get(self) -> dict[str, Any]:
        versions = self.versions()
        current = versions[-1] if versions else None
        locked = [v for v in versions if v["status"] == "verrouille"]
        return {
            "current": current,
            "locked": locked[-1] if locked else None,
            "versions": [{k: v[k] for k in ("version", "status", "created_at", "updated_at", "locked_at",
                                             "change_reason", "changes")} for v in versions],
            "empty": empty_plan(),
            "pending_changes": diff(locked[-1]["content"], current["content"])
            if current and locked and current["status"] == "brouillon" else [],
        }

    def version(self, number: Any) -> dict[str, Any]:
        for v in self.versions():
            if v["version"] == number:
                return v
        raise ValidationError("Cette version du plan n'existe pas.")

    def power_references(self, calc_id: int) -> list[int]:
        out = []
        for v in self._rows():
            if v["status"] != "verrouille":
                continue
            c = v["content"]
            if c.get("power_calc") == calc_id or any(i.get("power_calc") == calc_id for i in c.get("analyses", [])):
                out.append(v["version"])
        return out

    def _known_ids(self, extra: list[dict[str, Any]] | None = None) -> set[str]:
        ids = {i["id"] for r in self._rows() for i in r["content"].get("analyses", [])}
        return ids

    # -------------------------------------------------------------- écriture
    def save(self, raw: Any) -> None:
        rows = self._rows()
        content = clean_plan(raw, self._known_ids(), self._power_exists)
        now = now_iso()
        text = json.dumps(content, ensure_ascii=False)
        if not rows:
            self._conn.execute("INSERT INTO plan_versions (version, status, content, created_at, updated_at) "
                               "VALUES (1, 'brouillon', ?, ?, ?)", (text, now, now))
            self._log("plan", "Plan d'analyse commencé (version 1, brouillon)")
            return
        last = rows[-1]
        if last["content"] == content:
            return
        if last["status"] == "brouillon":
            self._conn.execute("UPDATE plan_versions SET content = ?, updated_at = ? WHERE version = ?",
                               (text, now, last["version"]))
            self._mark_dirty()
            return
        number = last["version"] + 1
        self._conn.execute("INSERT INTO plan_versions (version, status, content, created_at, updated_at) "
                           "VALUES (?, 'brouillon', ?, ?, ?)", (number, text, now, now))
        self._log("plan", f"Plan d'analyse modifié après verrouillage : version {number} en brouillon")

    def lock(self, reason: Any) -> int:
        rows = self._rows()
        if not rows or rows[-1]["status"] != "brouillon":
            raise ValidationError("Il n'y a pas de brouillon du plan à verrouiller.")
        last = rows[-1]
        reason = _text(reason, "Motif de la modification", REASON_MAX)
        if last["version"] > 1 and not reason:
            raise ValidationError("Indiquez le motif de la modification du plan : il sera conservé dans "
                                  "l'historique et dans le rapport.")
        content = last["content"]
        if not content["analyses"]:
            raise ValidationError("Ajoutez au moins une analyse prévue avant de verrouiller le plan.")
        if last["version"] > 1 and not diff(rows[-2]["content"], content):
            raise ValidationError("Cette version est identique à la précédente : rien à verrouiller.")
        missing = [i["id"] for i in content["analyses"] if not item_variables(i)]
        if missing:
            raise ValidationError(f"Indiquez les variables de l'analyse prévue {', '.join(missing)} avant de "
                                  "verrouiller le plan.")
        for calc in [content.get("power_calc"), *(i.get("power_calc") for i in content["analyses"])]:
            if calc is not None and not self._power_exists(calc):
                raise ValidationError("Un calcul de puissance cité dans le plan n'existe plus.")
        now = now_iso()
        self._conn.execute("UPDATE plan_versions SET status = 'verrouille', locked_at = ?, updated_at = ?, "
                           "change_reason = ? WHERE version = ?", (now, now, reason, last["version"]))
        self._log("plan", f"Plan d'analyse verrouillé (version {last['version']})"
                          + (", motif enregistré" if reason else ""), {"version": last["version"]})
        return last["version"]

    def discard_draft(self) -> None:
        rows = self._rows()
        if not rows or rows[-1]["status"] != "brouillon":
            raise ValidationError("Il n'y a pas de brouillon du plan à abandonner.")
        number = rows[-1]["version"]
        self._conn.execute("DELETE FROM plan_versions WHERE version = ?", (number,))
        self._log("plan", "Brouillon du plan abandonné" + (f" (retour à la version {number - 1})" if number > 1
                                                           else ""))

    # -------------------------------------------------------------- rattachement des analyses
    def link(self, item_id: Any, method: str, variable_names: list[str], reason: Any) -> dict[str, Any]:
        """Rattache une analyse lancée maintenant à une analyse prévue d'une version verrouillée."""
        locked = self.latest_locked()
        if locked is None:
            raise ValidationError("Aucun plan d'analyse verrouillé : l'analyse ne peut pas être rattachée au plan.")
        items = {i["id"]: i for i in locked["content"]["analyses"]}
        if not isinstance(item_id, str) or item_id not in items:
            raise ValidationError("Analyse prévue inconnue dans le plan verrouillé.")
        item = items[item_id]
        reason = _text(reason, "Raison de l'écart au plan", REASON_MAX)
        deviations = []
        if item["method"] != method:
            deviations.append(f"méthode prévue : {catalog.METHODS[item['method']]['label']}")
        planned = {n.casefold() for n in item_variables(item)}
        actual = {n.casefold() for n in variable_names}
        if planned != actual:
            deviations.append(f"variables prévues : {', '.join(item_variables(item))}")
        if deviations and not reason:
            raise ValidationError(f"Cette analyse s'écarte de l'analyse prévue {item_id} ({'; '.join(deviations)}) : "
                                  "indiquez la raison de l'écart.")
        return {"item": item_id, "version": locked["version"], "locked_at": locked["locked_at"],
                "planned": describe_item(item), "planned_method": item["method"],
                "planned_variables": item_variables(item), "deviation": bool(deviations),
                "deviations": deviations, "reason": reason if deviations else ""}


def classify(analysis: dict[str, Any], plan: dict[str, Any]) -> dict[str, str]:
    """Statut d'une analyse vis-à-vis du plan : prévue, prévue avec écart, hors plan, sans plan."""
    link = (analysis.get("choice") or {}).get("plan")
    if plan.get("locked") is None:
        return {"status": "sans_plan", "label": "Aucun plan d'analyse verrouillé"}
    if link:
        if link.get("deviation"):
            return {"status": "ecart", "label": f"Prévue au plan ({link['item']}, version {link['version']}), "
                                                f"avec un écart justifié"}
        return {"status": "prevue", "label": f"Prévue au plan ({link['item']}, version {link['version']})"}
    first = plan.get("first_lock_at")
    if first and analysis["created_at"] < first:
        return {"status": "avant_plan", "label": "Réalisée avant le verrouillage du plan"}
    return {"status": "hors_plan", "label": "Non prévue au plan : ajoutée après consultation des données"}


def power_gap(result: dict[str, Any], n_used: int) -> str | None:
    """Compare l'effectif utilisé aux effectifs nécessaires d'un calcul de taille d'échantillon, effet par effet.

    Renvoie None si l'effectif suffit pour tous les effets envisagés, sinon une phrase détaillée.
    """
    if result.get("mode") != "sample_size":
        return None
    short = [r for r in result["rows"] if n_used < r["n_total"]]
    if not short:
        return None
    enough = [r for r in result["rows"] if n_used >= r["n_total"]]
    text = (f"{n_used} observation(s) utilisée(s) : insuffisant pour "
            + ", ".join(f"l'effet {r['effect_text']} ({r['n_total']} nécessaires)" for r in short))
    if enough:
        text += " ; suffisant pour " + ", ".join(f"l'effet {r['effect_text']} ({r['n_total']})" for r in enough)
    return text + "."
