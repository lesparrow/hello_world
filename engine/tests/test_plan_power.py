"""Puissance et taille d'échantillon, plan d'analyse versionné et leur place dans le rapport."""

from __future__ import annotations

import json
import math
import sqlite3
import zipfile

import docx
import pytest

from statpfe.core.project import Project
from statpfe.errors import ValidationError
from statpfe.report.build import build
from statpfe.rpc.server import Engine
from statpfe.stats import power as P
from test_report import options, project, survey_csv  # noqa: F401 - fixture partagée

TWO = "two-sided"


# ---------------------------------------------------------------------- calculs
def ss(design, effects, **kw):
    return P.compute({"design": design, "mode": "sample_size", "effects": effects, **kw})


def test_known_textbook_values():
    # Cohen (1988), tableau 2.4.1 : d = 0,5, α = 0,05 bilatéral, puissance 0,80 → 64 par groupe
    assert ss("t_two", [{"d": 0.5}])["rows"][0]["n1"] == 64
    # r = 0,3 → 85 observations (pwr.r.test : 84,07)
    assert ss("correlation", [{"r": 0.3}])["rows"][0]["n1"] == 85


def test_effect_from_difference_and_sd_and_sign():
    a = ss("t_two", [{"diff": 2.5, "sd": 5}])["rows"][0]
    b = ss("t_two", [{"d": -0.5}])["rows"][0]
    assert a["n1"] == b["n1"] == 64 and a["effect"] == pytest.approx(0.5)


def test_comparison_of_several_effects_is_monotone():
    rows = ss("t_two", [{"d": 0.2}, {"d": 0.5}, {"d": 0.8}])["rows"]
    assert rows[0]["n1"] > rows[1]["n1"] > rows[2]["n1"]
    for r in rows:
        assert r["power"] >= 0.8
        smaller = P.power_t(r["effect"], r["n1"] - 1, r["n2"] - 1, 0.05, TWO)
        assert smaller < 0.8  # n est bien le plus petit entier qui suffit


def test_ratio_attrition_and_nonparametric():
    r = ss("t_two", [{"d": 0.5}], ratio=2, attrition=0.2)["rows"][0]
    assert r["n2"] == math.ceil(2 * r["n1"])
    assert r["recruit1"] == math.ceil(r["n1"] / 0.8) and r["recruit_total"] == r["recruit1"] + r["recruit2"]
    assert r["n_nonparametric"][0] == math.ceil(r["n1"] / (3 / math.pi))
    assert r["n_nonparametric_any"][0] >= r["n_nonparametric"][0]


def test_power_mode_and_minimum_effect_are_consistent():
    res = P.compute({"design": "t_two", "mode": "effect", "n1": 30, "n2": 40, "power": 0.9})
    d = res["rows"][0]["effect"]
    assert P.power_t(d, 30, 40, 0.05, TWO) == pytest.approx(0.9, abs=1e-10)
    pw = P.compute({"design": "t_two", "mode": "power", "n1": 30, "n2": 40, "effects": [{"d": d}]})
    assert pw["rows"][0]["power"] == pytest.approx(0.9, abs=1e-10)


def test_minimum_effect_for_proportions_gives_matching_proportions():
    res = P.compute({"design": "prop_two", "mode": "effect", "n1": 80, "n2": 80, "p_ref": 0.3})
    row = res["rows"][0]
    assert abs(P.cohen_h(row["p_high"], 0.3)) == pytest.approx(row["effect"], rel=1e-10)
    assert abs(P.cohen_h(row["p_low"], 0.3)) == pytest.approx(row["effect"], rel=1e-10)
    assert "0,3" in res["interpretation"][0]


def test_chi2_df_from_table_and_low_n_warning():
    res = P.compute({"design": "chi2", "mode": "power", "effects": [{"w": 0.5}], "n": 12, "rows": 3, "cols": 3})
    assert res["request"]["df"] == 4
    assert any(d["title"] == "Effectif faible pour un khi-deux" for d in res["diagnostics"])


