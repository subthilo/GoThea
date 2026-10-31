"""Erklär-Stufe (alle Fächer): Luna erklärt eine echte Aufgabe Schritt für Schritt, danach eine kleine Abfrage.

Abgestimmt mit dem Nutzer 31.10. (Klick-Modell im Artifact „Erklär-Tutorial Mockup“): Thea kommt bei
Textaufgaben (und manchmal im Unterricht) nicht mit; bei Akku „fast leer“ gibt es nur noch Erklärungen.
Jeder Schritt besteht aus kurzen Sätzen; jeder Satz wird geschrieben und vorgelesen, und genau das, wovon er
spricht, leuchtet: Stellen im Aufgabentext, Teile der Veranschaulichung (beim Dreisatz die Tabelle), Kärtchen.
Dinge erscheinen erst, wenn Luna davon spricht. Zum Schluss Fragen zum Antippen, nur zur Logik.

Daten in der Übung (``erklaerung``), geschrieben in Claude-Code-Sessions, von den Eltern freigegeben:
    markierungen: {id: Textstelle}       – wörtlich im Aufgabentext, genau einmal
    karten:       {id: {text, bleibt?, art?}} – Kärtchen links unter der Aufgabe; ohne „bleibt“ nur im Schritt
    schritte:     [[{satz, zeige: [ids], neu: [ids]}]]
    abfrage:      [{frage, antworten, richtig, warum}] – ``richtig`` = Index, ``warum`` je Antwort
Den ersten Schritt („Wir lesen zuerst die Aufgabe“, Satz für Satz, ids ``a1``, ``a2`` …) und die
Veranschaulichung (``anzeige``, vom Übungstyp aus seinen Daten gebaut) erzeugt der Code. ``antwort`` ist der
Antwortsatz. ``validate`` prüft ids, Textstellen, jede Zahl (nur Zahlen aus der Aufgabe und ihrer Lösung) und
jede Rechnung im Satz („150 geteilt durch 3 ist 50“).
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Dict, Iterable, List, Set

from backend.app.services.exercise_types.common import shuffled
from backend.app.services.spoken_audio import sentence_url

INTRO = "Wir lesen zuerst die Aufgabe."
_NUM = r"\d+(?:\.\d{3})*(?:,\d+)?"
_CALC = re.compile(rf"({_NUM})\s*(?:[^\d\s]+\s+)?(geteilt durch|mal)\s+({_NUM})\s*(?:[^\d\s]+\s+)?ist\s+({_NUM})")


def _sentences(text: str) -> List[str]:
    from backend.app.services.llm import sentences
    return sentences(text)


def _num(s: str) -> Fraction:
    return Fraction(s.replace(".", "").replace(",", "."))


def numbers_in(text: str) -> List[Fraction]:
    # Zahlen in Wörtern wie „0,7-Liter-Flaschen“ oder „1-Liter“ zählen mit
    return [_num(m) for m in re.findall(_NUM, text)]


def segments(task: str, marks: Dict[str, str]) -> List[dict]:
    """Aufgabentext in Stücke mit Marken: Satz (a1, a2 …) und jede Markierung, die das Stück überdeckt."""
    spans = []
    pos = 0
    for i, sentence in enumerate(_sentences(task), 1):
        start = task.index(sentence, pos)
        spans.append((start, start + len(sentence), f"a{i}"))
        pos = start + len(sentence)
    for mark_id, needle in marks.items():
        start = task.find(needle)
        if start >= 0:
            spans.append((start, start + len(needle), mark_id))
    cuts = sorted({0, len(task)} | {p for s, e, _ in spans for p in (s, e)})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        tags = [tag for s, e, tag in spans if s <= a and b <= e]
        out.append({"t": task[a:b], "marken": tags})
    return out


def _intro_step(task: str) -> List[dict]:
    beats = [{"satz": INTRO, "zeige": [], "neu": []}]
    beats += [{"satz": s, "zeige": [f"a{i}"], "neu": []} for i, s in enumerate(_sentences(task), 1)]
    return beats


def build(ex: dict, display: dict) -> dict:
    """Alles für die Ansicht: Textstücke, Schritte (mit Lese-Schritt vorn), Anzeige, Kärtchen, Abfrage mit
    gemischten Antworten, zu jedem gesprochenen Text die Audio-Datei."""
    data = ex["erklaerung"]
    steps = [_intro_step(ex["aufgabentext"])] + data["schritte"]
    steps = [[{**b, "zeige": b.get("zeige", []), "neu": b.get("neu", []), "audio": sentence_url(b["satz"])}
              for b in step] for step in steps]
    quiz = []
    for n, q in enumerate(data["abfrage"]):
        order = shuffled(list(range(len(q["antworten"]))), f"{ex['id']}-erklaeren-{n}")
        answers = [q["antworten"][i] for i in order]
        why = [q["warum"][i] for i in order]
        quiz.append({"frage": q["frage"], "antworten": answers, "richtig": order.index(q["richtig"]), "warum": why,
                     "audio": {"frage": sentence_url(q["frage"]), "antworten": [sentence_url(a) for a in answers],
                               "warum": [sentence_url(w) for w in why]}})
    return {
        "segmente": segments(ex["aufgabentext"], data.get("markierungen", {})),
        "schritte": steps,
        "anzeige": display,
        "karten": data.get("karten", {}),
        "antwort": ex["antwortsatz"],
        "abfrage": quiz,
    }


def spoken_texts(ex: dict) -> List[str]:
    """Jeder Text, den die Erklär-Stufe dieser Übung vorliest (für scripts/build_practice_help_audio.py)."""
    data = ex["erklaerung"]
    texts = [b["satz"] for step in [_intro_step(ex["aufgabentext"])] + data["schritte"] for b in step]
    for q in data["abfrage"]:
        texts += [q["frage"], *q["antworten"], *q["warum"]]
    return texts


def validate(ex: dict, display_ids: Iterable[str], allowed_numbers: Set[Fraction]) -> List[str]:
    """Fehlerliste der Erklärung (leer = stimmig). ``allowed_numbers``: Zahlen aus Aufgabe und Lösung."""
    data = ex.get("erklaerung")
    if not data:
        return []
    errors: List[str] = []
    task = ex["aufgabentext"]
    marks = data.get("markierungen", {})
    for mark_id, needle in marks.items():
        if task.count(needle) != 1:
            errors.append(f"Erklärung: Markierung „{mark_id}“ steht nicht genau einmal im Aufgabentext")
    known = set(marks) | set(display_ids) | set(data.get("karten", {})) | {"antwort"}
    known |= {f"a{i}" for i in range(1, len(_sentences(task)) + 1)}
    allowed = set(allowed_numbers) | set(numbers_in(task))

    def check_text(where: str, text: str) -> None:
        for value in numbers_in(text):
            if value not in allowed:
                errors.append(f"Erklärung {where}: Zahl {value} kommt in Aufgabe und Lösung nicht vor")
        for a, op, b, c in _CALC.findall(text):
            result = _num(a) / _num(b) if op == "geteilt durch" else _num(a) * _num(b)
            if result != _num(c):
                errors.append(f"Erklärung {where}: {a} {op} {b} ist nicht {c}")

    if not data.get("schritte"):
        errors.append("Erklärung: keine Schritte")
    for s, step in enumerate(data.get("schritte", []), 1):
        if not step:
            errors.append(f"Erklärung Schritt {s}: leer")
        for b, beat in enumerate(step, 1):
            where = f"Schritt {s}.{b}"
            if not beat.get("satz"):
                errors.append(f"Erklärung {where}: Satz fehlt")
                continue
            check_text(where, beat["satz"])
            for ref in beat.get("zeige", []) + beat.get("neu", []):
                if ref not in known:
                    errors.append(f"Erklärung {where}: „{ref}“ gibt es nicht")
    for card_id, card in data.get("karten", {}).items():
        check_text(f"Kärtchen {card_id}", card["text"])
    quiz = data.get("abfrage") or []
    if not quiz:
        errors.append("Erklärung: Abfrage fehlt")
    for n, q in enumerate(quiz, 1):
        answers = q.get("antworten") or []
        if len(answers) < 2 or not 0 <= q.get("richtig", -1) < len(answers):
            errors.append(f"Erklärung Frage {n}: Antworten oder richtige Antwort fehlen")
        if len(q.get("warum") or []) != len(answers):
            errors.append(f"Erklärung Frage {n}: zu jeder Antwort ein „warum“")
        for text in [q.get("frage", ""), *answers, *(q.get("warum") or [])]:
            check_text(f"Frage {n}", text)
    return errors
