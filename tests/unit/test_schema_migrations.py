from sqlalchemy import create_engine, text

from backend.app.database import ensure_schema_migrations


def test_old_database_gets_new_columns_and_current_kinds(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        # Stand vor Einführung der neuen Dokumentarten
        conn.execute(text("CREATE TABLE materials (id TEXT PRIMARY KEY, kind TEXT, title TEXT)"))
        conn.execute(text("INSERT INTO materials VALUES ('m1', 'Hefterseite', 'Notizen'), ('m2', 'Klausur', 'Arbeit'), ('m3', 'Test', 'Test')"))

    ensure_schema_migrations(engine)

    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(materials)"))}
        kinds = dict(conn.execute(text("SELECT id, kind FROM materials")).fetchall())
    assert {"solution_pages_json", "worked_on_paper", "teacher_graded"} <= cols
    assert kinds == {"m1": "Mitschrift", "m2": "Klassenarbeit", "m3": "Test"}
    engine.dispose()


def test_tests_are_isolated_from_real_data_and_openai():
    from backend.app import config
    assert "gothea_test_" in str(config.DATA_DIR)
    assert config.OPENAI_API_KEY == ""
    assert config.BACKGROUND_WORKERS_ENABLED is False


def test_old_board_table_gets_board_columns_and_keeps_its_boards(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old_boards.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tutor_sessions (id TEXT PRIMARY KEY, subject_id TEXT, title TEXT, board_state_json TEXT)"))
        conn.execute(text("INSERT INTO tutor_sessions VALUES ('ses_1', 'sub_math', 'Tafelübung', '[]')"))

    ensure_schema_migrations(engine)

    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(tutor_sessions)"))}
        row = conn.execute(text("SELECT title, title_source, archived_at FROM tutor_sessions")).one()
    assert {"updated_at", "last_opened_at", "title_source", "archived_at"} <= cols
    assert tuple(row) == ("Tafelübung", "auto", None)
    engine.dispose()
