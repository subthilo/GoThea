from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.config import APP_ENV, IS_STAGING, DB_PATH
from backend.app.database import get_db, Base, engine
from backend.app.services.seeder import seed_database

router = APIRouter(prefix="/api/v1", tags=["Environment"])

@router.get("/env")
def get_environment_info():
    return {
        "app_env": APP_ENV,
        "is_staging": IS_STAGING,
        "db_name": DB_PATH.name,
        "env_label": "STAGING (Testdaten)" if IS_STAGING else "PRODUKTION"
    }

@router.post("/staging/reset")
def reset_staging_database(db: Session = Depends(get_db)):
    if not IS_STAGING:
        raise HTTPException(
            status_code=403,
            detail="Datenbank-Reset ist ausschließlich in der Staging-Umgebung erlaubt!"
        )
    # Tabellen leeren und neu befüllen
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_database(db)

    # Staging Materialdateien, Dossier-Ordner, Cache & Inbox aufräumen
    from backend.app.config import MATERIALS_DIR, TEMP_UPLOADS_DIR, INBOX_DIR, PAGE_CACHE_DIR
    import shutil
    try:
        if MATERIALS_DIR.exists():
            shutil.rmtree(MATERIALS_DIR, ignore_errors=True)
        MATERIALS_DIR.mkdir(parents=True, exist_ok=True)

        if TEMP_UPLOADS_DIR.exists():
            shutil.rmtree(TEMP_UPLOADS_DIR, ignore_errors=True)
        TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

        if PAGE_CACHE_DIR.exists():
            shutil.rmtree(PAGE_CACHE_DIR, ignore_errors=True)
        PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Inbox-Dateien und _errors bereinigen
        if INBOX_DIR.exists():
            for item in INBOX_DIR.iterdir():
                if item.name.startswith("."):
                    continue
                if item.is_dir() and item.name == "_errors":
                    shutil.rmtree(item, ignore_errors=True)
                    item.mkdir(parents=True, exist_ok=True)
                elif item.is_file():
                    item.unlink(missing_ok=True)
    except Exception:
        pass

    return {
        "status": "success",
        "message": "Staging-Datenbank und Scan-Dateien wurden erfolgreich auf den Werkszustand zurückgesetzt."
    }
