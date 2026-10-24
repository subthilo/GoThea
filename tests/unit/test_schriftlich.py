"""Übungstyp „Schriftlich rechnen“: das Rechenwerk baut Gitter, Schritte und Fehlerbild für alle vier Verfahren."""
import pytest

from backend.app.services.exercise_types import schriftlich as sr

# Aufgaben aus Theas Unterlagen und dem Merkblatt (mat_7cc9d80e) mit Ergebnis
CASES = [
    ("addition", "348 + 275", "623"),
    ("addition", "34,8 + 2,75", "37,55"),
    ("addition", "160,5 + 27,8 + 0,87", "189,17"),
    ("addition", "18,45 + 59,75", "78,20"),
    ("subtraktion", "734 − 281", "453"),
    ("subtraktion", "73,4 − 2,81", "70,59"),
    ("subtraktion", "83,4 − 5,579", "77,821"),
    ("subtraktion", "77,821 − 28,8", "49,021"),
    ("multiplikation", "243 · 12", "2916"),
    ("multiplikation", "2,43 · 1,2", "2,916"),
    ("multiplikation", "37,5 · 3", "112,5"),
    ("division", "852 : 3", "284"),
    ("division", "8,52 : 3", "2,84"),
    ("division", "5,3405 : 55", "0,0971"),
    ("division", "34,445 : 2,5", "13,778"),
    ("division", "0,117 : 12", "0,00975"),
    ("division", "2100 : 0,7", "3000"),
    ("division", "612 : 6", "102"),
]


def ex(verfahren, aufgabe, **more):
    return {"id": "t", "verfahren": verfahren, "aufgabe": aufgabe, **more}


def row_text(cells, r):
    """Ziffern einer Zeile samt Komma, ohne Leerraum."""
    cs = sorted((c for c in cells if c["r"] == r and c["platz"] != "uebertrag"), key=lambda x: (x["c"], x["platz"] == "komma"))
    return "".join(c["z"] for c in cs)


def carries(cells):
    return {(c["r"], c["c"]): c["z"] for c in cells if c["platz"] == "uebertrag"}


@pytest.mark.parametrize("verfahren,aufgabe,result", CASES, ids=[c[1] for c in CASES])
def test_every_procedure_computes_and_reveals_every_cell(verfahren, aufgabe, result):
    task = ex(verfahren, aufgabe)
    assert sr.validate(task) == []
    data = sr.prepare(task)
    assert data["ergebnis_gerechnet"] == result
    cells = data["gitter"]["zellen"]
    res = [c for c in cells if c["art"] == "ergebnis" and c["platz"] != "uebertrag"]
    row = 0 if verfahren == "division" else max(c["r"] for c in res)
    assert row_text([c for c in res if c["r"] == row], row) == result
    # Zuschauen deckt alles auf, was Thea schreibt – jede Zelle genau einmal
    revealed = [cid for st in data["schritte"] for cid in st["zellen"]]
    assert len(revealed) == len(set(revealed))
    to_write = {c["id"] for c in cells if c["art"] not in ("aufgabe", "op")}
    assert set(revealed) == to_write
    # Antippen: drei verschiedene Antworten, eine davon richtig
    for st in data["schritte"]:
        if st.get("frage"):
            assert len(set(st["optionen"])) == 3 and st["antwort"] in st["optionen"], st
    # Fehlerbild weicht ab, aber nur in Zellen, die Thea schreibt
    picture = {(c["r"], c["c"], c["platz"]): c["z"] for c in data["fehlerbild"]["zellen"]}
    plain = {(c["r"], c["c"], c["platz"]): c["z"] for c in cells}
    diff = {pos for pos in set(picture) | set(plain) if picture.get(pos) != plain.get(pos)}
    assert diff
    given = {(c["r"], c["c"], c["platz"]) for c in cells if c["art"] in ("aufgabe", "op")}
    assert not diff & given


