"""
Schaubilder für Übungen, vom Code gezeichnet – wo es auf Längen, Lagen oder Werte genau ankommt
(Kraftpfeile, Diagramme) oder das Bildmodell nicht zeichnet (der Kraftmesser fiel zweimal durch dessen
Sicherheitsfilter, 7.11.). Vorlage ist immer die Abbildung aus Theas Unterlagen: gleiche Bauteile,
gleiche Begriffe, gleiche Pfeillängen.

Jede Abbildung entsteht zweimal: mit Ziffernkreisen (Übung) und mit den Begriffen (Lösung, „Im Buch“).
Ausgabe: backend/app/exercise_sets/bilder/<übung>.jpg und <übung>_original.jpg, dazu die Felder als JSON.

    .venv/bin/python scripts/draw_figures.py kraftmesser
    .venv/bin/python scripts/draw_figures.py kraftpfeile
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "backend" / "app" / "exercise_sets" / "bilder"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
S = 2  # Überabtastung: groß zeichnen, verkleinert ablegen (glatte Kanten)

INK = (30, 30, 30)
RED = (220, 40, 40)


def font(size: int, style: int = 0) -> ImageFont.FreeTypeFont:
    """style: 0 normal, 1 fett, 2 kursiv."""
    return ImageFont.truetype(FONT, size * S, index=style)


class Canvas:
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.image = Image.new("RGB", (width * S, height * S), "white")
        self.d = ImageDraw.Draw(self.image)

    def p(self, *xy):
        return [v * S for v in xy]

    def line(self, x0, y0, x1, y1, width=3, fill=INK):
        self.d.line(self.p(x0, y0, x1, y1), fill=fill, width=width * S)

    def rect(self, x0, y0, x1, y1, fill, outline=INK, width=2):
        self.d.rectangle(self.p(x0, y0, x1, y1), fill=fill, outline=outline, width=width * S)

    def ellipse(self, x0, y0, x1, y1, fill, outline=INK, width=2):
        self.d.ellipse(self.p(x0, y0, x1, y1), fill=fill, outline=outline, width=width * S)

    def polygon(self, points, fill, outline=None):
        self.d.polygon([v * S for pt in points for v in pt], fill=fill, outline=outline)

    def text(self, x, y, text, size=24, style=0, anchor="mm", fill=INK):
        self.d.text((x * S, y * S), text, font=font(size, style), anchor=anchor, fill=fill)

    def arrow(self, x0, y0, x1, y1, width=4, head=20, fill=INK):
        """Pfeil von (x0, y0) nach (x1, y1), Spitze am Ende."""
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / length, dy / length
        bx, by = x1 - ux * head, y1 - uy * head
        self.line(x0, y0, bx, by, width, fill)
        half = head * 0.42
        self.polygon([(x1, y1), (bx - uy * half, by + ux * half), (bx + uy * half, by - ux * half)], fill)

    def marker(self, x, y, nr, r=24):
        """Ziffernkreis wie bei figure_tool.py (weiß, schwarzer Ring) – der Pixeltest findet ihn."""
        self.ellipse(x - r, y - r, x + r, y + r, fill="white", outline="black", width=4)
        self.text(x, y + 1, str(nr), size=round(r * 1.15), style=1, fill="black")

    def save(self, name: str):
        out = self.image.resize((self.w, self.h), Image.LANCZOS)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        out.save(IMAGES_DIR / name, quality=90, optimize=True)
        return out


def emit(uebung: str, width: int, height: int, fields: list) -> None:
    print(json.dumps({"bild": {"datei": f"{uebung}.jpg", "original": f"{uebung}_original.jpg",
                               "breite": width, "hoehe": height},
                      "felder": [{"nr": nr, "x": round(x / width, 4), "y": round(y / height, 4), "begriff": b}
                                 for nr, x, y, b in fields]}, ensure_ascii=False, indent=2))


# --- Federkraftmesser (Physik plus 7, S. 9, Bild 1) ---------------------------------------------------

def kraftmesser() -> None:
    W, H = 600, 900
    # Ziffer/Begriff, Höhe der Hinweislinie, Endpunkt am Gerät
    labels = [(1, "Messbereich", 140, 338), (2, "Schraubenfeder", 300, 368),
              (3, "Skala", 520, 372), (4, "Nullpunkteinstellung", 745, 338)]

    def draw(with_numbers: bool) -> Canvas:
        c = Canvas(W, H)
        silver, dark, blue, red = (214, 218, 222), (40, 42, 46), (70, 140, 215), (225, 55, 45)
        # Aufhängung: Stange und Haken
        c.rect(300, 18, 560, 44, fill=(200, 204, 208))
        c.d.arc(c.p(405, 30, 445, 76), 180, 360, fill=INK, width=5 * S)
        c.line(425, 76, 425, 92, 5)
        # äußere Hülse mit Kappe
        c.rect(340, 92, 510, 118, fill=silver)
        c.rect(345, 118, 505, 760, fill=silver)
        c.text(425, 140, "10 N", size=22, style=1)
        # blauer Kopf und dunkler Innenraum mit Feder
        c.rect(352, 162, 498, 200, fill=blue, outline=None)
        c.rect(352, 200, 498, 352, fill=dark, outline=None)
        c.polygon([(430, 200), (498, 200), (498, 352), (470, 352)], fill=blue)
        pts = [(365 + (60 if i % 2 else 0), 214 + i * 12) for i in range(12)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            c.line(x0, y0, x1, y1, width=4, fill=(230, 232, 235))
        # Skalenrohr (innen), ragt unten heraus
        c.rect(362, 352, 488, 830, fill="white")
        for i, y in enumerate(range(352, 830, 48)):
            if i % 2 == 0:
                c.rect(362, y, 488, min(y + 48, 830), fill=red, outline=None)
        c.rect(362, 352, 488, 830, fill=None)
        # untere Hülse (Nullpunkteinstellung) über dem Skalenrohr
        c.rect(345, 700, 362, 760, fill=dark, outline=None)
        c.rect(488, 700, 505, 760, fill=dark, outline=None)
        c.rect(355, 830, 495, 846, fill=silver)
        c.line(425, 846, 425, 862, 5)
        c.d.arc(c.p(405, 852, 445, 894), 0, 200, fill=INK, width=5 * S)
        # Hinweislinien und Ziffern bzw. Begriffe
        for nr, word, y, x_end in labels:
            if with_numbers:
                c.line(276, y, x_end, y, width=2)
                c.marker(250, y, nr)
            else:
                c.line(300, y, x_end, y, width=2)
                c.text(292, y, word, size=24, anchor="rm")
        return c

    draw(True).save("ph-kraftmesser.jpg")
    draw(False).save("ph-kraftmesser_original.jpg")
    emit("ph-kraftmesser", W, H, [(nr, 250, y, word) for nr, word, y, _ in labels])


# --- Kraftpfeile (Arbeitsblatt „Darstellung von Kräften (1)“, A1) ------------------------------------

# Pfeillängen in Pixeln wie im Arbeitsblatt (gemessen am Scan, gerundet); je Seite eine Folge von
# Teilkräften, die aneinanderhängen. Buchstabe = Grafik im Blatt, Satz = Theas Zuordnung.
KRAFTPFEILE = [
    # nr, Buchstabe, Richtung, Teilpfeile zur ersten Seite (links/oben), zur zweiten (rechts/unten), Satz
    (1, "b", "h", [130, 130, 130], [240, 240],
     "Zwei Schülerinnen ziehen drei Schüler über die Grenzlinie."),
    (2, "a", "v", [280], [220],
     "Ein Heißluftballon steigt. Die Auftriebskraft ist größer als die Gewichtskraft."),
    (3, "d", "v", [215], [305],
     "Ein Heißluftballon sinkt, weil die Gewichtskraft größer geworden ist als die Auftriebskraft."),
    (4, "f", "h", [235], [235],
     "Herrchen will nach Hause gehen, Bello aber nicht. Beide ziehen gleich stark."),
    (5, "e", "v", [265], [265],
     "Ein Heißluftballon schwebt, weil die Auftriebskraft und die Gewichtskraft gleich groß sind."),
    (6, "c", "h", [160, 160], [162, 162, 162],
     "Drei Schüler ziehen zwei Schülerinnen beim Tauziehen über die Grenzlinie."),
]


def kraftpfeile() -> None:
    W, H = 1500, 760
    rows = {1: 130, 4: 380, 6: 630}           # waagerechte Grafiken links untereinander
    cols = {2: 1110, 3: 1260, 5: 1410}        # senkrechte Grafiken rechts nebeneinander

    def draw(with_numbers: bool):
        c = Canvas(W, H)
        fields = []
        for nr, letter, kind, first, second, sentence in KRAFTPFEILE:
            labels = iter(f"F{chr(0x2080 + i)}" for i in range(1, 10))
            if kind == "h":
                y = rows[nr]
                x0 = 120 + sum(first)                       # Angriffspunkt
                x = x0
                ends = []
                for seg in first:                           # vom Angriffspunkt nach links
                    ends.append((x, x - seg))
                    x -= seg
                for a, b in ends:
                    c.arrow(a, y, b, y)
                for a, b in reversed(ends):                 # F₁ ganz außen wie im Blatt
                    c.text((a + b) / 2, y - 26, next(labels), size=26)
                x = x0
                for seg in second:
                    c.arrow(x, y, x + seg, y)
                    c.text(x + seg / 2, y - 26, next(labels), size=26)
                    x += seg
                c.ellipse(x0 - 7, y - 7, x0 + 7, y + 7, fill=INK)
                mx, my = 56, y
            else:
                x = cols[nr]
                y0 = 90 + max(first[0], 280)
                c.arrow(x, y0, x, y0 - first[0])
                c.text(x + 30, y0 - first[0] / 2, next(labels), size=26)
                c.arrow(x, y0, x, y0 + second[0])
                c.text(x + 30, y0 + second[0] / 2, next(labels), size=26)
                c.ellipse(x - 7, y0 - 7, x + 7, y0 + 7, fill=INK)
                mx, my = x - 50, y0 - first[0] + 10
            if with_numbers:
                c.marker(mx, my, nr)
            else:
                c.rect(mx - 22, my - 22, mx + 22, my + 22, fill="white", width=3)
                c.text(mx, my, letter, size=28)
            fields.append((nr, mx, my, sentence))
        return c, fields

    c, fields = draw(True)
    c.save("ph-kraftpfeile.jpg")
    draw(False)[0].save("ph-kraftpfeile_original.jpg")
    emit("ph-kraftpfeile", W, H, fields)


if __name__ == "__main__":
    figures = {"kraftmesser": kraftmesser, "kraftpfeile": kraftpfeile}
    if len(sys.argv) != 2 or sys.argv[1] not in figures:
        sys.exit(__doc__)
    figures[sys.argv[1]]()
