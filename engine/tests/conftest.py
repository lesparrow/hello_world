import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Chaque test utilise ses propres dossiers de configuration et de travail."""
    monkeypatch.setenv("STATPFE_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("STATPFE_WORK_DIR", str(tmp_path / "work"))
    return tmp_path


@pytest.fixture
def study():
    return {
        "title": "Satisfaction des étudiants vis-à-vis du tutorat",
        "problem_statement": "Le tutorat améliore-t-il la réussite en première année ?",
        "objectives": "Mesurer l'effet du tutorat sur les notes.",
        "population": "Étudiants de L1, faculté des sciences",
        "sampling_method": "Échantillonnage aléatoire stratifié",
        "planned_sample_size": 120,
        "hypotheses": ["H1 : les étudiants tutorés ont de meilleures notes."],
    }
