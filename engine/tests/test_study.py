import pytest

from statpfe.core.study import Study
from statpfe.errors import ValidationError


def test_from_dict_strips_and_drops_empty_hypotheses(study):
    data = {**study, "title": "  Titre  ", "hypotheses": ["  H1  ", "", "   "]}
    s = Study.from_dict(data)
    assert s.title == "Titre"
    assert s.hypotheses == ["H1"]


@pytest.mark.parametrize("title", ["", "   ", None, 12, "x" * 301])
def test_invalid_title_is_rejected(title):
    with pytest.raises(ValidationError):
        Study.from_dict({"title": title})


@pytest.mark.parametrize("size", [0, -5, 1.5, "120", True])
def test_invalid_sample_size_is_rejected(size):
    with pytest.raises(ValidationError):
        Study.from_dict({"title": "T", "planned_sample_size": size})


def test_empty_sample_size_means_unknown():
    assert Study.from_dict({"title": "T", "planned_sample_size": ""}).planned_sample_size is None


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Study.from_dict({"title": "T", "pirate": 1})


def test_too_many_hypotheses():
    with pytest.raises(ValidationError):
        Study.from_dict({"title": "T", "hypotheses": [f"H{i}" for i in range(51)]})


def test_changed_fields():
    a = Study.from_dict({"title": "T"})
    b = a.merged({"objectives": "O", "hypotheses": ["H"]})
    assert a.changed_fields(b) == ["objectives", "hypotheses"]
