"""Was Thea gerade üben soll: welche Übungen dran sind, welche Abschnitte offen sind, und die Runde.

Thea wählt nicht selbst (Konzept-Doc, Tab „Übungen für Thea – Ablauf“): Tippt sie auf „Üben“ (alle Fächer)
oder auf einer Fachseite (ein Fach), stellt der Server eine Runde zusammen. Die Eltern steuern nur indirekt
über den Lernplan: Themen und Buchabschnitte von Tests und „gerade dran“.

Dran ist eine Übung, wenn ihr Thema gewählt ist oder ihre Quelle bzw. Fundstelle (Material + Seite in der
Datei) in einem gewählten Abschnitt liegt. Innerhalb eines Themas sind die Abschnitte der Übungen Knoten in
Buchreihenfolge; der nächste Knoten öffnet, wenn jede Übung des vorigen einmal geschafft ist (egal auf
welcher Stufe) – oder schon in derselben Runde, wenn alle Übungen davor darin vorkommen.

Die Runde, in dieser Reihenfolge:
1. Angefangenes (dran),
2. Test-Stoff nach der Phase des Lernplans: Erarbeiten/Üben → nächste Stufe der offenen Knoten,
   Generalprobe (letzter Tag) → schon Geschafftes aus allen Knoten des Tests; am Prüfungstag nichts,
3. „gerade dran“ → nächste Stufe der offenen Knoten,
dazwischen (an zweiter Stelle) eine fällige Wiederholung. **Schwerpunkt** (``schwerpunkt_bis`` in den
Übungsdaten, Nutzer 7.11.: vor dem Chemie-Test zuerst die Gefahrenpiktogramme): bis zu diesem Tag (Berliner
Zeit) stehen solche Übungen vor allen anderen dran-Übungen, auch vor Angefangenem, und sind nie gesperrt;
danach gilt wieder die Buchreihenfolge. Ist nichts dran: fällige Wiederholungen, auf der
Fachseite auch Auffrischen von Geschafftem. Akku „fast leer“: eine Aufgabe – gibt es Übungen mit Erklär-Stufe
(services/explanations.py), nur Erklärungen (Nutzer 31.10.: dann nur Tutorien); sonst abwechselnd etwas schon
Geschafftes und die leichteste Stufe einer neuen Übung. Tafel-Stufen nur bei vollem Akku und nach dem Einstieg.
Reine Rechnung ohne Datenbank: die Daten sammelt ``collect`` (Router).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Set, Tuple

# Runde: so viele Aufgaben (Einstieg = die ersten Übungstage, gemeinsam mit den Eltern)
ROUND_SIZE = {"einstieg": 4, "gewohnheit": 6}
EINSTIEG_TAGE = 5          # bis Thea an so vielen Tagen etwas geschafft hat, gilt der Einstieg
AKKU = ("fast_leer", "geht_so", "voll")

Section = Tuple[str, int, int]  # Kapitel-Material, erste und letzte Seite (Seiten in der Datei)


@dataclass
class DueTest:
    id: str
    fach: str
    datum: str
    tage: int
    phase: int                  # 1 Erarbeiten, 2 Üben, 3 Generalprobe, 0 Prüfungstag
    themen: Set[str] = field(default_factory=set)
    abschnitte: List[Section] = field(default_factory=list)


@dataclass
class Scope:
    tests: List[DueTest] = field(default_factory=list)       # nur Tests, die heute im Lernplan dran sind
    themen: Set[str] = field(default_factory=set)            # „gerade dran“
    abschnitte: List[Section] = field(default_factory=list)  # „gerade dran“


def _refs(fam: dict) -> List[Tuple[str, int]]:
    out = []
    for key in ("quelle", "nachschlagen"):
        ref = fam.get(key) or {}
        if ref.get("material_id") and isinstance(ref.get("material_seite"), int):
            out.append((ref["material_id"], ref["material_seite"]))
    return out


def matches(fam: dict, themen: Set[str], abschnitte: List[Section]) -> bool:
    if fam.get("thema") in themen:
        return True
    return any(mat == m and start <= page <= end for mat, page in _refs(fam) for m, start, end in abschnitte)


def reasons(fam: dict, scope: Scope) -> List[dict]:
    """Warum eine Übung dran ist: Tests (frühester zuerst) und „gerade dran“."""
    out = [{"art": "test", "test_id": t.id, "tage": t.tage, "phase": t.phase}
           for t in sorted(scope.tests, key=lambda t: t.datum)
           if t.fach == fam["fach"] and matches(fam, t.themen, t.abschnitte)]
    if matches(fam, scope.themen, scope.abschnitte):
        out.append({"art": "aktuell"})
    return out


def _order_key(fam: dict) -> tuple:
    q = fam.get("quelle") or {}
    return (q.get("material_seite") or 0, q.get("material_id") or "", str(q.get("nummer") or ""), fam["id"])


def _focus(fam: dict, now: datetime) -> bool:
    """Schwerpunkt bis einschließlich ``schwerpunkt_bis`` (Berliner Datum; ``now`` ist UTC ohne Zeitzone)."""
    until = fam.get("schwerpunkt_bis")
    today = now.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
    return bool(until) and today <= until


def nodes(families: List[dict]) -> Dict[str, List[List[dict]]]:
    """Thema → Knoten (Abschnitte der Übungen) in Buchreihenfolge, je Knoten die Übungen."""
    by_topic: Dict[str, Dict[str, List[dict]]] = {}
    for fam in sorted(families, key=_order_key):
        by_topic.setdefault(fam["thema"], {}).setdefault(fam.get("abschnitt") or fam["id"], []).append(fam)
    return {topic: list(sections.values()) for topic, sections in by_topic.items()}


def locked(families: List[dict], progress: Dict[str, dict]) -> Set[str]:
    """Übungen in Knoten, deren Vorgänger noch nicht jede Übung einmal geschafft haben."""
    out: Set[str] = set()
    for topic_nodes in nodes(families).values():
        blocked = False
        for node in topic_nodes:
            if blocked:
                out.update(f["id"] for f in node)
            elif not all(progress.get(f["id"], {}).get("geschafft") for f in node):
                blocked = True
    return out


def is_beginner(solved_days: int) -> bool:
    return solved_days < EINSTIEG_TAGE


def _allowed(fam: dict, board: bool) -> List[int]:
    # Erklären nur bei Akku „fast leer“ (eigener Zweig in build_round; Thea, 2.11.: sonst nicht)
    return [s for s in fam["stufen"] if (board or s not in fam["tafel_stufen"]) and s != fam.get("erklaeren")]


def _next_stage(fam: dict, progress: dict, board: bool) -> Optional[int]:
    solved = progress.get(fam["id"], {}).get("geschafft") or []
    higher = [s for s in _allowed(fam, board) if not solved or s > max(solved)]
    return higher[0] if higher else None


def _best_solved(fam: dict, progress: dict, board: bool) -> Optional[int]:
    solved = [s for s in progress.get(fam["id"], {}).get("geschafft") or [] if s in _allowed(fam, board)]
    return max(solved) if solved else None


def build_round(families: List[dict], scope: Scope, plan: dict, akku: str = "geht_so",
                fach: Optional[str] = None, solved_days: int = 0, now: Optional[datetime] = None,
                low_prev: Optional[str] = None) -> dict:
    """plan = Ergebnis von practice_plan.plan (stand, offen, wiederholen); low_prev = Art der letzten Runde mit
    Akku „fast leer“ ('sicher'/'leicht'). Liefert Runde, Anzahl für den Hinweis am Üben-Symbol und je Übung, ob
    sie dran oder gesperrt ist."""
    from backend.app.services.practice_plan import REPEAT_AFTER

    now = now or datetime.utcnow()
    beginner = is_beginner(solved_days)
    board = akku == "voll" and not beginner
    progress = plan.get("stand", {})
    # Buchreihenfolge, Schwerpunkt-Übungen vorneweg
    focus = {f["id"] for f in families if _focus(f, now)}
    families = sorted((f for f in families if fach is None or f["fach"] == fach),
                      key=lambda f: (f["id"] not in focus, _order_key(f)))
    by_id = {f["id"]: f for f in families}
    why = {f["id"]: reasons(f, scope) for f in families}
    due = [f for f in families if why[f["id"]]]
    shut = locked(due, progress) - focus
    focus_open = any(f["id"] in focus and _next_stage(f, progress, board) is not None for f in due)

    items: List[dict] = []
    used: Set[str] = set()

    def add(fam: dict, stage: Optional[int], art: str, exercise_id: Optional[str] = None, board_id=None) -> None:
        if stage is None or fam["id"] in used:
            return
        used.add(fam["id"])
        grund = why[fam["id"]][0] if why[fam["id"]] else None
        items.append({"exercise_id": exercise_id or fam["id"], "familie": fam["id"], "stufe": stage, "art": art,
                      "grund": grund, "board_id": board_id})

    # Fällige Wiederholungen (gehakt, mindestens einen Tag her), älteste zuerst
    repeats = []
    for r in plan.get("wiederholen", []):
        fam = by_id.get(r["familie"])
        if fam and (now - datetime.fromisoformat(r["seit"])) >= REPEAT_AFTER and r["stufe"] in _allowed(fam, board):
            repeats.append((fam, r))
    open_count = sum(1 for f in due if f["id"] not in shut and _next_stage(f, progress, board) is not None) + len(repeats)

    exam_day = {t.fach for t in scope.tests if t.phase == 0}
    explainable = [f for f in due if f.get("erklaeren") is not None and f["id"] not in shut and f["fach"] not in exam_day]
    if akku == "fast_leer" and explainable:
        # Nur Erklärungen: zuerst eine noch nicht angesehene (Buchreihenfolge), sonst die am längsten nicht gesehene
        unseen = [f for f in explainable if f["erklaeren"] not in (progress.get(f["id"], {}).get("geschafft") or [])]
        pick = unseen[0] if unseen else min(explainable, key=lambda f: progress.get(f["id"], {}).get("zuletzt") or "")
        add(pick, pick["erklaeren"], "erklaeren")
    elif akku == "fast_leer":
        # Eine Aufgabe, abwechselnd (low_prev = Art der letzten „fast leer“-Runde): etwas Sicheres – Geschafftes,
        # zuletzt am längsten nicht geübt, auf der höchsten Stufe ohne Tafel – und etwas Neues auf der leichtesten
        # Stufe. Sonst käme bei Dauer-„fast leer“ immer dieselbe geschaffte Übung und Thea käme nicht weiter.
        solved = [f for f in families if _best_solved(f, progress, False) is not None]
        solved.sort(key=lambda f: (not why[f["id"]], progress.get(f["id"], {}).get("zuletzt") or ""))
        easy = [f for f in due if f["id"] not in shut and f["fach"] not in exam_day
                and not progress.get(f["id"], {}).get("geschafft") and _allowed(f, False)]
        picks = [("sicher", solved), ("leicht", easy)]
        if low_prev == "sicher":
            picks.reverse()
        for art, candidates in picks:
            if candidates:
                f = candidates[0]
                add(f, _best_solved(f, progress, False) if art == "sicher" else min(_allowed(f, False)), art)
                break
    else:
        fresh: List[Tuple[dict, int, str]] = []
        for o in plan.get("offen", []):
            fam = by_id.get(o["familie"])
            if focus_open and fam and fam["id"] not in focus:
                continue  # Schwerpunkt geht vor Angefangenem
            if fam and why[fam["id"]] and fam["id"] not in shut and o["stufe"] in _allowed(fam, board):
                items_before = len(items)
                add(fam, o["stufe"], "weiter", o["exercise_id"], o.get("board_id"))
                if len(items) > items_before:
                    break  # höchstens ein angefangenes vorne
        for t in sorted(scope.tests, key=lambda t: t.datum):
            in_test = [f for f in due if any(g.get("test_id") == t.id for g in why[f["id"]])]
            if t.phase == 3:
                fresh += [(f, _best_solved(f, progress, board), "generalprobe") for f in in_test
                          if _best_solved(f, progress, board) is not None]
            elif t.phase in (1, 2):
                fresh += [(f, _next_stage(f, progress, board), "neu" if not progress.get(f["id"], {}).get("geschafft") else "weiter")
                          for f in in_test]
        current = [f for f in due if any(g["art"] == "aktuell" for g in why[f["id"]])]
        fresh += [(f, _next_stage(f, progress, board), "neu" if not progress.get(f["id"], {}).get("geschafft") else "weiter")
                  for f in current]

        size = ROUND_SIZE["einstieg" if beginner else "gewohnheit"]
        queue = [(f, s, a) for f, s, a in fresh if s is not None and f["fach"] not in exam_day]

        def still_locked(fam: dict) -> bool:
            # Gesperrt bleibt nur, wer auch dann noch gesperrt wäre, wenn alles in dieser Runde schon geschafft
            # wäre: so öffnet der nächste Knoten in derselben Runde (Laborgeräte → Grundregeln → Brenner).
            if fam["id"] not in shut:
                return False
            planned = {**progress, **{i: {"geschafft": [0]} for i in used}}
            return fam["id"] in locked(due, planned)

        while len(items) < size and (queue or repeats):
            if len(items) == 1 and repeats:
                fam, r = repeats.pop(0)
                add(fam, r["stufe"], "wiederholen", r["exercise_id"])
            elif queue:
                fam, stage, art = queue.pop(0)
                if not still_locked(fam):
                    add(fam, stage, art)
            else:
                fam, r = repeats.pop(0)
                add(fam, r["stufe"], "wiederholen", r["exercise_id"])
        if not items and fach is not None:
            # Fachseite, nichts dran: Geschafftes auffrischen
            solved = sorted((f for f in families if _best_solved(f, progress, board) is not None),
                            key=lambda f: progress.get(f["id"], {}).get("zuletzt") or "")
            for f in solved[:size]:
                add(f, _best_solved(f, progress, board), "auffrischen")

    return {
        "runde": items,
        "einstieg": beginner,
        "akku": akku,
        "anzahl_dran": open_count,
        "dran": {f["id"]: {"gruende": why[f["id"]], "gesperrt": f["id"] in shut} for f in due},
    }


def collect(db, now: Optional[datetime] = None) -> Tuple[Scope, int]:
    """Aus der Datenbank: Tests, die heute im Lernplan dran sind (mit Phase), „gerade dran“ und die Zahl der
    Tage, an denen Thea schon etwas geschafft hat."""
    from backend.app.models.practice_attempt import PracticeAttempt
    from backend.app.models.study_scope import StudyScope
    from backend.app.models.taxonomy import Topic
    from backend.app.models.test import Test
    from backend.app.services.effort_xp import local_day
    from backend.app.services.planner import compute_plan_overview

    now = now or datetime.utcnow()
    today = local_day(now)
    scope = Scope()
    for task in compute_plan_overview(db, today).today_plan.tasks:
        test = db.get(Test, task.test_id)
        if test is None:
            continue
        scope.tests.append(DueTest(
            id=test.id, fach=test.subject_id, datum=test.date, tage=task.days_until_test, phase=task.phase_number,
            themen={tp.id for tp in test.topics},
            abschnitte=[(sc.material_id, sc.start_page, sc.end_page) for sc in test.sections]))
    scope.themen = {tp.id for tp in db.query(Topic).filter(Topic.current_since.isnot(None))}
    scope.abschnitte = [(sc.material_id, sc.start_page, sc.end_page)
                        for sc in db.query(StudyScope).filter(StudyScope.test_id.is_(None))]
    solved_days = len({local_day(a.solved_at) for a in db.query(PracticeAttempt).filter(PracticeAttempt.solved_at.isnot(None))})
    return scope, solved_days
