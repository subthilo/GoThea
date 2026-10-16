"""Versuche an Übungen festhalten – Grundlage für Lernstand, Übungsauswahl und später XP.

Ein Versuch = eine Übung auf einer Stufe. Stufe 0 beginnt beim Öffnen im Tab „Üben“, die Tafel-Stufen
haben genau einen Versuch pro Übungstafel (beim Wiederöffnen geht er weiter). Jedes Ereignis wird mit
Zeit gespeichert; die Zähler am Versuch fassen es zusammen. Gezählt wird, was Thea getan hat – was
daraus für XP folgt, entscheidet später die Auswertung (nur Einsatz, nie richtige Antworten).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.practice_attempt import PracticeAttempt, PracticeEvent
from backend.app.models.whiteboard import TutorSession
from backend.app.services.practice_check import NOCH_NICHT, RICHTIG, UNSICHER

EVENT_KINDS = ("guess", "hint", "solution", "check")
CHECK_STATUSES = (RICHTIG, NOCH_NICHT, UNSICHER)


def start(db: Session, ex: dict, stage: int) -> PracticeAttempt:
    attempt = PracticeAttempt(exercise_id=ex["id"], exercise_type=ex.get("typ"), stage=stage)
    db.add(attempt)
    db.commit()
    return attempt


def for_board(db: Session, ex: dict, board: TutorSession) -> PracticeAttempt:
    """Der Versuch einer Übungstafel; bei der ersten Nutzung angelegt (auch für ältere Tafeln)."""
    attempt = (db.query(PracticeAttempt)
               .filter(PracticeAttempt.board_id == board.id, PracticeAttempt.exercise_id == ex["id"])
               .order_by(PracticeAttempt.started_at.desc())
               .first())
    if attempt is not None:
        return attempt
    attempt = PracticeAttempt(exercise_id=ex["id"], exercise_type=ex.get("typ"),
                              stage=board.practice_stage or 1, board_id=board.id)
    db.add(attempt)
    db.commit()
    return attempt


def record(db: Session, attempt: PracticeAttempt, kind: str, data: Optional[dict] = None) -> PracticeAttempt:
    """Ereignis speichern und die Zähler nachziehen. Prüfungen brauchen data['status']."""
    if kind not in EVENT_KINDS:
        raise ValueError(f"Unbekanntes Ereignis '{kind}'")
    data = data or {}
    now = datetime.utcnow()
    if kind == "check":
        status = data.get("status")
        if status not in CHECK_STATUSES:
            raise ValueError(f"Unbekanntes Prüfergebnis '{status}'")
        attempt.checks += 1
        if status == NOCH_NICHT:
            attempt.failed_checks += 1
        if status == RICHTIG and attempt.solved_at is None:
            attempt.solved_at = now
            # Hilfe nach dem Lösen (Lösung zum Vergleich ansehen) zählt nicht mehr
            attempt.solved_first_try = (attempt.failed_checks == 0 and attempt.hints_used == 0
                                        and not attempt.solution_shown)
    elif kind == "hint":
        attempt.hints_used += 1
    elif kind == "solution":
        attempt.solution_shown = True
    elif kind == "guess":
        attempt.guess = str(data.get("value", ""))[:40] or None
    attempt.last_activity_at = now
    db.add(PracticeEvent(attempt_id=attempt.id, kind=kind, created_at=now,
                         data_json=json.dumps(data, ensure_ascii=False) if data else None))
    db.commit()
    return attempt


def summary(attempt: PracticeAttempt) -> dict:
    return {
        "id": attempt.id,
        "exercise_id": attempt.exercise_id,
        "stage": attempt.stage,
        "board_id": attempt.board_id,
        "started_at": attempt.started_at.isoformat(),
        "last_activity_at": attempt.last_activity_at.isoformat(),
        "solved": attempt.solved_at is not None,
        "solved_first_try": bool(attempt.solved_first_try),
        "checks": attempt.checks,
        "failed_checks": attempt.failed_checks,
        "hints_used": attempt.hints_used,
        "solution_shown": attempt.solution_shown,
    }


def progress(db: Session) -> Dict[str, Dict[int, dict]]:
    """Lernstand pro Übung und Stufe: Versuche, gelöst (wann zuerst; auf Anhieb = ohne Fehler, Tipp, Lösung), zuletzt geübt.

    Versuche ohne jede Aktivität (nur geöffnet) zählen nicht als Versuch.
    """
    out: Dict[str, Dict[int, dict]] = {}
    attempts: List[PracticeAttempt] = db.query(PracticeAttempt).order_by(PracticeAttempt.started_at).all()
    for a in attempts:
        if a.checks == 0 and a.hints_used == 0 and not a.solution_shown:
            continue
        s = out.setdefault(a.exercise_id, {}).setdefault(a.stage, {
            "attempts": 0, "solved": False, "solved_first_try": False, "first_solved_at": None,
            "last_at": None,
        })
        s["attempts"] += 1
        if a.solved_at is not None:
            s["solved"] = True
            if a.solved_first_try:
                s["solved_first_try"] = True
            first = a.solved_at.isoformat()
            if s["first_solved_at"] is None or first < s["first_solved_at"]:
                s["first_solved_at"] = first
        last = a.last_activity_at.isoformat()
        if s["last_at"] is None or last > s["last_at"]:
            s["last_at"] = last
    return out
