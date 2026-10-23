"""Was Thea als Nächstes üben könnte: Stand pro Aufgabe, Wiederholen und Lunas Vorschlag.

Stufen bringt jeder Übungstyp mit (``stufen`` der Aufgabe, von viel nach wenig Hilfe; bei der Mathe-
Sachaufgabe -1 Gedankengang, 0 Bausteine, 1–4 Tafel).
Eine Aufgabe = das Original (A) mit seinen Zwillingen (B); eine Stufe gilt als geschafft, wenn
irgendeine davon auf dieser Stufe gelöst wurde. Was „dran“ ist, kommt vorerst aus dem Vorrat selbst
(alle Übungen); das Markieren der Abschnitte durch die Eltern folgt mit dem Freigabe-Ablauf.

Vorschlag, in dieser Reihenfolge:
1. ein angefangener, noch nicht gelöster Versuch (zuletzt geübt zuerst),
2. Wiederholen, was gehakt hat und mindestens einen Tag zurückliegt (mit einer ähnlichen Aufgabe),
3. die nächste Stufe der zuletzt geübten Aufgabe,
4. eine neue Aufgabe (Reihenfolge des Vorrats), auf der leichtesten Stufe,
5. Wiederholen, auch wenn es frisch ist.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from backend.app.models.practice_attempt import PracticeAttempt

REPEAT_AFTER = timedelta(hours=20)  # „am nächsten Tag“, auch wenn abends geübt wurde


def _active(a: PracticeAttempt) -> bool:
    return a.checks > 0 or a.hints_used > 0 or a.solution_shown


def _troubled(a: PracticeAttempt) -> bool:
    """Hat gehakt: Fehler, Tipp, Lösung angesehen (vor dem Lösen) oder nicht zu Ende gebracht."""
    if a.solved_at is not None:
        return not a.solved_first_try
    return _active(a)


def plan(families: List[dict], attempts: List[PracticeAttempt], now: Optional[datetime] = None,
         open_boards: Optional[set] = None) -> dict:
    """families: Originale wie ``practice_exercises.list_exercises()`` (mit ``zwillinge`` und ``stufen``).

    open_boards: Tafeln, die es noch gibt (nur dorthin wird zum Weiterschreiben verwiesen).
    """
    now = now or datetime.utcnow()
    open_boards = open_boards or set()
    family_of: Dict[str, str] = {}
    for fam in families:
        for ex_id in [fam["id"], *fam["zwillinge"]]:
            family_of[ex_id] = fam["id"]

    by_family: Dict[str, List[PracticeAttempt]] = {}
    for a in sorted(attempts, key=lambda a: a.last_activity_at):
        if a.exercise_id in family_of and _active(a):
            by_family.setdefault(family_of[a.exercise_id], []).append(a)

    progress: Dict[str, dict] = {}
    repeats: List[dict] = []
    open_attempts: List[PracticeAttempt] = []
    for fam in families:
        own = by_family.get(fam["id"], [])
        solved = sorted({a.stage for a in own if a.solved_at is not None})
        higher = [s for s in fam["stufen"] if not solved or s > solved[-1]]
        progress[fam["id"]] = {
            "geschafft": solved,
            "naechste_stufe": higher[0] if higher else None,
            "zuletzt": own[-1].last_activity_at.isoformat() if own else None,
        }
        # Offen: zuletzt aktiver Versuch je Stufe, der nicht gelöst ist und nach dem nichts gelöst wurde
        for stage in {a.stage for a in own}:
            latest = [a for a in own if a.stage == stage][-1]
            if latest.solved_at is None and stage not in solved:
                open_attempts.append(latest)
        # Wiederholen: die letzte Stufe, auf der es gehakt hat – erledigt, sobald danach auf dieser
        # oder einer höheren Stufe etwas auf Anhieb gelang
        trouble = None
        for a in own:
            if _troubled(a):
                trouble = a
            elif trouble is not None and a.solved_first_try and a.stage >= trouble.stage:
                trouble = None
        if trouble is not None:
            members = [fam["id"], *fam["zwillinge"]]
            used = {m: sum(1 for a in own if a.exercise_id == m and a.stage == trouble.stage) for m in members}
            repeats.append({
                "familie": fam["id"],
                "exercise_id": min(members, key=lambda m: (used[m], members.index(m))),
                "stufe": trouble.stage,
                "seit": trouble.last_activity_at.isoformat(),
                "_at": trouble.last_activity_at,
            })

    suggestion = None
    if open_attempts:
        a = max(open_attempts, key=lambda a: a.last_activity_at)
        suggestion = {"art": "weiter", "familie": family_of[a.exercise_id], "exercise_id": a.exercise_id,
                      "stufe": a.stage, "board_id": a.board_id if a.board_id in open_boards else None}
    if suggestion is None:
        due = [r for r in repeats if now - r["_at"] >= REPEAT_AFTER]
        if due:
            r = min(due, key=lambda r: r["_at"])
            suggestion = {"art": "wiederholen", "familie": r["familie"], "exercise_id": r["exercise_id"],
                          "stufe": r["stufe"], "board_id": None}
    if suggestion is None:
        recent = [f for f in families if progress[f["id"]]["zuletzt"] and progress[f["id"]]["naechste_stufe"] is not None]
        if recent:
            f = max(recent, key=lambda f: progress[f["id"]]["zuletzt"])
            suggestion = {"art": "weiter", "familie": f["id"], "exercise_id": f["id"],
                          "stufe": progress[f["id"]]["naechste_stufe"], "board_id": None}
    if suggestion is None:
        fresh = [f for f in families if progress[f["id"]]["zuletzt"] is None]
        if fresh:
            suggestion = {"art": "neu", "familie": fresh[0]["id"], "exercise_id": fresh[0]["id"],
                          "stufe": fresh[0]["stufen"][0], "board_id": None}
    if suggestion is None and repeats:
        r = min(repeats, key=lambda r: r["_at"])
        suggestion = {"art": "wiederholen", "familie": r["familie"], "exercise_id": r["exercise_id"],
                      "stufe": r["stufe"], "board_id": None}

    return {
        "stand": progress,
        "wiederholen": [{k: v for k, v in r.items() if k != "_at"} for r in sorted(repeats, key=lambda r: r["_at"])],
        "vorschlag": suggestion,
    }
