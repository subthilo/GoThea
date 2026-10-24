"""Übungstyp „Schriftlich rechnen“: Addition, Subtraktion, Multiplikation, Division im Kästchengitter.

Eine Übung nennt nur das ``verfahren`` und die ``aufgabe`` („5,3405 : 55“). Gitter, Rechenschritte mit Regelsätzen,
Antipp-Fragen und das Fehlerbild rechnet dieser Code aus – nach dem Merkblatt „Die schriftlichen
Grundrechenarten“ (mat_7cc9d80e, von den Eltern vorgegeben, 24.10.): Addition mit Übertrag zwischen Aufgabe und
Strich, Subtraktion im Ergänzungsverfahren (Übertrag bei der nächsten Stelle der unteren Zahl), Multiplikation mit
der größten Stelle beginnend (Teilprodukte mit Endnullen, Komma erst am Ende: Nachkommastellen zählen), Division
von links nach rechts (Teilen → Malnehmen → Abziehen → Herunterholen, Komma im Ergebnis beim Überschreiten).
Teilen durch eine Kommazahl: zuerst bei beiden Zahlen das Komma verschieben.

Stufen (von voller Hilfe bis selbstständig): -2 Zuschauen (die Rechnung baut sich Schritt für Schritt mit Regelsatz
auf), -1 Antippen (bei jedem Schritt eine Frage mit drei Antworten), 1 Ergebnis eintragen (alles andere steht),
2 Zwischenzeilen, Überträge und Ergebnis eintragen, 3 Aufgabe selbst stellengerecht aufschreiben und rechnen,
4 Fehler finden (fertige Rechnung mit einem typischen Fehler). Eingabe mit den Zahlentasten, Prüfung im Browser
(js/practice_schriftlich.js). Die letzte Stufe – komplett handschriftlich auf der Tafel, Luna liest, der Code
rechnet (Nutzer, 24.10.) – kommt, sobald Lunas Lesegenauigkeit für schriftliche Rechnungen gemessen ist.

Schreibregeln der Eltern (25.10.): Ziffern stehen immer in einem Kästchen, ein Komma verschiebt keine Ziffer – es
sitzt auf der senkrechten Rasterlinie rechts neben der Einerziffer, unten an der waagerechten Linie. Der Strich
liegt auf der Rasterlinie direkt unter der Zahlenzeile. Ein Übertrag steht klein unten rechts im Kästchen der Zahl,
der er zugeordnet ist (Addition: letzter Summand, Subtraktion: untere Zahl, Multiplikation: letztes Teilprodukt).

Zellen: ``{id, r, c, z, art, opt, platz}``; ``platz`` = ziffer | komma (rechts neben dem Kästchen) | uebertrag
(klein unten rechts im Kästchen). ``art`` = aufgabe | null (aufgefüllte Null) | op (Rechenzeichen, immer sichtbar)
| uebertrag | zwischen (Teilprodukte, Divisionszeilen) | ergebnis. ``opt``: darf leer bleiben (Überträge, Nullen,
die nicht zwingend sind). ``zeilen_info``: ``strich`` (Strich unter der Zeile), ``richtung`` (Schreibrichtung).
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from backend.app.services.exercise_types.common import shuffled

TYP = "schriftlich"
STAGES = [-2, -1, 1, 2, 3, 4]
BOARD_STAGES: List[int] = []

SIGNS = {"addition": "+", "subtraktion": "−", "multiplikation": "·", "division": ":"}
MAX_DECIMALS = 6   # Division: höchstens so viele Nachkommastellen, dann muss sie aufgehen
MAX_COLS = 22
MAX_ROWS = 14

PLACES = {
    5: ("Hunderttausender", "Hunderttausendern"), 4: ("Zehntausender", "Zehntausendern"),
    3: ("Tausender", "Tausendern"), 2: ("Hunderter", "Hundertern"), 1: ("Zehner", "Zehnern"), 0: ("Einer", "Einern"),
    -1: ("Zehntel", "Zehnteln"), -2: ("Hundertstel", "Hundertsteln"), -3: ("Tausendstel", "Tausendsteln"),
    -4: ("Zehntausendstel", "Zehntausendsteln"), -5: ("Hunderttausendstel", "Hunderttausendsteln"),
    -6: ("Millionstel", "Millionsteln"),
}


# --- Zahlen ------------------------------------------------------------------------------------------------

class Num:
    """Dezimalzahl wie geschrieben: Ziffern vor und nach dem Komma („0,87“ → "0", "87")."""

    def __init__(self, text: str):
        text = text.strip()
        if not re.fullmatch(r"\d+(,\d+)?", text):
            raise ValueError(f"„{text}“ ist keine Zahl")
        whole, _, dec = text.partition(",")
        self.whole = whole.lstrip("0") or "0"
        self.dec = dec
        self.text = self.whole + ("," + dec if dec else "")
        self.value = Decimal(self.whole + ("." + dec if dec else ""))

    def digit(self, place: int) -> Optional[int]:
        """Ziffer an der Stelle (0 Einer, 1 Zehner, -1 Zehntel …), None wenn die Zahl dort keine hat."""
        if place >= 0:
            return int(self.whole[-1 - place]) if place < len(self.whole) else None
        return int(self.dec[-place - 1]) if -place <= len(self.dec) else None


def fmt(value: Decimal, decimals: Optional[int] = None) -> str:
    """Zahl mit deutschem Komma; ohne decimals so kurz wie möglich."""
    if decimals is None:
        text = format(value.normalize(), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
    else:
        text = format(value.quantize(Decimal(1).scaleb(-decimals)), "f")
    return text.replace(".", ",")


def parse(ex: dict) -> Tuple[str, List[Num]]:
    verfahren = ex.get("verfahren")
    if verfahren not in SIGNS:
        raise ValueError(f"verfahren: {', '.join(SIGNS)}")
    sign = SIGNS[verfahren]
    text = str(ex.get("aufgabe") or "").replace("-", "−").replace("*", "·").replace("×", "·")
    parts = [p for p in re.split(r"\s*([+−·:])\s*", text.strip())]
    numbers, ops = parts[0::2], parts[1::2]
    if not ops or any(op != sign for op in ops):
        raise ValueError(f"Aufgabe „{ex.get('aufgabe')}“ passt nicht zu {verfahren} ({sign})")
    if verfahren != "addition" and len(numbers) != 2:
        raise ValueError("Genau zwei Zahlen (mehrere Summanden nur bei der Addition)")
    return verfahren, [Num(n) for n in numbers]


# --- Gitter ---------------------------------------------------------------------------------------------

SLOT_SUFFIX = {"ziffer": "", "komma": "k", "uebertrag": "u"}


class Grid:
    def __init__(self):
        self.cells: Dict[Tuple[int, int, str], dict] = {}
        self.rows: Dict[int, dict] = {}

    def put(self, r: int, c: int, z: str, art: str, opt: bool = False, platz: str = "ziffer") -> str:
        cid = f"r{r}c{c}{SLOT_SUFFIX[platz]}"
        self.cells[(r, c, platz)] = {"id": cid, "r": r, "c": c, "z": z, "art": art, "opt": opt, "platz": platz}
        return cid

    def get(self, r: int, c: int, platz: str = "ziffer") -> Optional[dict]:
        return self.cells.get((r, c, platz))

    def drop(self, r: int, c: int, platz: str = "ziffer"):
        self.cells.pop((r, c, platz), None)

    def row(self, r: int, **props):
        self.rows.setdefault(r, {}).update(props)

    def to_json(self) -> dict:
        cells = sorted(self.cells.values(), key=lambda x: (x["r"], x["c"], x["platz"]))
        height = max([c["r"] for c in cells] + list(self.rows)) + 1
        width = max(c["c"] for c in cells) + 2  # eine freie Spalte rechts (Stufe 3: verschoben aufgeschrieben)
        return {"spalten": width, "zeilen": height, "zellen": cells,
                "zeilen_info": {str(r): p for r, p in sorted(self.rows.items())}}


def _options(right, wrongs, seed: str) -> List[str]:
    """Richtige Antwort und zwei falsche; reichen die typischen Fehler nicht, Nachbarzahlen."""
    fallback = [right + 1, right + 2, right - 1] if isinstance(right, int) else []
    out = [str(right)]
    for w in list(wrongs) + fallback:
        if w is not None and str(w) not in out and (not isinstance(w, int) or w >= 0):
            out.append(str(w))
        if len(out) == 3:
            break
    return shuffled(out, seed)


def _step(satz: str, cells: List[str], frage: Optional[str] = None, antwort=None, wrongs=(), seed: str = "") -> dict:
    step = {"satz": satz, "zellen": cells}
    if frage:
        step.update(frage=frage, antwort=str(antwort), optionen=_options(antwort, wrongs, seed))
    return step


# --- Addition und Subtraktion ------------------------------------------------------------------------------

def _add_sub(verfahren: str, nums: List[Num], seed: str, forget_carry: Optional[int] = None) -> dict:
    """forget_carry: Stelle, deren Übertrag vergessen wird (Fehlerbild)."""
    sub = verfahren == "subtraktion"
    total = nums[0].value - nums[1].value if sub else sum(n.value for n in nums)
    D = max(len(n.dec) for n in nums)
    I_ops = max(len(n.whole) for n in nums)
    res = Num(fmt(total, D) if D else str(total))
    I = max(I_ops, len(res.whole))

    def col(p: int) -> int:  # Einer in Spalte I, Zehntel rechts daneben (das Komma braucht kein Kästchen)
        return I - p

    g = Grid()
    n = len(nums)
    last, res_r = n - 1, n  # Überträge im Kästchen der letzten Zahl, Strich darunter
    pads: List[str] = []
    for j, num in enumerate(nums):
        if j:
            g.put(j, 0, SIGNS[verfahren], "op")
        for p in range(I_ops - 1, -D - 1, -1):
            d = num.digit(p)
            if d is not None:
                g.put(j, col(p), str(d), "aufgabe")
            elif p < 0 or (D and p < I_ops):
                # Nullen auffüllen: rechts bei der oberen Zahl der Subtraktion zwingend (Ergänzen), sonst erlaubt
                pads.append(g.put(j, col(p), "0", "null", opt=not (sub and j == 0 and p < 0)))
        if D:
            g.put(j, col(0), ",", "aufgabe", platz="komma")
    g.row(last, strich=True)
    g.row(res_r, richtung="rtl")
    steps = []
    if pads:
        satz = ("Komma unter Komma! Fehlende Nachkommastellen füllen wir mit Nullen auf – sonst können wir nicht "
                "richtig ergänzen." if sub else "Komma unter Komma! Leere Stellen füllen wir mit Nullen auf.")
        steps.append(_step(satz, pads, "Was schreiben wir in die leeren Stellen?", "0", ["1", "nichts"], seed + "-null"))
    carry = 0
    carry_from: List[int] = []  # Stellen, die einen Übertrag weitergeben
    res_len = len(res.whole)
    for p in range(-D, I_ops):
        name = PLACES[p][0]
        if p == 0 and D:
            steps.append(_step("Das Komma ziehen wir im Ergebnis genau an der gleichen Stelle nach unten.",
                               [g.put(res_r, col(0), ",", "ergebnis", platz="komma")],
                               "Wohin kommt das Komma im Ergebnis?", "unter die Kommas", ["ans Ende", "nach vorne"],
                               f"{seed}-komma"))
        cells: List[str] = []
        if sub:
            top, bottom = nums[0].digit(p) or 0, (nums[1].digit(p) or 0)
            lower = bottom + carry
            pre = f"{carry} (Übertrag) + {bottom} = {lower}. " if carry else ""
            if lower <= top:
                diff, out, target = top - lower, 0, top
                text = f"{name}: {pre}Von {lower} bis {top} fehlen {diff}."
            else:
                diff, out, target = top + 10 - lower, 1, top + 10
                text = (f"{name}: {pre}Von {lower} bis {top} geht nicht. Also ergänzen wir von {lower} bis {top + 10}. "
                        f"Das sind {diff}.")
            if forget_carry is not None and p == forget_carry + 1 and carry:
                diff = (diff + 1) % 10
            if p > 0 and p >= res_len:
                text += " Eine 0 ganz vorne schreiben wir nicht."
            else:
                cells.append(g.put(res_r, col(p), str(diff), "ergebnis"))
                text += f" Wir schreiben {diff}" + (f" und notieren den Übertrag 1 bei den {PLACES[p + 1][1]} der unteren Zahl." if out else ".")
            if out:
                carry_from.append(p)
                if forget_carry != p:
                    cells.append(g.put(last, col(p + 1), "1", "uebertrag", opt=True, platz="uebertrag"))
            steps.append(_step(text, cells, f"{name}: Von {lower} bis {target} fehlen?", diff,
                               [diff + 1, diff - 1 if diff else diff + 2], f"{seed}-{p}"))
            carry = out
            continue
        digits = [num.digit(p) or 0 for num in nums]
        s = carry + sum(digits)
        terms = (f"{carry} (Übertrag) + " if carry else "") + " + ".join(map(str, digits))
        if forget_carry is not None and p == forget_carry + 1 and carry:
            s -= carry
        if p == I_ops - 1:
            for k, ch in enumerate(reversed(str(s))):
                cells.append(g.put(res_r, col(p + k), ch, "ergebnis"))
            text = f"{name}: {terms} = {s}. Wir schreiben {s}."
        else:
            cells.append(g.put(res_r, col(p), str(s % 10), "ergebnis"))
            text = f"{name}: {terms} = {s}. Wir schreiben {s % 10}"
            if s >= 10:
                text += f" auf und notieren {s // 10} als Übertrag bei den {PLACES[p + 1][1]}."
                carry_from.append(p)
                if forget_carry != p:
                    cells.append(g.put(last, col(p + 1), str(s // 10), "uebertrag", opt=True, platz="uebertrag"))
            else:
                text += "."
        steps.append(_step(text, cells, f"{terms} = ?", s, [s - carry if carry else s + 1, s + 10 if s < 10 else s - 10],
                           f"{seed}-{p}"))
        carry = s // 10
    return {"grid": g, "steps": steps, "ergebnis": res.text, "carry_from": carry_from, "res_row": res_r}


# --- Multiplikation ----------------------------------------------------------------------------------------

def _digits(num: Num) -> str:
    return (num.whole + num.dec).lstrip("0") or "0"


def _mul(nums: List[Num], seed: str, forget_zero: bool = False) -> dict:
    a, b = nums
    A, B = _digits(a), _digits(b)
    decimals = len(a.dec) + len(b.dec)
    g = Grid()
    for k, ch in enumerate(list(A) + ["·"] + list(B)):
        g.put(0, 1 + k, ch, "op" if ch == "·" else "aufgabe")
    end = len(A) + len(B) + 1  # Spalte der Einer des zweiten Faktors
    g.row(0, strich=True)
    steps = []
    vorspann = None
    if decimals:
        vorspann = f"{a.text} · {b.text}"
        steps.append(_step(f"Das Komma wird beim Aufschreiben und Rechnen zunächst völlig ignoriert: Wir rechnen {A} · {B}.",
                           [], "Was machen wir mit dem Komma?", "erst weglassen", ["mitrechnen", "streichen"], seed + "-ohne"))
    partials = []
    single = len(B) == 1
    for j, d in enumerate(map(int, B)):
        r = 1 + j
        k = len(B) - 1 - j
        prod = int(A) * d
        written = str(prod) + ("" if (forget_zero and k == 1) else "0" * k)
        partials.append(int(written))
        if j and not single:
            g.put(r, 0, "+", "op")
        cells = [g.put(r, end - i, ch, "ergebnis" if single else "zwischen") for i, ch in enumerate(reversed(written))]
        g.row(r, richtung="rtl")
        chain, carry = [], 0
        for i, x in enumerate(reversed(A)):
            p = d * int(x) + carry
            piece = f"{d} · {x} = {d * int(x)}" + (f", plus {carry} sind {p}" if carry else "")
            lastdigit = i == len(A) - 1
            piece += f", wir schreiben {p}." if lastdigit or p < 10 else f", wir schreiben {p % 10} und merken {p // 10}."
            chain.append(piece)
            carry = p // 10 if not lastdigit else 0
        text = f"Mit der {d} ({PLACES[k][0]}): " + " ".join(chain)
        if k == 1:
            text += " Die leere Einerstelle füllen wir mit einer 0 auf."
        elif k >= 2:
            text += f" Die {k} leeren Stellen rechts füllen wir mit Nullen auf."
        nocarry = int("".join(str(d * int(x) % 10) for x in A))
        steps.append(_step(text, cells, f"{d} · {A} = ?", prod, [nocarry, prod + 10, prod - 10], f"{seed}-m{j}"))
    product = sum(partials)
    res_r = 1
    if not single:
        last, res_r = len(B), len(B) + 1  # Überträge im Kästchen des letzten Teilprodukts, Strich darunter
        g.row(last, strich=True)
        g.row(res_r, richtung="rtl")
        cells, carry = [], 0
        strs = [str(x) for x in partials]
        for i in range(len(str(product))):
            s = carry + sum(int(x[-1 - i]) for x in strs if i < len(x))
            if s >= 10 and i + 1 < len(str(product)):
                cells.append(g.put(last, end - i - 1, str(s // 10), "uebertrag", opt=True, platz="uebertrag"))
            carry = s // 10
        for i, ch in enumerate(reversed(str(product))):
            cells.append(g.put(res_r, end - i, ch, "ergebnis"))
        joined = " + ".join(strs)
        steps.append(_step(f"Die Zwischenergebnisse werden schriftlich addiert: {joined} = {product}.", cells,
                           f"{joined} = ?", product, [product + 10, product - 10], seed + "-sum"))
    digits = str(product).rjust(decimals + 1, "0")
    result = digits[:len(digits) - decimals] + ("," + digits[len(digits) - decimals:] if decimals else "")
    if decimals:
        # Komma ins Ergebnis, ohne eine Ziffer zu verschieben; fehlt vorn eine Stelle, kommt eine 0 dazu („0,25“)
        cells = [g.put(res_r, end - i, "0", "ergebnis") for i in range(len(str(product)), len(digits))]
        cells.append(g.put(res_r, end - decimals, ",", "ergebnis", platz="komma"))

        def st(n: int) -> str:
            return f"{n} Nachkommastelle" + ("" if n == 1 else "n")
        steps.append(_step(f"Kommastellen zählen: {a.text} hat {st(len(a.dec))}, {b.text} hat {st(len(b.dec))}. "
                           f"Zusammen also {st(decimals)}. Ergebnis: {result}.", cells,
                           "Wie viele Nachkommastellen bekommt das Ergebnis?", decimals,
                           [max(len(a.dec), len(b.dec)), decimals + 1, decimals - 1], seed + "-komma"))
    return {"grid": g, "steps": steps, "ergebnis": result, "vorspann": vorspann, "res_row": res_r}


# --- Division ----------------------------------------------------------------------------------------------

def _shifted(a: Num, b: Num) -> Tuple[Num, Num, int]:
    shift = len(b.dec)
    if not shift:
        return a, b, 0
    factor = Decimal(10) ** shift
    return Num(fmt(a.value * factor)), Num(fmt(b.value * factor)), shift


def _divide(a: Num, divisor: int) -> Tuple[List[int], int, str]:
    """Ziffern des Dividenden samt angehängter Nullen, Anzahl Ganzer, Ergebnis. ValueError, wenn sie nicht aufgeht."""
    digits = [int(x) for x in a.whole + a.dec]
    n_int = len(a.whole)
    result = a.value / divisor
    decimals = 0
    while result != result.quantize(Decimal(1).scaleb(-decimals)):
        decimals += 1
        if decimals > MAX_DECIMALS:
            raise ValueError(f"Division geht nach {MAX_DECIMALS} Nachkommastellen nicht auf")
    while len(digits) - n_int < decimals:
        digits.append(0)
    return digits, n_int, fmt(result)


def _div(nums: List[Num], seed: str, error: Optional[str] = None) -> dict:
    a0, b0 = nums
    a, b, shift = _shifted(*nums)
    if b.dec or int(b.whole) == 0:
        raise ValueError("Teiler muss eine Zahl größer 0 sein")
    divisor = int(b.whole)
    digits, n_int, result = _divide(a, divisor)
    given = len(a.whole) + len(a.dec)
    g = Grid()
    cols = [1 + i for i in range(len(digits))]
    for i, d in enumerate(digits):
        g.put(0, cols[i], str(d), "null" if i >= given else "aufgabe")
    if len(digits) > n_int:  # Komma des Dividenden rechts neben seiner Einerziffer
        g.put(0, cols[n_int - 1], ",", "aufgabe" if a.dec else "null", platz="komma")
    col = cols[-1] + 1
    g.put(0, col, ":", "op")
    for k, ch in enumerate(b.whole):
        g.put(0, col + 1 + k, ch, "aufgabe")
    col += 1 + len(b.whole)
    g.put(0, col, "=", "op")
    qcol = col + 1
    steps = []
    vorspann = None
    if shift:
        vorspann = f"{a0.text} : {b0.text} = {a.text} : {b.text}"
        stellen = "eine Stelle" if shift == 1 else f"{shift} Stellen"
        steps.append(_step(f"Durch eine Kommazahl teilen wir nicht. Wir verschieben bei beiden Zahlen das Komma um {stellen} "
                           f"nach rechts: {vorspann}.", [], "Um wie viele Stellen verschieben wir das Komma?", shift,
                           [shift + 1, shift - 1 or shift + 2], seed + "-schieben"))
    g.row(0, richtung="ltr")
    q: List[str] = []           # Ziffern des Ergebnisses
    q_comma: Optional[int] = None  # Anzahl Ergebnisziffern vor dem Komma
    cur, started, row = 0, False, None  # row: Zeile der aktuellen Zahl (None = Aufgabenzeile)
    skipped: List[str] = []
    r = 1
    for i, d in enumerate(digits):
        cells: List[str] = []
        pre: List[str] = []
        if started and cur == 0 and i < n_int and not any(digits[i:]):
            # Rest 0, es folgen nur Nullen vor dem Komma: jede bekommt im Ergebnis eine 0
            for _ in range(i, n_int):
                q.append("0")
                cells.append(g.put(0, qcol + len(q) - 1, "0", "ergebnis"))
            zeros = n_int - i
            steps.append(_step(f"Der Rest ist 0 und es kommen nur noch Nullen. Für jede schreiben wir im Ergebnis eine 0 "
                               f"({zeros}-mal).", cells, "Wie viele Nullen kommen noch ins Ergebnis?", zeros,
                               [zeros + 1, zeros - 1], f"{seed}-nullen"))
            break
        cur = cur * 10 + d
        if i >= given:
            cells.append(g.get(0, cols[i])["id"])
            if i == n_int and not a.dec:
                cells.append(g.get(0, cols[n_int - 1], "komma")["id"])
            pre.append("Wir hängen eine 0 an.")
        if row is not None and started:
            cells.append(g.put(row, cols[i], str(d), "zwischen"))
            pre.append(f"Die {d} herunterholen.")
        elif started and i > 0:
            pre.append(f"Wir nehmen die {d} dazu.")
        if i == n_int:
            q_comma = len(q)
            cells.append(g.put(0, qcol + len(q) - 1, ",", "ergebnis", platz="komma"))
            pre.append("Wir überschreiten das Komma – im Ergebnis setzen wir sofort das Komma!")
        number = cur
        digit = cur // divisor
        if not started and digit == 0 and i < n_int - 1:
            skipped.append(str(cur))
            continue
        if skipped:
            pre.insert(0, " ".join(f"{x} : {divisor} geht nicht, wir nehmen die nächste Ziffer dazu." for x in skipped))
            skipped = []
        started = True
        q.append(str(digit))
        cells.append(g.put(0, qcol + len(q) - 1, str(digit), "ergebnis"))
        last = i == len(digits) - 1
        zero_tail = not last and len(digits) <= n_int and not any(digits[i + 1:])
        if digit:
            prod, rest = digit * divisor, cur - digit * divisor
            for k, ch in enumerate(reversed(str(prod))):
                cells.append(g.put(r, cols[i - k], ch, "zwischen"))
            g.row(r, strich=True, richtung="rtl")
            row = r + 1
            g.row(row, richtung="rtl")
            if rest or last or zero_tail:
                for k, ch in enumerate(reversed(str(rest))):
                    cells.append(g.put(row, cols[i - k], ch, "zwischen"))
            text = (f"{cur} : {divisor} = {digit}. Wir schreiben die {digit}. Rückrechnung: {digit} · {divisor} = {prod}. "
                    f"Abziehen: {cur} − {prod} = {rest}.")
            r += 2
            cur = rest
        else:
            text = (f"{cur} : {divisor} geht nicht. Vor dem Komma schreiben wir 0." if i == n_int - 1 and len(q) == 1
                    else f"{cur} : {divisor} geht nicht. Wir schreiben 0.")
        if last:
            text += " Der Rest ist 0 – fertig!"
        steps.append(_step(" ".join(pre + [text]), cells, f"Wie oft passt {divisor} in {number}?",
                           digit, [digit + 1 if digit < 9 else digit - 2, digit - 1 if digit else digit + 2], f"{seed}-d{i}"))
    if error:
        wrong, comma = list(q), q_comma
        if error == "null":  # eine 0 im Ergebnis vergessen
            k = next(k for k, ch in enumerate(wrong) if ch == "0" and k > 0)
            del wrong[k]
            if comma is not None and k < comma:
                comma -= 1
        elif error == "komma":  # Komma vergessen (bei „0,…“ samt der 0 davor)
            if comma == 1 and wrong[0] == "0":
                wrong = wrong[1:]
            comma = None
        for k in range(len(q)):
            g.drop(0, qcol + k)
            g.drop(0, qcol + k, "komma")
        for k, ch in enumerate(wrong):
            g.put(0, qcol + k, ch, "ergebnis")
        if comma:
            g.put(0, qcol + comma - 1, ",", "ergebnis", platz="komma")
    return {"grid": g, "steps": steps, "ergebnis": result, "vorspann": vorspann, "res_row": 0}


# --- Fehlerbild (Stufe 4) ------------------------------------------------------------------------------------

def _error_kind(ex: dict, verfahren: str, nums: List[Num], plain: dict) -> str:
    if ex.get("fehler"):
        return ex["fehler"]
    has_comma = "," in plain["ergebnis"]
    if verfahren in ("addition", "subtraktion"):
        return "uebertrag" if plain["carry_from"] else ("komma" if has_comma else "ziffer")
    if verfahren == "multiplikation":
        return "null" if len(_digits(nums[1])) > 1 else ("komma" if has_comma else "ziffer")
    q = plain["ergebnis"]
    return "null" if "0" in q.lstrip("0,") or q.startswith("0,0") else ("komma" if has_comma else "ziffer")


ERROR_TEXT = {
    "uebertrag": "Hier fehlt ein Übertrag.",
    "komma": {"addition": "Das Komma steht falsch. Komma unter Komma!",
              "subtraktion": "Das Komma steht falsch. Komma unter Komma!",
              "multiplikation": "Das Komma steht falsch. Zähl die Nachkommastellen beider Zahlen zusammen.",
              "division": "Im Ergebnis fehlt das Komma. Es kommt hinein, sobald wir es beim Herunterholen überschreiten."},
    "null": {"multiplikation": "Beim zweiten Zwischenergebnis fehlt die 0 am Ende – es ist um eine Stelle verrutscht.",
             "division": "Im Ergebnis fehlt eine 0: Passt die Zahl nicht hinein, schreiben wir 0."},
    "ziffer": "Hier hat sich ein Rechenfehler eingeschlichen.",
}


def _move_comma(g: Grid, row: int, verfahren: str) -> bool:
    """Komma im Ergebnis eine Stelle verschieben (Addition/Subtraktion nach rechts wie Theas 490,21, Multiplikation
    nach links: eine Nachkommastelle zu viel gezählt). Nie ganz vorn oder hinter die letzte Ziffer."""
    comma = next((c for (r, _, platz), c in g.cells.items() if r == row and platz == "komma"), None)
    if comma is None:
        return False
    cols = {c for (r, c, platz) in g.cells if r == row and platz == "ziffer"}
    c = comma["c"]
    for step in ((1, -1) if verfahren != "multiplikation" else (-1, 1)):
        target = c + step
        if target in cols and target + 1 in cols:
            g.drop(row, c, "komma")
            g.put(row, target, ",", "ergebnis", platz="komma")
            return True
    return False


def _error_picture(ex: dict, verfahren: str, nums: List[Num], plain: dict, seed: str) -> dict:
    kind = _error_kind(ex, verfahren, nums, plain)
    if verfahren in ("addition", "subtraktion") and kind == "uebertrag" and plain["carry_from"]:
        wrong = _add_sub(verfahren, nums, seed, forget_carry=plain["carry_from"][0])["grid"]
    elif verfahren == "multiplikation" and kind == "null" and len(_digits(nums[1])) > 1:
        wrong = _mul(nums, seed, forget_zero=True)["grid"]
    elif verfahren == "division" and kind in ("null", "komma") and (kind == "komma" or "0" in plain["ergebnis"][1:]):
        wrong = _div(nums, seed, error=kind)["grid"]
    else:
        wrong = _copy_grid(plain["grid"])
        if not (kind == "komma" and _move_comma(wrong, plain["res_row"], verfahren)):
            kind = "ziffer"
            cell = min((c for c in wrong.cells.values() if c["art"] == "ergebnis" and c["platz"] == "ziffer"),
                       key=lambda c: (c["r"], c["c"]))
            cell["z"] = str((int(cell["z"]) + 1) % 10)
    text = ERROR_TEXT[kind]
    text = text[verfahren] if isinstance(text, dict) else text
    return {"art": kind, "satz": text, "zellen": wrong.to_json()["zellen"]}


def _copy_grid(g: Grid) -> Grid:
    out = Grid()
    out.cells = {k: dict(v) for k, v in g.cells.items()}
    out.rows = {k: dict(v) for k, v in g.rows.items()}
    return out


# --- Schnittstelle des Typs ----------------------------------------------------------------------------------

def build(ex: dict) -> dict:
    verfahren, nums = parse(ex)
    seed = ex.get("id", "")
    if verfahren in ("addition", "subtraktion"):
        if verfahren == "subtraktion" and nums[0].value < nums[1].value:
            raise ValueError("Subtraktion: die obere Zahl muss die größere sein")
        plain = _add_sub(verfahren, nums, seed)
    elif verfahren == "multiplikation":
        if "0" in _digits(nums[1]):
            raise ValueError("Zweiter Faktor mit einer 0 – Teilprodukt 0 ist noch nicht vorgesehen")
        plain = _mul(nums, seed)
    else:
        plain = _div(nums, seed)
    return {"verfahren": verfahren, "nums": nums, "plain": plain, "seed": seed}


def validate(ex: dict) -> List[str]:
    try:
        built = build(ex)
    except (ValueError, StopIteration) as err:
        return [str(err) or "Aufgabe lässt sich nicht rechnen"]
    errors: List[str] = []
    grid = built["plain"]["grid"].to_json()
    if grid["spalten"] > MAX_COLS:
        errors.append(f"Zu breit für einen Bildschirm ({grid['spalten']} Spalten, höchstens {MAX_COLS})")
    if grid["zeilen"] > MAX_ROWS:
        errors.append(f"Zu hoch für einen Bildschirm ({grid['zeilen']} Zeilen, höchstens {MAX_ROWS})")
    expected = ex.get("ergebnis")
    if expected is not None and str(expected) != built["plain"]["ergebnis"]:
        errors.append(f"Ergebnis {expected} stimmt nicht, gerechnet: {built['plain']['ergebnis']}")
    try:
        _error_picture(ex, built["verfahren"], built["nums"], built["plain"], built["seed"])
    except (ValueError, StopIteration, IndexError) as err:
        errors.append(f"Fehlerbild für Stufe 4 lässt sich nicht bauen ({err or 'fehler'})")
    return errors


def prepare(ex: dict) -> dict:
    built = build(ex)
    plain = built["plain"]
    return {
        "gitter": plain["grid"].to_json(),
        "schritte": plain["steps"],
        "ergebnis_gerechnet": plain["ergebnis"],
        "vorspann": plain.get("vorspann"),
        "fehlerbild": _error_picture(ex, built["verfahren"], built["nums"], plain, built["seed"]),
    }


def summary(ex: dict) -> dict:
    return {}