def test_assumptions_curve_and_disclaimer():
    res = ss("t_paired", [{"d": 0.4}], effect_source="Étude pilote (n = 12)", alpha=0.01, power=0.9)
    text = " ".join(res["assumptions"])
    assert "α = 0,01" in text and "90\u00a0%" in text and "Étude pilote" in text and "dz" in text
    curve = res["charts"][0]
    assert curve["type"] == "power_curve" and curve["data"]["target"] == 0.9
    pts = curve["data"]["series"][0]["points"]
    assert all(a[1] <= b[1] + 1e-12 for a, b in zip(pts, pts[1:]))
    assert "ne garantit pas" in res["disclaimer"]
    assert not any(d["title"].startswith("Origine") for d in res["diagnostics"])
    assert any(d["title"].startswith("Origine") for d in ss("t_one", [{"d": 0.4}])["diagnostics"])


def test_post_collection_power_never_uses_observed_effect(project):
    a = project.analyses.get(project.ids["welch"])
    pre = P.from_analysis(a)["request"]
    assert pre["design"] == "t_two" and pre["mode"] == "power"
    assert pre["n1"] + pre["n2"] == a["result"]["n_used"]
    assert "effects" not in pre  # l'effet reste à supposer par l'auteur
    res = P.compute({**pre, "effects": [{"d": 0.5}]})
    assert any(d["title"] == "Puissance après la collecte" for d in res["diagnostics"])
    chi = P.from_analysis(project.analyses.get(project.ids["chi2"]))["request"]
    assert chi["design"] == "chi2" and chi["rows"] == 2 and chi["cols"] == 2
    with pytest.raises(ValidationError):
        P.from_analysis(project.analyses.get(project.ids["desc"]))


@pytest.mark.parametrize("request_,message", [
    ({"design": "x", "mode": "power"}, "type de test"),
    ({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0}]}, "nul"),
    ({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.5}], "alpha": 0.5}, "Seuil"),
    ({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.5}] * 7}, "Au plus"),
    ({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.0005}]}, "10 millions"),
    ({"design": "correlation", "mode": "power", "effects": [{"r": 1}], "n": 20}, "Corrélation"),
    ({"design": "t_two", "mode": "power", "effects": [{"d": 0.5}], "n1": 1, "n2": 10}, "groupe 1"),
    ({"design": "prop_two", "mode": "sample_size", "effects": [{"p1": 0.3, "p2": 0.3}]}, "nul"),
])
def test_invalid_requests(request_, message):
    with pytest.raises(ValidationError, match=message):
        P.compute(request_)


# ---------------------------------------------------------------------- calculs enregistrés
def test_power_store_persistence_and_journal(project, tmp_path):
    cid = project.power.save({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.5}],
                              "effect_source": "Méta-analyse X"}, "Taille pour H1")
    assert project.power.get(cid)["title"] == "Taille pour H1"
    assert project.journal()[0].action == "puissance"
    assert project.power.verify(cid) == []
    project.power.rename(cid, "Taille de l'échantillon")
    project.save()
    path = project.path
    project.close()
    q = Project.open(str(path))
    try:
        calc = q.power.get(cid)
        assert calc["title"] == "Taille de l'échantillon" and calc["result"]["rows"][0]["n1"] == 64
        assert q.describe()["power_count"] == 1
    finally:
        q.close(discard_changes=True)


def test_tampered_power_result_is_detected(project):
    cid = project.power.save({"design": "correlation", "mode": "sample_size", "effects": [{"r": 0.3}]})
    row = project._conn.execute("SELECT result FROM power_calcs WHERE id = ?", (cid,)).fetchone()
    res = json.loads(row[0])
    res["rows"][0]["n1"] = 40
    project._conn.execute("UPDATE power_calcs SET result = ? WHERE id = ?", (json.dumps(res), cid))
    assert project.power.verify(cid)
    checks = project.reports.check(options(project, power=[cid]))["checks"]
    assert any("résultat différent au recalcul" in i["title"] and i["level"] == "bloquant" for i in checks["items"])


