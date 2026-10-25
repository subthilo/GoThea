"""Ausmalbilder: aus SVG-Linien werden Felder – gefüllte Linien, Striche, Lücken, Punkte, Transformationen."""
import pytest

pytest.importorskip("shapely")
pytest.importorskip("svgelements")
from shapely.geometry import Point  # noqa: E402
from svgelements import Path as SvgPath  # noqa: E402

from backend.app.services import coloring_pages as svc  # noqa: E402


def svg(body, view="0 0 100 100", size=""):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" {size}>{body}</svg>'.encode()


def field_at(result, x, y):
    """Welches Feld liegt am Punkt (im 1000er-Raster)? Even-Odd wie im Browser: ungerade viele Ringe."""
    from shapely.geometry import Polygon
    hits = []
    for f in result["fields"]:
        inside = 0
        for sub in SvgPath(f["d"]).as_subpaths():
            pts = [(p.x, p.y) for p in SvgPath(sub).as_points()]
            if len(pts) >= 3 and Polygon(pts).contains(Point(x, y)):
                inside += 1
        if inside % 2:
            hits.append(f["id"])
    return hits


# Rahmen mit Loch (gefüllt, Even-Odd), senkrechter Balken teilt das Innere, ein Punkt links
FILLED = svg('<path fill-rule="evenodd" d="M0 0H100V100H0Z M10 10H90V90H10Z"/>'
             '<rect x="48" y="10" width="4" height="80"/><circle cx="25" cy="50" r="3"/>')


def test_filled_lines_give_two_fields_and_dots_are_holes():
    r = svc.compute(FILLED)
    assert (r["width"], r["height"]) == (1000.0, 1000.0)
    assert len(r["fields"]) == 2
    left, right = field_at(r, 300, 500), field_at(r, 700, 500)
    assert len(left) == 1 and len(right) == 1 and left != right
    assert field_at(r, 250, 500) == []        # im Punkt: Linie, kein Feld
    assert field_at(r, 50, 50) == []          # im Rahmen: Linie


def test_strokes_become_lines():
    data = svg('<circle cx="50" cy="50" r="40" fill="none" stroke="#000" stroke-width="2"/>'
               '<line x1="10" y1="50" x2="90" y2="50" stroke="black" stroke-width="2"/>')
    r = svc.compute(data)
    assert len(r["fields"]) == 2
    assert field_at(r, 500, 300) != field_at(r, 500, 700)
    assert field_at(r, 30, 30) == []          # außerhalb des Kreises: Hintergrund


def test_hairline_gaps_are_closed_but_real_openings_are_not():
    # Kreis aus zwei Bögen, dazwischen ein Haarspalt (0,02 % der Kante) – wird geschlossen
    arcs = ('<path d="M50 10 A40 40 0 0 1 50 90" fill="none" stroke="#000" stroke-width="1.5"/>'
            '<path d="M50 {g1} A40 40 0 0 1 50 {g2}" fill="none" stroke="#000" stroke-width="1.5"/>')
    closed = svg(arcs.format(g1="90.02", g2="9.98").replace("A40 40 0 0 1 50 9.98", "A40 40 0 0 1 50 9.98"))
    assert len(svc.compute(closed)["fields"]) == 1
    # breite Lücke: das Innere läuft nach außen aus – kein Feld
    opened = svg('<path d="M50 10 A40 40 0 0 1 50 90" fill="none" stroke="#000" stroke-width="1.5"/>'
                 '<path d="M45 89 A40 40 0 0 1 45 11" fill="none" stroke="#000" stroke-width="1.5"/>')
    with pytest.raises(svc.ColoringError):
        svc.compute(opened)


def test_default_fill_is_black_and_transforms_apply():
    data = svg('<g transform="translate(10 10) scale(0.8)"><path d="M0 0H100V100H0Z M5 5H95V95H5Z" '
               'fill-rule="evenodd"/></g>', view="0 0 100 100")
    r = svc.compute(data)
    assert len(r["fields"]) == 1
    assert field_at(r, 500, 500) and not field_at(r, 50, 50)


def test_coloured_pictures_and_garbage_are_rejected():
    with pytest.raises(svc.ColoringError, match="farbig"):
        svc.compute(svg('<rect width="100" height="100" fill="#ffd400"/>'))
    with pytest.raises(svc.ColoringError):
        svc.compute(b"<svg><path d='M0 0 L")


def test_wide_pictures_keep_their_aspect():
    data = svg('<path fill-rule="evenodd" d="M0 0H200V100H0Z M10 10H190V90H10Z"/>', view="0 0 200 100")
    r = svc.compute(data)
    assert (r["width"], r["height"]) == (1000.0, 500.0)