def test_layouts_follow_the_school_sheet():
    # Merkblatt + Schreibregeln der Eltern: Übertrag klein im Kästchen der unteren Zahl, Strich unter ihr
    data = sr.prepare(ex("addition", "348 + 275"))
    cells = data["gitter"]["zellen"]
    assert [row_text(cells, r) for r in range(3)] == ["348", "+275", "623"]
    assert carries(cells) == {(1, 1): "1", (1, 2): "1"}
    assert data["gitter"]["zeilen_info"]["1"]["strich"]
    # Multiplikation: 2430 + 486, Übertrag im Kästchen des letzten Teilprodukts
    cells = sr.prepare(ex("multiplikation", "243 · 12"))["gitter"]["zellen"]
    assert [row_text(cells, r) for r in range(4)] == ["243·12", "2430", "+486", "2916"]
    assert carries(cells) == {(2, 4): "1"}
    # Division 852 : 3 = 284, Zeilen unter den Ziffern
    cells = sr.prepare(ex("division", "852 : 3"))["gitter"]["zellen"]
    assert [row_text(cells, r) for r in range(7)] == ["852:3=284", "6", "25", "24", "12", "12", "0"]
    # Ergänzungsverfahren: obere Zahl zwingend mit Nullen auffüllen, Übertrag bei der unteren Zahl
    cells = sr.prepare(ex("subtraktion", "73,4 − 2,81"))["gitter"]["zellen"]
    assert [row_text(cells, r) for r in range(3)] == ["73,40", "−02,81", "70,59"]
    assert carries(cells) == {(1, 2): "1", (1, 3): "1"}
    pads = {(c["r"], c["opt"]) for c in cells if c["art"] == "null"}
    assert pads == {(0, False), (1, True)}


def test_comma_never_moves_a_digit():
    # Kommas haben kein Kästchen: Ziffern gleicher Stelle stehen in derselben Spalte, das Komma rechts der Einer
    cells = sr.prepare(ex("subtraktion", "77,821 − 28,8"))["gitter"]["zellen"]
    commas = {c["r"]: c["c"] for c in cells if c["platz"] == "komma"}
    assert commas == {0: commas[0], 1: commas[0], 2: commas[0]}
    digits = {(c["r"], c["c"]) for c in cells if c["platz"] == "ziffer" and c["art"] != "op"}
    assert {c for r, c in digits if r == 0} == {c for r, c in digits if r == 2}
    cells = sr.prepare(ex("multiplikation", "2,43 · 1,2"))["gitter"]["zellen"]
    assert row_text(cells, 3) == "2,916" and len([c for c in cells if c["r"] == 3 and c["platz"] == "ziffer"]) == 4


def test_sentences_use_the_wording_of_the_sheet():
    steps = sr.prepare(ex("subtraktion", "734 − 281"))["schritte"]
    assert steps[1]["satz"].startswith("Zehner: Von 8 bis 3 geht nicht. Also ergänzen wir von 8 bis 13. Das sind 5.")
    steps = sr.prepare(ex("division", "8,52 : 3"))["schritte"]
    assert "Wir überschreiten das Komma – im Ergebnis setzen wir sofort das Komma!" in steps[1]["satz"]
    steps = sr.prepare(ex("multiplikation", "2,43 · 1,2"))["schritte"]
    assert steps[0]["satz"].startswith("Das Komma wird beim Aufschreiben und Rechnen zunächst völlig ignoriert")
    assert "Zusammen also 3 Nachkommastellen" in steps[-1]["satz"]


def test_error_pictures_are_typical_mistakes():
    def wrong_result(task):
        data = sr.prepare(task)
        cells = [c for c in data["fehlerbild"]["zellen"] if c["art"] == "ergebnis"]
        row = 0 if task["verfahren"] == "division" else max(c["r"] for c in cells)
        return row_text(cells, row)
    assert wrong_result(ex("addition", "18,45 + 59,75")) == "78,10"          # Übertrag vergessen
    assert wrong_result(ex("subtraktion", "77,821 − 28,8")) == "59,021"
    assert wrong_result(ex("subtraktion", "77,821 − 28,8", fehler="komma")) == "490,21"  # Theas Fehler
    assert wrong_result(ex("addition", "1,2 + 3,4", fehler="komma")) == "5,6"  # zu kurz zum Verschieben: Ziffer
    assert wrong_result(ex("multiplikation", "37,5 · 3")) == "11,25"          # eine Nachkommastelle zu viel
    assert wrong_result(ex("division", "5,3405 : 55")) == "0,971"            # Null im Ergebnis vergessen
    assert wrong_result(ex("division", "4,1787 : 9")) == "4643"              # „0,“ vergessen


@pytest.mark.parametrize("task,message", [
    (ex("addition", "3 − 2"), "passt nicht"),
    (ex("subtraktion", "2,5 − 3"), "größere"),
    (ex("division", "1 : 3"), "geht nach"),
    (ex("multiplikation", "12 · 10"), "Faktor mit einer 0"),
    (ex("division", "123456789,5 : 5"), "Zu breit"),
    (ex("addition", "12 + 3", ergebnis="16"), "stimmt nicht"),
    (ex("multiplikation", "1,5 · zwei"), "keine Zahl"),
])
def test_bad_tasks_are_rejected(task, message):
    assert any(message in e for e in sr.validate(task))
