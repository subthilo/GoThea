"""Ausmalbilder aus hochgeladenen Vektorgrafiken (SVG): Linien bestimmen, Felder berechnen, freigeben.

Konzept-Doc, Tab „Ausmalbilder“. Felder sind die hellen Flächen, die ringsum von Linie umschlossen sind;
was zusammenhängend nach außen reicht, ist Hintergrund. Linie ist alles Dunkle: dunkel gefüllte Formen
(Even-Odd, verschachtelte Löcher – so liegen nachgezeichnete Bilder vor) und dunkle Striche (als Fläche
ihrer Breite). Haarspalten handgezeichneter Linien werden vorher geschlossen; Felder, die zu klein für den
Stift sind, gehören zur Linie.

Ergebnis (DATA_DIR/coloring/<id>.json), alles im 1000er-Raster (längere Seite = 1000):
  ink      Linienfläche (Even-Odd-Pfad) – zeichnet der Browser in Theas Linienfarbe
  fields   je Feld der Pfad zum Begrenzen der Striche; reicht um `bleed` unter die Linie, damit beim
           Dünnermachen der Linie kein weißer Rand aufblitzt
  outline  Umriss des Bildes (außerhalb = Hintergrund)
  thumb    vereinfachte Linienfläche für Listen
Die hochgeladene SVG geht nie an den Browser (SVGs können Skripte enthalten).

Dauer auf dem Pi für ein nachgezeichnetes Mandala mit rund 1800 Ringen: etwa 40 s – deshalb im Hintergrund.
"""
import json
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, List

from sqlalchemy.orm import Session

from backend.app import config
from backend.app.database import SessionLocal
from backend.app.models.coloring_page import ColoringPage

logger = logging.getLogger(__name__)

VERSION = 1
BOX = 1000.0                   # längere Seite des Ergebnisses
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
CLOSE_GAPS = 0.4 / 600         # Haarspalten bis zu diesem Anteil der Bildkante schließen (Probe: 0,4 px bei 600 px)
SAMPLE = 1 / 1500              # Abstand der Punkte beim Abtasten von Kurven (Anteil der Bildkante)
MIN_FIELD_AREA = 12.0          # im 1000er-Raster; kleinere Flächen gehören zur Linie
SIMPLIFY = 0.3                 # Vereinfachung der Linienfläche (1000er-Raster; sichtbar, also fein)
SIMPLIFY_FIELDS = 0.35         # Felder nur zum Begrenzen und Treffen, liegen unter der Linie: gröber
SIMPLIFY_THUMB = 5.0           # Vorschaubild in Listen

# Für die Hintergrund-Berechnung (Tests setzen eine eigene Sitzung)
session_factory: Callable[[], Session] = SessionLocal


def coloring_dir() -> Path:
    path = config.DATA_DIR / "coloring"
    path.mkdir(parents=True, exist_ok=True)
    return path


def svg_path(page: ColoringPage) -> Path:
    return coloring_dir() / f"{page.id}.svg"


def shapes_path(page: ColoringPage) -> Path:
    return coloring_dir() / f"{page.id}.json"


# ---- Berechnung ----
class ColoringError(ValueError):
    """Die Datei taugt nicht als Ausmalbild (Meldung für die Eltern)."""


def _d(geom, digits: int = 1) -> str:
    """Even-Odd-Pfad aus (Multi-)Polygonen."""
    parts = []
    for g in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        if g.is_empty:
            continue
        for ring in [g.exterior, *g.interiors]:
            pts = list(ring.coords)[:-1]
            if len(pts) >= 3:
                parts.append("M" + "L".join(f"{x:.{digits}f} {y:.{digits}f}" for x, y in pts) + "Z")
    return "".join(parts)


