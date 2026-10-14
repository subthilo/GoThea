import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.timetable import TimetableSlot
from backend.app.models.taxonomy import Subject
from backend.app.models.material import Material
from backend.app.services.parent_auth import require_parent
from backend.app.schemas.timetable import (
    TimetableOverviewResponse,
    TimetableSlotRead,
    TimetableSlotCreateUpdate,
    PeriodMeta,
)

router = APIRouter(prefix="/api/v1/timetable", tags=["Stundenplan"])

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

def get_initial_thea_slots_data() -> List[Dict[str, Any]]:
    """Definiert Theas offiziellen Stundenplan (Klasse 7D, Humboldt-Gymnasium Eichwalde)."""
    return [
        # --- MONTAG ---
        {"day": "Montag", "period": 1, "sub_id": "sub_german", "code": "D", "name": "Deutsch", "teacher": "DÜCK", "room": "201", "week": "both", "double": True},
        {"day": "Montag", "period": 2, "sub_id": "sub_german", "code": "D", "name": "Deutsch", "teacher": "DÜCK", "room": "201", "week": "both", "double": True},
        {"day": "Montag", "period": 3, "sub_id": "sub_math", "code": "Ma", "name": "Mathematik", "teacher": "HORN", "room": "303", "week": "both", "double": True},
        {"day": "Montag", "period": 4, "sub_id": "sub_math", "code": "Ma", "name": "Mathematik", "teacher": "HORN", "room": "303", "week": "both", "double": True},
        # Wechselstunde Montag 5. & 6.1:
        {"day": "Montag", "period": 5, "sub_id": "sub_sport", "code": "*Sp", "name": "Sport", "teacher": "DÜCK", "room": "gewo", "week": "A", "double": True, "note": "Sport in A-Woche"},
        {"day": "Montag", "period": 6, "sub_id": "sub_sport", "code": "*Sp", "name": "Sport", "teacher": "DÜCK", "room": "gewo", "week": "A", "double": True, "note": "Sport in A-Woche"},
        {"day": "Montag", "period": 5, "sub_id": "sub_english", "code": "En", "name": "Englisch", "teacher": "SCHD", "room": "104", "week": "B", "double": True, "note": "Englisch in B-Woche (En(B))"},
        {"day": "Montag", "period": 6, "sub_id": "sub_english", "code": "En", "name": "Englisch", "teacher": "SCHD", "room": "104", "week": "B", "double": True, "note": "Englisch in B-Woche (En(B))"},
        {"day": "Montag", "period": 7, "sub_id": None, "code": "*Mittag", "name": "Mittagspause", "teacher": None, "room": "Mensa", "week": "both", "is_break": True},
        {"day": "Montag", "period": 8, "sub_id": "sub_wat", "code": "WAT", "name": "WAT / Wirtschaft", "teacher": "BIEL", "room": "105", "week": "both", "double": True},
        {"day": "Montag", "period": 9, "sub_id": "sub_wat", "code": "WAT", "name": "WAT / Wirtschaft", "teacher": "BIEL", "room": "105", "week": "both", "double": True},

        # --- DIENSTAG ---
        {"day": "Dienstag", "period": 1, "sub_id": "sub_bio", "code": "Bio", "name": "Biologie", "teacher": "DEWI", "room": "207", "week": "both", "double": True},
        {"day": "Dienstag", "period": 2, "sub_id": "sub_bio", "code": "Bio", "name": "Biologie", "teacher": "DEWI", "room": "207", "week": "both", "double": True},
        {"day": "Dienstag", "period": 3, "sub_id": "sub_franzoesisch", "code": "Fr", "name": "Französisch", "teacher": "PAYS", "room": "203", "week": "both", "double": True},
        {"day": "Dienstag", "period": 4, "sub_id": "sub_franzoesisch", "code": "Fr", "name": "Französisch", "teacher": "PAYS", "room": "203", "week": "both", "double": True},
        {"day": "Dienstag", "period": 5, "sub_id": None, "code": "*GT-Mittag", "name": "Ganztags-Mittag", "teacher": None, "room": "Schulhof / Mensa", "week": "both", "is_break": True},
        {"day": "Dienstag", "period": 6, "sub_id": None, "code": "*GT-Mittag", "name": "Ganztags-Mittag", "teacher": None, "room": "Schulhof / Mensa", "week": "both", "is_break": True},
        {"day": "Dienstag", "period": 7, "sub_id": "sub_pb", "code": "PB", "name": "Politische Bildung", "teacher": "LAUT", "room": "315", "week": "both"},
        {"day": "Dienstag", "period": 8, "sub_id": "sub_ler", "code": "LER", "name": "LER / Religion", "teacher": "EISE / SCHN", "room": "007 / 302", "week": "both", "double": True, "note": "LER (R 007) oder Religion (R 302)"},
        {"day": "Dienstag", "period": 9, "sub_id": "sub_ler", "code": "LER", "name": "LER / Religion", "teacher": "EISE / SCHN", "room": "007 / 302", "week": "both", "double": True},

        # --- MITTWOCH ---
        {"day": "Mittwoch", "period": 1, "sub_id": "sub_physics", "code": "Ph", "name": "Physik", "teacher": "BIEL", "room": "106", "week": "both", "double": True},
        {"day": "Mittwoch", "period": 2, "sub_id": "sub_physics", "code": "Ph", "name": "Physik", "teacher": "BIEL", "room": "106", "week": "both", "double": True},
        {"day": "Mittwoch", "period": 3, "sub_id": "sub_german", "code": "D", "name": "Deutsch", "teacher": "DÜCK", "room": "201", "week": "both", "double": True},
        {"day": "Mittwoch", "period": 4, "sub_id": "sub_german", "code": "D", "name": "Deutsch", "teacher": "DÜCK", "room": "201", "week": "both", "double": True},
        {"day": "Mittwoch", "period": 5, "sub_id": "sub_english", "code": "En", "name": "Englisch", "teacher": "SCHD", "room": "104", "week": "both"},
        {"day": "Mittwoch", "period": 6, "sub_id": None, "code": "*Mittag", "name": "Mittagspause", "teacher": None, "room": "Mensa", "week": "both", "is_break": True},
        {"day": "Mittwoch", "period": 7, "sub_id": "sub_geo", "code": "Geo", "name": "Geografie", "teacher": "SCHÖ", "room": "101", "week": "both"},

        # --- DONNERSTAG ---
        {"day": "Donnerstag", "period": 1, "sub_id": "sub_english", "code": "En", "name": "Englisch", "teacher": "SCHD", "room": "104", "week": "both", "double": True},
        {"day": "Donnerstag", "period": 2, "sub_id": "sub_english", "code": "En", "name": "Englisch", "teacher": "SCHD", "room": "104", "week": "both", "double": True},
        {"day": "Donnerstag", "period": 3, "sub_id": "sub_sport", "code": "*Sp", "name": "Sport", "teacher": "DÜCK", "room": "gewo", "week": "both", "double": True},
        {"day": "Donnerstag", "period": 4, "sub_id": "sub_sport", "code": "*Sp", "name": "Sport", "teacher": "DÜCK", "room": "gewo", "week": "both", "double": True},
        {"day": "Donnerstag", "period": 5, "sub_id": "sub_chemie", "code": "Ch", "name": "Chemie", "teacher": "SCHW", "room": "210", "week": "both"},
        {"day": "Donnerstag", "period": 6, "sub_id": None, "code": "*Mittag", "name": "Mittagspause", "teacher": None, "room": "Mensa", "week": "both", "is_break": True},
        {"day": "Donnerstag", "period": 7, "sub_id": "sub_musik", "code": "Mu", "name": "Musik", "teacher": "ERDM", "room": "N1.2", "week": "both"},

        # --- FREITAG ---
        {"day": "Freitag", "period": 1, "sub_id": "sub_history", "code": "Ge", "name": "Geschichte", "teacher": "DÜCK", "room": "102", "week": "both"},
        {"day": "Freitag", "period": 2, "sub_id": "sub_musik", "code": "Mu", "name": "Musik", "teacher": "ERDM", "room": "N1.2", "week": "both"},
        {"day": "Freitag", "period": 3, "sub_id": "sub_franzoesisch", "code": "Fr", "name": "Französisch", "teacher": "PAYS", "room": "203", "week": "both", "double": True},
        {"day": "Freitag", "period": 4, "sub_id": "sub_franzoesisch", "code": "Fr", "name": "Französisch", "teacher": "PAYS", "room": "203", "week": "both", "double": True},
        {"day": "Freitag", "period": 5, "sub_id": "sub_math", "code": "Ma", "name": "Mathematik", "teacher": "HORN", "room": "303", "week": "both", "double": True},
        {"day": "Freitag", "period": 6, "sub_id": "sub_math", "code": "Ma", "name": "Mathematik", "teacher": "HORN", "room": "303", "week": "both", "double": True},
        {"day": "Freitag", "period": 7, "sub_id": None, "code": "*Mittag", "name": "Mittagspause", "teacher": None, "room": "Mensa", "week": "both", "is_break": True},
    ]

