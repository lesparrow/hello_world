"""Phase 10 : l'IA remplit l'application (copilote), le moteur vérifie, l'utilisateur valide.

Le modèle est remplacé par un serveur factice qui renvoie une réponse fixée par le test :
on vérifie ici le chemin complet (contexte transmis, lecture, validation, application,
mention « proposé par l'IA », validation, annulation), pas la qualité d'un vrai modèle.
"""

from __future__ import annotations

import json

import docx
import pytest

from fake_model_server import FakeModelServer
from statpfe.ai import copilot
from statpfe.rpc.server import Engine
from test_ai import call, call_error, wait
from test_report import options, project  # noqa: F401


@pytest.fixture
def ai(project):
    server = FakeModelServer()
    e = Engine()
    e.project = project
    call(e, "ai.update_settings", changes={"enabled": True, "base_url": server.url, "model": "modele-test:1b"})
    yield e, server
    server.close()


def run(e: Engine, server: FakeModelServer, action: str, reply, **params) -> dict:
    server.reply = reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
    snap = wait(e, call(e, "ai.copilot_start", action=action, params=params)["id"])
    assert snap["status"] == "termine", snap
    return snap["proposal"]


# ---------------------------------------------------------------------- étude
def test_study_is_filled_marked_validated_and_undone(ai, project):
    e, server = ai
    preview = call(e, "ai.copilot_preview", action="study",
                   params={"subject": "Je veux savoir si le tutorat aide les étudiants de L1."})
    assert "<sujet_etudiant>" in preview["text"] and "tutorat aide" in preview["text"]
    assert "Email" not in preview["text"] and "Nom (" not in preview["text"]  # identifiants jamais transmis
    reply = {"title": "Effet du tutorat sur la réussite en L1",
             "problem_statement": "Le tutorat est répandu. Améliore-t-il la réussite des étudiants de L1 ?",
             "objectives": "Comparer les notes des étudiants tutorés et non tutorés.",
             "population": "Étudiants de première année", "planned_sample_size": 120,
             "hypotheses": ["Les étudiants tutorés obtiennent de meilleures notes.",
                            "La satisfaction est liée au tutorat."]}
    p = run(e, server, "study", reply, subject="Je veux savoir si le tutorat aide les étudiants de L1.")
    assert p["status"] == "proposee" and p["action"] == "study"
    keys = {f["key"] for f in p["proposal"]["fields"]}
    assert keys == {"title", "problem_statement", "objectives", "population", "hypotheses"}
    # Taille d'échantillon inventée (absente du sujet) : écartée, avec explication.
    assert any("Taille d'échantillon" in i["text"] for i in p["issues"])
    # Ollama est contraint à répondre en JSON.
    assert server.requests[-1]["body"].get("format") == "json"

    res = call(e, "ai.copilot_apply", proposal_id=p["id"], selection={"fields": ["title", "hypotheses"]})
    assert res["proposal"]["status"] == "appliquee" and res["proposal"]["can_undo"]
    assert project.study.title == "Effet du tutorat sur la réussite en L1"
    assert len(project.study.hypotheses) == 2 and project.study.objectives == "Mesurer l'effet du tutorat."
    marks = {m["target"] for m in call(e, "ai.marks")["marks"]}
    assert marks == {"study.title", "study.hypotheses"} and res["project"]["ai_marks"] == 2
    assert call_error(e, "ai.copilot_apply", proposal_id=p["id"], selection={}).startswith("Cette proposition")

    # L'utilisateur modifie le titre : la mention disparaît, l'annulation n'est plus possible.
    call(e, "project.update_study", changes={"title": "Tutorat et réussite en L1"})
    assert {m["target"] for m in call(e, "ai.marks")["marks"]} == {"study.hypotheses"}
    assert "modifiés ou validés" in call_error(e, "ai.copilot_undo", proposal_id=p["id"])

    # Nouvelle proposition, appliquée puis annulée : l'étude revient à l'état précédent.
    p2 = run(e, server, "study", {"population": "Étudiants de L1 et L2"}, subject="Population élargie",
             fields=["population"])
    call(e, "ai.copilot_apply", proposal_id=p2["id"])
    assert project.study.population == "Étudiants de L1 et L2"
    call(e, "ai.copilot_undo", proposal_id=p2["id"])
    assert project.study.population == "Étudiants de L1"
    assert "study.population" not in {m["target"] for m in call(e, "ai.marks")["marks"]}

    # Validation explicite.
    out = call(e, "ai.marks_validate", targets=["study.hypotheses"])
    assert out["validated"] == 1 and out["marks"] == []
    journal = " ".join(j["summary"] for j in project.describe()["journal"])
    assert "Proposition de l'IA appliquée" in journal and "validé(s)" in journal


