"""Übungstyp „Schriftlich rechnen“, Stufe 5 auf der Tafel: „Luna liest, der Code rechnet“ (wie practice_check.py).

Thea schreibt die ganze Rechnung frei auf ein Kästchenblatt (Nutzer, 24.10.: letzte Stufe komplett handschriftlich,
Luna wertet aus).
1. ``read_board``: Luna überträgt Theas Zeilen Zeichen für Zeichen, ohne zu korrigieren, dazu das Ergebnis.
2. ``evaluate``: Das Programm vergleicht mit seiner eigenen Rechnung (services/exercise_types/schriftlich.py):
   stimmt das Ergebnis, ist die Aufgabe gelöst; sonst nennt es die erste Zeile, die nicht stimmt, mit dem gelesenen
   Wert – ohne die richtige Zahl zu verraten.
3. Ist Luna beim Lesen unsicher, fragt sie nach, statt zu urteilen.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from backend.app.prompts.practice import PRACTICE_WRITTEN_READING_SYSTEM_PROMPT
from backend.app.services import llm
from backend.app.services.exercise_types import schriftlich
from backend.app.services.practice_check import NOCH_NICHT, RICHTIG, UNSICHER


def read_board(ex: dict, stage: int, image_base64: str) -> dict:
    """Luna liest die Tafel. Wirft llm.LLMError, wenn die KI nicht antwortet."""
    data_url = image_base64 if image_base64.startswith("data:") else f"data:image/jpeg;base64,{image_base64}"
    messages = [
        {"role": "system", "content": PRACTICE_WRITTEN_READING_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": f"AUFGABE: {ex['aufgabe']} (schriftliche {ex['verfahren'].capitalize()})\n"
                                     "Lies jetzt ab, was Thea geschrieben hat."},
            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
        ]},
    ]
    return llm.chat_json(messages, purpose="Übung prüfen (Schriftlich rechnen)")


def _number(text) -> Optional[Decimal]:
    """„78,20“ → 78.20; None, wenn es keine Zahl ist (Rechenzeichen, ?)."""
    t = re.sub(r"\s", "", str(text or "")).lstrip("+−-")
    if not re.fullmatch(r"\d+(,\d+)?", t):
        return None
    try:
        return Decimal(t.replace(",", "."))
    except InvalidOperation:
        return None


def expected_rows(ex: dict) -> List[str]:
    """Zeilen der richtigen Rechnung von oben nach unten (Ziffern und Komma, ohne Überträge)."""
    grid = schriftlich.build(ex)["plain"]["grid"].to_json()
    rows: Dict[int, List[dict]] = {}
    for c in grid["zellen"]:
        if c["platz"] != "uebertrag":
            rows.setdefault(c["r"], []).append(c)
    out = []
    for r in sorted(rows):
        cells = sorted(rows[r], key=lambda x: (x["c"], x["platz"] == "komma"))
        out.append("".join(c["z"] for c in cells))
    return out


def _same_row(read: str, expected: str) -> bool:
    a, b = _number(read), _number(expected)
    if a is not None and b is not None:
        return a == b  # „02,75“ wie „2,75“, „78,2“ wie „78,20“
    return re.sub(r"[\s+−-]", "", str(read)) == re.sub(r"[\s+−-]", "", expected)


def evaluate(ex: dict, stage: int, read: dict) -> dict:
    """Ergebnis: status, probleme (Bereich = Zeilennummer ab 1 bzw. „ergebnis“, gelesener Text), hinweise."""
    result = schriftlich.build(ex)["plain"]["ergebnis"]
    written = str(read.get("ergebnis") or "").strip()
    unsure = bool(read.get("unsicher")) or "?" in written
    if _number(written) is not None and _number(written) == _number(result):
        return {"status": RICHTIG, "probleme": [], "hinweise": []}
    problems: List[dict] = []
    if not written:
        problems.append({"bereich": "ergebnis", "text": "Ich finde noch kein Ergebnis.", "gelesen": "", "unsicher": False})
    else:
        # erste Zeile, die nicht zur richtigen Rechnung passt (die Aufgabe selbst steht oben)
        rows = [str(x) for x in read.get("zeilen") or []]
        for k, (got, want) in enumerate(zip(rows, expected_rows(ex))):
            if not _same_row(got, want):
                problems.append({"bereich": str(k + 1), "text": f"In der {k + 1}. Zeile lese ich „{got}“. Da stimmt etwas nicht.",
                                 "gelesen": got, "unsicher": unsure or "?" in got})
                break
        problems.append({"bereich": "ergebnis", "text": f"Als Ergebnis lese ich „{written}“. Das stimmt noch nicht.",
                         "gelesen": written, "unsicher": unsure})
    status = UNSICHER if all(p["unsicher"] for p in problems) else NOCH_NICHT
    return {"status": status, "probleme": problems, "hinweise": []}


def feedback(ex: dict, outcome: dict, attempt: int) -> str:
    """Lunas Satz an Thea: Lob oder die erste Stelle, die nicht stimmt; ab dem 2. Versuch die Regel dazu."""
    if outcome["status"] == RICHTIG:
        return "Richtig gerechnet!"
    first = outcome["probleme"][0]
    if outcome["status"] == UNSICHER:
        return f"Ich bin mir nicht sicher, ob ich richtig lese: „{first['gelesen'] or '?'}“. Schreibst du es noch mal deutlicher?"
    text = first["text"]
    if attempt >= 2:
        nach = ex.get("nachschlagen") or {}
        text += f" Schau im Merkblatt nach: {nach['stelle']}." if nach.get("stelle") else ""
    return text


def marks(read: dict, outcome: dict) -> List[dict]:
    """Kasten um die erste Zeile mit Problem (Lage von Luna, Prozent des Tafelbilds)."""
    areas = read.get("bereiche") or []
    out = []
    for p in outcome["probleme"][:1]:
        k = len(read.get("zeilen") or []) if p["bereich"] == "ergebnis" else int(p["bereich"])
        box = areas[k - 1] if isinstance(areas, list) and 0 < k <= len(areas) else None
        if isinstance(box, dict) and all(isinstance(box.get(key), (int, float)) for key in ("x_pct", "y_pct", "w_pct", "h_pct")):
            out.append({"action": "highlight_box", "coords": {key: box[key] for key in ("x_pct", "y_pct", "w_pct", "h_pct")}})
    return out


def describe_read(read: dict, ex: dict) -> Dict[str, str]:
    """Gelesene Zeilen und Ergebnis für die Anzeige („gelesen: …“)."""
    out = {str(k + 1): str(z) for k, z in enumerate(read.get("zeilen") or []) if z}
    if read.get("ergebnis"):
        out["ergebnis"] = str(read["ergebnis"])
    return out
