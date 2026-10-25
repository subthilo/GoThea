"""Mandalas zum Ausmalen: der Code erzeugt sie aus einem Startwert, jedes Feld als geschlossene Form.

Aufbau: Mittelmotiv, dann konzentrische Ringe nach außen, je Ring ein Motiv (Blütenblätter, Tropfen,
Bögen, Punkte, Zacken, Rauten, Wellen, schlichtes Band), 6–16fach symmetrisch, äußere Ringe dürfen die
Teilung verdoppeln. Jedes Feld ist ein Pfad, der mit der Even-Odd-Regel gefüllt wird (Löcher = Motive im
Ringgrund); damit kann der Browser beim Malen prüfen, in welchem Feld der Stift aufsetzt, und den Strich
darauf begrenzen. Die Linien sind die Ränder der Felder.

Koordinaten: Quadrat 0…SIZE, Mitte in der Mitte, Winkel 0 = oben, im Uhrzeigersinn.
Qualität: zu kleine oder zu schmale Felder (mit dem Stift nicht auszumalen) und eine Feldzahl außerhalb der
Schwierigkeit verwerfen das Mandala; generate() versucht dann den nächsten Startwert.
Gespeichert wird später die fertige Form (nicht nur der Startwert), damit Verbesserungen am Generator
Theas Bilder nicht verändern.
"""
import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

VERSION = 1
SIZE = 1000.0
C = SIZE / 2
R_OUT = 490.0

Point = Tuple[float, float]

# Feldzahl und kleinste Felder je Schwierigkeit (Einheiten des 1000er-Quadrats; Breite = 2·Fläche/Umfang)
DIFFICULTIES = {
    "leicht": dict(fields=(20, 70), min_width=16.0, min_area=1400.0, rings=(3, 3), symmetry=(6, 8)),
    "mittel": dict(fields=(60, 160), min_width=10.0, min_area=600.0, rings=(4, 5), symmetry=(8, 10, 12)),
    "schwer": dict(fields=(140, 340), min_width=6.5, min_area=220.0, rings=(5, 7), symmetry=(12, 16)),
}


def polar(r: float, a: float) -> Point:
    return (C + r * math.sin(a), C - r * math.cos(a))


