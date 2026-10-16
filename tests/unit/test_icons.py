"""Einheitliche Icons: alle Symbole der Oberfläche kommen aus frontend/Icons.

- css/icons.css ist aus dem Icons-Ordner erzeugt und aktuell (scripts/build_icon_css.py).
- Jedes im Frontend verwendete Icon existiert als SVG.
- Keine Emojis mehr in HTML/JS der Oberfläche (sie sahen je nach Gerät anders aus und passten nicht zum Linienstil).
"""
import re
from pathlib import Path
from urllib.parse import unquote

from scripts.build_icon_css import CSS_FILE, ICON_DIR, build_css, icon_slug

FRONTEND = ICON_DIR.parent
SOURCES = [FRONTEND / "index.html", FRONTEND / "whiteboard.js", FRONTEND / "cloze_trainer.js",
           *sorted((FRONTEND / "dialogs").glob("*.html")), *sorted((FRONTEND / "js").glob("*.js"))]

# Emoji und Bildzeichen, die früher als Icons dienten; typografische Zeichen (→ ↳ • …) bleiben erlaubt
EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿⬀-⯿⏩-⏿⤀-⥿"
                   "▲▶▼▾◀⛶↕↔↺]|&times;")


def _icon_names():
    return {p.stem for p in ICON_DIR.glob("*.svg")}


def _used_icons(text):
    names = set(re.findall(r"""\b(?:icon|iconText|makeIconButton)\(\s*["']([^"']+)["']""", text))
    names |= set(re.findall(r"""/static/Icons/([^"'?`]+)\.svg""", text))
    return {unquote(n) for n in names}


def test_icon_css_is_up_to_date():
    assert CSS_FILE.read_text(encoding="utf-8") == build_css(), "scripts/build_icon_css.py ausführen"


def test_every_used_icon_exists():
    names = _icon_names()
    slugs = {icon_slug(n) for n in names}
    missing = []
    for src in SOURCES:
        if src.name == "icons.js":  # definiert die Helfer, Beispiele im Kommentar
            continue
        text = src.read_text(encoding="utf-8")
        missing += [f"{src.name}: {n}" for n in _used_icons(text) if n not in names]
        missing += [f"{src.name}: i-{s}" for s in re.findall(r"\bui-icon i-([a-z0-9-]+)", text) if s not in slugs]
    # Rückgabewerte der Zuordnungen (Fach, Dokumentart, Übungsmethode)
    for src in (FRONTEND / "js" / "icons.js", FRONTEND / "js" / "subject_detail.js"):
        text = src.read_text(encoding="utf-8")
        for block in re.findall(r"function \w+IconName\(.*?\n}\n", text, re.S):
            for n in re.findall(r'(?:return|:)\s*"([^"]+)"', block):
                if n not in names:
                    missing.append(f"{src.name}: {n}")
    assert missing == []


def test_subject_table_has_known_icons_and_distinct_colors():
    """Fächer sind farbcodiert: jedes Fach eine eigene Farbe (Pausen/Freistunden teilen sich ein Grau)."""
    js = (FRONTEND / "js" / "icons.js").read_text(encoding="utf-8")
    table = js.split("const SUBJECTS = [", 1)[1].split("];", 1)[0]
    rows = re.findall(r'icon: "([^"]+)", color: "(#[0-9a-f]{6})"', table)
    assert len(rows) >= 17
    assert {i for i, _ in rows} <= _icon_names()
    neutral = {"Mittagspause", "Pause", "Freistunde"}
    colors = [c for i, c in rows if i not in neutral]
    assert len(colors) == len(set(colors)), "zwei Fächer mit derselben Farbe"


def test_no_emoji_icons_in_frontend():
    found = []
    for src in SOURCES:
        for i, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if EMOJI.search(line):
                found.append(f"{src.name}:{i}: {line.strip()[:80]}")
    assert found == [], "Emojis durch icon(\"…\") ersetzen:\n" + "\n".join(found)


def test_new_icons_follow_the_style():
    """Gleiches Raster und gleiche Linie wie die vorhandenen Icons."""
    for svg in ICON_DIR.glob("*.svg"):
        head = svg.read_text(encoding="utf-8").split(">", 1)[0]
        assert 'viewBox="0 0 100 100"' in head, svg.name
        assert 'stroke-width="4"' in head, svg.name
        assert 'stroke-linecap="round"' in head, svg.name


def test_icon_slug_matches_js():
    js = (FRONTEND / "js" / "icons.js").read_text(encoding="utf-8")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        assert f'.replace(/{a}/g, "{b}")' in js
    assert icon_slug("Politische Bildung") == "politische-bildung"
    assert Path(CSS_FILE).name == "icons.css"
