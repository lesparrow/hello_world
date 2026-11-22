"""Construction du contenu du rapport à partir du projet.

Tout le contenu vient du projet : fiche de l'étude, dictionnaires, versions des
données et résultats enregistrés. Aucun nombre n'est recalculé ni inventé ici ;
les sections que seul l'auteur peut écrire (discussion, conclusion) sont
explicitement marquées « à rédiger ».
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from statpfe import __version__
from statpfe.report import charts
from statpfe.report.fmt import NBSP, cell, fixed, stat
from statpfe.report.model import (
    Bullets, Cover, Document, Figure, Heading, PageBreak, Para, Run, Table, Toc,
)
from statpfe.core.plan import ALTERNATIVES as PLAN_ALT
from statpfe.core.plan import ROLES as PLAN_ROLES
from statpfe.core.plan import classify, describe_item, item_variables, power_gap
from statpfe.report.options import COVER_FIELDS, TEMPLATES
from statpfe.stats.catalog import METHODS

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]
DIAG_LABEL = {"bloquant": "Erreur bloquante", "important": "Avertissement important",
              "methodologique": "Avertissement méthodologique", "information": "Information"}
ALTERNATIVE = {"two-sided": "bilatérale", "less": "unilatérale (inférieur)", "greater": "unilatérale (supérieur)"}
WIDE = 8  # au-delà, un tableau de résultats est transposé
DISCLAIMER = ("Rapport préparé avec STATPFE : document de travail à relire et à réviser par l'auteur et son "
              "encadrement. Il n'a fait l'objet d'aucune validation scientifique.")
INTERPRETATION_NOTE = ("Lecture produite par des règles fixes à partir des valeurs calculées, sans intelligence "
                       "artificielle. À vérifier et à reformuler par l'auteur.")


def french_date(d: date) -> str:
    return f"{d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]} {d.year}"


def is_descriptive(analysis: dict[str, Any]) -> bool:
    return METHODS.get(analysis["method"], {}).get("family") == "describe"


def _paragraphs(text: str, placeholder: str) -> list[Para]:
    chunks = [c.strip() for c in text.replace("\r\n", "\n").split("\n\n") if c.strip()]
    if not chunks:
        return [Para.of(placeholder, "placeholder")]
    return [Para.of(" ".join(line.strip() for line in c.split("\n"))) for c in chunks]


def _short(fp: str | None) -> str:
    return (fp or "")[:12]


class Builder:
    def __init__(self, project, options: dict[str, Any], today: date | None = None, draw: bool = True):
        self.p = project
        self.draw = draw  # False : plan du rapport seulement, sans dessiner les figures
        self.o = options
        self.sections = options["sections"]
        self.today = today or date.today()
        self.study = project.study
        chosen = [project.analyses.get(i) for i in options["analyses"]]
        # Numérotation dans l'ordre d'apparition : descriptives puis inférentielles, dans l'ordre choisi.
        self.analyses: list[dict[str, Any]] = ([a for a in chosen if is_descriptive(a)]
                                               + [a for a in chosen if not is_descriptive(a)])
        self.number = {a["id"]: i + 1 for i, a in enumerate(self.analyses)}
        self.plan = project.plan.get()
        self.plan["first_lock_at"] = project.plan.first_lock_at()
        self.locked = self.plan["locked"]
        known_power = {c["id"] for c in project.power.list()}
        self.power_calcs = [project.power.get(i) for i in (options.get("power") or []) if i in known_power]
        self.power_number = {c["id"]: k + 1 for k, c in enumerate(self.power_calcs)}
        self.status = {a["id"]: classify(a, self.plan) for a in self.analyses}
        self.doc = Document(
            title=self.study.title,
            footer=f"STATPFE {__version__} · {french_date(self.today)} · Document de travail à réviser, non validé "
                   "scientifiquement")
        self.chapter = 0
        self.sub = 0
        self.annex = 0
        self.tables = 0
        self.figures = 0
        self._datasets: dict[int, dict[str, Any] | None] = {}
        self.ai_used: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ outils
    def add(self, *blocks) -> None:
        self.doc.blocks.extend(blocks)

    def h1(self, text: str, annex: bool = False) -> None:
        if annex:
            self.annex += 1
            self.add(Heading(1, text, f"Annexe {chr(64 + self.annex)}."))
        else:
            self.chapter += 1
            self.sub = 0
            self.add(Heading(1, text, f"{self.chapter}."))

    def h2(self, text: str) -> None:
        self.sub += 1
        self.add(Heading(2, text, f"{self.chapter}.{self.sub}." if self.chapter and not self.annex else ""))

    def table(self, caption: str, columns: list[str], rows: list[list[str]], *, note: str = "", source: str = "",
              numeric: list[bool] | None = None) -> None:
        self.tables += 1
        self.add(Table(self.tables, caption, columns, rows, note, source, numeric or []))

    def dataset(self, dataset_id: int) -> dict[str, Any] | None:
        if dataset_id not in self._datasets:
            try:
                self._datasets[dataset_id] = self.p.data.get(dataset_id)
            except Exception:  # jeu supprimé depuis l'analyse
                self._datasets[dataset_id] = None
        return self._datasets[dataset_id]

    def source(self, a: dict[str, Any]) -> str:
        return (f"Source : jeu « {a['dataset_name'] or 'supprimé'} », {a['version_name']}, analyse n° "
                f"{self.number[a['id']]} du rapport (empreinte des données {_short(a['data_fingerprint'])}…).")

    def label(self, a: dict[str, Any]) -> str:
        return f"Analyse {self.number[a['id']]}"

    def used_datasets(self) -> list[int]:
        ids = []
        for a in self.analyses:
            if a["dataset_id"] not in ids and self.dataset(a["dataset_id"]) is not None:
                ids.append(a["dataset_id"])
        if not ids:
            ids = [d["id"] for d in self.p.data.list()]
        return ids

    # ------------------------------------------------------------------ document
    def build(self) -> Document:
        s = self.sections
        if s["cover"]:
            self.cover()
        if s["toc"]:
            self.add(Toc(), PageBreak())
        if s["introduction"]:
            self.introduction()
        if s["hypotheses"]:
            self.hypotheses()
        if s.get("plan"):
            self.plan_section()
        if s["population"]:
            self.population()
        if s.get("power"):
            self.power_section()
        if s["variables"]:
            self.variables()
        if s["preparation"]:
            self.preparation()
        if s["methodology"]:
            self.methodology()
        if s["descriptive"]:
            self.results("Statistiques descriptives", [a for a in self.analyses if is_descriptive(a)])
        if s["inferential"]:
            self.results("Analyses inférentielles", [a for a in self.analyses if not is_descriptive(a)])
        if s["discussion"]:
            self.discussion()
        if s["limits"]:
            self.limits()
        if s["conclusion"]:
            self.h1("Conclusion")
            self.add(Para.of("[À rédiger par l'auteur : réponse à la problématique, principaux résultats rappelés "
                             "avec prudence, perspectives.]", "placeholder"))
        if s["annex_traceability"]:
            self.traceability()
        if s["annex_journal"]:
            self.journal()
        return self.doc

    def cover(self) -> None:
        t = TEMPLATES[self.o["template"]]
        fields = [(COVER_FIELDS[k], v) for k, v in self.o["cover"].items() if v and k not in ("city", "year")]
        place = ", ".join(v for v in (self.o["cover"].get("city"), french_date(self.today)) if v)
        if self.o["cover"].get("year"):
            fields.append(("Année universitaire", self.o["cover"]["year"]))
        self.add(Cover(t["document"], self.study.title, fields, place, DISCLAIMER), PageBreak())

    def introduction(self) -> None:
        self.h1("Présentation de l'étude")
        self.h2("Problématique")
        self.add(*_paragraphs(self.study.problem_statement,
                              "[Problématique non renseignée dans la fiche « Étude » de STATPFE.]"))
        self.h2("Objectifs")
        self.add(*_paragraphs(self.study.objectives, "[Objectifs non renseignés dans la fiche « Étude ».]"))

    def linked(self, index: int) -> list[dict[str, Any]]:
        return [a for a in self.analyses if (a.get("choice") or {}).get("hypothesis") == index]

    def hypotheses(self) -> None:
        self.h1("Hypothèses")
        if not self.study.hypotheses:
            self.add(Para.of("[Aucune hypothèse n'est enregistrée dans la fiche « Étude ».]", "placeholder"))
            return
        items = []
        for i, h in enumerate(self.study.hypotheses):
            tested = self.linked(i)
            run = [Run(f"H{i + 1}. ", bold=True), Run(h)]
            if tested:
                run.append(Run(" Mise à l'épreuve par : " + ", ".join(
                    f"{self.label(a)} ({a['method_label']})" for a in tested) + ".", italic=True))
            else:
                run.append(Run(" Aucune analyse de ce rapport n'est liée à cette hypothèse.", italic=True))
            items.append(run)
        self.add(Bullets(items))

    def population(self) -> None:
        self.h1("Population et échantillonnage")
        self.h2("Population étudiée")
        self.add(*_paragraphs(self.study.population, "[Population non décrite dans la fiche « Étude ».]"))
        self.h2("Méthode d'échantillonnage")
        self.add(*_paragraphs(self.study.sampling_method,
                              "[Méthode d'échantillonnage non décrite dans la fiche « Étude ».]"))
        sizes = []
        for ds_id in self.used_datasets():
            ds = self.dataset(ds_id)
            if ds:
                sizes.append(f"{ds['original']['rows']} observation(s) dans le jeu « {ds['name']} »")
        planned = self.study.planned_sample_size
        text = (f"Taille d'échantillon prévue : {planned}. " if planned else "Taille d'échantillon prévue : non "
                "renseignée. ")
        if sizes:
            text += "Données recueillies : " + " ; ".join(sizes) + "."
        self.add(Para.of(text))

    def variables(self) -> None:
        self.h1("Description des variables")
        self.add(Para.of("Le dictionnaire ci-dessous reprend le type, le niveau de mesure et le rôle déclarés pour "
                         "chaque variable. Les variables identifiantes y figurent par leur nom seulement : leurs "
                         "valeurs ne sont jamais reproduites dans ce rapport."))
        for ds_id in self.used_datasets():
            ds = self.dataset(ds_id)
            if ds is None:
                continue
            missing = {q["key"]: q for q in ds["quality"]["variables"]}
            rows = []
            for v in ds["variables"]:
                q = missing.get(v["key"], {})
                m = q.get("missing", 0)
                rows.append([v["name"], v["type_label"], v["level_label"], v["role_label"],
                             f"{m} ({fixed(q.get('missing_rate', 0) * 100, 1)}{NBSP}%)"])
            self.table(f"Dictionnaire des variables du jeu « {ds['name']} »",
                       ["Variable", "Type", "Niveau de mesure", "Rôle", "Valeurs manquantes"], rows,
                       note=f"{ds['original']['rows']} observations, {ds['original']['columns']} variables "
                            "(données d'origine).",
                       source=f"Source : fichier « {ds['source']['file_name']} », importé le "
                              f"{ds['source']['imported_at'][:10]}.",
                       numeric=[False, False, False, False, True])

    def preparation(self) -> None:
        self.h1("Préparation des données")
        used_versions = {(a["dataset_id"], a["version_id"]) for a in self.analyses}
        for ds_id in self.used_datasets():
            ds = self.dataset(ds_id)
            if ds is None:
                continue
            src = ds["source"]
            self.h2(f"Jeu de données « {ds['name']} »")
            self.add(Para.of(
                f"Fichier source « {src['file_name']} » importé le {src['imported_at'][:10]} "
                f"({ds['original']['rows']} lignes, {ds['original']['columns']} colonnes). Le fichier d'origine est "
                f"conservé à l'identique dans le projet (empreinte SHA-256 {src['sha256'][:12]}…) ; les "
                "transformations sont appliquées à des versions de travail, sans modifier l'original."))
            versions = [v for v in ds["versions"] if (ds_id, v["id"]) in used_versions] or []
            if not versions:
                self.add(Para.of("Les analyses de ce rapport portent sur les données d'origine, sans transformation."))
            for v in versions:
                rows = [[str(st["index"] + 1), st.get("description", st["op"]),
                         "—" if st.get("rows_before") is None else str(st["rows_before"]),
                         "—" if st.get("rows_after") is None else str(st["rows_after"])] for st in v["steps"]]
                if rows:
                    self.table(f"Étapes de préparation de la version « {v['name']} »",
                               ["Étape", "Opération", "Lignes avant", "Lignes après"], rows,
                               note=f"Version obtenue : {v['rows']} lignes, {v['columns']} variables."
                               if v["rows"] is not None else "Cette version doit être corrigée.",
                               numeric=[True, False, True, True])
                else:
                    self.add(Para.of(f"La version « {v['name']} » ne comporte aucune transformation."))

    def methodology(self) -> None:
        self.h1("Méthodologie statistique")
        envs = {json.dumps(a["environment"], sort_keys=True) for a in self.analyses}
        env = self.analyses[0]["environment"] if self.analyses else {}
        software = (f"Les calculs ont été réalisés avec STATPFE {env.get('statpfe', __version__)} (Python "
                    f"{env.get('python', '?')}, NumPy {env.get('numpy', '?')}, SciPy {env.get('scipy', '?')}, "
                    f"pandas {env.get('pandas', '?')}).")
        if len(envs) > 1:
            software += " Certaines analyses ont été calculées avec d'autres versions ; elles sont précisées en annexe."
        software += (" Les procédures de calcul de STATPFE sont comparées automatiquement aux fonctions de base du "
                     "logiciel R sur un ensemble de cas de référence à chaque modification du logiciel.")
        self.add(Para.of(software))
        if not self.analyses:
            self.add(Para.of("[Aucune analyse n'est incluse dans ce rapport.]", "placeholder"))
            return
        rows = []
        for a in self.analyses:
            pr = a["params"]
            opts = []
            if "alternative" in METHODS.get(a["method"], {}).get("params", []):
                opts.append(f"hypothèse {ALTERNATIVE.get(pr.get('alternative', 'two-sided'), 'bilatérale')}")
            if "conf_level" in METHODS.get(a["method"], {}).get("params", []):
                opts.append(f"IC à {fixed(float(pr.get('conf_level', 0.95)) * 100, 0)}{NBSP}%")
            row = [str(self.number[a["id"]]), a["title"], a["method_label"],
                   ", ".join(a["result"].get("variables", [])), "; ".join(opts) or "—",
                   f"{a['dataset_name'] or '—'}, {a['version_name']}"]
            if self.locked:
                row.append(self.plan_short(a))
            rows.append(row)
        columns = ["N°", "Analyse", "Méthode", "Variables", "Options", "Données"] + (["Plan"] if self.locked else [])
        self.table("Analyses réalisées", columns, rows, numeric=[True] + [False] * (len(columns) - 1),
                   note="Plan : « prévue » = rattachée, au moment du calcul, à une analyse d'un plan déjà verrouillé ; "
                        "« hors plan » = ajoutée après consultation des données." if self.locked else "")
        alts = {a["params"].get("alternative", "two-sided") for a in self.analyses
                if "alternative" in METHODS.get(a["method"], {}).get("params", [])}
        levels = {float(a["params"].get("conf_level", 0.95)) for a in self.analyses
                  if "conf_level" in METHODS.get(a["method"], {}).get("params", [])}
        if alts or levels:
            parts = []
            if alts == {"two-sided"}:
                parts.append("Tous les tests sont bilatéraux")
            elif alts:
                parts.append("Le caractère bilatéral ou unilatéral de chaque test est indiqué dans le tableau")
            if len(levels) == 1:
                lv = levels.pop()
                parts.append(f"le seuil de signification est de {fixed((1 - lv) * 100, 0)}{NBSP}% et les "
                             f"intervalles de confiance sont à {fixed(lv * 100, 0)}{NBSP}%")
            elif levels:
                parts.append("le niveau de confiance de chaque analyse est indiqué dans le tableau")
            self.add(Para.of(" ; ".join(parts) + "."))
        strategies = sorted({a["result"]["missing"]["strategy"] for a in self.analyses
                             if a["result"].get("missing") and a["result"]["missing"].get("strategy")})
        if strategies:
            self.add(Para.of("Valeurs manquantes : chaque analyse utilise les observations complètes pour les "
                             "variables concernées (les statistiques descriptives utilisent les valeurs disponibles "
                             "de chaque variable). Le nombre d'observations exclues est indiqué avec chaque résultat."))
        self.add(Para.of("Les tests de normalité et d'égalité des variances sont rapportés à titre indicatif ; le choix "
                         "des méthodes ne repose pas sur leur seule significativité."))
        choices = [a for a in self.analyses if (a.get("choice") or {}).get("mode") == "assistant"]
        if choices:
            self.h2("Choix des méthodes")
            self.add(Para.of("Les méthodes ont été choisies avec l'assistant méthodologique de STATPFE, dont les règles "
                             "fixes tiennent compte du type des variables, du plan d'étude, des effectifs et de la forme "
                             "des distributions."))
            items = []
            for a in choices:
                c = a["choice"]
                run = [Run(f"{self.label(a)} ({a['title']}). ", bold=True)]
                if c.get("followed"):
                    run.append(Run(f"Méthode recommandée et retenue : {c.get('chosen_label')}. "
                                   + " ".join(c.get("recommendation_reasons") or [])))
                else:
                    run.append(Run(f"Méthode recommandée : {c.get('recommended_label') or 'aucune'} ; méthode retenue : "
                                   f"{c.get('chosen_label')}. Justification de l'auteur : {c.get('reason') or '—'}"))
                items.append(run)
            self.add(Bullets(items))

    def results(self, title: str, analyses: list[dict[str, Any]]) -> None:
        self.h1(title)
        if not analyses:
            self.add(Para.of("[Aucune analyse de ce type n'est incluse dans ce rapport.]", "placeholder"))
            return
        for a in analyses:
            self.analysis(a)

    def analysis(self, a: dict[str, Any]) -> None:
        r = a["result"]
        c = a.get("choice") or {}
        self.h2(f"{self.label(a)} : {a['title']}")
        context = [f"Méthode : {a['method_label']}.",
                   f"Données : jeu « {a['dataset_name'] or 'supprimé'} », {a['version_name']}"
                   + (f", n = {r['n_used']} observation(s) utilisée(s)." if r.get("n_used") is not None else ".")]
        if c.get("purpose_label"):
            context.append(f"Nature : {c['purpose_label'].lower()}.")
        if c.get("hypothesis") is not None and c.get("hypothesis_text"):
            context.append(f"Hypothèse mise à l'épreuve : H{c['hypothesis'] + 1}.")
        if self.locked:
            context.append(f"Plan d'analyse : {self.status[a['id']]['label'][0].lower()}"
                           f"{self.status[a['id']]['label'][1:]}.")
            link = c.get("plan") or {}
            if link.get("deviation"):
                context.append(f"Écart au plan ({'; '.join(link.get('deviations') or [])}), raison : "
                               f"{link.get('reason') or '—'}.")
        self.add(Para.of(" ".join(context), "note"))
        if r.get("missing") and r["missing"].get("text"):
            self.add(Para.of(r["missing"]["text"], "note"))
        summary = r.get("summary") or []
        if summary:
            self.table(f"Résultats principaux : {a['title']}", ["Indicateur", "Valeur"],
                       [[s["label"], stat(s.get("value"), s.get("kind", "value"), s.get("digits", 3))]
                        for s in summary],
                       source=self.source(a), numeric=[False, True])
        for t in r.get("tables") or []:
            kinds = t.get("kinds") or []
            rows = [[cell(v, kinds[j] if j < len(kinds) else None) for j, v in enumerate(row)] for row in t["rows"]]
            columns = list(t["columns"])
            numeric = [(kinds[j] if j < len(kinds) else "num") in ("int", "num", "pct") and j > 0
                       for j in range(len(columns))]
            if len(columns) > WIDE and 0 < len(rows) <= WIDE - 2:
                # Tableau trop large pour une page : indicateurs en lignes, séries en colonnes.
                lead = sum(1 for k in kinds[:3] if k == "text") or 1
                heads = [" · ".join(r[:lead]) for r in rows]
                columns, rows = ["Indicateur"] + heads, [[columns[j]] + [r[j] for r in rows]
                                                          for j in range(lead, len(columns))]
                numeric = [False] + [True] * len(heads)
            self.table(t["title"], columns, rows, note=t.get("note", ""), source=self.source(a), numeric=numeric)
        if self.o["figures"]:
            for ch in r.get("charts") or []:
                self.figures += 1
                png = charts.render(ch) if self.draw else b""
                self.add(Figure(self.figures, ch["title"], png, charts.describe(ch), self.source(a)))
        if r.get("interpretation"):
            self.add(Para([Run("Lecture. ", bold=True)] + [Run(" ".join(r["interpretation"]))]))
            self.add(Para.of(INTERPRETATION_NOTE, "note"))
        diags = [d for d in r.get("diagnostics") or [] if d["level"] != "information"]
        if diags:
            self.add(Para([Run("Diagnostics", bold=True)]))
            self.add(Bullets([[Run(f"{DIAG_LABEL.get(d['level'], d['level'])} : ", bold=True),
                               Run(d["title"] + (f" {d['detail']}" if d.get("detail") else ""))] for d in diags]))
        if self.o.get("ai_texts", True):
            for t in self.p.ai_texts.kept(a["id"]):
                self.ai_text(t)

    def ai_text(self, t: dict[str, Any]) -> None:
        """Texte retenu par l'auteur, toujours signalé comme rédigé avec l'aide d'une IA."""
        self.ai_used.append(t)
        where = ("Texte rédigé avec l'aide de Claude (service en ligne d'Anthropic, via Claude Code)"
                 if t["provider"] == "claude_code" else "Texte rédigé avec l'aide d'une IA locale")
        self.add(Para([Run(where, bold=True),
                       Run(f" ({t['task_label'].lower()} ; modèle {t['model']} ; proposition du "
                           f"{_fr_date(t['created_at'])}), relu et retenu par l'auteur"
                           + (" puis modifié" if t["edited"] else "") + ". Il ne remplace pas le jugement de "
                           "l'auteur ni celui de l'encadrant.", italic=True)], "ai"))
        bullets: list[list[Run]] = []
        for line in [x.strip() for x in t["text"].split("\n")]:
            if line.startswith(("- ", "• ", "* ")):
                bullets.append([Run(line[2:].strip())])
                continue
            if bullets:
                self.add(Bullets(bullets))
                bullets = []
            if line:
                self.add(Para([Run(line)], "ai"))
        if bullets:
            self.add(Bullets(bullets))

    # ------------------------------------------------------------------ plan d'analyse
    def plan_short(self, a: dict[str, Any]) -> str:
        st = self.status[a["id"]]
        link = (a.get("choice") or {}).get("plan") or {}
        return {"prevue": f"Prévue ({link.get('item')})", "ecart": f"Prévue ({link.get('item')}), écart justifié",
                "avant_plan": "Avant le plan", "hors_plan": "Hors plan"}.get(st["status"], "—")

    def realised(self, item_id: str) -> list[dict[str, Any]]:
        return [a for a in self.analyses if ((a.get("choice") or {}).get("plan") or {}).get("item") == item_id]

    def plan_section(self) -> None:
        self.h1("Plan d'analyse")
        locked = self.locked
        if locked is None:
            current = self.plan["current"]
            text = ("Aucun plan d'analyse n'a été défini dans STATPFE." if current is None else
                    f"Le plan d'analyse est en brouillon (version {current['version']}) et n'a pas été verrouillé : il "
                    "ne permet pas de distinguer les analyses prévues des analyses exploratoires.")
            self.add(Para.of(text), Para.of("[À compléter par l'auteur si un plan a été établi en dehors de STATPFE "
                                            "(protocole, préenregistrement).]", "placeholder"))
            return
        c = locked["content"]
        lock_date = locked["locked_at"][:10]
        first_analysis = min((a["created_at"] for a in self.p.analyses.list()), default=None)
        imports = [d["imported_at"] for d in self.p.data.list()]
        first_lock = self.plan["first_lock_at"]
        timing = []
        if imports:
            timing.append("avant l'import des données" if first_lock < min(imports) else "après l'import des données")
        if first_analysis is not None:
            timing.append("avant toute analyse" if first_lock < first_analysis else
                          "après le début des analyses")
        intro = (f"Le plan d'analyse a été verrouillé pour la première fois le {_fr_date(first_lock)}"
                 + (f" ({' et '.join(timing)})" if timing else "") + ". ")
        intro += (f"La version présentée ici est la version {locked['version']}, verrouillée le {_fr_date(lock_date)}."
                  if locked["version"] > 1 or len(self.plan["versions"]) > 1 else "Il n'a pas été modifié depuis.")
        self.add(Para.of(intro))
        if self.plan["current"]["status"] == "brouillon":
            self.add(Para.of(f"Une version {self.plan['current']['version']} est en préparation (brouillon non "
                             "verrouillé) : elle n'est pas reprise dans ce rapport.", "note"))
        self.h2("Objectifs et hypothèses")
        self.add(*_paragraphs(c["objectives"], "[Objectifs non renseignés dans le plan.]"))
        if c["hypotheses"]:
            self.add(Para.of("Hypothèses du plan (numérotées P1, P2… pour les distinguer de celles de la fiche de "
                             "l'étude) :", "note"))
            self.add(Bullets([[Run(f"P{i + 1}. ", bold=True), Run(h)] for i, h in enumerate(c["hypotheses"])]))
        self.h2("Variables")
        self.add(Para([Run("Variables principales : ", bold=True),
                       Run(", ".join(c["primary_variables"]) or "non précisées.")]),
                 Para([Run("Variables secondaires : ", bold=True),
                       Run(", ".join(c["secondary_variables"]) or "aucune.")]))
        self.h2("Analyses prévues")
        rows = []
        for item in c["analyses"]:
            done = self.realised(item["id"])
            hyp = f"P{item['hypothesis'] + 1}" if item.get("hypothesis") is not None else "—"
            rows.append([item["id"], METHODS[item["method"]]["label"], ", ".join(item_variables(item)) or "—", hyp,
                         PLAN_ROLES[item["role"]], PLAN_ALT[item["alternative"]],
                         ", ".join(self.label(a) for a in done) if done else "Non présente dans ce rapport"])
        self.table(f"Analyses prévues au plan (version {locked['version']})",
                   ["N°", "Méthode", "Variables", "Hyp.", "Rôle", "Test", "Réalisée"], rows,
                   note=f"Seuil de signification prévu : {fixed(c['alpha'], 3).rstrip('0').rstrip(',')}.")
        details = []
        for i in c["analyses"]:
            parts = [i["description"].rstrip(". ")] if i["description"] else []
            if i.get("power_calc") in self.power_number:
                parts.append(f"effectif justifié par le calcul de puissance n° {self.power_number[i['power_calc']]}")
            if parts:
                details.append([Run(f"{i['id']} : ", bold=True), Run(" ; ".join(parts) + ".")])
        if details:
            self.add(Bullets(details))
        self.h2("Règles fixées à l'avance")
        for label, key, empty in (("Critères d'exclusion", "exclusion_criteria", "non précisés"),
                                  ("Valeurs manquantes", "missing_values", "traitement non précisé"),
                                  ("Tests multiples", "multiplicity", "aucune correction prévue"),
                                  ("Analyses exploratoires envisagées", "exploratory", "aucune")):
            self.add(Para([Run(f"{label} : ", bold=True), Run(c[key] or f"{empty}.")]))
        if c.get("sample_size") or c.get("power_calc"):
            txt = f"Taille d'échantillon prévue : {c['sample_size']}." if c.get("sample_size") else ""
            if c.get("power_calc") in self.power_number:
                txt += f" Justification : calcul de puissance n° {self.power_number[c['power_calc']]}."
            elif c.get("power_calc"):
                txt += " Justification : un calcul de puissance enregistré (non inclus dans ce rapport)."
            self.add(Para.of(txt.strip()))
        if len(self.plan["versions"]) > 1:
            self.h2("Historique des versions")
            hist = []
            for v in self.plan["versions"]:
                hist.append([str(v["version"]), "Verrouillée" if v["status"] == "verrouille" else "Brouillon",
                             v["locked_at"][:16].replace("T", " ") if v["locked_at"] else "—",
                             v["change_reason"] or ("Version initiale" if v["version"] == 1 else "—"),
                             "; ".join(ch["detail"] for ch in v["changes"]) or "—"])
            self.table("Versions du plan d'analyse", ["V.", "État", "Verrouillée le", "Motif", "Changements"],
                       hist, numeric=[True, False, False, False, False])

    def plan_limits(self) -> list[list[Run]]:
        items: list[list[Run]] = []
        if self.locked is None:
            if self.analyses and any(not is_descriptive(a) for a in self.analyses):
                items.append([Run("Plan d'analyse : ", bold=True),
                              Run("aucun plan verrouillé avant les analyses ; les analyses prévues ne peuvent pas être "
                                  "distinguées des analyses exploratoires.")])
            return items
        for a in self.analyses:
            st = self.status[a["id"]]
            if st["status"] == "hors_plan" and not is_descriptive(a):
                items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                              Run("non prévue au plan d'analyse, ajoutée après consultation des données ; à présenter "
                                  "comme exploratoire.")])
            elif st["status"] == "avant_plan" and not is_descriptive(a):
                items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                              Run("réalisée avant le verrouillage du plan d'analyse.")])
            elif st["status"] == "ecart":
                link = a["choice"]["plan"]
                items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                              Run(f"écart à l'analyse prévue {link['item']} ({'; '.join(link['deviations'])}) ; raison : "
                                  f"{link.get('reason') or '—'}")])
        for item in self.locked["content"]["analyses"]:
            if not self.realised(item["id"]):
                items.append([Run(f"{item['id']} : ", bold=True),
                              Run(f"analyse prévue au plan non présente dans ce rapport ({describe_item(item)}).")])
        first_analysis = min((a["created_at"] for a in self.p.analyses.list()), default=None)
        for v in self.plan["versions"]:
            if v["status"] == "verrouille" and v["version"] > 1 and first_analysis and v["locked_at"] > first_analysis:
                items.append([Run(f"Plan d'analyse, version {v['version']} : ", bold=True),
                              Run(f"modifié après le début des analyses ; motif : {v['change_reason'] or '—'}.")])
        return items

    # ------------------------------------------------------------------ puissance
    def power_section(self) -> None:
        self.h1("Taille d'échantillon et puissance")
        if not self.power_calcs:
            self.add(Para.of("[Aucun calcul de puissance n'est inclus dans ce rapport. Justifiez ici la taille de "
                             "l'échantillon.]", "placeholder"))
            return
        self.add(Para.of("Les calculs suivants ont été réalisés avec STATPFE selon les formules de Cohen (1988), "
                         "identiques à celles du paquet R pwr. Une puissance est une estimation qui dépend entièrement "
                         "des hypothèses retenues, en particulier de l'effet attendu : elle ne garantit pas la validité "
                         "de l'étude."))
        for c in self.power_calcs:
            r = c["result"]
            k = self.power_number[c["id"]]
            self.h2(f"Calcul de puissance n° {k} : {c['title']}")
            src = (f"Source : calcul de puissance n° {k} du rapport, enregistré le {c['created_at'][:10]} "
                   f"(STATPFE {c['environment'].get('statpfe', '?')}, SciPy {c['environment'].get('scipy', '?')}).")
            self.add(Para([Run("Hypothèses du calcul. ", bold=True)]))
            self.add(Bullets([[Run(x)] for x in r["assumptions"]]))
            for t in r["tables"]:
                kinds = t.get("kinds") or []
                rows = [[cell(v, kinds[j] if j < len(kinds) else None) for j, v in enumerate(row)] for row in t["rows"]]
                self.table(t["title"], list(t["columns"]), rows, note=t.get("note", ""), source=src,
                           numeric=[(kinds[j] if j < len(kinds) else "num") in ("int", "num", "pct") and j > 0
                                    for j in range(len(t["columns"]))])
            if self.o["figures"]:
                for ch in r.get("charts") or []:
                    self.figures += 1
                    png = charts.render(ch) if self.draw else b""
                    self.add(Figure(self.figures, ch["title"], png, charts.describe(ch), src))
            self.add(Para([Run("Lecture. ", bold=True), Run(" ".join(r["interpretation"]))]))
            for d in r.get("diagnostics") or []:
                if d["level"] != "information":
                    self.add(Para([Run(f"{DIAG_LABEL.get(d['level'], d['level'])} : ", bold=True),
                                   Run(f"{d['title']}. {d.get('detail', '')}".strip())], "note"))
            self.add(Para.of(r["disclaimer"] + " Équivalent R : " + r["r_equivalent"] + ".", "note"))

    def power_limits(self) -> list[list[Run]]:
        items: list[list[Run]] = []
        if not self.locked:
            return items
        calcs = {c["id"]: c for c in self.power_calcs}
        for item in self.locked["content"]["analyses"]:
            calc = calcs.get(item.get("power_calc"))
            if calc is None or calc["result"]["mode"] != "sample_size":
                continue
            for a in self.realised(item["id"]):
                n = a["result"].get("n_used")
                gap = power_gap(calc["result"], n) if n is not None else None
                if gap:
                    items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                                  Run(f"{gap} Selon le calcul de puissance n° {self.power_number[calc['id']]}, la "
                                      "puissance est inférieure à celle visée pour les effets insuffisamment couverts.")])
        return items

    def discussion(self) -> None:
        self.h1("Discussion")
        guide = ("[À rédiger par l'auteur : confrontez chaque résultat aux hypothèses"
                 + (" (" + ", ".join(f"H{i + 1}" for i in range(len(self.study.hypotheses))) + ")"
                    if self.study.hypotheses else "")
                 + " et à la littérature ; distinguez la significativité statistique de l'importance pratique "
                   "(tailles d'effet) ; rappelez qu'un résultat non significatif ne prouve pas l'absence d'effet.]")
        self.add(Para.of(guide, "placeholder"))

    def limits(self) -> None:
        self.h1("Limites")
        items: list[list[Run]] = []
        inferential = [a for a in self.analyses if not is_descriptive(a)]
        if len(inferential) > 1:
            items.append([Run(f"{len(inferential)} tests statistiques sont présentés sans correction pour "
                              "comparaisons multiples : le risque qu'au moins un résultat soit significatif par hasard "
                              "est supérieur au seuil annoncé pour chaque test.")])
        for a in self.analyses:
            c = a.get("choice") or {}
            if c.get("purpose") == "exploratoire":
                items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                              Run("analyse exploratoire, à présenter comme une piste et non comme une confirmation.")])
            if c.get("mode") == "assistant" and not c.get("followed"):
                items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                              Run(f"méthode différente de la recommandation ({c.get('recommended_label') or 'aucune'}) ; "
                                  f"justification : {c.get('reason') or '—'}")])
            for m in c.get("missing_information") or []:
                items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                              Run(f"information signalée au moment du choix de la méthode : {m}")])
            for d in a["result"].get("diagnostics") or []:
                if d["level"] in ("bloquant", "important"):
                    items.append([Run(f"{self.label(a)} ({a['title']}) : ", bold=True),
                                  Run(f"{DIAG_LABEL[d['level']].lower()}, {d['title']}"
                                      + (f" {d['detail']}" if d.get("detail") else ""))])
        items.extend(self.plan_limits())
        items.extend(self.power_limits())
        for i, h in enumerate(self.study.hypotheses):
            if not self.linked(i):
                items.append([Run(f"H{i + 1} : ", bold=True),
                              Run("aucune analyse de ce rapport n'est explicitement liée à cette hypothèse.")])
        if items:
            self.add(Para.of("Points relevés automatiquement à partir des analyses et des choix enregistrés (les "
                             "avertissements méthodologiques figurent avec chaque analyse) :"))
            self.add(Bullets(items))
        self.add(Para.of("[À compléter par l'auteur : représentativité de l'échantillon, qualité des mesures, biais "
                         "possibles, portée des conclusions.]", "placeholder"))

    def traceability(self) -> None:
        self.h1("Traçabilité des analyses", annex=True)
        self.add(Para.of("Chaque analyse peut être recalculée à l'identique dans STATPFE à partir des informations "
                         "ci-dessous. L'empreinte SHA-256 identifie exactement les données utilisées."))
        for a in self.analyses:
            c = a.get("choice") or {}
            mode = {"assistant": "avec l'assistant méthodologique (règles " + str(c.get("rules_version")) + ")",
                    "direct": "directement par l'auteur"}.get(c.get("mode"), "non enregistré")
            rows = [
                ["Méthode", a["method_label"]],
                ["Paramètres", json.dumps(a["params"], ensure_ascii=False, sort_keys=True)],
                ["Données", f"jeu « {a['dataset_name'] or 'supprimé'} », {a['version_name']}"],
                ["Empreinte des données (SHA-256)", a["data_fingerprint"]],
                ["Date du calcul", a["created_at"][:19].replace("T", " ")],
                ["Environnement", " · ".join(f"{k} {v}" for k, v in a["environment"].items())],
                ["Choix de la méthode", mode],
                ["Plan d'analyse", self.status[a["id"]]["label"]],
                ["État des données", a["status_label"]],
                ["Textes rédigés avec l'aide d'une IA", self.ai_summary(a["id"])],
            ]
            self.add(Table(None, f"{self.label(a)} : {a['title']}", ["Élément", "Valeur"], rows, key_value=True))
        self.ai_annex()

    def ai_summary(self, analysis_id: int) -> str:
        texts = self.p.ai_texts.list(analysis_id)
        kept = [t for t in texts if t["status"] == "retenu"] if self.o.get("ai_texts", True) else []
        if not texts:
            return "aucun"
        return (f"{len(texts)} proposition(s) de l'IA, {len(kept)} retenue(s) dans ce rapport après relecture"
                + (f" (modèle(s) : {', '.join(sorted({t['model'] for t in kept}))})" if kept else ""))

    def ai_annex(self) -> None:
        self.add(Para([Run("Utilisation de l'intelligence artificielle. ", bold=True)]))
        if not self.ai_used:
            self.add(Para.of("Aucun texte de ce rapport n'a été rédigé avec l'aide d'une intelligence artificielle. "
                             "Les lectures des résultats sont produites par des règles fixes du logiciel."))
            return
        local = sorted({t["model"] for t in self.ai_used if t["provider"] != "claude_code"})
        cloud = sorted({t["model"] for t in self.ai_used if t["provider"] == "claude_code"})
        where = []
        if local:
            where.append(f"un modèle de langage exécuté sur l'ordinateur de l'auteur ({', '.join(local)})")
        if cloud:
            where.append(f"Claude, service en ligne d'Anthropic utilisé via Claude Code avec l'autorisation explicite "
                         f"de l'auteur ({', '.join(cloud)})")
        self.add(Para.of(
            f"{len(self.ai_used)} texte(s) de ce rapport, encadré(s) et signalé(s) comme tel(s), ont été rédigés avec "
            f"l'aide de {' et de '.join(where)}, puis relus et retenus "
            "par l'auteur. Le modèle n'a reçu que des résultats déjà calculés par STATPFE (jamais les données "
            "brutes) ; il n'a effectué aucun calcul. Un contrôle automatique a vérifié que chaque nombre de ces "
            "textes figure dans les résultats calculés. Ce contrôle ne garantit pas l'exactitude du propos : "
            "l'auteur en reste responsable."))

    def journal(self) -> None:
        self.h1("Journal méthodologique", annex=True)
        entries = list(reversed(self.p.journal(limit=2000)))
        self.table("Journal du projet (ordre chronologique)", ["Date", "Action", "Résumé"],
                   [[e.at[:16].replace("T", " "), e.action, e.summary] for e in entries])


def _fr_date(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        return french_date(date.fromisoformat(iso[:10]))
    except ValueError:
        return iso[:10]


def build(project, options: dict[str, Any], today: date | None = None, draw: bool = True) -> Document:
    return Builder(project, options, today, draw).build()


__all__ = ["build", "french_date", "is_descriptive"]
