"""Übung auf der Tafel prüfen: „Luna liest, der Code rechnet“ (Konzept-Doc, Steckbrief Typ 1).

1. ``read_board``: Luna überträgt Theas Handschrift in Werte und beurteilt nur Antwortsatz und Begründung.
2. ``evaluate``: Das Programm prüft die Mathematik – jede Tabellenzeile, Rechenschritte, Ergebnis, Einheit,
   die Zahl im Antwortsatz. Jeder gültige Weg zählt (auch ein anderer Hilfswert als im Buch).
3. Bei einem Fehler nennt die Rückmeldung immer den gelesenen Wert; ist Luna unsicher, fragt sie nach,
   statt zu urteilen.
Jede Prüfung wird mit Bild und gelesenen Werten protokolliert (DATA_DIR/practice_checks), um zu messen,
wie oft Luna sich verliest.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime
from fractions import Fraction
from typing import Dict, List, Optional

from backend.app import config
from backend.app.prompts.practice import PRACTICE_READING_SYSTEM_PROMPT
from backend.app.services import llm
from backend.app.services.practice_exercises import fmt_number

logger = logging.getLogger(__name__)

RICHTIG, NOCH_NICHT, UNSICHER = "richtig", "noch_nicht", "unsicher"


# --- Ablesen der Handschrift --------------------------------------------------------------------------


def _reading_prompt(ex: dict, stage: int) -> str:
    lines = [f"AUFGABE: {ex['aufgabentext']}", f"GERÜST-STUFE: {stage} (1 = Tabelle vorgegeben, 4 = leeres Blatt)"]
    if ex["schema"].startswith("dreisatz"):
        g1, g2 = ex["groessen"]
        lines.append(f"Erwartet wird eine Dreisatz-Tabelle mit den Spalten „{g1['name']}“ und „{g2['name']}“.")
    else:
        lines.append("Erwartet wird eine Rechnung (ohne Tabelle).")
    if (ex.get("begruendung") or {}).get("verlangt"):
        lines.append(f"ERWARTETE BEGRÜNDUNG (nur zum Vergleich des Inhalts): {ex['begruendung']['erwartung']}")
    lines.append("Lies jetzt Theas Lösung vom Bild ab.")
    return "\n".join(lines)


def read_board(ex: dict, stage: int, image_base64: str) -> dict:
    """Luna liest die Tafel. Wirft llm.LLMError, wenn die KI nicht antwortet."""
    data_url = image_base64 if image_base64.startswith("data:") else f"data:image/jpeg;base64,{image_base64}"
    messages = [
        {"role": "system", "content": PRACTICE_READING_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": _reading_prompt(ex, stage)},
            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
        ]},
    ]
    return llm.chat_json(messages, purpose="Übung prüfen")


# --- Prüfen durch das Programm --------------------------------------------------------------------------


def parse_number(text) -> Optional[Fraction]:
    """'1,50', '1.5', '10 €', '3000' → Zahl; nicht lesbar → None."""
    if text is None:
        return None
    t = str(text).replace("−", "-").strip()
    m = re.search(r"-?\d+(?:[.,]\d+)?", t.replace(" ", ""))
    if not m:
        return None
    return Fraction(m.group(0).replace(",", "."))


def parse_op(text) -> Optional[tuple]:
    """':3', '·10', 'x 10', '*10', '/3' → (':' oder '·', Zahl)."""
    if not text:
        return None
    t = str(text).strip().replace(" ", "")
    if not t:
        return None
    kind = ":" if t[0] in ":/÷" else "·" if t[0] in "·•*xX×." else None
    value = parse_number(t[1:]) if kind else None
    return (kind, value) if kind and value else None


def _apply(op: tuple, value: Fraction) -> Fraction:
    kind, factor = op
    return value / factor if kind == ":" else value * factor


def _fmt(value: Fraction, money: bool = False) -> str:
    return fmt_number(value, money)


def evaluate(ex: dict, stage: int, read: dict) -> dict:
    """Prüft die gelesenen Werte. Ergebnis: status, probleme (mit Bereich und gelesenem Wert), hinweise."""
    problems: List[dict] = []
    hints: List[str] = []
    unsure = set(read.get("unsicher") or [])
    result = Fraction(str(ex["ergebnis"]["wert"]))

    def problem(area: str, text: str, read_value: Optional[str] = None):
        problems.append({"bereich": area, "text": text, "gelesen": read_value, "unsicher": area in unsure})

    final_read = (read.get("ergebnis") or "").strip()

    if ex["schema"].startswith("dreisatz"):
        _check_table(ex, stage, read, problem, hints)
        rows = read.get("tabelle") or []
        if not final_read and rows:
            final_read = str(rows[-1].get("rechts") or "")
    else:
        calc = (read.get("rechnung") or "").strip()
        if not calc:
            problem("rechnung", "Ich sehe noch keine Rechnung.")
        elif not final_read:
            numbers = re.findall(r"\d+(?:[.,]\d+)?", calc)
            final_read = numbers[-1] if numbers else ""

    final = parse_number(final_read)
    if final is None:
        if not problems:
            problem("ergebnis", "Ich finde noch kein Ergebnis.")
    elif final != result:
        problem("ergebnis", f"Beim Ergebnis lese ich {final_read}. Das stimmt noch nicht.", final_read)

    # Einheit: am Ergebnis oder im Antwortsatz
    units = {u for u in (ex["ergebnis"]["einheit"], (ex.get("groessen") or [{}, {}])[1].get("einheit")) if u}
    sentence = (read.get("antwortsatz") or "").strip()
    if final == result and units and not any(u in (read.get("einheit") or "") + " " + sentence for u in units):
        problem("ergebnis", "Dein Ergebnis stimmt! Es fehlt nur noch die Einheit.", final_read)

    # Antwortsatz: vorhanden, sprachlich passend (Luna), Zahl passt zum Ergebnis (Programm)
    if not sentence:
        problem("antwortsatz", "Jetzt fehlt noch der Antwortsatz.")
    else:
        numbers = re.findall(r"\d[\d.]*(?:,\d+)?", sentence)
        in_sentence = parse_number(numbers[-1].replace(".", "")) if numbers else None
        if in_sentence is None:
            problem("antwortsatz", "In deinem Antwortsatz fehlt die Zahl.", sentence)
        elif in_sentence != result:
            problem("antwortsatz", f"Im Antwortsatz lese ich {numbers[-1]}. Passt das zu deinem Ergebnis?", sentence)
        elif read.get("antwortsatz_passt") is False:
            problem("antwortsatz", read.get("antwortsatz_hinweis") or "Schau noch mal auf deinen Antwortsatz.", sentence)

    # Begründung (falls verlangt): Inhalt beurteilt Luna
    if (ex.get("begruendung") or {}).get("verlangt"):
        reasoning = (read.get("begruendung") or "").strip()
        if not reasoning:
            problem("begruendung", "Die Aufgabe will noch eine Begründung.")
        elif read.get("begruendung_passt") is False:
            problem("begruendung", read.get("begruendung_hinweis") or "Überleg noch mal, warum die Zuordnung proportional ist.", reasoning)

    if not problems:
        status = RICHTIG
    elif all(p["unsicher"] for p in problems):
        status = UNSICHER
    else:
        status = NOCH_NICHT
    return {"status": status, "probleme": problems, "hinweise": hints}


def _check_table(ex: dict, stage: int, read: dict, problem, hints: List[str]) -> None:
    """Dreisatz-Tabelle: Startzeile, jede Zeile gehört zur Zuordnung, Rechenschritte stimmen, Ziel erreicht."""
    anti = ex["schema"] == "dreisatz_antiproportional"
    money = ex["groessen"][1]["einheit"] == "€"
    raw_rows = read.get("tabelle") or []
    if not raw_rows:
        problem("tabelle", "Ich finde noch keine Dreisatz-Tabelle.")
        return
    rows = []
    for i, r in enumerate(raw_rows, start=1):
        x, y = parse_number(r.get("links")), parse_number(r.get("rechts"))
        if x is None or y is None:
            problem("tabelle", f"In Zeile {i} der Tabelle fehlt noch etwas.", f"{r.get('links', '')} → {r.get('rechts', '')}")
            return
        rows.append((x, y))

    x0, y0 = (Fraction(str(v)) for v in ex["zeilen"][0])
    if rows[0] != (x0, y0):
        problem("tabelle", f"In der ersten Zeile lese ich {_fmt(rows[0][0])} → {_fmt(rows[0][1], money)}. "
                           f"In der Aufgabe steht {_fmt(x0)} → {_fmt(y0, money)}.",
                f"{_fmt(rows[0][0])} → {_fmt(rows[0][1], money)}")
        return

    ops_l = read.get("schritte_links") or []
    ops_r = read.get("schritte_rechts") or []
    missing_ops = False
    for i in range(1, len(rows)):
        (xp, yp), (x, y) = rows[i - 1], rows[i]
        # gehört die Zeile zur Zuordnung? (antiproportional: gleiches Produkt, sonst gleicher Quotient)
        fits = (x * y == x0 * y0) if anti else (y * x0 == y0 * x)
        shown = f"{_fmt(x)} → {_fmt(y, money)}"
        if not fits:
            problem("tabelle", f"In Zeile {i + 1} lese ich {shown}. Das passt noch nicht zur ersten Zeile.", shown)
            return
        for side, ops, prev, cur in (("links", ops_l, xp, x), ("rechts", ops_r, yp, y)):
            op = parse_op(ops[i - 1]) if i - 1 < len(ops) else None
            if op is None:
                missing_ops = True
            elif _apply(op, prev) != cur:
                text = str(ops[i - 1]).strip()
                problem("tabelle", f"Rechenschritt {side} {text}: {_fmt(prev, side == 'rechts' and money)} {text} "
                                   f"ergibt nicht {_fmt(cur, side == 'rechts' and money)}.", text)
                return

    target_x = Fraction(str(ex["zeilen"][-1][0]))
    if rows[-1][0] != target_x:
        problem("tabelle", f"Gefragt ist nach {_fmt(target_x)}. In deiner letzten Zeile steht {_fmt(rows[-1][0])}.",
                _fmt(rows[-1][0]))
    if missing_ops:
        # Stufe 1 hat Kästchen dafür; sonst nur ein Tipp, der Weg zählt trotzdem
        if stage == 1:
            problem("tabelle", "Schreib noch die Rechenschritte in die Kästchen.")
        else:
            hints.append("Tipp: Schreib die Rechenschritte neben die Tabelle, so wie im Buch.")


# --- Rückmeldung --------------------------------------------------------------------------------------


def feedback(ex: dict, outcome: dict, attempt: int) -> str:
    """Lunas Satz an Thea: Lob, das erste Problem mit gelesenem Wert, ab dem 2. Versuch eine Hilfe."""
    if outcome["status"] == RICHTIG:
        text = "Richtig! Alles stimmt: Rechnung, Ergebnis und Antwortsatz."
        if outcome["hinweise"]:
            text += " " + outcome["hinweise"][0]
        return text
    first = outcome["probleme"][0]
    if outcome["status"] == UNSICHER:
        return f"Hier bin ich mir nicht sicher, ob ich richtig lese: „{first['gelesen'] or '?'}“. Schreibst du es noch mal deutlicher?"
    text = first["text"]
    helps = [ex["hilfen"]["denkanstoss"], ex["hilfen"]["hinweis"]]
    if attempt >= 2:
        text += " " + helps[min(attempt - 2, len(helps) - 1)]
    return text


def marks(read: dict, outcome: dict) -> List[dict]:
    """Kästen um die Bereiche mit Problemen (Lage von Luna, Prozent des Tafelbilds)."""
    areas = read.get("bereiche") or {}
    out = []
    for area in dict.fromkeys(p["bereich"] for p in outcome["probleme"]):
        box = areas.get(area)
        if isinstance(box, dict) and all(isinstance(box.get(k), (int, float)) for k in ("x_pct", "y_pct", "w_pct", "h_pct")):
            out.append({"action": "highlight_box", "coords": {k: box[k] for k in ("x_pct", "y_pct", "w_pct", "h_pct")}})
    return out


# --- Protokoll zum Messen ------------------------------------------------------------------------------


def log_check(ex_id: str, stage: int, image_base64: str, read: dict, outcome: dict) -> None:
    """Bild + gelesene Werte + Urteil ablegen (zum Messen der Lesegenauigkeit). Fehler hier stören nie."""
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = config.DATA_DIR / "practice_checks"
        folder.mkdir(parents=True, exist_ok=True)
        raw = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        image_file = folder / f"{stamp}_{ex_id}_s{stage}.jpg"
        image_file.write_bytes(base64.b64decode(raw))
        entry = {"zeit": stamp, "uebung": ex_id, "stufe": stage, "bild": image_file.name,
                 "gelesen": read, "status": outcome["status"], "probleme": outcome["probleme"]}
        with open(folder / "checks.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:  # Protokoll darf die Prüfung nie verhindern
        logger.warning(f"Übungsprüfung nicht protokolliert: {e}")


def speech_text(text: str) -> str:
    """Für die Sprachausgabe: Rechenzeichen ausschreiben."""
    return text.replace("·", " mal ").replace(" : ", " geteilt durch ").replace("→", "zu")


def describe_read(read: dict, ex: dict) -> Dict[str, str]:
    """Kurzfassung der gelesenen Werte für die Anzeige („gelesen: …“)."""
    out = {}
    if read.get("tabelle"):
        out["tabelle"] = " | ".join(f"{r.get('links', '')} → {r.get('rechts', '')}" for r in read["tabelle"])
    for key in ("rechnung", "ergebnis", "antwortsatz", "begruendung"):
        if read.get(key):
            out[key] = str(read[key])
    return out
