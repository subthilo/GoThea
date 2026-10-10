import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Umgebung: "staging" oder "production" (Default: "staging" für Sicherheit)
APP_ENV = os.getenv("APP_ENV", "staging").lower()
IS_STAGING = APP_ENV == "staging"

# Datenverzeichnis getrennt nach Umgebung: data/staging oder data/prod
ENV_SUBDIR = "staging" if IS_STAGING else "prod"
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data" / ENV_SUBDIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app_data.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

MATERIALS_DIR = DATA_DIR / "materials"
MATERIALS_DIR.mkdir(parents=True, exist_ok=True)

TEMP_UPLOADS_DIR = DATA_DIR / "temp_uploads"
TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