def test_unreadable_answer_is_reported(ai):
    e, server = ai
    p = run(e, server, "study", "Voici ma proposition : un très bon titre !", subject="Sujet")
    assert p["status"] == "illisible" and "JSON" in p["issues"][0]["text"]
    assert "illisible" in call_error(e, "ai.copilot_apply", proposal_id=p["id"])
    # Réponse JSON entourée de texte ou dans un bloc ``` : lue quand même.
    assert copilot.parse_json('Bien sûr !\n```json\n{"title": "T {1}"}\n```') == {"title": "T {1}"}
    assert copilot.parse_json('avant {"a": "x}"} après') == {"a": "x}"}
    assert copilot.parse_json("[1, 2]") is None


def test_study_action_needs_a_subject(ai, project):
    e, _ = ai
    project.update_study({"problem_statement": "", "objectives": "", "hypotheses": []})
    project.update_study({"title": "T"})
    assert "Décrivez" in call_error(e, "ai.copilot_preview", action="study", params={})
    assert "inconnue" in call_error(e, "ai.copilot_preview", action="pirate", params={})


# ---------------------------------------------------------------------- variables et nettoyage
def test_variables_dictionary_and_recode(ai, project):
    e, server = ai
    preview = call(e, "ai.copilot_preview", action="variables", params={"dataset_id": project.ds})
    text = preview["text"]
    assert "Sexe" in text and "modalités : F (" in text  # effectifs des modalités, pas de lignes brutes
    assert "contenu non transmis" in text and "@exemple.ma" not in text
    reply = {"variables": [
        {"name": "Note", "label": "Note finale sur 20", "level": "continu", "role": "a_expliquer", "unit": "points"},
        {"name": "satisfaction", "label": "Satisfaction (1 à 5)", "level": "ordinal", "role": "explicative",
         "missing_codes": ["9"]},
        {"name": "Inconnue", "label": "x"},
        {"name": "Tutorat", "level": "continu"}],
        "recodes": [{"variable": "Sexe", "new_name": "Sexe recode", "mapping": {"F": "Femme", "M": "Homme",
                                                                                "X": "Autre"}},
                    {"variable": "Sexe", "mapping": {"Z": "Y"}}]}
    p = run(e, server, "variables", reply, dataset_id=project.ds)
    prop = p["proposal"]
    by = {v["name"]: v for v in prop["variables"]}
    assert by["Note"]["changes"] == {"label": "Note finale sur 20", "role": "a_expliquer", "unit": "points"}
    assert by["Satisfaction"]["changes"]["level"] == "ordinal" and "missing_codes" not in by["Satisfaction"]["changes"]
    assert "Tutorat" not in by  # niveau incompatible avec le type : écarté
    texts = " ".join(i["text"] for i in p["issues"])
    assert "Inconnue" in texts and "incompatible" in texts and "absent(s) des données" in texts
    assert len(prop["recodes"]) == 1
    rc = prop["recodes"][0]
    assert rc["mapping"] == {"F": "Femme", "M": "Homme"} and rc["new_name"] == "Sexe_recode" and rc["rows"] == 40

    res = call(e, "ai.copilot_apply", proposal_id=p["id"], selection={"variables": ["Note"], "recodes": [0]})
    vid = res["proposal"]["applied"]["version_id"]
    note = next(v for v in project.data._variables(project.ds) if v.name == "Note")
    assert note.label == "Note finale sur 20" and note.role == "a_expliquer"
    df, variables, _ = project.data.materialize(project.ds, vid)
    assert set(df["Sexe_recode"].dropna()) == {"Femme", "Homme"}
    marks = {m["target"] for m in call(e, "ai.marks")["marks"]}
    assert marks == {f"var:{project.ds}:Note", f"version:{vid}"}
    call(e, "ai.copilot_undo", proposal_id=p["id"])
    note = next(v for v in project.data._variables(project.ds) if v.name == "Note")
    assert note.label == "" and note.role == "non_defini"
    assert all(v["id"] != vid for v in project.data.get(project.ds)["versions"])


