"""XP nur für Einsatz, nie für richtige Antworten (Konzept-Doc „Einsatz, Level und Streaks“, abgestimmt 18.10.2026).

Die XP werden nicht gespeichert, sondern bei jedem Aufruf aus den Übungsversuchen berechnet
(services/practice_attempts.py). So lassen sich die Zahlen nachstellen, ohne Altdaten umzurechnen.

Wofür es Punkte gibt (je Versuch):
- ernsthaft versucht (mindestens eine Prüfung)                10
- nach „noch nicht“ erneut geprüft (Fehler korrigiert, max. 3)  +5 je Mal
- Tipp oder Lösung genutzt (max. 2)                             +2 je Mal
- Stufe dieser Aufgabe zum ersten Mal gewagt                    +5
- aus „Wiederholen“ geübt (es hatte dort gehakt)                +5
- zu Ende gebracht (gelöst, egal mit wie viel Hilfe)            +5
- erster ernsthafter Versuch des Tages                         +10
Schutz gegen Abgrasen: dieselbe Übung auf derselben Stufe zählt pro Tag nur zweimal.
Ein Versuch gehört zu dem Tag, an dem er zum ersten Mal geprüft wurde (Ortszeit Berlin).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.app.models.practice_attempt import PracticeAttempt
from backend.app.services import practice_exercises
from backend.app.services.practice_check import NOCH_NICHT

LOCAL_TZ = ZoneInfo("Europe/Berlin")

XP_TRIED = 10
XP_RECHECK, MAX_RECHECKS = 5, 3
XP_HELP, MAX_HELPS = 2, 2
XP_NEW_STAGE = 5
XP_REPEAT = 5
XP_FINISHED = 5
XP_FIRST_OF_DAY = 10
MAX_COUNTED_PER_DAY = 2  # je Übung und Stufe


def local_day(moment: datetime) -> date:
    """UTC-Zeitpunkt aus der Datenbank → Kalendertag in Berlin."""
    return moment.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()


def _checks(a: PracticeAttempt) -> List[dict]:
    out = []
    for ev in a.events:
        if ev.kind == "check":
            data = json.loads(ev.data_json) if ev.data_json else {}
            out.append({"at": ev.created_at, "status": data.get("status")})
    return out


def _troubled(a: PracticeAttempt, checks: List[dict]) -> bool:
    if a.solved_at is not None:
        return not a.solved_first_try
    return bool(checks) or a.hints_used > 0 or a.solution_shown


def awards(attempts: List[PracticeAttempt], family_of: Optional[Dict[str, str]] = None) -> List[dict]:
    """Punkte je ernsthaftem Versuch, zeitlich geordnet: {attempt_id, tag, xp, teile, geloest, drangeblieben}."""
    family_of = family_of or {}
    rows = []
    for a in attempts:
        checks = _checks(a)
        if checks:
            rows.append((checks[0]["at"], a, checks))
    rows.sort(key=lambda r: r[0])

    stages_tried: set = set()            # (Familie, Stufe)
    open_trouble: Dict[str, int] = {}    # Familie → Stufe, auf der es zuletzt gehakt hat
    counted: Dict[tuple, int] = defaultdict(int)
    days_with_xp: set = set()
    out = []
    for first_at, a, checks in rows:
        fam = family_of.get(a.exercise_id, a.exercise_id)
        day = local_day(first_at)
        parts: Dict[str, int] = {}
        rechecks = sum(1 for prev, _ in zip(checks, checks[1:]) if prev["status"] == NOCH_NICHT)

        key = (a.exercise_id, a.stage, day)
        counted[key] += 1
        if counted[key] <= MAX_COUNTED_PER_DAY:
            parts["versucht"] = XP_TRIED
            if rechecks:
                parts["dranbleiben"] = XP_RECHECK * min(rechecks, MAX_RECHECKS)
            helps = a.hints_used + (1 if a.solution_shown else 0)
            if helps:
                parts["hilfe"] = XP_HELP * min(helps, MAX_HELPS)
            if (fam, a.stage) not in stages_tried:
                parts["neue_stufe"] = XP_NEW_STAGE
            if open_trouble.get(fam) == a.stage:
                parts["wiederholt"] = XP_REPEAT
            if a.solved_at is not None:
                parts["zu_ende"] = XP_FINISHED
            if day not in days_with_xp:
                parts["erster_des_tages"] = XP_FIRST_OF_DAY
                days_with_xp.add(day)

        # Stand fortschreiben (auch für Versuche, die heute nichts mehr bringen)
        stages_tried.add((fam, a.stage))
        if _troubled(a, checks):
            open_trouble[fam] = a.stage
        elif a.solved_first_try and fam in open_trouble and a.stage >= open_trouble[fam]:
            del open_trouble[fam]

        out.append({
            "attempt_id": a.id,
            "tag": day.isoformat(),
            "xp": sum(parts.values()),
            "teile": parts,
            "geloest": a.solved_at is not None,
            "drangeblieben": rechecks > 0,
        })
    return out


def streak_days(days: List[date], today: date) -> int:
    """Übungstage in Folge; ein einzelner verpasster Tag unterbricht die Serie nicht."""
    if not days:
        return 0
    ordered = sorted(set(days), reverse=True)
    if (today - ordered[0]).days > 2:
        return 0
    streak = 1
    for newer, older in zip(ordered, ordered[1:]):
        if (newer - older).days > 2:
            break
        streak += 1
    return streak


def summary(db: Session, now: Optional[datetime] = None) -> dict:
    """Gesamt-XP, heute, Streak, Zähler für Auszeichnungen."""
    family_of = {}
    for fam in practice_exercises.list_exercises():
        for ex_id in [fam["id"], *fam["zwillinge"]]:
            family_of[ex_id] = fam["id"]
    rows = awards(db.query(PracticeAttempt).all(), family_of)
    today = local_day(now or datetime.utcnow())
    today_rows = [r for r in rows if r["tag"] == today.isoformat()]
    days = [date.fromisoformat(r["tag"]) for r in rows]
    return {
        "total_xp": sum(r["xp"] for r in rows),
        "today_xp": sum(r["xp"] for r in today_rows),
        "today_attempts": len(today_rows),
        "attempts": len(rows),
        "finished": sum(1 for r in rows if r["geloest"]),
        "today_finished": sum(1 for r in today_rows if r["geloest"]),
        "persisted": sum(1 for r in rows if r["drangeblieben"]),
        "streak_days": streak_days(days, today),
        "last_day": max(days).isoformat() if days else None,
    }
