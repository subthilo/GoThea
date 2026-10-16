"""Erzeugt frontend/css/icons.css aus allen SVGs in frontend/Icons.

Jedes Icon wird als CSS-Maske eingebunden und übernimmt so die Textfarbe (currentColor) –
hell auf dunklem Grund, Hover- und Aktiv-Farben inklusive. Nach dem Hinzufügen eines Icons
dieses Skript laufen lassen; tests/unit/test_icons.py prüft, dass die CSS-Datei aktuell ist.

Aufruf: .venv/bin/python scripts/build_icon_css.py
"""
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "frontend" / "Icons"
CSS_FILE = ROOT / "frontend" / "css" / "icons.css"

HEADER = """/* ==========================================================================
   ICONS – erzeugt von scripts/build_icon_css.py, nicht von Hand ändern.
   Verwendung: <span class="ui-icon i-suche" aria-hidden="true"></span>
   bzw. in JS: icon("Suche"). Das Icon folgt der Textfarbe (currentColor).
   ========================================================================== */
.ui-icon {
  display: inline-block;
  flex: none;
  width: 1.2em;
  height: 1.2em;
  vertical-align: -0.22em;
  background-color: currentColor;
  -webkit-mask: no-repeat center / contain;
  mask: no-repeat center / contain;
}
"""


def icon_slug(name: str) -> str:
    """Dateiname ohne Endung → CSS-Klassenteil (muss zu iconSlug() in js/icons.js passen)."""
    s = name.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), (" ", "-")):
        s = s.replace(a, b)
    return s


def build_css() -> str:
    rules = []
    for svg in sorted(ICON_DIR.glob("*.svg"), key=lambda p: icon_slug(p.stem)):
        url = "/static/Icons/" + quote(svg.name)
        rules.append(f'.i-{icon_slug(svg.stem)} {{ -webkit-mask-image: url("{url}"); mask-image: url("{url}"); }}')
    return HEADER + "\n" + "\n".join(rules) + "\n"


if __name__ == "__main__":
    CSS_FILE.write_text(build_css(), encoding="utf-8")
    print(f"{CSS_FILE.relative_to(ROOT)} geschrieben.")