# ---------------------------------------------------------------------- plan et choix des tests
def test_plan_tests_are_checked_by_the_engine_then_run_in_one_click(ai, project):
    e, server = ai
    reply = {"analyses": [
        {"hypothesis": 1, "method": "welch", "variables": {"outcome": ["Note"], "group": ["Tutorat"]},
         "role": "principale", "justification": "Note quantitative, deux groupes indépendants."},
        {"hypothesis": 2, "method": "pearson", "variables": {"x": ["Satisfaction"], "y": ["Note"]},
         "justification": "Deux variables numériques."},
        {"hypothesis": None, "method": "anova", "variables": {}},
        {"hypothesis": None, "method": "welch", "variables": {"outcome": ["Note"], "group": ["Email"]}},
        {"hypothesis": None, "method": "descriptives", "variables": {"variables": ["Note"]}, "role": "secondaire"}],
        "primary_variables": ["Note"], "missing_values": "Analyse des cas complets.", "multiplicity": "Aucune."}
    p = run(e, server, "plan", reply, dataset_id=project.ds)
    items = p["proposal"]["analyses"]
    assert [i["method"] for i in items] == ["welch", "pearson", "welch", "descriptives"]
    assert items[0]["check"]["verdict"] in ("conforme", "acceptable") and items[0]["hypothesis"] == 0
    assert items[2]["check"]["verdict"] == "impossible" and "identifiant" in items[2]["check"]["text"]
    assert any("anova" in i["text"] for i in p["issues"])
    res = call(e, "ai.copilot_apply", proposal_id=p["id"], selection={"use_engine": [1]})
    assert res["proposal"]["applied"]["analyses"] == 3  # l'analyse impossible n'est pas ajoutée
    plan = call(e, "plan.get")["current"]
    assert plan["status"] == "brouillon" and len(plan["content"]["analyses"]) == 3
    assert plan["content"]["analyses"][0]["description"].startswith("Proposé par l'IA, vérifié par le moteur")
    assert plan["content"]["missing_values"] == "Analyse des cas complets."
    if items[1]["check"].get("recommended") and items[1]["check"]["recommended"] != "pearson":
        assert plan["content"]["analyses"][1]["method"] == items[1]["check"]["recommended"]

    assert "Verrouillez" in call_error(e, "plan.run_all", dataset_id=project.ds)
    call(e, "plan.lock", reason="")
    out = call(e, "plan.run_all", dataset_id=project.ds)["run"]
    assert out["ran"] == 3, out
    first = project.analyses.get(out["results"][0]["analysis_id"])
    assert first["choice"]["plan"]["item"] == plan["content"]["analyses"][0]["id"]
    assert first["choice"]["hypothesis"] == 0
    again = call(e, "plan.run_all", dataset_id=project.ds)["run"]
    assert again["ran"] == 0 and {r["status"] for r in again["results"]} == {"deja_lancee"}


