"""Setzt die Startseite (index.html) aus ihren Teilen zusammen.

- Eine Zeile ``<!-- include: dialogs/name.html -->`` wird durch den Inhalt dieser Datei ersetzt
  (Pfad relativ zum Frontend-Ordner, nur eine Ebene, kein Verlassen des Ordners).
- ``{{v}}`` wird durch eine Versionskennung der Frontend-Dateien ersetzt (Cache-Buster für
  ``?v=…``). Sie ergibt sich aus Pfad, Größe und Änderungszeit aller .js/.css-Dateien und ändert
  sich damit bei jedem Deploy, auch beim reinen Frontend-Deploy ohne Neustart.
"""
import hashlib
import re
from pathlib import Path

INCLUDE_RE = re.compile(r"^[ \t]*<!-- include: ([\w./-]+) -->[ \t]*\n", re.MULTILINE)
VERSION_PLACEHOLDER = "{{v}}"


def asset_version(frontend_dir: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(frontend_dir.rglob("*")):
        if path.suffix in (".js", ".css") and path.is_file():
            st = path.stat()
            h.update(f"{path.relative_to(frontend_dir)}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:10]


def _include(frontend_dir: Path, match: re.Match) -> str:
    root = frontend_dir.resolve()
    target = (root / match.group(1)).resolve()
    if root not in target.parents or not target.is_file():
        raise FileNotFoundError(f"index.html: Teil {match.group(1)!r} fehlt")
    return target.read_text(encoding="utf-8")


def render_index(frontend_dir: Path) -> str:
    html = (frontend_dir / "index.html").read_text(encoding="utf-8")
    html = INCLUDE_RE.sub(lambda m: _include(frontend_dir, m), html)
    return html.replace(VERSION_PLACEHOLDER, asset_version(frontend_dir))
