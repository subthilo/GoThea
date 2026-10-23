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
# Modell für die Dokumentanalyse jedes Uploads. Standard: Hauptmodell, weil gpt-4o-mini in
# der Messung (scripts/eval_document_classification.py) schlechter klassifizierte und für
# Seitenbilder ein Vielfaches an Tokens verbrauchte.
OPENAI_ANALYSIS_MODEL = os.getenv("OPENAI_ANALYSIS_MODEL", OPENAI_MODEL)
# Sprachausgabe (bisher fest im Code: tts-1 mit Stimme nova)
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "nova")
# Schaubilder für Übungen nachzeichnen (nur in Sessions am Mac, scripts/figure_tool.py) und das Ergebnis
# gegen das Original prüfen lassen (im Machbarkeitsversuch fand gpt-6.1-sol feinste Fachfehler in Grafiken)
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
OPENAI_REVIEW_MODEL = os.getenv("OPENAI_REVIEW_MODEL", "gpt-6.1-sol")
# Zeitlimit pro Versuch und Wiederholungen bei Netz-/Serverfehlern; Standard = bisheriges Verhalten
# der OpenAI-Bibliothek. Erst anhand von logs/llm_usage.jsonl (Dauer pro Zweck) verschärfen.
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "600"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))

# Hintergrund-Worker (Seiten-Renderer, Übungs-Pool) beim App-Start; in Tests abgeschaltet
BACKGROUND_WORKERS_ENABLED = os.getenv("GOTHEA_BACKGROUND_WORKERS", "1") != "0"

# Umgebung: "staging" oder "production" (Default: "staging" für Sicherheit)
APP_ENV = os.getenv("APP_ENV", "staging").lower()
IS_STAGING = APP_ENV == "staging"

# Übungen aus echten Aufgaben (Probebetrieb, ohne Freigabe durch die Eltern; Daten liefern Lösungen
# mit). Standard: nur auf Staging an, damit Thea sie auf Produktion nicht vorzeitig sieht.
EXERCISE_TRIAL_ENABLED = os.getenv("GOTHEA_EXERCISE_TRIAL", "1" if IS_STAGING else "0") == "1"

# Datenverzeichnis getrennt nach Umgebung: data/staging oder data/prod
ENV_SUBDIR = "staging" if IS_STAGING else "prod"
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data" / ENV_SUBDIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app_data.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# Gemeinsam für Staging und Produktion: inhaltsadressierte Ergebnisse (z. B. Seiten-Erschließung),
# damit dieselbe Datei nicht in beiden Umgebungen erneut per KI verarbeitet wird
SHARED_DATA_DIR = Path(os.getenv("SHARED_DATA_DIR", str(PROJECT_ROOT / "data" / "shared")))
SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Langsames Nachholen der Buch-Erschließung im Hintergrund (Sekunden zwischen zwei Buchseiten, 0 = aus)
BOOK_EXTRACTION_INTERVAL_SECONDS = float(os.getenv("GOTHEA_BOOK_EXTRACTION_INTERVAL", "20"))

MATERIALS_DIR = DATA_DIR / "materials"
MATERIALS_DIR.mkdir(parents=True, exist_ok=True)

TEMP_UPLOADS_DIR = DATA_DIR / "temp_uploads"
TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

INBOX_DIR = Path(os.getenv("INBOX_DIR", str(PROJECT_ROOT / "inbox" / ENV_SUBDIR)))
INBOX_DIR.mkdir(parents=True, exist_ok=True)
INBOX_ERRORS_DIR = INBOX_DIR / "_errors"

PAGE_CACHE_DIR = DATA_DIR / "cache" / "rendered_pages"
PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)



