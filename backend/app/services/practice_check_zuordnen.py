"""Übungstyp „Zuordnen“ auf der Tafel prüfen: „Luna liest, der Code vergleicht“ (wie practice_check.py für Mathe).

1. ``read_board``: Luna überträgt, was Thea zu jeder Nummer geschrieben hat – Buchstabe für Buchstabe, ohne zu
   korrigieren.
2. ``evaluate``: Das Programm vergleicht mit dem Begriff aus dem Buch (Groß-/Kleinschreibung und Leerzeichen
   egal, Begriffe aus ``auch`` gelten auch). Bei langen Wörtern zählt ein einzelner Buchstabe daneben noch als
   richtig, mit dem Hinweis auf die Schreibweise.
3. Jede Rückmeldung nennt den gelesenen Text; ist Luna unsicher, fragt sie nach, statt zu urteilen.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from backend.app.prompts.practice import PRACTICE_LABEL_READING_SYSTEM_PROMPT
from backend.app.services import llm
from backend.app.services.practice_check import NOCH_NICHT, RICHTIG, UNSICHER

SPELLING_TOLERANCE_FROM = 6  # ab dieser Länge darf ein Buchstabe abweichen


def read_board(ex: dict, stage: int, image_base64: str) -> dict:
    """Luna liest die Tafel. Wirft llm.LLMError, wenn die KI nicht antwortet."""
    data_url = image_base64 if image_base64.startswith("data:") else f"data:image/jpeg;base64,{image_base64}"
    numbers = ", ".join(str(f["nr"]) for f in ex["felder"])
    messages = [
        {"role": "system", "content": PRACTICE_LABEL_READING_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": f"AUFGABE: {ex['aufgabentext']}\nNUMMERN: {numbers}\nLies jetzt ab, was Thea geschrieben hat."},
            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
        ]},
    ]
    return llm.chat_json(messages, purpose="Übung prüfen (Zuordnen)")


def _norm(text) -> str:
    return re.sub(r"[\s\-–]+", " ", str(text or "")).strip(" .,;:").lower()


def _distance(a: str, b: str) -> int:
    """Levenshtein-Abstand (kurze Begriffe, einfache Tabelle)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _match(written: str, field: dict) -> Optional[str]:
    """'genau', 'schreibweise' (ein Buchstabe daneben) oder None."""
    w = _norm(written)
    accepted = [_norm(t) for t in [field["begriff"], *field.get("auch", [])]]
    if w in accepted:
        return "genau"
    if any(len(t) >= SPELLING_TOLERANCE_FROM and _distance(w, t) <= 1 for t in accepted):
        return "schreibweise"
    return None


def evaluate(ex: dict, stage: int, read: dict) -> dict:
    """Vergleicht die gelesenen Begriffe. Ergebnis: status, probleme (Bereich = Nummer, gelesener Text), hinweise."""
    written: Dict[int, str] = {}
    for row in read.get("zeilen") or []:
        try:
            written[int(row.get("nr"))] = str(row.get("text") or "").strip()
        except (TypeError, ValueError):
            continue
    unsure = set()
    for n in read.get("unsicher") or []:
        try:
            unsure.add(int(n))
        except (TypeError, ValueError):
            pass
    problems: List[dict] = []
    hints: List[str] = []
    for field in ex["felder"]:
        nr, text = field["nr"], written.get(field["nr"], "")
        if not text:
            problems.append({"bereich": str(nr), "text": f"Bei {nr} fehlt noch der Begriff.", "gelesen": "",
                             "unsicher": False})
            continue
        found = _match(text, field)
        if found == "schreibweise":
            hints.append(f"Bei {nr} schreibt man „{field['begriff']}“.")
        elif found is None:
            problems.append({"bereich": str(nr), "text": f"Bei {nr} lese ich „{text}“. Das passt noch nicht.",
                             "gelesen": text, "unsicher": nr in unsure or "?" in text})
    if not problems:
        status = RICHTIG
    elif all(p["unsicher"] for p in problems):
        status = UNSICHER
    else:
        status = NOCH_NICHT
    return {"status": status, "probleme": problems, "hinweise": hints}


def feedback(ex: dict, outcome: dict, attempt: int) -> str:
    """Lunas Satz an Thea: Lob, das erste Problem mit gelesenem Text, ab dem 2. Versuch eine Hilfe."""
    if outcome["status"] == RICHTIG:
        text = "Richtig! Alle Begriffe stimmen."
        if outcome["hinweise"]:
            text += " " + " ".join(outcome["hinweise"][:2])
        return text
    problems = outcome["probleme"]
    first = problems[0]
    if outcome["status"] == UNSICHER:
        return f"Bei {first['bereich']} bin ich mir nicht sicher, ob ich richtig lese: „{first['gelesen'] or '?'}“. Schreibst du es noch mal deutlicher?"
    text = first["text"]
    if len(problems) > 1:
        others = ", ".join(p["bereich"] for p in problems[1:4])
        text += f" Schau auch noch mal bei {others}."
    if attempt >= 2 and (ex.get("hilfen") or {}).get("denkanstoss"):
        text += " " + ex["hilfen"]["denkanstoss"]
    if attempt >= 3 and ex.get("nachschlagen"):
        text += f" Im Buch steht es auf Seite {ex['nachschlagen']['seite']}."
    return text


def marks(read: dict, outcome: dict) -> List[dict]:
    """Kästen um die Begriffe mit Problemen (Lage von Luna, Prozent des Tafelbilds)."""
    areas = read.get("bereiche") or {}
    out = []
    for p in outcome["probleme"]:
        box = areas.get(p["bereich"])
        if isinstance(box, dict) and all(isinstance(box.get(k), (int, float)) for k in ("x_pct", "y_pct", "w_pct", "h_pct")):
            out.append({"action": "highlight_box", "coords": {k: box[k] for k in ("x_pct", "y_pct", "w_pct", "h_pct")}})
    return out


def describe_read(read: dict, ex: dict) -> Dict[str, str]:
    """Gelesene Begriffe für die Anzeige („gelesen: …“)."""
    return {str(r.get("nr")): str(r.get("text") or "") for r in read.get("zeilen") or [] if r.get("text")}
