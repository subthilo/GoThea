"""
Schaubilder für Übungen (Typ „Zuordnen“) aus einer Buchabbildung – nur in Sessions am Mac.

Die Abbildung soll aussehen wie im Buch: Das Bildmodell zeichnet die Originalabbildung nach, ersetzt die
Beschriftungen durch Ziffernkreise, ein Vision-Modell prüft das Ergebnis gegen das Original, ein Pixeltest
bestätigt jeden Kreis. Freigegeben wird erst nach dem Blick der Eltern (Session).

1. prepare: Buchseite auf dem Pi rendern (Staging-Datenbank), Ausschnitt schneiden, Beschriftungen mit der
   macOS-Texterkennung lesen. Ergebnis in data/figures/<name>/: original.png, labels.json und key.json
   (Vorlage: Ziffer → Begriff wie im Buch; in der Session prüfen und kürzen, z. B. Temperaturen weglassen).
     .venv/bin/python scripts/figure_tool.py prepare brenner --material mat_5407a000_ch01 --seite 17 \\
         --ausschnitt 11,60,53,88      (links, oben, rechts, unten in Prozent der Seite)
2. redraw: nachzeichnen lassen und prüfen, bis ein Versuch besteht (höchstens --versuche).
     .venv/bin/python scripts/figure_tool.py redraw brenner
3. export: bestandenen Versuch als Bild der Übung ablegen und die Felder (Ziffer, Lage, Begriff) ausgeben.
     .venv/bin/python scripts/figure_tool.py export brenner 1 ch-brenner

Abbildungen ohne Beschriftungen (z. B. Arbeitsheft-Zeichnungen mit leeren Linien): statt redraw den Ausschnitt
selbst nehmen – mark hellt den Scan auf und setzt die Ziffernkreise an die Lagen aus key.json ("x", "y" in
Pixeln von original.png); ein Versuch wie bei redraw, export bleibt gleich.
     .venv/bin/python scripts/figure_tool.py mark grundregeln
Zeigt „Im Buch“ eine andere Stelle als der Ausschnitt (Lösung steht im Buch), legt buch diesen Ausschnitt ab;
export nimmt dann ihn als Original.
     .venv/bin/python scripts/figure_tool.py buch grundregeln --material mat_5407a000_ch01 --seite 16 \\
         --ausschnitt 8,14,92,52
"""
import argparse
import base64
import io
import json
import math
import shlex
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app import config  # noqa: E402
from backend.app.services import llm  # noqa: E402

WORK_DIR = ROOT / "data" / "figures"
IMAGES_DIR = ROOT / "backend" / "app" / "exercise_sets" / "bilder"
RENDER_DPI = 250
STAGING_DB = "/home/pi/GoThea/data/staging/app_data.db"


# --- 1. Ausschnitt und Beschriftungen ------------------------------------------------------------------


def pi_host() -> str:
    return subprocess.run([str(ROOT / "scripts" / "pi_host.sh")], capture_output=True, text=True,
                          check=True).stdout.strip()


def render_page(material_id: str, page: int) -> Image.Image:
    """Seite einer Material-Datei der Staging-Datenbank, gerendert auf dem Pi (dort gibt es pdftoppm)."""
    host = pi_host()
    query = (f"import sqlite3; print(sqlite3.connect('file:{STAGING_DB}?mode=ro', uri=True)"
             f".execute('select file_path, mime_type from materials where id=?', ({material_id!r},)).fetchone())")
    remote = (f"set -e; row=$(python3 -c {shlex.quote(query)}); echo \"$row\" >&2; "
              f"f=$(python3 -c \"import ast,sys; r=ast.literal_eval(sys.argv[1]); print(r[0] if r else '')\" \"$row\"); "
              f"test -n \"$f\"; case \"$f\" in *.pdf) pdftoppm -f {page} -l {page} -r {RENDER_DPI} -png \"$f\" "
              f"| cat ;; *) cat \"$f\" ;; esac")
    out = subprocess.run(["ssh", f"pi@{host}", remote], capture_output=True, check=True)
    return Image.open(io.BytesIO(out.stdout)).convert("RGB")


def ocr_lines(image_path: Path) -> list:
    out = subprocess.run(["swift", str(ROOT / "scripts" / "ocr_labels.swift"), str(image_path)],
                         capture_output=True, text=True, check=True).stdout
    lines = []
    for row in out.splitlines():
        x, y, w, h, text = row.split("\t", 4)
        x, y, w, h = map(int, (x, y, w, h))
        lines.append({"text": text, "box": [x, y, x + w, y + h]})
    return lines


