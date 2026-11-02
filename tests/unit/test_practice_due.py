"""Was dran ist und die Runde (services/practice_due.py) – mit erfundenen Übungen, ohne Datenbank."""
from datetime import datetime, timedelta

from backend.app.services.practice_due import DueTest, Scope, build_round, locked, matches, nodes

NOW = datetime(2026, 10, 24, 15, 0)
AH = "mat_ah_ch01"     # Arbeitsheft-Kapitel
BUCH = "mat_buch_ch01"


def fam(id, seite, abschnitt, thema="top_sicher", fach="sub_chemie", nummer="1", nach=None, stufen=(-1, 1, 2, 3)):
    return {"id": id, "fach": fach, "thema": thema, "abschnitt": abschnitt, "zwillinge": [],
            "stufen": list(stufen), "tafel_stufen": [3],
            "quelle": {"material_id": AH, "material_seite": seite, "nummer": nummer},
            "nachschlagen": {"material_id": BUCH, "material_seite": nach} if nach else None}


LABOR = fam("labor", 1, "Laborgeräte", nummer="1", nach=19)
REGELN = fam("regeln", 1, "Regeln", nummer="2", nach=16)
BRENNER = fam("brenner", 2, "Brenner", nummer="3", nach=17)
MATHE = fam("dreisatz", 5, "Dreisatz", thema="top_dreisatz", fach="sub_math")
ALL = [BRENNER, REGELN, LABOR, MATHE]


def plan(stand=None, offen=(), wiederholen=()):
    return {"stand": stand or {}, "offen": list(offen), "wiederholen": list(wiederholen)}


def done(*ids, stages=(1,)):
    return {i: {"geschafft": list(stages), "zuletzt": "2026-10-20T10:00:00"} for i in ids}


def test_exercise_is_due_by_topic_or_by_source_or_lookup_page():
    assert matches(LABOR, {"top_sicher"}, [])
    assert matches(LABOR, set(), [(AH, 1, 2)])          # Quelle im Arbeitsheft-Abschnitt
    assert matches(LABOR, set(), [(BUCH, 19, 19)])      # Fundstelle im Buch
    assert not matches(LABOR, set(), [(AH, 3, 5), ("mat_anderes", 1, 99)])


def test_nodes_follow_book_order_and_open_one_after_another():
    order = [[f["id"] for f in node] for node in nodes(ALL)["top_sicher"]]
    assert order == [["labor"], ["regeln"], ["brenner"]]
    assert locked(ALL, {}) == {"regeln", "brenner"}
    assert locked(ALL, done("labor")) == {"brenner"}
    assert locked(ALL, done("labor", "regeln")) == set()


def test_round_follows_the_nodes_and_opens_the_next_one_within_the_round():
    scope = Scope(themen={"top_sicher"})
    out = build_round(ALL, scope, plan(), now=NOW)
    # Labor steht in der Runde → Regeln öffnen gleich mit, danach Brenner (Nutzer 31.10.: sonst zu wenig)
    assert [(i["familie"], i["stufe"], i["art"]) for i in out["runde"]] == [
        ("labor", -1, "neu"), ("regeln", -1, "neu"), ("brenner", -1, "neu")]
    assert out["einstieg"] and out["dran"]["brenner"]["gesperrt"]  # über Runden hinweg weiter gesperrt
    out = build_round(ALL, scope, plan(done("labor", stages=(-1,))), now=NOW)
    assert [(i["familie"], i["stufe"]) for i in out["runde"]] == [("labor", 1), ("regeln", -1), ("brenner", -1)]


def test_a_full_round_does_not_skip_ahead_past_a_node_left_out():
    many = [{**LABOR, "id": f"labor{n}", "abschnitt": LABOR.get("abschnitt")} for n in range(5)]
    scope = Scope(themen={"top_sicher"})
    out = build_round(many + [REGELN, BRENNER], scope, plan(), now=NOW)
    assert len(out["runde"]) == 4 and {i["familie"] for i in out["runde"]} <= {f["id"] for f in many}


def test_board_stages_only_with_full_battery_after_the_beginning():
    scope = Scope(themen={"top_sicher"})
    progress = done("labor", "regeln", "brenner", stages=(-1, 1, 2))
    assert build_round(ALL, scope, plan(progress), akku="voll", solved_days=1, now=NOW)["runde"] == []
    out = build_round(ALL, scope, plan(progress), akku="voll", solved_days=10, now=NOW)
    assert {i["stufe"] for i in out["runde"]} == {3} and len(out["runde"]) == 3


def test_test_topics_come_first_and_a_due_repeat_is_mixed_in():
    scope = Scope(tests=[DueTest(id="tst_1", fach="sub_math", datum="2026-10-28", tage=4, phase=1,
                                 themen={"top_dreisatz"})],
                  themen={"top_sicher"})
    repeat = {"familie": "labor", "exercise_id": "labor", "stufe": 1, "seit": (NOW - timedelta(days=2)).isoformat()}
    out = build_round(ALL, scope, plan(done("labor"), wiederholen=[repeat]), solved_days=10, now=NOW)
    assert [(i["familie"], i["art"]) for i in out["runde"]] == [
        ("dreisatz", "neu"), ("labor", "wiederholen"), ("regeln", "neu"), ("brenner", "neu")]
    assert out["runde"][0]["grund"] == {"art": "test", "test_id": "tst_1", "tage": 4, "phase": 1}
    # Frische Wiederholung (unter 20 h) wartet noch
    fresh = {**repeat, "seit": (NOW - timedelta(hours=3)).isoformat()}
    out = build_round(ALL, scope, plan(done("labor"), wiederholen=[fresh]), solved_days=10, now=NOW)
    assert "wiederholen" not in [i["art"] for i in out["runde"]]


