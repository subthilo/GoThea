"""Blüten-Mandalas zum Ausmalen (indischer Stil): der Code zeichnet Linien, die Felder berechnet die Geometrie.

Gezeichnet wird wie von Hand, von außen nach innen in Schichten: Schmuck an den Spitzen, äußere und innere
Blütenblätter (versetzt, mit Innenblatt, Ader und Tropfen), ein Perlenkranz, Bänder (Perlen mit Auge,
überlappende Kreise wie beim Spirographen, Bögen, Zacken), in der Mitte eine Sonne aus schmalen Blättern.
Was weiter vorn liegt, verdeckt die Linien dahinter (die Blätter liegen wirklich übereinander).

Felder: shapely bildet aus allen Linien die geschlossenen Flächen (polygonize). Flächen, die für den Stift
zu klein oder zu schmal sind, werden „Tinte“ – in Linienfarbe gefüllt, nicht bemalbar (wie bei gedruckten
Mandalas, wo sich Linien drängen). Jedes Feld ist ein Pfad mit Even-Odd-Regel (Löcher = innere Ränder);
damit prüft der Browser beim Malen, in welchem Feld der Stift aufsetzt, und begrenzt den Strich darauf.

Koordinaten: Quadrat 0…SIZE, Mitte in der Mitte, Winkel 0 = oben, im Uhrzeigersinn.
Gespeichert wird später die fertige Form (nicht der Startwert): Verbesserungen am Generator ändern
Theas Bilder nicht.
"""
import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import polygonize, unary_union

VERSION = 2
SIZE = 1000.0
C = SIZE / 2
R_MAX = 490.0

XY = Tuple[float, float]

DIFFICULTIES = {
    # fields: bemalbare Felder; ink_*: kleiner/schmaler wird Tinte (Einheiten des 1000er-Quadrats)
    "leicht": dict(fields=(25, 90), ink_area=900.0, ink_width=12.0, symmetry=(8, 10), bands=(1, 1),
                   details=0.2, spiro=False),
    "mittel": dict(fields=(80, 220), ink_area=420.0, ink_width=8.0, symmetry=(12, 16), bands=(2, 2),
                   details=0.6, spiro=True),
    "schwer": dict(fields=(200, 480), ink_area=160.0, ink_width=5.0, symmetry=(16, 20, 24), bands=(2, 3),
                   details=0.9, spiro=True),
}


def polar(r: float, a: float) -> XY:
    return (C + r * math.sin(a), C - r * math.cos(a))


def bezier(p0: XY, c1: XY, c2: XY, p1: XY, steps: int = 18) -> List[XY]:
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p1[0],
                    u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p1[1]))
    return out


def circle_pts(cx: float, cy: float, r: float, steps: Optional[int] = None) -> List[XY]:
    steps = steps or max(24, int(r * 0.9))
    return [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps))
            for i in range(steps + 1)]


# ---- Zeichenfläche mit Schichten ----
class Canvas:
    """Linien von hinten nach vorn: jede neue Form mit Fläche verdeckt, was schon hinter ihr liegt."""

    def __init__(self):
        self.lines: List = []

    def add(self, pts: Sequence[XY], cover: bool = True) -> None:
        """Geschlossene Form (erster = letzter Punkt): verdeckt die Linien dahinter; offen: nur Linie."""
        closed = len(pts) > 3 and math.dist(pts[0], pts[-1]) < 1e-6
        if closed and cover:
            self.cover(Polygon(pts))
        self.lines.append(LineString(pts))

    def cover(self, area) -> None:
        area = area.buffer(0)
        self.lines = [g for g in (line.difference(area) for line in self.lines) if not g.is_empty]

    def add_circle(self, r: float, cx: float = C, cy: float = C, cover: bool = True) -> None:
        self.add(circle_pts(cx, cy, r), cover)


# ---- Motive ----
def petal_pts(rb: float, rt: float, am: float, hw: float, shape: str) -> List[XY]:
    """Blatt mit Fuß auf dem Kreis rb (Breite ±hw), Spitze bei rt; geschlossen über den Fuß."""
    L = rt - rb
    if shape == "zwiebel":   # Kuppel mit Spitze (indisch)
        k = [(0.40, 1.30), (0.82, 0.18)]
    elif shape == "rund":
        k = [(0.45, 1.20), (0.95, 0.75)]
    else:                    # spitz
        k = [(0.35, 1.05), (0.75, 0.45)]
    b0, b1, tip = polar(rb, am - hw), polar(rb, am + hw), polar(rt, am)
    left = bezier(b0, polar(rb + L * k[0][0], am - hw * k[0][1]), polar(rb + L * k[1][0], am - hw * k[1][1]), tip)
    right = bezier(tip, polar(rb + L * k[1][0], am + hw * k[1][1]), polar(rb + L * k[0][0], am + hw * k[0][1]), b1)
    base = [polar(rb, am + hw - 2 * hw * i / 8) for i in range(1, 8)]
    return left + right[1:] + base + [b0]


