import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# SQLite Optimierungen: WAL-Modus & Fremdschlüssel aktivieren
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_schema_migrations(target_engine):
    """
    Führt schlanke, abwärtskompatible SQLite-Spaltenmigrationen aus,
    damit bestehende Datenbanken neue Spalten ohne Datenverlust erhalten.
    """
    if "sqlite" not in str(target_engine.url):
        return

    from sqlalchemy import text
    with target_engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='materials';")).fetchone()
        if res:
            existing_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(materials);")).fetchall()]
            new_cols = [
                ("dossier_id", "TEXT REFERENCES dossiers(id) ON DELETE SET NULL"),
                ("dossier_order", "INTEGER NOT NULL DEFAULT 1"),
                ("parent_id", "TEXT REFERENCES materials(id) ON DELETE CASCADE"),
                ("start_page", "INTEGER"),
                ("end_page", "INTEGER"),
                ("toc_json", "TEXT"),
                ("solution_pages_json", "TEXT"),
                ("worked_on_paper", "BOOLEAN"),
                ("teacher_graded", "BOOLEAN"),
            ]
            for col_name, col_def in new_cols:
                if col_name not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE materials ADD COLUMN {col_name} {col_def};"))
                    except Exception as e:
                        logger.warning(f"Migration: Spalte materials.{col_name} nicht angelegt: {e}")

            # Frühere Dokumentarten auf die heutigen abbilden (z. B. Hefterseite -> Mitschrift)
            if "kind" in existing_cols:
                from backend.app.services.document_kinds import LEGACY_KINDS
                for legacy, current in LEGACY_KINDS.items():
                    conn.execute(text("UPDATE materials SET kind = :new WHERE kind = :old"), {"new": current, "old": legacy})
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='tutor_sessions';")).fetchone()
        if res:
            session_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(tutor_sessions);")).fetchall()]
            for col_name, col_def in [
                ("updated_at", "DATETIME"),
                ("last_opened_at", "DATETIME"),
                ("title_source", "TEXT NOT NULL DEFAULT 'auto'"),
                ("archived_at", "DATETIME"),
                ("practice_exercise_id", "TEXT"),
                ("practice_stage", "INTEGER"),
            ]:
                if col_name not in session_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE tutor_sessions ADD COLUMN {col_name} {col_def};"))
                    except Exception as e:
                        logger.warning(f"Migration: Spalte tutor_sessions.{col_name} nicht angelegt: {e}")
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='topics';")).fetchone()
        if res:
            topic_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(topics);")).fetchall()]
            if "area" not in topic_cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN area TEXT;"))
        conn.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