# ---------------------------------------------------------------------- taille d'échantillon
def test_power_parameters_proposed_and_computed_by_engine(ai, project):
    e, server = ai
    p = run(e, server, "power", {"design": "t_two", "effect": 0.5, "alpha": 0.05, "power": 0.8,
                                 "effect_source": "repère de Cohen", "justification": "Deux groupes."})
    prop = p["proposal"]
    assert prop["request"]["effects"] == [{"d": 0.5}]
    n_total = next(s for s in prop["computed"]["summary"] if s["key"] == "n_total")["value"]
    assert n_total == 128  # calculé par le moteur (pwr::pwr.t.test), pas par le modèle
    assert any("Cohen" in i["text"] for i in p["issues"])
    res = call(e, "ai.copilot_apply", proposal_id=p["id"])
    calc = res["proposal"]["applied"]["power_id"]
    assert project.power.exists(calc)
    call(e, "ai.copilot_undo", proposal_id=p["id"])
    assert not project.power.exists(calc)
    bad = run(e, server, "power", {"design": "inconnu"})
    assert bad["status"] == "illisible" and bad["issues"][0]["level"] == "bloquant"


# ---------------------------------------------------------------------- rédaction
def test_report_sections_are_number_checked_and_flagged(ai, project, tmp_path):
    e, server = ai
    ctx = call(e, "ai.copilot_preview", action="report", params={})["text"]
    t_line = next(line for line in ctx.splitlines() if line.startswith("- t :"))
    t_value = t_line.split(":", 1)[1].strip()
    reply = {"discussion": f"La différence observée (t = {t_value}) va dans le sens de H1.",
             "limites": "- Échantillon de volontaires.\n- Effectif de 999 étudiants seulement.",
             "conclusion": "Les résultats suggèrent un lien, sans établir de cause."}
    p = run(e, server, "report", reply)
    secs = p["proposal"]["sections"]
    assert not secs["discussion"]["checks"]["blocking"] and secs["limites"]["checks"]["blocking"]
    with pytest.raises(AssertionError, match="nombres absents"):
        call(e, "ai.copilot_apply", proposal_id=p["id"])
    call(e, "ai.copilot_apply", proposal_id=p["id"],
         selection={"edits": {"limites": "- Échantillon de volontaires.\n- Effectif modeste."}})
    assert set(copilot.report_texts(project)) == {"discussion", "limites", "conclusion"}
    path = tmp_path / "r.docx"
    checks = call(e, "report.check", options=options(project))["checks"]
    assert any("proposé(s) par l'IA" in i["title"] for i in checks["items"])
    project.reports.export(str(path), "docx", options(project))
    body = "\n".join(par.text for par in docx.Document(str(path)).paragraphs)
    assert "va dans le sens de H1" in body and "NON ENCORE RELUE" in body and "Effectif modeste." in body
    call(e, "ai.marks_validate", targets=["report.*"])
    assert all(t["validated"] for t in copilot.report_texts(project).values())
    project.reports.export(str(path), "docx", options(project))
    body = "\n".join(par.text for par in docx.Document(str(path)).paragraphs)
    assert "NON ENCORE RELUE" not in body and "relu et validé par l'auteur" in body
    # L'auteur réécrit la conclusion : son texte remplace la proposition.
    call(e, "report.save_texts", texts={"conclusion": "Ma conclusion."})
    assert copilot.report_texts(project)["conclusion"]["edited"] is True


# ---------------------------------------------------------------------- question libre
def test_ask_panel_answers_with_suggestion(ai, project):
    e, server = ai
    p = run(e, server, "ask", {"answer": "Commencez par compléter vos hypothèses.", "suggestion": "study"},
            question="Par quoi commencer ?", screen="etude")
    assert p["status"] == "reponse" and p["proposal"]["suggestion"] == "study"
    assert "ne s'applique pas" in call_error(e, "ai.copilot_apply", proposal_id=p["id"])
    assert "Écrivez" in call_error(e, "ai.copilot_preview", action="ask", params={"question": " "})
    lst = call(e, "ai.copilot_list")["proposals"]
    assert lst[0]["id"] == p["id"]


def test_copilot_requires_enabled_ai(project):
    e = Engine()
    e.project = project
    assert "désactivée" in call_error(e, "ai.copilot_start", action="study", params={"subject": "x"})
    assert {a["key"] for a in call(e, "ai.copilot_catalog")["actions"]} == set(copilot.ACTIONS)