def drop_pts(r0: float, r1: float, am: float, hw: float) -> List[XY]:
    """Tropfen: runder Fuß innen bei r0, Spitze außen bei r1."""
    L = r1 - r0
    tip, bottom = polar(r1, am), polar(r0, am)
    a = bezier(tip, polar(r1 - L * 0.45, am - hw * 0.6), polar(r0 - L * 0.05, am - hw * 1.3), bottom)
    b = bezier(bottom, polar(r0 - L * 0.05, am + hw * 1.3), polar(r1 - L * 0.45, am + hw * 0.6), tip)
    return a + b[1:]


def leaf_pts(r0: float, r1: float, am: float, hw: float) -> List[XY]:
    """Schmales spitzes Blatt (beide Enden spitz) – Sonne in der Mitte, Augen in Blättern."""
    p0, p1 = polar(r0, am), polar(r1, am)
    L = r1 - r0
    a = bezier(p0, polar(r0 + L * 0.3, am - hw), polar(r0 + L * 0.7, am - hw), p1)
    b = bezier(p1, polar(r0 + L * 0.7, am + hw), polar(r0 + L * 0.3, am + hw), p0)
    return a + b[1:]


def curl_pts(cx: float, cy: float, r: float, turns: float, a0: float, direction: int) -> List[XY]:
    """Kringel: offene Spirale nach innen (Schmuck, bildet kein Feld)."""
    n = int(40 * turns)
    return [(cx + r * (1 - 0.8 * i / n) * math.sin(a0 + direction * 2 * math.pi * turns * i / n),
             cy - r * (1 - 0.8 * i / n) * math.cos(a0 + direction * 2 * math.pi * turns * i / n)) for i in range(n + 1)]


@dataclass
class Plan:
    seed: int
    difficulty: str
    n: int
    steps: List[str] = field(default_factory=list)  # für den Fingerabdruck


