"""Bemalbare Flächen: jede ausgewiesene Kachel hat eine bekannte Kachelart (js/paint_slots.js)."""
import re
from pathlib import Path

from backend.app.services.paintings import FORMAT_RE, SLOT_KEY_RE

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _kinds():
    src = (FRONTEND / "js" / "paint_slots.js").read_text(encoding="utf-8")
    block = re.search(r"const PAINT_TILE_KINDS = \{(.*?)\n\};", src, re.S).group(1)
    return dict(re.findall(r"^\s*([a-z0-9_-]+): \{ aspect: ([0-9.]+) \}", block, re.M))


def _sources():
    files = [FRONTEND / "index.html", *sorted((FRONTEND / "js").glob("*.js")), *sorted((FRONTEND / "dialogs").glob("*.html"))]
    # Kommentarzeilen (Erklärungen mit Platzhaltern wie "<Kachelart>") zählen nicht
    return {f.name: re.sub(r"^\s*//.*$", "", f.read_text(encoding="utf-8"), flags=re.M) for f in files}


def test_tile_kinds_are_valid_formats():
    kinds = _kinds()
    assert kinds, "keine Kachelarten gefunden"
    for name, aspect in kinds.items():
        assert FORMAT_RE.match(name) and name != "square", name
        assert float(aspect) > 0


def test_every_marked_tile_has_a_known_kind():
    kinds = _kinds()
    used = set()
    for name, text in _sources().items():
        used |= {(name, k) for k in re.findall(r'data-paint-kind="([^"]+)"', text)}
        used |= {(name, k) for k in re.findall(r'dataset\.paintKind = "([^"]+)"', text)}
    assert used, "keine bemalbaren Kacheln gefunden"
    unknown = sorted((f, k) for f, k in used if k not in kinds)
    assert not unknown, f"unbekannte Kachelart: {unknown}"


def test_static_tile_names_are_valid_slot_parts():
    for name, text in _sources().items():
        for tile in re.findall(r'data-paint-tile="([^"]+)"', text):
            assert SLOT_KEY_RE.match(tile) and "/" not in tile and tile != "tile", (name, tile)
            assert not tile.startswith("sub_"), (name, tile)  # sub_… ist für Fach-IDs reserviert (Rückfall)