def seed_timetable_slots_if_empty(db: Session, user_id: str = "usr_thea"):
    """Befüllt die timetable_slots Tabelle mit Theas Stundenplan, falls noch keine Slots existieren."""
    count = db.query(TimetableSlot).filter_by(user_id=user_id).count()
    if count > 0:
        return

    slots_data = get_initial_thea_slots_data()

    # Fehlende Fächer synchronisieren, damit Fremdschlüssel gültig sind
    try:
        from backend.app.services.timetable_analyzer import sync_subjects_to_database
        needed_names = [item["name"] for item in slots_data if not item.get("is_break")]
        sync_subjects_to_database(db, needed_names)
    except Exception:
        pass

    # Fächer vorbereiten
    subjects_by_id = {s.id: s for s in db.query(Subject).all()}
    subjects_by_name = {s.name.lower(): s for s in db.query(Subject).all()}
    periods_by_num = {p.period: p for p in PERIODS_CONFIG}

    for item in slots_data:
        p_meta = periods_by_num.get(item["period"])
        sub = subjects_by_id.get(item.get("sub_id")) or subjects_by_name.get((item.get("name") or "").lower())
        valid_sub_id = sub.id if sub else None

        slot = TimetableSlot(
            id=f"slot_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            day_of_week=item["day"],
            period=item["period"],
            period_label=p_meta.label if p_meta else f"{item['period']}. Std",
            start_time=p_meta.start_time if p_meta else None,
            end_time=p_meta.end_time if p_meta else None,
            subject_id=valid_sub_id,
            subject_code=item.get("code"),
            subject_name=item.get("name") or (sub.name if sub else "Allgemein"),
            custom_title=item.get("code") if item.get("is_break") else None,
            teacher=item.get("teacher"),
            room=item.get("room"),
            week_type=item.get("week", "both"),
            is_double_period=item.get("double", False),
            is_break=item.get("is_break", False),
            note=item.get("note")
        )
        db.add(slot)
    db.commit()


