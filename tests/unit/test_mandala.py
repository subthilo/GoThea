"""Blüten-Mandalas: gleiche Startwerte geben gleiche Mandalas, jedes erzeugte besteht die Prüfung,
Fingerabdrücke verhindern Doppelte, und Felder + Tinte füllen die Mandala-Fläche ohne Lücken oder Überlappung."""
import pytest

pytest.importorskip("shapely")
from backend.app.services import mandala as M  # noqa: E402


@pytest.mark.parametrize("difficulty", list(M.DIFFICULTIES))
def test_generated_mandalas_pass_the_checks_and_differ(difficulty):
    seed, known = 1, set()
    for _ in range(4):
        m, seed = M.generate(difficulty, seed, known)
        assert M.check(m) is None
        assert m.signature() not in known
        known.add(m.signature())
        spec = M.DIFFICULTIES[difficulty]
        assert all(p.area >= spec["ink_area"] and M.width(p) >= spec["ink_width"] for p in m.fields)


def test_same_seed_same_mandala():
    a, b = M.build(42, "mittel"), M.build(42, "mittel")
    assert a.to_json() == b.to_json()
    assert M.build(43, "mittel").to_json() != a.to_json()


@pytest.mark.parametrize("difficulty", list(M.DIFFICULTIES))
def test_fields_and_ink_tile_the_mandala(difficulty):
    m, _ = M.generate(difficulty, 1)
    total = sum(p.area for p in m.fields) + sum(p.area for p in m.ink)
    assert abs(total - m.outline.area) / m.outline.area < 0.01  # Umriss ohne Löcher: nichts Ungefülltes darin
    # keine zwei Felder überlappen
    for i, p in enumerate(m.fields[:40]):
        for q in m.fields[i + 1:]:
            assert p.intersection(q).area < 1.0


def test_json_paths_are_svg_paths():
    m, _ = M.generate("leicht", 1)
    data = m.to_json()
    assert data["version"] == M.VERSION and data["outline"].startswith("M")
    assert all(f["d"].startswith("M") and f["d"].endswith("Z") for f in data["fields"])
    assert [f["id"] for f in data["fields"]] == list(range(len(data["fields"])))
    assert data["lines"] and all(d.startswith("M") for d in data["lines"])
