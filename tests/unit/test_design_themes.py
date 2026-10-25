"""Farbschemen für Thea: eine Quelle (design_themes.json), erzeugtes CSS, garantierte Lesbarkeit.

- css/theme_colors.css ist aktuell (scripts/build_theme_css.py).
- Jedes Schema ist lesbar: Schrift, Akzent, Schrift auf Akzent-Knöpfen, jede Fachfarbe auf Karten.
- Namen sind schlichte Farbwörter (Thea sieht nur Tupfer, der Name steht im Tooltip).
- Kein festes Indigo mehr im CSS – sonst bliebe beim Umschalten etwas lila.
"""
import itertools
import math
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
    for signal in ("success-text", "warning-text", "info-text", "danger-text"):
        assert design.contrast(tok[signal], card) >= 4.5, signal
    weak = [c for c in subject_colors(light=not theme["dark"]) if min(design.contrast(c, card), design.contrast(c, hover)) < 3]
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


def _lab(h):
    rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    rgb = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    x = (rgb[0] * 0.4124 + rgb[1] * 0.3576 + rgb[2] * 0.1805) / 0.95047
    y = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
    z = (rgb[0] * 0.0193 + rgb[1] * 0.1192 + rgb[2] * 0.9505) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _ciede2000(a, b):
    L1, a1, b1 = _lab(a)
    L2, a2, b2 = _lab(b)
    cb = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cb ** 7 / (cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1 = math.degrees(math.atan2(b1, a1p)) % 360
    h2 = math.degrees(math.atan2(b2, a2p)) % 360
    dl, dc, dh = L2 - L1, c2p - c1p, h2 - h1
    if c1p * c2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dH = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lb, cbp = (L1 + L2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hb = h1 + h2
    elif abs(h1 - h2) <= 180:
        hb = (h1 + h2) / 2
    else:
        hb = (h1 + h2 + 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hb - 30)) + 0.24 * math.cos(math.radians(2 * hb))
         + 0.32 * math.cos(math.radians(3 * hb + 6)) - 0.2 * math.cos(math.radians(4 * hb - 63)))
    sl = 1 + 0.015 * (lb - 50) ** 2 / math.sqrt(20 + (lb - 50) ** 2)
    sc, sh = 1 + 0.045 * cbp, 1 + 0.015 * cbp * t
    rt = -2 * math.sin(math.radians(60 * math.exp(-((hb - 275) / 25) ** 2))) * math.sqrt(cbp ** 7 / (cbp ** 7 + 25 ** 7))
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dH / sh) ** 2 + rt * (dc / sc) * (dH / sh))


def test_light_subject_colours_stay_distinguishable():
    """Der zweite Satz für helle Schemen: Theas Fächer (ohne Religion, Informatik) so unterscheidbar wie der dunkle."""
    js = (FRONTEND / "js" / "icons.js").read_text(encoding="utf-8")
    rows = dict(re.findall(r'icon: "([^"]+)", color: "#[0-9a-f]{6}", light: "(#[0-9a-f]{6})"', js))
    thea = [c for name, c in rows.items() if name not in {"Religion", "Informatik", "Bücher", "Mittagspause", "Pause", "Freistunde"}]
    closest = min((_ciede2000(a, b), a, b) for a, b in itertools.combinations(thea, 2))
    assert closest[0] >= 17.9, closest


def test_white_filtered_image_icons_have_a_light_variant():
    """Bild-Icons, die per Filter weiß werden, wären auf hellem Grund unsichtbar: jede Regel braucht ihr helles Gegenstück."""
    missing = []
    for css in sorted((FRONTEND / "css").glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8"), flags=re.S)
        light = set(re.findall(r':root\[data-theme-kind="light"\] ([^,{]+?)\s*[,{]', text))
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
            if "data-theme-kind" in sel or not re.search(r"brightness\(0\) invert\(", body):
                continue
            for s in (x.strip() for x in sel.split(",")):
                if s and not s.startswith("@") and s not in light:
                    missing.append(f"{css.name}: {s}")
    assert missing == []