# ---------------------------------------------------------------------- plan d'analyse
def plan_content(**over):
    c = {"objectives": "Mesurer l'effet du tutorat.", "hypotheses": ["Les tutorés ont de meilleures notes."],
         "primary_variables": ["Note"], "secondary_variables": ["Satisfaction"],
         "analyses": [{"method": "welch", "variables": {"outcome": ["Note"], "group": ["Tutorat"]}, "hypothesis": 0,
                       "role": "principale", "description": "Analyse principale."},
                      {"method": "pearson", "variables": {"x": ["Note"], "y": ["Satisfaction"]}, "role": "secondaire"}],
         "exclusion_criteria": "Questionnaires incomplets.", "missing_values": "Cas complets.",
         "exploratory": "Effet du sexe.", "alpha": 0.05}
    c.update(over)
    return c


def test_plan_versions_lock_and_history(project):
    plan = project.plan
    assert plan.get()["current"] is None
    plan.save(plan_content())
    cur = plan.get()["current"]
    assert cur["version"] == 1 and cur["status"] == "brouillon"
    assert [i["id"] for i in cur["content"]["analyses"]] == ["A1", "A2"]
    content = cur["content"]
    content["objectives"] = "Objectif précisé."
    plan.save(content)
    assert len(plan.get()["versions"]) == 1  # le brouillon se modifie sur place
    assert plan.lock("") == 1
    with pytest.raises(ValidationError, match="pas de brouillon"):
        plan.lock("x")
    # Modification après verrouillage : nouvelle version, l'ancienne reste intacte.
    content = plan.get()["current"]["content"]
    content["analyses"] = content["analyses"][:1] + [{"method": "chi2",
                                                      "variables": {"row": ["Sexe"], "col": ["Tutorat"]}}]
    plan.save(content)
    state = plan.get()
    assert state["current"]["version"] == 2 and state["locked"]["version"] == 1
    assert [i["id"] for i in state["current"]["content"]["analyses"]] == ["A1", "A3"]  # A2 n'est jamais réutilisé
    details = [c["detail"] for c in state["pending_changes"]]
    assert any("ajoutée" in d and "A3" in d for d in details) and any("retirée" in d and "A2" in d for d in details)
    with pytest.raises(ValidationError, match="motif"):
        plan.lock("")
    assert plan.lock("Corrélation remplacée par un khi-deux après avis de l'encadrant.") == 2
    assert [i["id"] for i in plan.version(1)["content"]["analyses"]] == ["A1", "A2"]
    versions = plan.get()["versions"]
    assert versions[1]["change_reason"].startswith("Corrélation") and versions[1]["changes"]
    assert sum(e.action == "plan" for e in project.journal()) == 4


def test_plan_discard_draft_and_validation(project):
    plan = project.plan
    plan.save(plan_content())
    plan.lock("")
    content = plan.get()["current"]["content"]
    content["alpha"] = 0.01
    plan.save(content)
    plan.discard_draft()
    assert plan.get()["current"]["version"] == 1 and plan.get()["current"]["content"]["alpha"] == 0.05
    for bad, msg in [({"analyses": [{"method": "inconnue"}]}, "méthode"),
                     ({"analyses": [{"id": "A99", "method": "welch"}]}, "identifiant"),
                     ({"analyses": [{"method": "welch", "variables": {"x": ["a"]}}]}, "variables"),
                     ({"analyses": [{"method": "welch", "hypothesis": 5}]}, "hypothèse"),
                     ({"alpha": 0.5}, "seuil"), ({"inconnu": 1}, "inconnu")]:
        with pytest.raises(ValidationError, match=msg):
            plan.save(plan_content(**bad))


def test_lock_requires_planned_analyses_with_variables(project):
    project.plan.save(plan_content(analyses=[]))
    with pytest.raises(ValidationError, match="au moins une analyse"):
        project.plan.lock("")
    project.plan.save(plan_content(analyses=[{"method": "welch"}]))
    with pytest.raises(ValidationError, match="variables"):
        project.plan.lock("")