def build_lines(seed: int, difficulty: str) -> Tuple[Canvas, Plan]:
    spec = DIFFICULTIES[difficulty]
    rnd = random.Random(seed)
    n = rnd.choice(spec["symmetry"])
    plan = Plan(seed=seed, difficulty=difficulty, n=n)
    cv = Canvas()
    d = 2 * math.pi / n
    detail = lambda: rnd.random() < spec["details"]

    # Radien (von innen): Mitte | Bänder | Perlenkranz | Blätter innen | Blätter außen | Spitzen
    r_center = R_MAX * (rnd.uniform(0.22, 0.26) if difficulty == "leicht" else rnd.uniform(0.15, 0.2))
    r_bands = R_MAX * rnd.uniform(0.40, 0.48)
    bead_w = R_MAX * (rnd.uniform(0.09, 0.11) if difficulty == "leicht" else rnd.uniform(0.06, 0.085))
    r_beads = r_bands + bead_w
    r_tip_out = R_MAX * rnd.uniform(0.86, 0.93)
    r_tip_in = r_beads + (r_tip_out - r_beads) * rnd.uniform(0.55, 0.72)
    shape_out, shape_in = rnd.choice(["zwiebel", "spitz", "rund"]), rnd.choice(["zwiebel", "spitz"])
    plan.steps += [shape_out, shape_in]

    # 1) Schmuck an den äußeren Spitzen (ganz hinten)
    deco = rnd.choice(["punkt", "tropfen", "kringel"] if difficulty != "leicht" else ["punkt"])
    plan.steps.append(deco)
    for k in range(n):
        am = (k + 0.5) * d
        if deco == "punkt":
            rr = min(R_MAX - r_tip_out, r_tip_out * math.sin(d / 2)) * 0.55
            x, y = polar(r_tip_out + rr * 0.85, am)  # sitzt auf der Blattspitze
            cv.add_circle(rr, x, y)
        elif deco == "tropfen":
            cv.add(drop_pts(r_tip_out + 4, R_MAX, am, d * 0.18))
        else:
            for side in (-1, 1):
                x, y = polar(r_tip_out - 6, am + side * d * 0.22)
                cv.add(curl_pts(x, y, (R_MAX - r_tip_out) * 0.55, 1.4, am, side), cover=False)

    # 2) Äußere Blätter (zwischen den inneren, ragen weiter hinaus)
    hw_out = d / 2 * rnd.uniform(0.85, 1.0)
    for k in range(n):
        am = (k + 0.5) * d
        cv.add(petal_pts(r_beads, r_tip_out, am, hw_out, shape_out))
        if detail():
            L = r_tip_out - r_beads
            cv.add(petal_pts(r_beads + L * 0.12, r_tip_out - L * 0.14, am, hw_out * 0.55, shape_out))
        if detail():
            L = r_tip_out - r_beads
            cv.add(drop_pts(r_beads + L * 0.45, r_tip_out - L * 0.25, am, hw_out * 0.22))

    # 3) Innere Blätter (vorn, auf Lücke zu den äußeren)
    hw_in = d / 2 * rnd.uniform(0.9, 1.05)
    inner_detail = rnd.choice(["blatt", "auge", "ader"])
    plan.steps.append(inner_detail)
    for k in range(n):
        am = k * d
        cv.add(petal_pts(r_beads, r_tip_in, am, hw_in, shape_in))
        L = r_tip_in - r_beads
        if inner_detail == "blatt" and detail():
            cv.add(petal_pts(r_beads + L * 0.15, r_tip_in - L * 0.18, am, hw_in * 0.5, shape_in))
        elif inner_detail == "auge" and detail():
            cv.add(leaf_pts(r_beads + L * 0.25, r_tip_in - L * 0.25, am, hw_in * 0.45))
        elif detail():
            cv.add([polar(r_beads - 2, am), polar(r_tip_in - L * 0.12, am)], cover=False)

    # 4) Perlenkranz (vorn, verdeckt die Blattfüße)
    beads = n * (2 if difficulty != "leicht" and (r_bands * 2 * math.pi / n) > bead_w * 3.2 else 1)
    bead_r = min(bead_w / 2, (r_bands + bead_w / 2) * math.sin(math.pi / beads)) * 0.96
    cv.cover(Point(C, C).buffer(r_bands))
    for k in range(beads):
        x, y = polar(r_bands + bead_w / 2, (k + 0.5) * 2 * math.pi / beads)
        cv.add_circle(bead_r, x, y)
        if bead_r * 0.6 > spec["ink_width"] * 1.6:
            cv.add_circle(bead_r * 0.4, x, y)
    cv.add_circle(r_bands)
    plan.steps.append(f"perlen{beads}")

    # 5) Bänder zwischen Mitte und Perlenkranz (von außen nach innen)
    count = rnd.randint(*spec["bands"])
    edges = [r_bands]
    for i in range(count):
        edges.append(r_bands - (r_bands - r_center) * (i + 1) / count)
    kinds = ["spiro", "augen", "boegen", "zacken"] if spec["spiro"] else ["augen", "boegen", "zacken"]
    prev = None
    for i in range(count):
        r1, r0 = edges[i], edges[i + 1]
        kind = rnd.choice([k for k in kinds if k != prev])
        prev = kind
        plan.steps.append(kind)
        m = n * (2 if (r0 + r1) * math.pi / n > (r1 - r0) * 2.5 else 1)
        band = Point(C, C).buffer(r1).difference(Point(C, C).buffer(r0))
        if kind == "spiro":
            # überlappende Kreise, auf das Band beschnitten; so viele, dass die Linsen ausmalbar bleiben
            rs = (r1 - r0) * 0.62  # schneidet die Bandränder deutlich (Berühren gäbe Splitter)
            rm = (r0 + r1) / 2
            m = max(6, min(n, int(2 * math.pi * rm / (rs * 1.15))))
            for k in range(m):
                x, y = polar(rm, k * 2 * math.pi / m)
                circ = LineString(circle_pts(x, y, rs)).intersection(band)
                if not circ.is_empty:
                    cv.lines.append(circ)
        elif kind == "augen":
            rad = min((r1 - r0) * 0.36, (r0 + r1) / 2 * math.sin(math.pi / m) * 0.8)
            for k in range(m):
                x, y = polar((r0 + r1) / 2, (k + 0.5) * 2 * math.pi / m)
                cv.add_circle(rad, x, y, cover=False)
                if rad * 0.55 > spec["ink_width"] * 1.6:
                    cv.add_circle(rad * 0.45, x, y, cover=False)
        elif kind == "boegen":
            for k in range(m):
                a0, a1 = k * 2 * math.pi / m, (k + 1) * 2 * math.pi / m
                h = (r1 - r0) * 0.8
                cv.lines.append(LineString(bezier(polar(r0, a0), polar(r0 + h * 1.3, a0 + (a1 - a0) * 0.1),
                                                  polar(r0 + h * 1.3, a1 - (a1 - a0) * 0.1), polar(r0, a1))))
        else:  # zacken
            pts = []
            for k in range(m):
                pts += [polar(r0, k * 2 * math.pi / m), polar(r1, (k + 0.5) * 2 * math.pi / m)]
            cv.lines.append(LineString(pts + [pts[0]]))
        cv.add_circle(r1, cover=False)
        cv.add_circle(r0, cover=False)

    # 6) Mitte: Sonne aus schmalen Blättern um einen kleinen Kreis
    core = r_center * rnd.uniform(0.25, 0.35)
    rays = n if n <= 16 else n // 2
    cv.cover(Point(C, C).buffer(r_center))
    for k in range(rays):
        cv.add(leaf_pts(core * 1.15, r_center * 0.9, (k + 0.5) * 2 * math.pi / rays,
                        math.pi / rays * 0.85), cover=False)
    cv.add_circle(core, cover=False)
    cv.add_circle(r_center, cover=False)
    plan.steps.append(f"sonne{rays}")
    return cv, plan