def group_labels(lines: list) -> list:
    """Zeilen einer Beschriftung zusammenfassen (gleiche Spalte, direkt untereinander), oben nach unten."""
    groups = []
    for line in sorted(lines, key=lambda l: l["box"][1]):
        x0, y0, x1, y1 = line["box"]
        height = y1 - y0
        for g in groups:
            gx0, _, gx1, gy1 = g["box"]
            if abs(gx0 - x0) < 1.5 * height and -0.4 * height <= y0 - gy1 < 0.6 * height:
                g["box"] = [min(gx0, x0), g["box"][1], max(gx1, x1), y1]
                g["text"] += " " + line["text"]
                break
        else:
            groups.append({"text": line["text"], "box": list(line["box"])})
    for g in groups:  # Silbentrennung und Hinweisstriche der Beschriftungslinien entfernen
        g["text"] = g["text"].replace("- ", "").strip(" -—–")
    return sorted(groups, key=lambda g: (g["box"][1], g["box"][0]))


def cut(material_id: str, page_no: int, ausschnitt: str) -> Image.Image:
    page = render_page(material_id, page_no)
    left, top, right, bottom = (float(v) / 100 for v in ausschnitt.split(","))
    return page.crop((int(left * page.width), int(top * page.height), int(right * page.width), int(bottom * page.height)))