# ---- Pfade: SVG für den Browser, Polygon für die Prüfung ----
class Path:
    """Ein geschlossener Teilpfad aus Linien, Kreisbögen um die Mitte und kubischen Kurven."""

    def __init__(self, start: Point):
        self.start = start
        self.ops: List[tuple] = []
        self.cur = start

    def line(self, p: Point) -> "Path":
        self.ops.append(("L", p))
        self.cur = p
        return self

    def arc(self, r: float, a0: float, a1: float) -> "Path":
        """Kreisbogen um die Mitte von Winkel a0 nach a1 (a1 > a0: im Uhrzeigersinn)."""
        self.ops.append(("A", r, a0, a1))
        self.cur = polar(r, a1)
        return self

    def curve(self, c1: Point, c2: Point, p: Point) -> "Path":
        self.ops.append(("C", c1, c2, p))
        self.cur = p
        return self

    def svg(self) -> str:
        f = lambda p: f"{p[0]:.1f} {p[1]:.1f}"
        out = [f"M{f(self.start)}"]
        for op in self.ops:
            if op[0] == "L":
                out.append(f"L{f(op[1])}")
            elif op[0] == "C":
                out.append(f"C{f(op[1])} {f(op[2])} {f(op[3])}")
            else:
                _, r, a0, a1 = op
                # Volle Kreise in zwei Hälften (ein SVG-Bogen kann nicht an seinen Anfang zurück)
                steps = 2 if abs(a1 - a0) > math.pi * 1.5 else 1
                for i in range(1, steps + 1):
                    a = a0 + (a1 - a0) * i / steps
                    large = 1 if abs(a1 - a0) / steps > math.pi else 0
                    sweep = 1 if a1 > a0 else 0
                    out.append(f"A{r:.1f} {r:.1f} 0 {large} {sweep} {f(polar(r, a))}")
        return "".join(out) + "Z"

    def polygon(self) -> List[Point]:
        pts = [self.start]
        cur = self.start
        for op in self.ops:
            if op[0] == "L":
                pts.append(op[1])
            elif op[0] == "C":
                _, c1, c2, p = op
                for i in range(1, 13):
                    t = i / 12
                    u = 1 - t
                    pts.append((u ** 3 * cur[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p[0],
                                u ** 3 * cur[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p[1]))
            else:
                _, r, a0, a1 = op
                n = max(2, int(abs(a1 - a0) * r / 6))
                pts.extend(polar(r, a0 + (a1 - a0) * i / n) for i in range(1, n + 1))
            cur = pts[-1]
        return pts


def _area(poly: List[Point]) -> float:
    s = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


def _perimeter(poly: List[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(poly, poly[1:] + poly[:1]))


@dataclass
class Field:
    """Ein Feld: erster Teilpfad = Umriss, weitere = Löcher (Even-Odd)."""
    outer: Path
    holes: List[Path] = field(default_factory=list)

    def svg(self) -> str:
        return "".join(p.svg() for p in [self.outer, *self.holes])

    def area(self) -> float:
        return _area(self.outer.polygon()) - sum(_area(h.polygon()) for h in self.holes)

    def width(self) -> float:
        perim = _perimeter(self.outer.polygon()) + sum(_perimeter(h.polygon()) for h in self.holes)
        return 2 * self.area() / perim if perim else 0.0


# ---- Grundformen ----
def circle(r: float) -> Path:
    return Path(polar(r, 0)).arc(r, 0, 2 * math.pi)


def sector(r0: float, r1: float, a0: float, a1: float) -> Path:
    p = Path(polar(r0, a0)).line(polar(r1, a0)).arc(r1, a0, a1).line(polar(r0, a1))
    return p.arc(r0, a1, a0) if r0 > 0 else p


def annulus(r0: float, r1: float, holes: List[Path]) -> Field:
    return Field(circle(r1), ([circle(r0)] if r0 > 0 else []) + holes)


def petal(a: float, b: float, am: float, hw: float, roundness: float) -> Path:
    """Blütenblatt von Radius a (Ansatz) bis b (Spitze), Mitte bei Winkel am, halbe Breite hw (Winkel)."""
    L = b - a
    base, tip = polar(a, am), polar(b, am)
    k1, k2 = 0.9 + roundness * 0.4, 0.6 + roundness * 0.7
    left = (polar(a + L * 0.25, am - hw * k1), polar(a + L * 0.8, am - hw * k2))
    right = (polar(a + L * 0.25, am + hw * k1), polar(a + L * 0.8, am + hw * k2))
    return Path(base).curve(left[0], left[1], tip).curve(right[1], right[0], base)


def drop(a: float, b: float, am: float, hw: float) -> Path:
    """Tropfen: runder Fuß innen bei a, Spitze außen bei b."""
    L = b - a
    tip, bottom = polar(b, am), polar(a, am)
    return (Path(tip)
            .curve(polar(b - L * 0.45, am - hw * 0.55), polar(a - L * 0.02, am - hw * 1.25), bottom)
            .curve(polar(a - L * 0.02, am + hw * 1.25), polar(b - L * 0.45, am + hw * 0.55), tip))


def dot(rm: float, am: float, rad: float) -> Path:
    cx, cy = polar(rm, am)
    k = 0.5523 * rad
    return (Path((cx, cy - rad))
            .curve((cx + k, cy - rad), (cx + rad, cy - k), (cx + rad, cy))
            .curve((cx + rad, cy + k), (cx + k, cy + rad), (cx, cy + rad))
            .curve((cx - k, cy + rad), (cx - rad, cy + k), (cx - rad, cy))
            .curve((cx - rad, cy - k), (cx - k, cy - rad), (cx, cy - rad)))


def diamond(r0: float, r1: float, am: float, hw: float) -> Path:
    rm = (r0 + r1) / 2
    return (Path(polar(r1, am)).line(polar(rm, am + hw)).line(polar(r0, am)).line(polar(rm, am - hw)))


# ---- Ringe: jeder liefert seine Felder ----
@dataclass
class Ring:
    kind: str
    r0: float
    r1: float
    n: int
    phase: float
    dividers: bool
    variant: float  # 0…1, Form-Feinheit je Motiv
    nested: bool


def ring_fields(ring: Ring) -> List[Field]:
    r0, r1, n, ph = ring.r0, ring.r1, ring.n, ring.phase
    d = 2 * math.pi / n
    band = r1 - r0
    pad = band * 0.06
    mid = lambda k: ph + (k + 0.5) * d
    fields: List[Field] = []

    def ground(motifs_per_sector: List[List[Path]]) -> None:
        if ring.dividers:
            for k in range(n):
                fields.append(Field(sector(r0, r1, ph + k * d, ph + (k + 1) * d), motifs_per_sector[k]))
        else:
            fields.append(annulus(r0, r1, [m for ms in motifs_per_sector for m in ms]))

    if ring.kind in ("petals", "drops", "diamonds", "dots"):
        motifs: List[List[Path]] = []
        hw = d / 2 * (0.62 + 0.25 * ring.variant)
        for k in range(n):
            am = mid(k)
            if ring.kind == "petals":
                outer = petal(r0 + pad, r1 - pad, am, hw, ring.variant)
                inner = petal(r0 + pad + band * 0.22, r1 - pad - band * 0.18, am, hw * 0.45, ring.variant) \
                    if ring.nested else None
            elif ring.kind == "drops":
                outer = drop(r0 + pad + band * 0.12, r1 - pad, am, hw * 0.8)
                inner = drop(r0 + pad + band * 0.32, r1 - pad - band * 0.2, am, hw * 0.38) if ring.nested else None
            elif ring.kind == "diamonds":
                outer = diamond(r0 + pad, r1 - pad, am, hw)
                inner = diamond(r0 + pad + band * 0.22, r1 - pad - band * 0.22, am, hw * 0.45) \
                    if ring.nested else None
            else:
                rad = min(band / 2 - pad, (r0 + band / 2) * math.sin(d / 2) * 0.82) * (0.7 + 0.25 * ring.variant)
                outer = dot((r0 + r1) / 2, am, rad)
                inner = dot((r0 + r1) / 2, am, rad * 0.5) if ring.nested else None
            motifs.append([outer])
            fields.append(Field(outer, [inner] if inner else []))
            if inner:
                fields.append(Field(inner))
        ground(motifs)

    elif ring.kind == "zigzag":
        # Dreiecke abwechselnd innen und außen, füllen den Ring ganz
        for k in range(n):
            a0, am, a1 = ph + k * d, mid(k), ph + (k + 1) * d
            fields.append(Field(Path(polar(r0, a0)).line(polar(r1, am)).line(polar(r0, a1)).arc(r0, a1, a0)))
            fields.append(Field(Path(polar(r1, am)).arc(r1, am, am + d).line(polar(r0, a1)).line(polar(r1, am))))

    elif ring.kind == "scallops":
        # Bögen auf dem inneren Kreis, darüber der Grund (bei Teilern je Bogen ein Stück)
        h = band * (0.55 + 0.3 * ring.variant)
        bumps = []
        for k in range(n):
            a0, a1 = ph + k * d, ph + (k + 1) * d
            c1, c2 = polar(r0 + h * 1.3, a0 + d * 0.08), polar(r0 + h * 1.3, a1 - d * 0.08)
            bumps.append((a0, a1, c1, c2))
            fields.append(Field(Path(polar(r0, a0)).curve(c1, c2, polar(r0, a1)).arc(r0, a1, a0)))
        if ring.dividers:
            for a0, a1, c1, c2 in bumps:
                fields.append(Field(Path(polar(r0, a0)).curve(c1, c2, polar(r0, a1)).line(polar(r1, a1))
                                    .arc(r1, a1, a0).line(polar(r0, a0))))
        else:
            loop = Path(polar(r0, bumps[0][0]))
            for a0, a1, c1, c2 in bumps:
                loop.curve(c1, c2, polar(r0, a1))
            fields.append(Field(circle(r1), [loop]))

    elif ring.kind == "waves":
        # Wellenlinie teilt den Ring in innen und außen, Teiler an den Nulldurchgängen
        amp = band * (0.18 + 0.12 * ring.variant)
        rm = (r0 + r1) / 2
        wave = lambda a: rm + amp * math.sin((a - ph) * n)  # eine ganze Welle je Sektor, Nulldurchgang am Teiler
        for k in range(n):
            a0, a1 = ph + k * d, ph + (k + 1) * d
            pts = [polar(wave(a0 + (a1 - a0) * i / 16), a0 + (a1 - a0) * i / 16) for i in range(17)]
            inner = Path(polar(r0, a0)).line(pts[0])
            for p in pts[1:]:
                inner.line(p)
            fields.append(Field(inner.line(polar(r0, a1)).arc(r0, a1, a0)))
            outer = Path(pts[0])
            for p in pts[1:]:
                outer.line(p)
            fields.append(Field(outer.line(polar(r1, a1)).arc(r1, a1, a0).line(pts[0])))

    else:  # "band": schlichter Ring, geteilt
        for k in range(n):
            fields.append(Field(sector(r0, r1, ph + k * d, ph + (k + 1) * d)))
    return fields


def center_fields(rc: float, m: int, phase: float, variant: float) -> List[Field]:
    """Mitte: Blüte aus m Blättern um einen kleinen Kreis, dazwischen der Grund."""
    core = rc * (0.2 + 0.08 * variant)
    hw = math.pi / m * 0.8
    petals = [petal(core, rc * 0.9, phase + (k + 0.5) * 2 * math.pi / m, hw, variant) for k in range(m)]
    fields = [Field(circle(core))] + [Field(p) for p in petals]
    fields.append(Field(circle(rc), [circle(core)] + petals))
    return fields


# ---- Bauplan ----
MOTIFS = ["petals", "drops", "scallops", "dots", "zigzag", "diamonds", "waves", "band"]


@dataclass
class Mandala:
    seed: int
    difficulty: str
    symmetry: int
    rings: List[Ring]
    fields: List[Field]

    def signature(self) -> str:
        """Fingerabdruck gegen Doppelte: Symmetrie, Motivfolge, gerundete Proportionen."""
        parts = [str(self.symmetry)] + [f"{r.kind}{r.n}{int(r.dividers)}{int(r.nested)}{round(r.r1 / R_OUT, 1)}"
                                        for r in self.rings]
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]

    def to_json(self) -> dict:
        return {
            "version": VERSION, "size": SIZE, "seed": self.seed, "difficulty": self.difficulty,
            "symmetry": self.symmetry, "signature": self.signature(),
            "outline": circle(R_OUT).svg(),
            "fields": [{"id": i, "d": f.svg()} for i, f in enumerate(self.fields)],
        }


def build(seed: int, difficulty: str) -> Mandala:
    spec = DIFFICULTIES[difficulty]
    rnd = random.Random(seed)
    n = rnd.choice(spec["symmetry"])
    ring_count = rnd.randint(*spec["rings"])
    rc = R_OUT * rnd.uniform(0.16, 0.24)
    weights = [rnd.uniform(0.75, 1.35) for _ in range(ring_count)]
    widths = [(R_OUT - rc) * w / sum(weights) for w in weights]

    rings: List[Ring] = []
    r, prev = rc, None
    ring_n = n
    for i, w in enumerate(widths):
        kind = rnd.choice([m for m in MOTIFS if m != prev and not (m == "band" and i == len(widths) - 1)])
        prev = kind
        # Zu breite, flache Zellen: Teilung verdoppeln (aufblühendes Mandala)
        while 2 * math.pi * (r + w / 2) / ring_n > 2.4 * w and ring_n < 32 and difficulty != "leicht":
            ring_n *= 2
        rings.append(Ring(kind=kind, r0=r, r1=r + w, n=ring_n, phase=(math.pi / ring_n) * (i % 2),
                          dividers=rnd.random() < (0.3 if difficulty == "leicht" else 0.6),
                          variant=rnd.random(), nested=difficulty != "leicht" and rnd.random() < 0.45))
        r += w
    fields = center_fields(rc, n, 0.0, rnd.random())
    for ring in rings:
        fields.extend(ring_fields(ring))
    return Mandala(seed=seed, difficulty=difficulty, symmetry=n, rings=rings, fields=fields)


def check(m: Mandala) -> Optional[str]:
    """None = gut, sonst der Grund zum Verwerfen."""
    spec = DIFFICULTIES[m.difficulty]
    lo, hi = spec["fields"]
    if not lo <= len(m.fields) <= hi:
        return f"{len(m.fields)} Felder"
    for f in m.fields:
        if f.area() < spec["min_area"]:
            return f"Feld zu klein ({f.area():.0f})"
        if f.width() < spec["min_width"]:
            return f"Feld zu schmal ({f.width():.1f})"
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
    return {"fields": len(m.fields), "min_area": min(f.area() for f in m.fields),
            "min_width": min(f.width() for f in m.fields)}