@router.get("", response_model=TimetableOverviewResponse)
def get_timetable(
    week_type: Optional[str] = None,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Liefert den vollständigen, strukturierten Wochen-Stundenplan mit
    A-/B-Wochen-Support, Raum-, Lehrer- und Fachzuordnung.
    """
    # Aktuelle Kalenderwoche ermitteln: ungerade = A-Woche, gerade = B-Woche
    current_calendar_week = datetime.now().isocalendar()[1]
    calculated_week_type = "A" if (current_calendar_week % 2 != 0) else "B"
    active_week = week_type.upper() if week_type in ("A", "B", "a", "b") else calculated_week_type

    # Original-Scan ermitteln
    scan_material = db.query(Material).filter(
        (Material.kind == "Stundenplan") | (Material.title.ilike("%stundenplan%"))
    ).order_by(Material.created_at.desc()).first()

    scan_mat_id = scan_material.id if scan_material else None
    scan_mat_title = scan_material.title if scan_material else None

    # Alle Slots laden
    slots_db = db.query(TimetableSlot).filter_by(user_id=user_id).all()
    subjects_map = {s.id: s for s in db.query(Subject).all()}

    output_slots: List[TimetableSlotRead] = []
    for slot in slots_db:
        sub = subjects_map.get(slot.subject_id) if slot.subject_id else None
        output_slots.append(
            TimetableSlotRead(
                id=slot.id,
                day_of_week=slot.day_of_week,
                period=slot.period,
                period_label=slot.period_label,
                start_time=slot.start_time,
                end_time=slot.end_time,
                subject_id=slot.subject_id,
                subject_code=slot.subject_code,
                subject_name=slot.subject_name,
                subject_icon=sub.icon if sub else ("🥪" if slot.is_break else "📚"),
                subject_color=sub.color_code if sub else ("#64748b" if slot.is_break else "#6366f1"),
                custom_title=slot.custom_title,
                teacher=slot.teacher,
                room=slot.room,
                week_type=slot.week_type,
                is_double_period=slot.is_double_period,
                is_break=slot.is_break,
                note=slot.note,
            )
        )

    return TimetableOverviewResponse(
        school_name="Humboldt-Gymnasium Eichwalde",
        class_name="Klasse 7D",
        school_year="2026/2027",
        current_week_type=active_week,
        scan_material_id=scan_mat_id,
        scan_material_title=scan_mat_title,
        periods=PERIODS_CONFIG,
        slots=output_slots,
        week_differences=[
            "Montag 5./6.1 Std: In A-Woche Sport (Halle gewo, Fr. DÜCK), in B-Woche Englisch (Raum 104, Fr. SCHD)."
        ]
    )


@router.get("/today")
def get_today_timetable(
    week_type: Optional[str] = None,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Liefert den Tagesplan für den heutigen Wochentag (oder Montag, falls Wochenende).
    """
    weekdays_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    today_idx = datetime.now().weekday()
    current_day = weekdays_de[today_idx] if today_idx < 5 else "Montag"
    is_weekend = today_idx >= 5

    current_calendar_week = datetime.now().isocalendar()[1]
    calculated_week_type = "A" if (current_calendar_week % 2 != 0) else "B"
    active_week = week_type.upper() if week_type in ("A", "B", "a", "b") else calculated_week_type

    slots_db = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.user_id == user_id,
            TimetableSlot.day_of_week == current_day,
            TimetableSlot.week_type.in_(["both", active_week])
        )
        .order_by(TimetableSlot.period)
        .all()
    )

    subjects_map = {s.id: s for s in db.query(Subject).all()}
    output = []
    for slot in slots_db:
        sub = subjects_map.get(slot.subject_id) if slot.subject_id else None
        output.append({
            "id": slot.id,
            "period": slot.period,
            "period_label": slot.period_label,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "subject_id": slot.subject_id,
            "subject_name": slot.subject_name,
            "subject_code": slot.subject_code,
            "subject_icon": sub.icon if sub else ("🥪" if slot.is_break else "📚"),
            "subject_color": sub.color_code if sub else ("#64748b" if slot.is_break else "#6366f1"),
            "teacher": slot.teacher,
            "room": slot.room,
            "is_break": slot.is_break,
            "note": slot.note
        })

    return {
        "day": current_day,
        "is_weekend": is_weekend,
        "active_week": active_week,
        "slots_count": len([s for s in output if not s.get("is_break")]),
        "lessons": output
    }