def prepare(args) -> None:
    folder = WORK_DIR / args.name
    folder.mkdir(parents=True, exist_ok=True)
    crop = cut(args.material, args.seite, args.ausschnitt)
    crop.save(folder / "original.png")
    labels = group_labels(ocr_lines(folder / "original.png"))
    (folder / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    key = {"material_id": args.material, "seite": args.seite, "ausschnitt": args.ausschnitt,
           "beschreibung": "", "begriffe": [{"nr": i, "begriff": g["text"], "original": g["text"]}
                                            for i, g in enumerate(labels, 1)]}
    if not (folder / "key.json").exists():
        (folder / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{folder}: original.png {crop.size[0]}×{crop.size[1]}, {len(labels)} Beschriftungen")
    for i, g in enumerate(labels, 1):
        print(f"  {i:2}  {g['text']}")


# --- 2. Nachzeichnen und prüfen ------------------------------------------------------------------------

REDRAW_PROMPT = """Zeichne diese Schulbuch-Abbildung ({beschreibung}) EXAKT nach: gleiche Bauteile, gleiche Formen und
Proportionen, gleiche Anordnung, gleiche Farben, gleiche Pfeile und gleiche Hinweislinien an denselben Stellen.
Nichts hinzufügen, nichts weglassen, nichts verschönern.

Einzige Änderung: ALLE Wörter, Zahlen und Einheiten der Abbildung entfernen. Stattdessen am äußeren Ende jeder
Hinweislinie, genau dort, wo vorher die Beschriftung begann, ein kleiner weißer Kreis mit schwarzem Rand und einer
Ziffer:
{zuordnung}
Außer diesen Ziffern darf kein Text im Bild stehen. Weißer Hintergrund, klare Linien wie im Original."""

REVIEW_PROMPT = """Bild 1 ist eine beschriftete Schulbuch-Abbildung (Original). Bild 2 soll sie exakt nachzeichnen, mit
nummerierten Kreisen statt der Beschriftungen. Soll-Zuordnung (Ziffer → Beschriftung im Original):
{zuordnung}
Bild 2 ist {breite}×{hoehe} Pixel groß.

Prüfe Bild 2 streng, aber nur FACHLICH – Thea lernt mit diesem Bild die Begriffe aus dem Buch:
1. Für jede Ziffer: Gibt es genau einen Kreis? Mittelpunkt in Pixeln von Bild 2. Zeigt das Ende seiner Hinweislinie
   auf dasselbe Bauteil bzw. dieselbe Stelle wie im Original die Linie der Soll-Beschriftung? Wenige Pixel
   Versatz am selben Bauteil sind in Ordnung; ein anderes Bauteil, ein mehrdeutiges Ziel oder eine fehlende
   Linie nicht.
2. Steht in Bild 2 Text außer den Ziffern?
3. Fachliche Abweichungen der Zeichnung: fehlende, zusätzliche oder vertauschte Bauteile, falsche oder fehlende
   Pfeile, Farben mit Bedeutung (z. B. rot = Gas, blau = Luft) vertauscht. NICHT melden: Stil, Strichstärke,
   Schattierung, weichere Farbverläufe, leicht andere Proportionen.
Urteil: "ok" nur, wenn jede Ziffer genau einmal vorkommt und richtig zeigt, kein fremder Text da ist und es keine
fachliche Abweichung gibt; sonst "verwerfen".
Antworte als JSON: {{"marker": [{{"nr": 1, "x": 0, "y": 0, "zeigt_auf": "...", "richtig": true, "abweichung": ""}}],
"fremder_text": [], "fachliche_abweichungen": [], "urteil": "ok"}}"""


def _size_for(image: Image.Image) -> str:
    ratio = image.width / image.height
    return "1536x1024" if ratio > 1.25 else "1024x1536" if ratio < 0.8 else "1024x1024"


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def ring_at(image: Image.Image, x: float, y: float, search: int = 14):
    """Ziffernkreis nahe (x, y): dunkler Ring um eine helle Mitte. Liefert (x, y, Radius) oder None."""
    gray = image.convert("L")
    px = gray.load()
    w, h = gray.size

    def lum(px_x, px_y):
        return px[min(max(int(px_x), 0), w - 1), min(max(int(px_y), 0), h - 1)]

    angles = [(math.cos(a * math.pi / 24), math.sin(a * math.pi / 24)) for a in range(48)]
    best = None
    for dy in range(-search, search + 1, 2):
        for dx in range(-search, search + 1, 2):
            cx, cy = x + dx, y + dy
            for r in range(12, 40, 2):
                ring = sum(1 for ax, ay in angles
                           if min(lum(cx + ax * rr, cy + ay * rr) for rr in (r - 1, r, r + 1)) < 110) / len(angles)
                if ring < 0.85:
                    continue
                inner = [lum(cx + ax * r * 0.75, cy + ay * r * 0.75) for ax, ay in angles]
                if sum(inner) / len(inner) < 170:  # innen weiß (nur die Ziffer ist dunkel)
                    continue
                if best is None or ring > best[0]:
                    best = (ring, cx, cy, r)
    return None if best is None else (best[1], best[2], best[3])


def review(original_png: bytes, drawn: Image.Image, key: dict) -> dict:
    zuordnung = "\n".join(f"{b['nr']} = {b['original']}" for b in key["begriffe"])
    messages = [{"role": "user", "content": [
        {"type": "text", "text": REVIEW_PROMPT.format(zuordnung=zuordnung, breite=drawn.width, hoehe=drawn.height)},
        {"type": "image_url", "image_url": {"url": _data_url(original_png), "detail": "high"}},
        {"type": "image_url", "image_url": {"url": _data_url(_png(drawn)), "detail": "high"}},
    ]}]
    report = llm.chat_json(messages, purpose="Schaubild prüfen", model=config.OPENAI_REVIEW_MODEL)
    problems = list(report.get("fremder_text") or []) + list(report.get("fachliche_abweichungen") or [])
    found = {}
    for m in report.get("marker") or []:
        if not m.get("richtig", False):
            problems.append(f"Ziffer {m.get('nr')}: {m.get('abweichung') or 'zeigt nicht auf die Soll-Stelle'}")
        ring = ring_at(drawn, float(m.get("x", -100)), float(m.get("y", -100)))
        if ring is None:
            problems.append(f"Ziffer {m.get('nr')}: kein Kreis bei ({m.get('x')}, {m.get('y')})")
        else:
            found[int(m["nr"])] = {"x": ring[0], "y": ring[1], "r": ring[2]}
    expected = {b["nr"] for b in key["begriffe"]}
    if set(found) != expected:
        problems.append(f"Ziffern gefunden: {sorted(found)}, erwartet: {sorted(expected)}")
    report["kreise"] = found
    report["probleme"] = problems
    report["bestanden"] = report.get("urteil") == "ok" and not problems
    return report


def redraw(args) -> None:
    folder = WORK_DIR / args.name
    key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
    original = Image.open(folder / "original.png").convert("RGB")
    original_png = _png(original)
    zuordnung = "\n".join(f"{b['nr']} = {b['original']}" for b in key["begriffe"])
    prompt = REDRAW_PROMPT.format(beschreibung=key.get("beschreibung") or "siehe Bild", zuordnung=zuordnung)
    start = 1 + len(list(folder.glob("versuch_*.png")))
    for n in range(start, start + args.versuche):
        print(f"Versuch {n}: zeichnen …", flush=True)
        drawn = Image.open(io.BytesIO(llm.image_edit(original_png, prompt, purpose="Schaubild nachzeichnen",
                                                     size=_size_for(original)))).convert("RGB")
        drawn.save(folder / f"versuch_{n}.png")
        print(f"Versuch {n}: prüfen …", flush=True)
        report = review(original_png, drawn, key)
        (folder / f"versuch_{n}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Versuch {n}: {'bestanden' if report['bestanden'] else 'durchgefallen'}")
        for p in report["probleme"]:
            print(f"   {p}")
        if report["bestanden"]:
            return
    print("Kein Versuch bestanden.")


# --- 2b. Ohne Nachzeichnen: Ziffernkreise auf den Ausschnitt setzen -----------------------------------

MARK_FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
MARK_MAX_SIDE = 1536


def mark(args) -> None:
    from PIL import ImageDraw, ImageFont

    folder = WORK_DIR / args.name
    key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
    original = Image.open(folder / "original.png").convert("RGB")
    scale = min(1.0, MARK_MAX_SIDE / max(original.size))
    image = original.resize((round(original.width * scale), round(original.height * scale)), Image.LANCZOS)
    # Papiergrau und durchscheinende Rückseite des Scans aufhellen, die Zeichnung bleibt
    image = image.point(lambda v: min(255, round(v * 255 / args.weiss)))
    draw = ImageDraw.Draw(image)
    radius = max(16, round(image.width / 46))
    font = ImageFont.truetype(MARK_FONT, round(radius * 1.15), index=1)
    for b in key["begriffe"]:
        x, y = b["x"] * scale, b["y"] * scale
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white", outline="black",
                     width=max(3, radius // 7))
        draw.text((x, y), str(b["nr"]), fill="black", font=font, anchor="mm")
    n = 1 + len(list(folder.glob("versuch_*.png")))
    image.save(folder / f"versuch_{n}.png")
    found, problems = {}, []
    for b in key["begriffe"]:
        ring = ring_at(image, b["x"] * scale, b["y"] * scale)
        if ring is None:
            problems.append(f"Ziffer {b['nr']}: kein Kreis gefunden")
        else:
            found[int(b["nr"])] = {"x": ring[0], "y": ring[1], "r": ring[2]}
    report = {"art": "markiert", "kreise": found, "probleme": problems, "bestanden": not problems}
    (folder / f"versuch_{n}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Versuch {n}: {'bestanden' if report['bestanden'] else 'durchgefallen'} ({image.width}×{image.height})")
    for p in problems:
        print(f"   {p}")


def book(args) -> None:
    folder = WORK_DIR / args.name
    folder.mkdir(parents=True, exist_ok=True)
    crop = cut(args.material, args.seite, args.ausschnitt)
    crop.save(folder / "buch.png")
    print(f"{folder}: buch.png {crop.size[0]}×{crop.size[1]}")


# --- 3. Für die Übung ablegen ---------------------------------------------------------------------------


def export(args) -> None:
    folder = WORK_DIR / args.name
    key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
    report = json.loads((folder / f"versuch_{args.versuch}.json").read_text(encoding="utf-8"))
    drawn = Image.open(folder / f"versuch_{args.versuch}.png").convert("RGB")
    original = Image.open(folder / ("buch.png" if (folder / "buch.png").exists() else "original.png")).convert("RGB")
    original.thumbnail((1400, 1400))
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    drawn.save(IMAGES_DIR / f"{args.uebung}.jpg", quality=85, optimize=True)
    original.save(IMAGES_DIR / f"{args.uebung}_original.jpg", quality=85, optimize=True)
    fields = []
    for b in key["begriffe"]:
        ring = report["kreise"][str(b["nr"])]
        fields.append({"nr": b["nr"], "x": round(ring["x"] / drawn.width, 4), "y": round(ring["y"] / drawn.height, 4),
                       "begriff": b["begriff"], **({"auch": b["auch"]} if b.get("auch") else {})})
    print(json.dumps({"bild": {"datei": f"{args.uebung}.jpg", "original": f"{args.uebung}_original.jpg",
                               "breite": drawn.width, "hoehe": drawn.height}, "felder": fields},
                     ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("name")
    p.add_argument("--material", required=True)
    p.add_argument("--seite", type=int, required=True, help="Seite in der Datei (bei Buchkapiteln im Kapitel-PDF)")
    p.add_argument("--ausschnitt", required=True, help="links,oben,rechts,unten in Prozent der Seite")
    p.set_defaults(run=prepare)
    p = sub.add_parser("redraw")
    p.add_argument("name")
    p.add_argument("--versuche", type=int, default=3)
    p.set_defaults(run=redraw)
    p = sub.add_parser("mark")
    p.add_argument("name")
    p.add_argument("--weiss", type=int, default=225, help="Helligkeit, die zu Weiß wird (Papier des Scans)")
    p.set_defaults(run=mark)
    p = sub.add_parser("buch")
    p.add_argument("name")
    p.add_argument("--material", required=True)
    p.add_argument("--seite", type=int, required=True)
    p.add_argument("--ausschnitt", required=True)
    p.set_defaults(run=book)
    p = sub.add_parser("export")
    p.add_argument("name")
    p.add_argument("versuch", type=int)
    p.add_argument("uebung", help="ID der Übung, z. B. ch-brenner")
    p.set_defaults(run=export)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