def test_analysis_link_to_locked_plan(project):
    ds = project.ds
    params = {"outcome": "Note", "group": "Tutorat", "levels": ["non", "oui"]}
    with pytest.raises(ValidationError, match="Aucun plan"):
        project.analyses.run(ds, None, "welch", params, choice={"mode": "direct", "plan_item": "A1"})
    project.plan.save(plan_content())
    project.plan.lock("")
    aid = project.analyses.run(ds, None, "welch", params, choice={"mode": "direct", "plan_item": "A1",
                                                                  "purpose": "confirmatoire"})
    link = project.analyses.get(aid)["choice"]["plan"]
    assert link["item"] == "A1" and link["version"] == 1 and not link["deviation"]
    with pytest.raises(ValidationError, match="écart"):
        project.analyses.run(ds, None, "mann_whitney", {"outcome": "Note", "group": "Tutorat"},
                             choice={"mode": "direct", "plan_item": "A1"})
    aid2 = project.analyses.run(ds, None, "mann_whitney", {"outcome": "Note", "group": "Tutorat"},
                                choice={"mode": "direct", "plan_item": "A1",
                                        "plan_reason": "Distribution très asymétrique."})
    link2 = project.analyses.get(aid2)["choice"]["plan"]
    assert link2["deviation"] and "méthode prévue" in link2["deviations"][0]
    with pytest.raises(ValidationError, match="inconnue"):
        project.analyses.run(ds, None, "welch", params, choice={"mode": "direct", "plan_item": "A9"})


def test_power_calc_used_by_locked_plan_cannot_be_deleted(project):
    cid = project.power.save({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.5}]})
    other = project.power.save({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.8}]})
    content = plan_content(power_calc=cid)
    project.plan.save(content)
    project.power.delete(other)  # brouillon seulement : pas de blocage pour les autres
    project.plan.lock("")
    with pytest.raises(ValidationError, match="verrouillé"):
        project.power.delete(cid)
    assert project.power.list()[0]["locked_in_plan"] == [1]


def test_migration_from_format_4(project, tmp_path):
    project.save()
    path = project.path
    project.close()
    work = tmp_path / "m"
    work.mkdir()
    with zipfile.ZipFile(path) as zf:
        zf.extractall(work)
    conn = sqlite3.connect(work / "project.sqlite")
    conn.executescript("DROP TABLE power_calcs; DROP TABLE plan_versions; "
                       "UPDATE meta SET value = '4' WHERE key = 'format_version';")
    conn.commit()
    conn.close()
    manifest = json.loads((work / "manifest.json").read_text())
    manifest["format_version"] = 4
    (work / "manifest.json").write_text(json.dumps(manifest))
    with zipfile.ZipFile(path, "w") as zf:
        for f in work.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(work).as_posix())
    q = Project.open(str(path))
    try:
        assert q.dirty and q.describe()["format_version"] == 6
        assert q.power.list() == [] and q.plan.get()["current"] is None
        assert q.analyses.count() == 3
    finally:
        q.close(discard_changes=True)


# ---------------------------------------------------------------------- rapport
def full_setup(project):
    cid = project.power.save({"design": "t_two", "mode": "sample_size", "effects": [{"d": 0.5}, {"d": 0.8}],
                              "effect_source": "Étude de Martin (2020)"}, "Taille pour H1")
    content = plan_content(power_calc=cid)
    content["analyses"][0]["power_calc"] = cid
    project.plan.save(content)
    project.plan.lock("")
    linked = project.analyses.run(project.ds, None, "welch",
                                  {"outcome": "Note", "group": "Tutorat", "levels": ["non", "oui"]},
                                  choice={"mode": "direct", "plan_item": "A1", "purpose": "confirmatoire",
                                          "hypothesis": 0})
    return cid, linked


def test_report_distinguishes_planned_and_unplanned(project):
    cid, linked = full_setup(project)
    late = project.analyses.run(project.ds, None, "spearman", {"x": "Note", "y": "Satisfaction"})
    opts = options(project, analyses=[linked, late, project.ids["chi2"]], power=[cid])
    opts["sections"].update(plan=True, power=True)
    text = build(project, opts, draw=False).text()
    assert "Plan d'analyse" in text and "Analyses prévues au plan (version 1)" in text
    assert "Prévue au plan (A1, version 1)" in text
    assert "non prévue au plan : ajoutée après consultation des données" in text
    assert "réalisée avant le verrouillage du plan" in text  # le khi-deux du jeu d'essai
    assert "A2 : analyse prévue au plan non présente dans ce rapport" in text
    assert "Prévue (A1)" in text and "Hors plan" in text  # colonne Plan de la méthodologie
    assert "Taille d'échantillon et puissance" in text and "Calcul de puissance n° 1 : Taille pour H1" in text
    assert "Étude de Martin (2020)" in text and "pwr" in text
    assert "effectif justifié par le calcul de puissance n° 1" in text
    # 40 observations < 128 nécessaires pour d = 0,5
    assert "insuffisant pour l'effet d = 0,5 (128 nécessaires), l'effet d = 0,8 (52 nécessaires)" in text
    checks = project.reports.check(opts)["checks"]
    titles = [i["title"] for i in checks["items"]]
    assert "Analyse prévue A2 absente du rapport" in titles
    assert any("effectif inférieur au calcul de puissance" in t for t in titles)
    assert any(t.startswith("Plan d'analyse verrouillé") for t in checks["passed"])
    assert any(t.startswith("Calculs de puissance refaits") for t in checks["passed"])
    assert checks["blocking"] == 0


