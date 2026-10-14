import json
from unittest.mock import MagicMock, patch

from backend.app.models.timetable import TimetableSlot
from backend.app.services.timetable_slots import (
    build_slot_specs,
    describe_week_differences,
    parse_period,
    parse_week,
    replace_timetable_slots,
)


def _e(stunde, fach, kuerzel, raum=None, lehrer=None, woche="beide", pause=False):
    return {"stunde": stunde, "fach": fach, "kuerzel": kuerzel, "raum": raum, "lehrer": lehrer, "woche": woche, "pause": pause}


# Nachbildung von Theas Untis-Foto (Klasse 7D, A-Woche mit handschriftlichem En(B))
PHOTO_WOCHENPLAN = {
    "Montag": [
        _e("1", "Deutsch", "D", "201", "DÜCK"), _e("2", "Deutsch", "D", "201", "DÜCK"),
        _e("5", "Sport", "*Sp", "gewo", "DÜCK", woche="A"), _e("6.1", "Sport", "*Sp", "gewo", "DÜCK", woche="A"),
        _e("5", "Englisch", "En", None, None, woche="B"), _e("6.1", "Englisch", "En", None, None, woche="B"),
        _e("6.2", "Mittag", "*Mittag", pause=True),
        _e("7", "WAT", "WAT", "105", "BIEL"),
    ],
    "Dienstag": [
        _e("5", "GT-Mittag", "*GT-Mittag", pause=True),
        _e("7", "LER", "LER", "007", "EISE"), _e("7", "Religion", "Rel", "302", "SCHN"),
        _e("8", "LER", "LER", "007", "EISE"), _e("8", "Religion", "Rel", "302", "SCHN"),
    ],
    "Freitag": [
        _e("1", "Geschichte", "Ge", "102", "DÜCK"), _e("2", "Musik", "Mu", "N1.2", "ERDM"),
    ],
}


def _find(specs, day, period, week="both"):
    return next(s for s in specs if s["day"] == day and s["period"] == period and s["week"] == week)


def test_parse_period_and_week():
    assert parse_period("6.1") == 6
    assert parse_period("6.2") == 7
    assert parse_period("7") == 8
    assert parse_period(8) == 9
    assert parse_period("3.") == 3
    assert parse_period("x") is None
    assert parse_week("beide") == "both"
    assert parse_week("both") == "both"
    assert parse_week("B-Woche") == "B"
    assert parse_week("A") == "A"


def test_build_slot_specs_from_photo_grid():
    specs = build_slot_specs(PHOTO_WOCHENPLAN)

    deutsch = _find(specs, "Montag", 1)
    assert deutsch["sub_id"] == "sub_german" and deutsch["double"] is True

    # A/B-Wechsel bleibt getrennt und ist jeweils Doppelstunde
    sport_a = _find(specs, "Montag", 6, "A")
    englisch_b = _find(specs, "Montag", 5, "B")
    assert sport_a["name"] == "Sport" and sport_a["double"] is True
    assert englisch_b["name"] == "Englisch" and englisch_b["double"] is True

    mittag = _find(specs, "Montag", 7)
    assert mittag["is_break"] is True and mittag["sub_id"] is None and mittag["name"] == "Mittagspause"

    wat = _find(specs, "Montag", 8)
    assert wat["double"] is False

    # Parallele Kurse werden zu einem Slot zusammengeführt
    ler = _find(specs, "Dienstag", 8)
    assert ler["code"] == "LER / Rel"
    assert ler["teacher"] == "EISE / SCHN" and ler["room"] == "007 / 302"
    assert ler["double"] is True
    assert "oder" in ler["note"]

    # Geteilte Freitagszelle: zwei Einzelstunden, keine Doppelstunde
    assert _find(specs, "Freitag", 1)["name"] == "Geschichte"
    assert _find(specs, "Freitag", 2)["name"] == "Musik"
    assert _find(specs, "Freitag", 1)["double"] is False


def test_replace_timetable_slots_keeps_existing_when_nothing_recognized(db_session):
    replace_timetable_slots(db_session, build_slot_specs(PHOTO_WOCHENPLAN))
    count = db_session.query(TimetableSlot).count()
    assert count == len(build_slot_specs(PHOTO_WOCHENPLAN))

    # Nur Pausen oder leer -> bisheriger Plan bleibt
    assert replace_timetable_slots(db_session, build_slot_specs({"Montag": [_e("6.2", "Mittag", "*Mittag", pause=True)]})) == 0
    assert replace_timetable_slots(db_session, []) == 0
    assert db_session.query(TimetableSlot).count() == count


def test_describe_week_differences(db_session):
    replace_timetable_slots(db_session, build_slot_specs(PHOTO_WOCHENPLAN))
    diffs = describe_week_differences(db_session.query(TimetableSlot).all())
    assert diffs == ["Montag 5./6.1 Std: A-Woche Sport, B-Woche Englisch."]


def test_import_timetable_writes_slots(client, db_session, tmp_path):
    img = tmp_path / "stundenplan.png"
    from PIL import Image
    Image.new("RGB", (40, 30), "white").save(img)

    mock_client = MagicMock()
    choice = MagicMock()
    choice.message.content = json.dumps({
        "ist_stundenplan": True,
        "titel": "Stundenplan Thea - Klasse 7D",
        "erkannte_faecher": ["Deutsch", "Sport", "Englisch", "WAT", "LER", "Religion", "Geschichte", "Musik"],
        "wochenplan": PHOTO_WOCHENPLAN,
    })
    mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

    with patch("backend.app.services.timetable_analyzer.OPENAI_API_KEY", "sk-fake"), \
         patch("openai.OpenAI", return_value=mock_client), \
         patch("backend.app.services.timetable_analyzer.render_material_page_as_image", return_value=(img.read_bytes(), "image/png")), \
         open(img, "rb") as f:
        res = client.post("/api/v1/taxonomy/import-timetable", files={"file": ("stundenplan.png", f, "image/png")})

    assert res.status_code == 200
    data = res.json()
    assert data["slots_imported"] == len(build_slot_specs(PHOTO_WOCHENPLAN))
    assert "in den Stundenplan übernommen" in data["message"]

    overview = client.get("/api/v1/timetable?week_type=B").json()
    assert any(s["day_of_week"] == "Montag" and s["subject_name"] == "Englisch" and s["week_type"] == "B" for s in overview["slots"])
    assert overview["week_differences"] == ["Montag 5./6.1 Std: A-Woche Sport, B-Woche Englisch."]


def test_unpaired_week_entries_apply_to_both_weeks():
    # KI überträgt den Aufdruck "A Woche" auf alle Stunden; nur Montag 5. hat echtes B-Gegenstück
    grid = {"Montag": [
        _e("1", "Deutsch", "D", "201", "DÜCK", woche="A"),
        _e("5", "Sport", "*Sp", "gewo", "DÜCK", woche="A"),
        _e("5", "Englisch", "En", woche="B"),
    ]}
    specs = build_slot_specs(grid)
    assert _find(specs, "Montag", 1)["week"] == "both"
    assert _find(specs, "Montag", 5, "A")["name"] == "Sport"
    assert _find(specs, "Montag", 5, "B")["name"] == "Englisch"
