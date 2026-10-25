"""Erzeugt frontend/css/theme_colors.css aus backend/app/design_themes.json.

Je Schema ein Block mit allen CSS-Farben (berechnet von services/design.derive, inkl. Prüfung,
dass jede Fachfarbe aus js/icons.js auf Karten sichtbar bleibt). Nach einer Änderung an den
Schemen oder an den Fachfarben ausführen; tests/unit/test_design_themes.py prüft, dass das CSS aktuell ist.

Aufruf: .venv/bin/python scripts/build_theme_css.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services import design  # noqa: E402

CSS_FILE = ROOT / "frontend" / "css" / "theme_colors.css"
ICONS_JS = ROOT / "frontend" / "js" / "icons.js"
NEUTRAL = {"Mittagspause", "Pause", "Freistunde", "Bücher"}

HEADER = """/* ==========================================================================
   FARBSCHEMEN – erzeugt von scripts/build_theme_css.py aus backend/app/design_themes.json,
   nicht von Hand ändern. Gewählt über <html data-theme="…">, ohne Angabe gilt das erste.
   ========================================================================== */
"""


def subject_colors(light: bool = False):
    """Fachfarben aus der SUBJECTS-Tabelle in js/icons.js (ohne Pausen und Neutrales);
    light=True: der zweite Satz für helle Schemen."""
    table = ICONS_JS.read_text(encoding="utf-8").split("const SUBJECTS = [", 1)[1].split("];", 1)[0]
    rows = re.findall(r'icon: "([^"]+)", color: "(#[0-9a-f]{6})", light: "(#[0-9a-f]{6})"', table)
    return [lt if light else c for icon, c, lt in rows if icon not in NEUTRAL]


def tokens_for(theme):
    return design.derive(theme, subject_colors(light=not theme["dark"]))


def build_css():
    parts = [HEADER]
    for i, theme in enumerate(design.themes()):
        selector = f':root[data-theme="{theme["id"]}"]'
        if i == 0:
            selector = ":root,\n" + selector
        lines = "\n".join(f"  --{k}: {v};" for k, v in tokens_for(theme).items())
        scheme = "dark" if theme["dark"] else "light"
        parts.append(f"{selector} {{\n  color-scheme: {scheme};\n{lines}\n}}\n")
    return "\n".join(parts)


if __name__ == "__main__":
    CSS_FILE.write_text(build_css(), encoding="utf-8")
    print(f"{CSS_FILE.relative_to(ROOT)}: {len(design.themes())} Farbschemen")