def test_report_without_plan_says_so(project):
    opts = options(project)
    opts["sections"].update(plan=True, power=True)
    text = build(project, opts, draw=False).text()
    assert "Aucun plan d'analyse n'a été défini dans STATPFE." in text
    assert "aucun plan verrouillé avant les analyses" in text
    assert "Aucun calcul de puissance n'est inclus" in text
    titles = [i["title"] for i in project.reports.check(opts)["checks"]["items"]]
    assert "Aucun plan d'analyse" in titles


def test_plan_history_in_report(project):
    cid, linked = full_setup(project)
    content = project.plan.get()["current"]["content"]
    content["alpha"] = 0.01
    project.plan.save(content)
    project.plan.lock("Seuil abaissé (tests multiples).")
    opts = options(project, analyses=[linked], power=[cid])
    text = build(project, opts, draw=False).text()
    assert "Versions du plan d'analyse" in text and "Seuil abaissé (tests multiples)." in text
    assert "modifié après le début des analyses" in text
    titles = [i["title"] for i in project.reports.check(opts)["checks"]["items"]]
    assert "Plan modifié après le début des analyses (version 2)" in titles


def test_old_options_get_new_sections_from_template(project):
    opts = options(project)
    del opts["sections"]["plan"], opts["sections"]["power"]
    opts.pop("power")
    cid = project.power.save({"design": "correlation", "mode": "sample_size", "effects": [{"r": 0.3}]})
    clean = project.reports.check(opts)["options"]
    assert clean["sections"]["plan"] and clean["sections"]["power"] and clean["power"] == [cid]


def test_docx_with_power_curve(project, tmp_path):
    cid, linked = full_setup(project)
    out = tmp_path / "rapport.docx"
    res = project.reports.export(str(out), "docx", options(project, analyses=[linked], power=[cid]))
    d = docx.Document(str(out))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "Courbe de la puissance" in text and "prévue au plan (A1, version 1)" in text
    assert len(d.inline_shapes) == res["figures"]
    pdf = tmp_path / "rapport.pdf"
    project.reports.export(str(pdf), "pdf", options(project, analyses=[linked], power=[cid]))
    assert pdf.read_bytes()[:5] == b"%PDF-"


# ---------------------------------------------------------------------- RPC
def test_rpc_power_and_plan(tmp_path, study):
    e = Engine()
    assert e.methods["power.compute"]({"request": {"design": "t_two", "mode": "sample_size",
                                                   "effects": [{"d": 0.5}]}})["rows"][0]["n1"] == 64
    cat = e.methods["power.catalog"]({})
    assert {d["key"] for d in cat["designs"]} == set(P.DESIGNS)
    e.methods["project.create"]({"path": str(tmp_path / "p.statpfe"), "study": study})
    saved = e.methods["power.save"]({"request": {"design": "correlation", "mode": "sample_size",
                                                 "effects": [{"r": 0.3}]}, "title": "r"})
    assert saved["project"]["power_count"] == 1
    r = e.methods["plan.save"]({"content": plan_content()})
    assert r["project"]["plan_status"] == {"version": 1, "status": "brouillon", "locked_version": None}
    r = e.methods["plan.lock"]({"reason": ""})
    assert r["plan"]["locked"]["version"] == 1 and r["project"]["plan_status"]["locked_version"] == 1
    assert e.methods["plan.version"]({"version": 1})["status"] == "verrouille"
    e.shutdown()
