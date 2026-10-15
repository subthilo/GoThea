import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.database import Base, get_db
from backend.app.services.seeder import seed_database
from backend.main import app

# Schnelle In-Memory SQLite Datenbank für Tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def engine():
    # Jeder Test bekommt eine eigene, frische In-Memory-Datenbank: keine Daten zwischen Tests,
    # auch wenn der getestete Code selbst commit()/rollback() aufruft.
    # StaticPool: alle Threads eines Tests teilen dieselbe Verbindung (sonst sähe jeder Thread
    # eine eigene, leere In-Memory-Datenbank).
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Seed-Daten für Tests einspielen
    seed_database(session)

    yield session

    session.close()

@pytest.fixture(scope="function")
def client(db_session):
    """Test-Client im Eltern-Modus (Rechteprüfung wird überbrückt)."""
    from backend.app.services.parent_auth import require_parent

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_parent] = lambda: True
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def strict_client(db_session):
    """Test-Client ohne Eltern-Rechte (echte Rechteprüfung aktiv, z. B. Thea-Modus)."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def isolated_parent_auth(tmp_path, monkeypatch):
    """Jeder Test bekommt eine eigene PIN-Datei (Standard-PIN 1234) und frische Fehlversuchs-Zähler."""
    from backend.app.services import parent_auth
    monkeypatch.setattr(parent_auth, "AUTH_FILE", tmp_path / "parent_auth.json")
    monkeypatch.setattr(parent_auth, "DEFAULT_PIN", "1234")
    parent_auth.reset_lockout_state()
    yield
    parent_auth.reset_lockout_state()

@pytest.fixture(autouse=True)
def disable_openai_in_tests(monkeypatch):
    """Verhindert echte OpenAI API-Aufrufe während der Standard-Test-Suite."""
    monkeypatch.setattr("backend.app.services.document_analyzer.OPENAI_API_KEY", None)
    monkeypatch.setattr("backend.app.services.timetable_analyzer.OPENAI_API_KEY", None)


