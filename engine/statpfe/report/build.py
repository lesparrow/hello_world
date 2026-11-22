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
        if s["population"]:
            self.population()
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
            rows.append([str(self.number[a["id"]]), a["title"], a["method_label"],
                         ", ".join(a["result"].get("variables", [])), "; ".join(opts) or "—",
                         f"{a['dataset_name'] or '—'}, {a['version_name']}"])
        self.table("Analyses réalisées", ["N°", "Analyse", "Méthode", "Variables", "Options", "Données"], rows,
                   numeric=[True, False, False, False, False, False])
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
                ["État des données", a["status_label"]],
            ]
            self.add(Table(None, f"{self.label(a)} : {a['title']}", ["Élément", "Valeur"], rows, key_value=True))

    def journal(self) -> None:
        self.h1("Journal méthodologique", annex=True)
        entries = list(reversed(self.p.journal(limit=2000)))
        self.table("Journal du projet (ordre chronologique)", ["Date", "Action", "Résumé"],
                   [[e.at[:16].replace("T", " "), e.action, e.summary] for e in entries])


def build(project, options: dict[str, Any], today: date | None = None, draw: bool = True) -> Document:
    return Builder(project, options, today, draw).build()


__all__ = ["build", "french_date", "is_descriptive"]
