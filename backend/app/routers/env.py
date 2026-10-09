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
    return {
        "status": "success",
        "message": "Staging-Datenbank wurde erfolgreich auf den Werkszustand zurückgesetzt."
    }
