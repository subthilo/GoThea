"""
Übersetzt einen KI-erkannten Wochenplan (Untis-Raster) in TimetableSlot-Einträge.
"""
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.taxonomy import Subject
from backend.app.models.timetable import TimetableSlot
from backend.app.schemas.timetable import PeriodMeta

PERIODS_CONFIG = [
    PeriodMeta(period=1, label="1. Std", start_time="07:45", end_time="08:30", is_break=False),
    PeriodMeta(period=2, label="2. Std", start_time="08:30", end_time="09:15", is_break=False),
    PeriodMeta(period=3, label="3. Std", start_time="09:45", end_time="10:30", is_break=False),
    PeriodMeta(period=4, label="4. Std", start_time="10:30", end_time="11:15", is_break=False),
    PeriodMeta(period=5, label="5. Std", start_time="11:25", end_time="12:10", is_break=False),
    PeriodMeta(period=6, label="6.1 Std", start_time="12:15", end_time="13:00", is_break=False),
    PeriodMeta(period=7, label="6.2 Std", start_time="13:05", end_time="13:50", is_break=False),
    PeriodMeta(period=8, label="7. Std", start_time="13:55", end_time="14:40", is_break=False),
    PeriodMeta(period=9, label="8. Std", start_time="14:40", end_time="15:25", is_break=False),
]

# Untis-Zeilenbeschriftung -> interne Periode (6. Stunde ist in 6.1 und 6.2 geteilt)
UNTIS_ROW_TO_PERIOD: Dict[str, int] = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
    "6": 6, "6.1": 6, "6.2": 7, "7": 8, "8": 9,
}

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]

BREAK_NAMES = {
    "mittag": "Mittagspause",
    "gt-mittag": "Ganztags-Mittag",
}


def parse_period(raw: Any) -> Optional[int]:
    label = str(raw or "").strip().rstrip(".").replace(",", ".")
    label = re.sub(r"\s*(std|stunde)\.?$", "", label, flags=re.I).strip().rstrip(".")
    return UNTIS_ROW_TO_PERIOD.get(label)


def parse_week(raw: Any) -> str:
    w = re.sub(r"[^a-z]", "", str(raw or "").lower())
    if w in ("a", "awoche", "wochea"):
        return "A"
    if w in ("b", "bwoche", "wocheb"):
        return "B"
    return "both"


def _break_name(entry: Dict[str, Any]) -> Optional[str]:
    if entry.get("pause"):
        key = re.sub(r"^[\*\s]+", "", str(entry.get("kuerzel") or entry.get("fach") or "")).lower()
        return BREAK_NAMES.get(key, "Pause")
    for field in ("kuerzel", "fach"):
        key = re.sub(r"^[\*\s]+", "", str(entry.get(field) or "")).lower()
        if key in BREAK_NAMES:
            return BREAK_NAMES[key]
    return None


def _join_distinct(values: List[Optional[str]]) -> Optional[str]:
    seen: List[str] = []
    for v in values:
        v = (v or "").strip()
        if v and v not in seen:
            seen.append(v)
    return " / ".join(seen) or None


