"""Rechnet die Pilot-Übungen vom Typ 'Sachaufgabe mit Lösungsweg' nach.

Grundsatz „Luna liest, der Code rechnet“: Jede Zeile des Musterwegs, das
Ergebnis und die Zahl im Antwortsatz werden exakt (Bruchrechnung) geprüft.
Aufruf: .venv/bin/python experiments/uebungen/verify_sachaufgabe.py
"""

from __future__ import annotations

import json
import re
import sys
from fractions import Fraction
from pathlib import Path

DATEI = Path(__file__).with_name("sachaufgabe_pilot.json")


def zahl(x) -> Fraction:
    return Fraction(str(x).replace(",", "."))


def wende_an(op: str, wert: Fraction) -> Fraction:
    faktor = zahl(op[1:])
    return wert / faktor if op[0] == ":" else wert * faktor


def umkehr(op: str) -> str:
    return ("·" if op[0] == ":" else ":") + op[1:]


def pruefe_dreisatz(u: dict) -> list[str]:
    fehler = []
    zeilen = [(zahl(a), zahl(b)) for a, b in u["zeilen"]]
    anti = u["schema"] == "dreisatz_antiproportional"
    for i, op in enumerate(u["schritte"]):
        (x0, y0), (x1, y1) = zeilen[i], zeilen[i + 1]
        op_rechts = umkehr(op) if anti else op
        if wende_an(op, x0) != x1:
            fehler.append(f"Zeile {i + 2} links: {x0} {op} ≠ {x1}")
        if wende_an(op_rechts, y0) != y1:
            fehler.append(f"Zeile {i + 2} rechts: {y0} {op_rechts} ≠ {y1}")
    # Die Zuordnung selbst: proportional = gleicher Quotient, antiproportional = gleiches Produkt
    kennwerte = {x * y if anti else y / x for x, y in zeilen}
    if len(kennwerte) != 1:
        fehler.append(f"Zeilen gehören nicht zu einer Zuordnung: {kennwerte}")
    if zeilen[-1][1] != zahl(u["ergebnis"]["wert"]):
        fehler.append("letzte Zeile ≠ Ergebnis")
    return fehler


def pruefe_rechnung(u: dict) -> list[str]:
    a, b = (zahl(z) for z in u["rechnung"]["zahlen"])
    fehler = []
    if a / b != zahl(u["ergebnis"]["wert"]):
        fehler.append(f"{a} : {b} = {a / b}, nicht {u['ergebnis']['wert']}")
    links, rechts = (zahl(t) for t in u["rechnung"]["umformung"].split(":"))
    if links / rechts != a / b or rechts.denominator != 1:
        fehler.append("Umformung (Komma verschieben) stimmt nicht")
    return fehler


def zahl_im_satz(satz: str) -> Fraction | None:
    treffer = re.findall(r"\d[\d.]*(?:,\d+)?", satz)
    return zahl(treffer[-1].replace(".", "")) if treffer else None


def main() -> int:
    daten = json.loads(DATEI.read_text(encoding="utf-8"))
    ids = {u["id"] for u in daten["uebungen"]}
    gesamt = 0
    for u in daten["uebungen"]:
        fehler = pruefe_rechnung(u) if u["schema"] == "rechnung" else pruefe_dreisatz(u)
        # Der Antwortsatz nennt das Ergebnis und dessen Einheit
        if zahl_im_satz(u["antwortsatz"]) != zahl(u["ergebnis"]["wert"]):
            fehler.append("Zahl im Antwortsatz ≠ Ergebnis")
        einheit = u["ergebnis"]["einheit"]
        if einheit and einheit not in u["antwortsatz"]:
            fehler.append(f"Einheit „{einheit}“ fehlt im Antwortsatz")
        if not u["antwortsatz"].startswith(u["antwort_anfang"]):
            fehler.append("Antwortsatz beginnt nicht mit antwort_anfang")
        # Schätzfrage: Die richtige Antwort muss zum Ergebnis passen
        sf = u["schaetzfrage"]
        erg, ref = zahl(u["ergebnis"]["wert"]), zahl(sf["vergleichswert"])
        if (erg > ref) != (sf["ergebnis_ist"] == "groesser") or erg == ref:
            fehler.append(f"Schätzfrage passt nicht: Ergebnis {erg}, Vergleich {ref}, erwartet {sf['ergebnis_ist']}")
        if sf["antwort"] not in sf["optionen"]:
            fehler.append("Antwort der Schätzfrage steht nicht in den Optionen")
        if zahl(u["fehlerbeispiel"]["wert"]) == erg:
            fehler.append("Fehlerbeispiel ist gleich dem Ergebnis")
        if u["ableitung"] == "B" and u.get("zwilling_von") not in ids:
            fehler.append("zwilling_von zeigt auf keine Übung")
        gesamt += len(fehler)
        print(f"{'OK ' if not fehler else 'FEHLER'} {u['id']}")
        for f in fehler:
            print(f"       {f}")
    print(f"\n{len(daten['uebungen'])} Übungen, {gesamt} Fehler")
    return 1 if gesamt else 0


if __name__ == "__main__":
    sys.exit(main())
