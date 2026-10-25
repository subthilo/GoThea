"""Mandala-Generator: gleiche Startwerte geben gleiche Mandalas, jedes erzeugte besteht die Prüfung,
Fingerabdrücke verhindern Doppelte, und die Felder füllen die Kreisfläche ohne Lücken oder Überlappung."""
import math

import pytest

from backend.app.services import mandala as M


@pytest.mark.parametrize("difficulty", list(M.DIFFICULTIES))
def test_generated_mandalas_pass_the_checks_and_differ(difficulty):
    seed, known = 1, set()
    for _ in range(8):
        m, seed = M.generate(difficulty, seed, known)
        assert M.check(m) is None
        assert m.signature() not in known
        known.add(m.signature())
        lo, hi = M.DIFFICULTIES[difficulty]["fields"]
        assert lo <= len(m.fields) <= hi


def test_same_seed_same_mandala():
    a, b = M.build(42, "mittel"), M.build(42, "mittel")
    assert a.to_json() == b.to_json()
    assert M.build(43, "mittel").to_json() != a.to_json()


@pytest.mark.parametrize("difficulty", list(M.DIFFICULTIES))
def test_fields_tile_the_disc(difficulty):
    # Summe der Feldflächen = Kreisfläche: keine Lücken, keine Überlappungen (Even-Odd-Felder)
    m, _ = M.generate(difficulty, 1)
    total = sum(f.area() for f in m.fields)
    disc = math.pi * M.R_OUT ** 2
    assert abs(total - disc) / disc < 0.01


def test_json_paths_are_closed_svg_paths():
    m, _ = M.generate("leicht", 1)
    data = m.to_json()
    assert data["version"] == M.VERSION and data["outline"].startswith("M")
    assert all(f["d"].startswith("M") and f["d"].endswith("Z") for f in data["fields"])
    assert [f["id"] for f in data["fields"]] == list(range(len(data["fields"])))
