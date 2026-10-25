"""Farbschemen für Thea: eine Quelle (design_themes.json), erzeugtes CSS, garantierte Lesbarkeit.

- css/theme_colors.css ist aktuell (scripts/build_theme_css.py).
- Jedes Schema ist lesbar: Schrift, Akzent, Schrift auf Akzent-Knöpfen, jede Fachfarbe auf Karten.
- Namen sind schlichte Farbwörter (Thea sieht nur Tupfer, der Name steht im Tooltip).
- Kein festes Indigo mehr im CSS – sonst bliebe beim Umschalten etwas lila.
"""
import re


import pytest

from backend.app.services import design
from scripts.build_theme_css import CSS_FILE, build_css, subject_colors, tokens_for

FRONTEND = CSS_FILE.parents[1]
THEMES = design.themes()


def test_theme_css_is_up_to_date():
    assert CSS_FILE.read_text(encoding="utf-8") == build_css(), "scripts/build_theme_css.py ausführen"


def test_ids_unique_and_names_are_plain_colour_words():
    ids = design.theme_ids()
    assert len(ids) == len(set(ids))
    assert ids[0] == design.DEFAULT_THEME
    for t in THEMES:
        assert re.fullmatch(r"[a-z]+", t["id"]), t["id"]
        assert re.fullmatch(r"[A-ZÄÖÜ][a-zäöüß]+", t["name"]), t["name"]


@pytest.mark.parametrize("theme", THEMES, ids=[t["id"] for t in THEMES])
def test_theme_is_readable(theme):
    tok = tokens_for(theme)
    card, hover = tok["bg-card"], tok["bg-card-hover"]
    assert design.contrast(tok["text-primary"], tok["bg-primary"]) >= 7
    assert design.contrast(tok["text-secondary"], card) >= 4.5
    assert design.contrast(tok["text-muted"], card) >= 3
    assert design.contrast(tok["accent"], card) >= 3
    assert design.contrast(tok["on-accent"], tok["accent"]) >= 4.4
    weak = [c for c in subject_colors() if min(design.contrast(c, card), design.contrast(c, hover)) < 3]
    assert weak == [], f"Fachfarben auf Karten schlecht sichtbar: {weak}"


def test_frontend_knows_the_same_legacy_names_and_neutral_theme():
    js = (FRONTEND / "js" / "theme.js").read_text(encoding="utf-8")
    legacy = dict(re.findall(r'(\w+): "(\w+)"', js.split("const LEGACY_THEMES = {", 1)[1].split("}", 1)[0]))
    assert legacy == design.LEGACY_THEMES
    assert f'const NEUTRAL_THEME = "{design.DEFAULT_THEME}";' in js


def test_no_fixed_indigo_left_in_css():
    allowed = ("transparent 27px, rgba(99, 102, 241, 0.2) 28px", "transparent 4px, rgba(99, 102, 241, 0.6) 5px")
    found = []
    for css in sorted((FRONTEND / "css").glob("*.css")):
        if css.name == "theme_colors.css":
            continue
        for n, line in enumerate(css.read_text(encoding="utf-8").splitlines(), 1):
            if any(a in line for a in allowed):
                continue  # Linien der Tafel-Fläche, gehören zum Papier, nicht zum Schema
            if re.search(r"rgba\(99, ?102, ?241|#6366f1|#818cf8", line, re.I):
                found.append(f"{css.name}:{n}")
    assert found == []


def test_unknown_and_legacy_theme_names_are_normalized():
    assert design.normalize_theme("space") == "indigo"
    assert design.normalize_theme("candy") == "lila"
    assert design.normalize_theme("gibtsnicht") == design.DEFAULT_THEME
    assert design.normalize_theme(None) == design.DEFAULT_THEME


def test_theme_list_offers_dot_colours():
    entry = design.theme_list()[1]
    assert set(entry) == {"id", "name", "dark", "bg", "accent"}