# ---- Felder ----
@dataclass
class Mandala:
    plan: Plan
    lines: List                  # shapely-Linien (Linienbild)
    fields: List[Polygon]        # bemalbare Felder
    ink: List[Polygon]           # zu kleine Flächen, in Linienfarbe
    outline: object  # Polygon oder MultiPolygon (ohne Löcher)

    @property
    def difficulty(self) -> str:
        return self.plan.difficulty

    def signature(self) -> str:
        """Fingerabdruck gegen Doppelte: Symmetrie, Motivfolge, Feldzahl."""
        key = f"{self.plan.n}|{'-'.join(self.plan.steps)}|{len(self.fields) // 10}"
        return hashlib.sha1(key.encode()).hexdigest()[:16]

    def to_json(self) -> dict:
        return {
            "version": VERSION, "size": SIZE, "seed": self.plan.seed, "difficulty": self.plan.difficulty,
            "symmetry": self.plan.n, "signature": self.signature(),
            "outline": svg_polygon(self.outline),
            "fields": [{"id": i, "d": svg_polygon(p)} for i, p in enumerate(self.fields)],
            "ink": [svg_polygon(p) for p in self.ink],
            "lines": [svg_line(g) for g in self.lines],
        }


def _ring(coords) -> str:
    pts = list(coords)
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts[:-1]) + "Z"


def svg_polygon(p) -> str:
    p = p.simplify(0.25, preserve_topology=True)
    return "".join(_ring(g.exterior.coords) + "".join(_ring(h.coords) for h in g.interiors)
                   for g in (p.geoms if hasattr(p, "geoms") else [p]))


def svg_line(g) -> str:
    parts = g.geoms if hasattr(g, "geoms") else [g]
    out = []
    for part in parts:
        if part.length < 0.5:
            continue
        pts = list(part.simplify(0.25).coords)
        out.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts))
    return "".join(out)


def width(p: Polygon) -> float:
    return 2 * p.area / p.length if p.length else 0.0


def build(seed: int, difficulty: str) -> Mandala:
    spec = DIFFICULTIES[difficulty]
    cv, plan = build_lines(seed, difficulty)
    merged = unary_union(MultiLineString([]) if not cv.lines else cv.lines)
    faces = list(polygonize(merged))
    fields, ink = [], []
    for f in faces:
        (ink if f.area < spec["ink_area"] or width(f) < spec["ink_width"] else fields).append(f)
    # Umriss = alles, was zum Mandala gehört (Teile, die sich nur in Punkten berühren, wachsen zusammen);
    # außerhalb davon ist Hintergrund
    merged_faces = unary_union(faces).buffer(0.5).buffer(-0.5)
    parts = merged_faces.geoms if hasattr(merged_faces, "geoms") else [merged_faces]
    outline = unary_union([Polygon(g.exterior) for g in parts])
    return Mandala(plan=plan, lines=cv.lines, fields=fields, ink=ink, outline=outline)


def check(m: Mandala) -> Optional[str]:
    """None = gut, sonst der Grund zum Verwerfen."""
    lo, hi = DIFFICULTIES[m.difficulty]["fields"]
    if not lo <= len(m.fields) <= hi:
        return f"{len(m.fields)} Felder"
    ink_area = sum(p.area for p in m.ink)
    if ink_area > 0.12 * m.outline.area:
        return f"zu viel Tinte ({ink_area / m.outline.area:.0%})"
    return None


def generate(difficulty: str, seed: int, known: Optional[set] = None, tries: int = 200) -> Tuple[Mandala, int]:
    """Erstes gutes, neues Mandala ab diesem Startwert; liefert es und den nächsten freien Startwert."""
    known = known if known is not None else set()
    for s in range(seed, seed + tries):
        m = build(s, difficulty)
        if check(m) is None and m.signature() not in known:
            return m, s + 1
    raise RuntimeError(f"Kein gutes Mandala ({difficulty}) ab Startwert {seed}")


def stats(m: Mandala) -> Dict[str, float]:
    return {"fields": len(m.fields), "ink": len(m.ink), "min_width": min(width(p) for p in m.fields)}