def compute(data: bytes) -> dict:
    """SVG → Linienfläche, Felder, Umriss (1000er-Raster). Wirft ColoringError bei unbrauchbaren Dateien."""
    import numpy as np
    from shapely.affinity import affine_transform
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    from svgelements import SVG, Color, Path as SvgPath, Shape

    try:
        svg = SVG.parse(BytesIO(data))
    except Exception as e:  # kaputtes XML, unbekannte Struktur
        raise ColoringError(f"Die Datei ist keine lesbare SVG-Grafik ({e.__class__.__name__}).")

    def dark(color) -> bool:
        if color is None or color.value is None:
            return False
        c = Color(color)
        return c.alpha > 80 and c.brightness < 0.5

    shapes = [el for el in svg.elements() if isinstance(el, Shape)]
    boxes = [el.bbox() for el in shapes if el.bbox() is not None]
    if not boxes:
        raise ColoringError("In der Datei sind keine Formen.")
    W = float(svg.width or 0) or max(b[2] for b in boxes)
    H = float(svg.height or 0) or max(b[3] for b in boxes)
    size = max(W, H)
    step = size * SAMPLE

    def sample(path) -> List[tuple]:
        n = max(8, int(path.length(error=1e-3) / step))
        return [tuple(p) for p in path.npoint(np.linspace(0, 1, n + 1))]

    rings, strokes = [], []
    for el in shapes:
        path = SvgPath(el)
        if len(path) == 0:
            continue
        if dark(el.fill):
            for sub in path.as_subpaths():
                pts = sample(SvgPath(sub))
                if len(pts) >= 4:
                    poly = Polygon(pts).buffer(0)
                    if not poly.is_empty and poly.area > 0:
                        rings.append(poly)
        width = getattr(el, "implicit_stroke_width", None) or el.stroke_width or 0
        if width and dark(el.stroke):
            for sub in path.as_subpaths():
                pts = sample(SvgPath(sub))
                if len(pts) >= 2:
                    strokes.append(LineString(pts).buffer(width / 2))
    if not rings and not strokes:
        raise ColoringError("Keine dunklen Linien gefunden – ist das Bild schon farbig?")

    # Even-Odd: ein Ring ist schwarz bei gerader Verschachtelungstiefe, ein Loch bei ungerader
    tree = STRtree(rings)
    depth = []
    for i, r in enumerate(rings):
        pt = r.representative_point()
        depth.append(sum(1 for j in tree.query(r)
                         if j != i and rings[j].area > r.area and rings[j].contains(pt)))
    pieces = []
    for i, r in enumerate(rings):
        if depth[i] % 2 == 0:
            kids = [rings[j] for j in tree.query(r)
                    if depth[j] == depth[i] + 1 and r.contains(rings[j].representative_point())]
            pieces.append(r.difference(unary_union(kids)) if kids else r)
    ink = unary_union(pieces + strokes)

    close = size * CLOSE_GAPS
    ink = ink.buffer(close).buffer(-close)

    # Ins 1000er-Raster
    s = BOX / size
    ink = affine_transform(ink, [s, 0, 0, s, 0, 0])
    w, h = W * s, H * s
    frame = box(0, 0, w, h).union(box(*ink.bounds))
    white = frame.difference(ink)
    comps = list(white.geoms) if hasattr(white, "geoms") else [white]
    edge = frame.exterior
    outside = [c for c in comps if c.intersects(edge)]
    inside = [c for c in comps if not c.intersects(edge)]
    tiny = [c for c in inside if c.area < MIN_FIELD_AREA]
    fields = [c for c in inside if c.area >= MIN_FIELD_AREA]
    if not fields:
        raise ColoringError("Keine geschlossenen Felder gefunden – sind die Linien offen?")
    if tiny:
        ink = unary_union([ink, *tiny])
    outline = frame.difference(unary_union(outside)) if outside else frame

    # Wie weit reicht ein Feld unter die Linie? Etwa die halbe Linienbreite (Fläche / Randlänge)
    bleed = max(0.3, min(4.0, ink.area / max(ink.boundary.length, 1.0)))
    fields.sort(key=lambda f: (round(f.centroid.y / 20), f.centroid.x))
    clips = [f.buffer(bleed, join_style=2).intersection(outline).simplify(SIMPLIFY_FIELDS) for f in fields]

    return {
        "version": VERSION, "width": round(w, 1), "height": round(h, 1), "bleed": round(bleed, 2),
        "ink": _d(ink.simplify(SIMPLIFY)), "outline": _d(outline.simplify(SIMPLIFY)),
        "fields": [{"id": i, "d": _d(c)} for i, c in enumerate(clips)],
        "thumb": _d(ink.simplify(SIMPLIFY_THUMB), digits=0),
    }