def build_slot_specs(wochenplan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Wandelt den 'wochenplan' der KI-Analyse in Slot-Spezifikationen um:
    - eine Spezifikation je Tag, Periode und Woche (A/B/both)
    - parallele Kurse derselben Stunde (z. B. LER / Religion) werden zusammengeführt
    - aufeinanderfolgende gleiche Stunden werden als Doppelstunde markiert
    """
    from backend.app.services.timetable_analyzer import match_subject_to_canonical

    parsed = []
    for day in WEEKDAYS:
        for entry in (wochenplan or {}).get(day) or []:
            if not isinstance(entry, dict):
                continue
            period = parse_period(entry.get("stunde"))
            if period is None:
                continue
            parsed.append((day, period, parse_week(entry.get("woche")), entry))

    # Eine A- oder B-Stunde ohne Gegenstück in der anderen Woche gilt für beide Wochen
    # (z. B. wenn die KI den Aufdruck "A Woche" auf den ganzen Plan überträgt)
    weeks_at: Dict[tuple, set] = {}
    for day, period, week, _ in parsed:
        weeks_at.setdefault((day, period), set()).add(week)

    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for day, period, week, entry in parsed:
        if week != "both" and weeks_at[(day, period)] == {week}:
            week = "both"
        grouped.setdefault((day, period, week), []).append(entry)

    specs: List[Dict[str, Any]] = []
    for (day, period, week), entries in grouped.items():
        break_name = _break_name(entries[0])
        if break_name:
            specs.append({
                "day": day, "period": period, "week": week, "is_break": True,
                "sub_id": None, "code": (entries[0].get("kuerzel") or entries[0].get("fach") or "").strip() or None,
                "name": break_name, "teacher": None, "room": None, "double": False, "note": None,
            })
            continue

        canon = [match_subject_to_canonical(e.get("fach") or "") or match_subject_to_canonical(e.get("kuerzel") or "") for e in entries]
        names = [c["name"] if c else (e.get("fach") or e.get("kuerzel") or "").strip() for c, e in zip(canon, entries)]
        specs.append({
            "day": day, "period": period, "week": week, "is_break": False,
            "sub_id": canon[0]["id"] if canon[0] else None,
            "canonical_name": canon[0]["name"] if canon[0] else None,
            "code": _join_distinct([e.get("kuerzel") for e in entries]),
            "name": _join_distinct(names) or "Unterricht",
            "teacher": _join_distinct([e.get("lehrer") for e in entries]),
            "room": _join_distinct([e.get("raum") for e in entries]),
            "double": False,
            "note": "Parallele Kurse: " + " oder ".join(names) if len(entries) > 1 else None,
        })

    # Doppelstunden: gleiche Stunde direkt danach (gleicher Tag, gleiche Woche)
    index = {(s["day"], s["period"], s["week"]): s for s in specs}
    for s in specs:
        nxt = index.get((s["day"], s["period"] + 1, s["week"]))
        if nxt and not s["is_break"] and not nxt["is_break"] and \
           (s["name"], s["teacher"], s["room"]) == (nxt["name"], nxt["teacher"], nxt["room"]):
            s["double"] = True
            nxt["double"] = True

    specs.sort(key=lambda s: (WEEKDAYS.index(s["day"]), s["period"], s["week"]))
    return specs


def insert_timetable_slots(db: Session, slot_specs: List[Dict[str, Any]], user_id: str = "usr_thea") -> int:
    """Legt TimetableSlots aus Slot-Spezifikationen an (ohne Commit)."""
    subjects_by_id = {s.id: s for s in db.query(Subject).all()}
    subjects_by_name = {s.name.lower(): s for s in subjects_by_id.values()}
    periods_by_num = {p.period: p for p in PERIODS_CONFIG}

    for item in slot_specs:
        p_meta = periods_by_num.get(item["period"])
        sub = None
        if not item.get("is_break"):
            sub = subjects_by_id.get(item.get("sub_id")) or \
                  subjects_by_name.get((item.get("canonical_name") or item.get("name") or "").lower())

        db.add(TimetableSlot(
            id=f"slot_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            day_of_week=item["day"],
            period=item["period"],
            period_label=p_meta.label if p_meta else f"{item['period']}. Std",
            start_time=p_meta.start_time if p_meta else None,
            end_time=p_meta.end_time if p_meta else None,
            subject_id=sub.id if sub else None,
            subject_code=item.get("code"),
            subject_name=item.get("name") or (sub.name if sub else "Allgemein"),
            custom_title=item.get("code") if item.get("is_break") else None,
            teacher=item.get("teacher"),
            room=item.get("room"),
            week_type=item.get("week", "both"),
            is_double_period=item.get("double", False),
            is_break=item.get("is_break", False),
            note=item.get("note"),
        ))
    return len(slot_specs)


def replace_timetable_slots(db: Session, slot_specs: List[Dict[str, Any]], user_id: str = "usr_thea") -> int:
    """Ersetzt den kompletten Stundenplan, sofern mindestens eine Unterrichtsstunde erkannt wurde."""
    if not any(not s.get("is_break") for s in slot_specs):
        return 0
    db.query(TimetableSlot).filter_by(user_id=user_id).delete()
    count = insert_timetable_slots(db, slot_specs, user_id=user_id)
    db.commit()
    return count


def describe_week_differences(slots: List[TimetableSlot]) -> List[str]:
    """Beschreibt Stunden, die sich zwischen A- und B-Woche unterscheiden."""
    labels = {p.period: p.label.replace(" Std", "") for p in PERIODS_CONFIG}
    by_key: Dict[tuple, Dict[str, List[TimetableSlot]]] = {}
    for s in slots:
        if s.week_type in ("A", "B"):
            by_key.setdefault((s.day_of_week, s.subject_name), {}).setdefault(s.week_type, []).append(s)

    differences: List[str] = []
    seen_periods = set()
    for (day, _), weeks in by_key.items():
        for week, items in weeks.items():
            periods = tuple(sorted(i.period for i in items))
            if (day, periods) in seen_periods:
                continue
            seen_periods.add((day, periods))
            a = [s for s in slots if s.day_of_week == day and s.period in periods and s.week_type == "A"]
            b = [s for s in slots if s.day_of_week == day and s.period in periods and s.week_type == "B"]
            period_text = "/".join(labels.get(p, str(p)) for p in periods)
            a_text = a[0].subject_name if a else "frei"
            b_text = b[0].subject_name if b else "frei"
            differences.append(f"{day} {period_text} Std: A-Woche {a_text}, B-Woche {b_text}.")
    days_order = {d: i for i, d in enumerate(WEEKDAYS)}
    return sorted(differences, key=lambda t: days_order.get(t.split(" ")[0], 9))