@router.post("/reset", dependencies=[Depends(require_parent)])
def reset_timetable_to_default(
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """Setzt den Stundenplan auf Theas Standardplan (Klasse 7D) zurück."""
    db.query(TimetableSlot).filter_by(user_id=user_id).delete()
    db.commit()
    seed_timetable_slots_if_empty(db, user_id=user_id)
    return {"status": "success", "message": "Stundenplan erfolgreich auf Werkseinstellungen (Klasse 7D) zurückgesetzt."}


@router.post("/slot", response_model=TimetableSlotRead, status_code=201, dependencies=[Depends(require_parent)])
def create_timetable_slot(
    slot_in: TimetableSlotCreateUpdate,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """Fügt eine neue Unterrichtsstunde zum Stundenplan hinzu."""
    sub = db.query(Subject).filter_by(id=slot_in.subject_id).first() if slot_in.subject_id else None
    new_slot = TimetableSlot(
        id=f"slot_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        day_of_week=slot_in.day_of_week,
        period=slot_in.period,
        period_label=slot_in.period_label or f"{slot_in.period}. Std",
        start_time=slot_in.start_time,
        end_time=slot_in.end_time,
        subject_id=sub.id if sub else None,
        subject_code=slot_in.subject_code,
        subject_name=slot_in.subject_name,
        custom_title=slot_in.custom_title,
        teacher=slot_in.teacher,
        room=slot_in.room,
        week_type=slot_in.week_type or "both",
        is_double_period=slot_in.is_double_period,
        is_break=slot_in.is_break,
        note=slot_in.note
    )
    db.add(new_slot)
    db.commit()
    db.refresh(new_slot)

    return TimetableSlotRead(
        id=new_slot.id,
        day_of_week=new_slot.day_of_week,
        period=new_slot.period,
        period_label=new_slot.period_label,
        start_time=new_slot.start_time,
        end_time=new_slot.end_time,
        subject_id=new_slot.subject_id,
        subject_code=new_slot.subject_code,
        subject_name=new_slot.subject_name,
        subject_icon=sub.icon if sub else ("🥪" if new_slot.is_break else "📚"),
        subject_color=sub.color_code if sub else ("#64748b" if new_slot.is_break else "#6366f1"),
        custom_title=new_slot.custom_title,
        teacher=new_slot.teacher,
        room=new_slot.room,
        week_type=new_slot.week_type,
        is_double_period=new_slot.is_double_period,
        is_break=new_slot.is_break,
        note=new_slot.note
    )


@router.put("/slot/{slot_id}", response_model=TimetableSlotRead, dependencies=[Depends(require_parent)])
def update_timetable_slot(
    slot_id: str,
    slot_in: TimetableSlotCreateUpdate,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """Aktualisiert eine bestehende Unterrichtsstunde."""
    slot = db.query(TimetableSlot).filter_by(id=slot_id, user_id=user_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Stundenplan-Eintrag nicht gefunden.")

    sub = db.query(Subject).filter_by(id=slot_in.subject_id).first() if slot_in.subject_id else None

    slot.day_of_week = slot_in.day_of_week
    slot.period = slot_in.period
    slot.period_label = slot_in.period_label or slot.period_label
    slot.start_time = slot_in.start_time
    slot.end_time = slot_in.end_time
    slot.subject_id = sub.id if sub else None
    slot.subject_code = slot_in.subject_code
    slot.subject_name = slot_in.subject_name
    slot.custom_title = slot_in.custom_title
    slot.teacher = slot_in.teacher
    slot.room = slot_in.room
    slot.week_type = slot_in.week_type or slot.week_type
    slot.is_double_period = slot_in.is_double_period
    slot.is_break = slot_in.is_break
    slot.note = slot_in.note

    db.commit()
    db.refresh(slot)

    return TimetableSlotRead(
        id=slot.id,
        day_of_week=slot.day_of_week,
        period=slot.period,
        period_label=slot.period_label,
        start_time=slot.start_time,
        end_time=slot.end_time,
        subject_id=slot.subject_id,
        subject_code=slot.subject_code,
        subject_name=slot.subject_name,
        subject_icon=sub.icon if sub else ("🥪" if slot.is_break else "📚"),
        subject_color=sub.color_code if sub else ("#64748b" if slot.is_break else "#6366f1"),
        custom_title=slot.custom_title,
        teacher=slot.teacher,
        room=slot.room,
        week_type=slot.week_type,
        is_double_period=slot.is_double_period,
        is_break=slot.is_break,
        note=slot.note
    )


@router.delete("/slot/{slot_id}", status_code=204, dependencies=[Depends(require_parent)])
def delete_timetable_slot(
    slot_id: str,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """Entfernt eine Unterrichtsstunde aus dem Stundenplan."""
    slot = db.query(TimetableSlot).filter_by(id=slot_id, user_id=user_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Stundenplan-Eintrag nicht gefunden.")
    db.delete(slot)
    db.commit()
    return None

