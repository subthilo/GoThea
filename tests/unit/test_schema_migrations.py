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