def test_dress_rehearsal_mixes_what_was_solved_and_exam_day_is_quiet():
    scope = Scope(tests=[DueTest(id="tst_1", fach="sub_chemie", datum="2026-10-25", tage=1, phase=3,
                                 themen={"top_sicher"})])
    out = build_round(ALL, scope, plan(done("labor", "regeln", stages=(-1, 1))), solved_days=10, now=NOW)
    assert [(i["familie"], i["stufe"], i["art"]) for i in out["runde"]] == [
        ("labor", 1, "generalprobe"), ("regeln", 1, "generalprobe")]
    scope.tests[0].phase = 0
    assert build_round(ALL, scope, plan(done("labor")), solved_days=10, now=NOW)["runde"] == []


def test_low_battery_gives_one_safe_task_and_subject_page_refreshes_when_nothing_is_due():
    progress = done("labor", "regeln", stages=(-1, 1, 3))
    out = build_round(ALL, Scope(themen={"top_sicher"}), plan(progress), akku="fast_leer", now=NOW)
    assert [(i["stufe"], i["art"]) for i in out["runde"]] == [(1, "sicher")]  # ohne Tafel-Stufe
    # Noch nichts geschafft: leichteste Stufe der ersten offenen Übung statt „nichts dran“
    out = build_round(ALL, Scope(themen={"top_sicher", "top_dreisatz"}), plan(), akku="fast_leer",
                      fach="sub_math", now=NOW)
    assert [(i["familie"], i["stufe"], i["art"]) for i in out["runde"]] == [("dreisatz", -1, "leicht")]
    assert build_round(ALL, Scope(), plan(), akku="fast_leer", now=NOW)["runde"] == []
    # Nichts dran: in „Üben“ leer, auf der Fachseite Auffrischen
    assert build_round(ALL, Scope(), plan(progress), now=NOW)["runde"] == []
    out = build_round(ALL, Scope(), plan(progress), fach="sub_chemie", now=NOW)
    assert {i["art"] for i in out["runde"]} == {"auffrischen"}


def test_low_battery_alternates_safe_and_new_so_thea_still_moves_on():
    scope = Scope(themen={"top_sicher"})
    progress = done("labor", "regeln", stages=(-1, 1))
    def pick(low_prev, stand=progress):
        out = build_round(ALL, scope, plan(stand), akku="fast_leer", low_prev=low_prev, now=NOW)
        return [(i["familie"], i["stufe"], i["art"]) for i in out["runde"]]
    assert pick(None) == [("labor", 1, "sicher")]
    assert pick("leicht") == [("labor", 1, "sicher")]
    assert pick("sicher") == [("brenner", -1, "leicht")]  # Neues auf der leichtesten Stufe
    # Nichts Neues mehr offen: wieder etwas Sicheres
    assert pick("sicher", done("labor", "regeln", "brenner")) == [("labor", 1, "sicher")]


def test_subject_page_only_shows_that_subject_and_count_feeds_the_dock_hint():
    scope = Scope(themen={"top_sicher", "top_dreisatz"})
    out = build_round(ALL, scope, plan(), fach="sub_math", now=NOW)
    assert [i["familie"] for i in out["runde"]] == ["dreisatz"]
    assert build_round(ALL, scope, plan(), now=NOW)["anzahl_dran"] == 2  # Labor + Dreisatz offen, Rest gesperrt


def test_started_attempt_comes_first():
    scope = Scope(themen={"top_sicher", "top_dreisatz"})
    offen = [{"familie": "dreisatz", "exercise_id": "dreisatz", "stufe": 1, "board_id": None}]
    out = build_round(ALL, scope, plan(offen=offen), now=NOW)
    assert (out["runde"][0]["familie"], out["runde"][0]["art"]) == ("dreisatz", "weiter")


def test_low_battery_brings_only_explanations_when_there_are_any():
    sa = {**fam("gummi", 1, "Dreisatz", thema="top_dreisatz", fach="sub_math", stufen=(-2, -1, 0)), "erklaeren": -2}
    sb = {**fam("drucker", 2, "Dreisatz", thema="top_dreisatz", fach="sub_math", stufen=(-2, -1, 0)), "erklaeren": -2}
    scope = Scope(themen={"top_sicher", "top_dreisatz"})
    families = ALL + [sa, sb]
    pick = lambda progress: [(i["familie"], i["stufe"], i["art"])
                             for i in build_round(families, scope, plan(progress), akku="fast_leer", now=NOW)["runde"]]
    assert pick({}) == [("gummi", -2, "erklaeren")]
    # Angesehen → die nächste Erklärung; alle angesehen → die am längsten nicht gesehene
    assert pick(done("gummi", stages=(-2,))) == [("drucker", -2, "erklaeren")]
    seen = {**done("gummi", stages=(-2,)), "drucker": {"geschafft": [-2], "zuletzt": "2026-10-10T10:00:00"}}
    assert pick(seen) == [("drucker", -2, "erklaeren")]
    # Andere Akkus: nie Erklären (Thea, 2.11.) – neue Sachaufgaben beginnen beim Gedankengang, auch wenn die
    # Erklärung angefangen oder geschafft ist
    for akku in ("geht_so", "voll"):
        for progress in ({}, done("gummi", stages=(-2,))):
            out = build_round(families, scope, plan(progress), akku=akku, now=NOW)
            stages = {i["familie"]: i["stufe"] for i in out["runde"]}
            assert stages.get("gummi") == -1 and -2 not in stages.values(), (akku, progress, stages)
    started = {"stand": {}, "offen": [{"familie": "gummi", "exercise_id": "gummi", "stufe": -2}], "wiederholen": []}
    out = build_round(families, scope, started, akku="geht_so", now=NOW)
    assert -2 not in [i["stufe"] for i in out["runde"]]