# ---- Seiten ----
def summary(page: ColoringPage, parent: bool) -> dict:
    out = dict(id=page.id, name=page.name, status=page.status, width=page.width, height=page.height,
               field_count=page.field_count, created_at=page.created_at, updated_at=page.updated_at)
    if parent:
        out["error"] = page.error
    return out


def visible(page: ColoringPage, parent: bool) -> bool:
    return page.archived_at is None and (parent or page.status == "freigegeben")


def create(db: Session, name: str, data: bytes) -> ColoringPage:
    if not data:
        raise ColoringError("Die Datei ist leer.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ColoringError("Die Datei ist zu groß (höchstens 5 MB).")
    if b"<svg" not in data.lower():
        raise ColoringError("Das ist keine SVG-Datei.")
    page = ColoringPage(name=(name or "Ausmalbild").strip()[:120] or "Ausmalbild", status="rechnet")
    db.add(page)
    db.flush()
    svg_path(page).write_bytes(data)
    db.commit()
    return page


def process(page_id: str) -> None:
    """Hintergrund: Felder berechnen und Status setzen (eigene Sitzung, die Anfrage ist längst zurück)."""
    db = session_factory()
    try:
        page = db.get(ColoringPage, page_id)
        if page is None:
            return
        try:
            result = compute(svg_path(page).read_bytes())
        except ColoringError as e:
            page.status, page.error = "fehler", str(e)
        except Exception as e:
            logger.exception("Ausmalbild %s: Berechnung fehlgeschlagen", page_id)
            page.status, page.error = "fehler", f"Berechnung fehlgeschlagen ({e.__class__.__name__})."
        else:
            tmp = shapes_path(page).with_suffix(".json.tmp")
            tmp.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
            tmp.replace(shapes_path(page))
            page.status, page.error = "berechnet", None
            page.width, page.height, page.field_count = result["width"], result["height"], len(result["fields"])
        page.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def recover_interrupted(db: Session) -> int:
    """Beim Start: Berechnungen, die ein Neustart abgebrochen hat, als Fehler markieren (neu berechenbar)."""
    pages = db.query(ColoringPage).filter(ColoringPage.status == "rechnet").all()
    for page in pages:
        page.status, page.error = "fehler", "Berechnung unterbrochen (Neustart) – bitte neu berechnen."
    db.commit()
    return len(pages)


def set_released(db: Session, page: ColoringPage, released: bool) -> ColoringPage:
    if page.status not in ("berechnet", "freigegeben"):
        raise ColoringError("Nur fertig berechnete Bilder lassen sich freigeben.")
    page.status = "freigegeben" if released else "berechnet"
    page.updated_at = datetime.utcnow()
    db.commit()
    return page


def thumb_svg(page: ColoringPage) -> "bytes | None":
    """Kleines SVG aus der berechneten Linienfläche (für Listen; nie das hochgeladene Original)."""
    path = shapes_path(page)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {data["width"]} {data["height"]}">'
            f'<path d="{data["thumb"]}" fill="#000" fill-rule="evenodd"/></svg>').encode()


def shapes_version(page: ColoringPage) -> int:
    return int(page.updated_at.timestamp() * 1000) if page.updated_at else 0

