import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 1. Automatisch .env laden (Root oder Fallback auf experiments/.env)
_root_env = PROJECT_ROOT / ".env"
if _root_env.exists():
    load_dotenv(_root_env)
else:
    _study_env = PROJECT_ROOT / "experiments" / "openai_study" / ".env"
    if _study_env.exists():
        load_dotenv(_study_env)

# OpenAI Integration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Günstiges Modell für die Vorverarbeitung jedes Uploads (Dokument- & Stundenplananalyse)
OPENAI_ANALYSIS_MODEL = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4o-mini")

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

INBOX_DIR = Path(os.getenv("INBOX_DIR", str(PROJECT_ROOT / "inbox" / ENV_SUBDIR)))
INBOX_DIR.mkdir(parents=True, exist_ok=True)
INBOX_ERRORS_DIR = INBOX_DIR / "_errors"

PAGE_CACHE_DIR = DATA_DIR / "cache" / "rendered_pages"
PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_PHRASES_DIR = DATA_DIR / "audio_phrases"
AUDIO_PHRASES_DIR.mkdir(parents=True, exist_ok=True)

CLOZE_POOL_DIR = DATA_DIR / "cloze_pool"
CLOZE_POOL_DIR.mkdir(parents=True, exist_ok=True)

EXERCISE_POOL_DIR = DATA_DIR / "exercise_pool"
EXERCISE_POOL_DIR.mkdir(parents=True, exist_ok=True)


