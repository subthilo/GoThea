import os
import json
import logging
import random
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.config import EXERCISE_POOL_DIR, CLOZE_POOL_DIR, OPENAI_API_KEY
from backend.app.models.taxonomy import Subject
from backend.app.models.material import Material
from backend.app.services.tutor_service import generate_board_exercise, normalize_cloze_content

logger = logging.getLogger(__name__)

TARGET_POOL_SIZE = 2

# Fächerspezifische bevorzugte Aufgabentypen für den Hintergrund-Vorrat
SUBJECT_EXERCISE_TYPES: Dict[str, List[str]] = {
    "sub_math": ["math_problem", "math_example", "formula_derivation", "fill_in_the_blank"],
    "sub_physics": ["physics_diagram", "formula_derivation", "math_problem", "fill_in_the_blank"],
    "sub_english": ["fill_in_the_blank", "text_question"],
    "sub_german": ["fill_in_the_blank", "text_question"],
    "sub_biology": ["fill_in_the_blank", "text_question"],
}

DEFAULT_SUBJECTS = ["sub_english", "sub_math", "sub_physics", "sub_biology", "sub_german"]


class ExercisePoolManager:
    """
    Intelligenter Hintergrund-Vorratsspeicher für alle Übungsarten in GoThea:
    - Lückentext (fill_in_the_blank) inkl. Satz-Audios
    - Rechenaufgaben (math_problem)
    - Rechenbeispiele (math_example)
    - Physik-Diagramme (physics_diagram)
    - Formel-Herleitungen (formula_derivation)
    - Textfragen (text_question)

    Hält kontinuierlich vorgerenderte Übungen inklusive Sprachausgabe bereit.
    Startet beim Start der GoThea-App im Hintergrund (wie der PageRenderingService),
    sodass das Starten einer beliebigen Übung im System SOFORT (< 10 ms) erfolgt.
    """

    def __init__(self, storage_dir: Path = EXERCISE_POOL_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._session_factory = None
        self._replenishing_keys = set()

    def canonical_subject_key(self, subject_id: Optional[str]) -> str:
        s = (subject_id or "sub_english").lower()
        if "english" in s:
            return "sub_english"
        elif "math" in s:
            return "sub_math"
        elif "bio" in s:
            return "sub_biology"
        elif "physic" in s or "physik" in s:
            return "sub_physics"
        elif "german" in s or "deutsch" in s:
            return "sub_german"
        return s

    def resolve_auto_exercise_type(self, subject_key: str) -> str:
        """Bestimmt den typischen Standard-Aufgabentyp für ein Fach."""
        if "physic" in subject_key:
            return "physics_diagram"
        elif "math" in subject_key:
            return "math_problem"
        return "fill_in_the_blank"

    def _get_pool_file(self, subject_key: str, exercise_type: str) -> Path:
        return self.storage_dir / f"pool_{subject_key}_{exercise_type}.json"

    def _load_pool(self, subject_key: str, exercise_type: str) -> List[Dict[str, Any]]:
        pool_file = self._get_pool_file(subject_key, exercise_type)
        if pool_file.exists():
            try:
                with open(pool_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception as e:
                logger.warning(f"Fehler beim Laden des Pools {pool_file.name}: {e}")
                return []

        # Abwärtskompatibilität für Lückentexte (frühere Dateinamen pool_{subject_key}.json)
        if exercise_type == "fill_in_the_blank":
            legacy_files = [
                self.storage_dir / f"pool_{subject_key}.json",
                CLOZE_POOL_DIR / f"pool_{subject_key}.json"
            ]
            for lf in legacy_files:
                if lf.exists():
                    try:
                        with open(lf, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, list) and data:
                                # Migrieren in neue Datei
                                self._save_pool(subject_key, exercise_type, data)
                                return data
                    except Exception as e:
                        logger.warning(f"Fehler beim Laden der Alt-Pool-Datei {lf.name}: {e}")
        return []

    def _save_pool(self, subject_key: str, exercise_type: str, exercises: List[Dict[str, Any]]):
        pool_file = self._get_pool_file(subject_key, exercise_type)
        try:
            with open(pool_file, "w", encoding="utf-8") as f:
                json.dump(exercises, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Fehler beim Speichern des Pools {pool_file.name}: {e}")

    def get_exercise_from_pool(
        self,
        subject_id: Optional[str],
        exercise_type: Optional[str] = "fill_in_the_blank",
        difficulty: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Holt sofort eine vorab erstellte Übung aus dem Speicher (0 ms Wartezeit).
        Entfernt sie aus dem Vorrat und weckt den Hintergrund-Worker zum Nachproduzieren.
        """
        subject_key = self.canonical_subject_key(subject_id)
        target_type = (exercise_type or "auto").strip().lower()

        candidate_types = []
        if target_type == "auto":
            primary = self.resolve_auto_exercise_type(subject_key)
            all_types = SUBJECT_EXERCISE_TYPES.get(subject_key, ["fill_in_the_blank", "math_problem"])
            candidate_types = [primary] + [t for t in all_types if t != primary]
        else:
            candidate_types = [target_type]

        with self._lock:
            for ex_type in candidate_types:
                pool = self._load_pool(subject_key, ex_type)
                if pool:
                    exercise = pool.pop(0)
                    self._save_pool(subject_key, ex_type, pool)
                    logger.info(
                        f"⚡ Blitzschnelle Übung ({ex_type}) aus Vorrat entnommen für {subject_key}! "
                        f"Verbleibend: {len(pool)}"
                    )
                    # Hintergrund-Worker wecken
                    self._wake_event.set()
                    return exercise

        logger.info(f"Keine gepoolte Übung für {subject_key} (Typ: {target_type}) vorhanden. On-Demand erforderlich.")
        self._wake_event.set()
        return None

    def get_pool_status(self) -> Dict[str, int]:
        """Gibt den Füllstand aller Übungspools zurück."""
        with self._lock:
            status: Dict[str, int] = {}
            # Alle Pools im Verzeichnis prüfen
            for f in self.storage_dir.glob("pool_*.json"):
                key = f.stem.replace("pool_", "")
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        items = json.load(fp)
                        status[key] = len(items) if isinstance(items, list) else 0
                except Exception:
                    status[key] = 0

            # Auch CLOZE_POOL_DIR prüfen für Altdaten
            if CLOZE_POOL_DIR != self.storage_dir and CLOZE_POOL_DIR.exists():
                for f in CLOZE_POOL_DIR.glob("pool_*.json"):
                    key = f.stem.replace("pool_", "")
                    if key not in status:
                        try:
                            with open(f, "r", encoding="utf-8") as fp:
                                items = json.load(fp)
                                status[key] = len(items) if isinstance(items, list) else 0
                        except Exception:
                            pass
            return status

    def trigger_background_replenish(self, subject_id: Optional[str], exercise_type: str = "fill_in_the_blank"):
        """Weckt den Hintergrund-Worker oder startet einen Ad-Hoc-Thread."""
        self._wake_event.set()
        if not (self._worker_thread and self._worker_thread.is_alive()):
            # Falls der permanente Service nicht läuft (z.B. in isolierten Tests), Fallback-Thread starten
            subject_key = self.canonical_subject_key(subject_id)
            replenish_key = f"{subject_key}_{exercise_type}"
            if replenish_key in self._replenishing_keys:
                return
            t = threading.Thread(
                target=self._replenish_single_key,
                args=(subject_key, subject_id, exercise_type),
                daemon=True
            )
            t.start()

    def _replenish_single_key(self, subject_key: str, subject_id: Optional[str], exercise_type: str):
        key = f"{subject_key}_{exercise_type}"
        self._replenishing_keys.add(key)
        try:
            session_factory = self._session_factory
            if not session_factory:
                from backend.app.database import SessionLocal
                session_factory = SessionLocal
            db = session_factory()
            try:
                with self._lock:
                    current_pool = self._load_pool(subject_key, exercise_type)
                    needed = TARGET_POOL_SIZE - len(current_pool)
                if needed > 0:
                    ex = self._produce_single_exercise(subject_key, subject_id, exercise_type, db)
                    if ex:
                        with self._lock:
                            pool = self._load_pool(subject_key, exercise_type)
                            pool.append(ex)
                            self._save_pool(subject_key, exercise_type, pool)
                            logger.info(f"✅ Übung ({exercise_type}) für {subject_key} nachproduziert! (Pool: {len(pool)})")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Fehler beim Ad-Hoc Replenish für {key}: {e}", exc_info=True)
        finally:
            self._replenishing_keys.discard(key)

    # -------------------------------------------------------------------------
    # Permanenter Hintergrund-Dienst (analog zu PageRenderingService)
    # -------------------------------------------------------------------------
    def start(self, session_factory=None):
        """Startet den kontinuierlichen Hintergrund-Worker-Thread."""
        if session_factory:
            self._session_factory = session_factory
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._wake_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="ExercisePoolBackgroundWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("🚀 ExercisePoolManager Hintergrund-Worker gestartet.")

    def stop(self):
        """Beendet den Hintergrund-Worker geordnet."""
        self._stop_event.set()
        self._wake_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("🛑 ExercisePoolManager Hintergrund-Worker gestoppt.")

    def _worker_loop(self):
        """
        Dauerhafter Hintergrund-Prozess:
        Prüft regelmäßig alle Fächer und Aufgabentypen. Fehlt eine Aufgabe im Vorrat,
        wird sie schonend im Hintergrund mit Audio gerendert.
        """
        logger.info("🔄 ExercisePool Hintergrund-Schleife läuft.")
        if self._stop_event.wait(timeout=1.0):
            return

        while not self._stop_event.is_set():
            try:
                produced = self._process_next_missing_exercise()
                if produced:
                    # Zwischen Generierungen schonend warten (3s), um CPU und OpenAI API nicht zu überlasten
                    self._stop_event.wait(timeout=3.0)
                else:
                    # Alle Vorräte sind voll! Im Leerlauf warten, bis etwas verbraucht oder wake_event gesetzt wird
                    self._wake_event.wait(timeout=25.0)
                    self._wake_event.clear()
            except Exception as e:
                logger.error(f"Fehler in ExercisePool Worker-Schleife: {e}", exc_info=True)
                self._stop_event.wait(timeout=5.0)

    def _process_next_missing_exercise(self) -> bool:
        """
        Sucht den Pool mit dem größten Mangel (< TARGET_POOL_SIZE) und generiert eine Aufgabe.
        Gibt True zurück, wenn eine Aufgabe generiert wurde, sonst False (alle voll).
        """
        session_factory = self._session_factory
        if not session_factory:
            from backend.app.database import SessionLocal
            session_factory = SessionLocal

        # 1. Bestandsaufnahme
        candidates = []
        with self._lock:
            for sub_key, ex_types in SUBJECT_EXERCISE_TYPES.items():
                for ex_type in ex_types:
                    pool = self._load_pool(sub_key, ex_type)
                    if len(pool) < TARGET_POOL_SIZE:
                        # Priorität: Lückentext und Rechenaufgaben haben Vorrang
                        prio = 1 if ex_type in ("fill_in_the_blank", "math_problem") else 2
                        candidates.append((prio, len(pool), sub_key, ex_type))

        if not candidates:
            return False  # Alles voll!

        # Nach Priorität und geringstem Füllstand sortieren
        candidates.sort(key=lambda c: (c[0], c[1]))
        _, current_len, chosen_sub, chosen_type = candidates[0]

        logger.info(
            f"🔄 ExercisePool Hintergrund-Rendering: Erstelle '{chosen_type}' für {chosen_sub} "
            f"(Aktuell: {current_len}/{TARGET_POOL_SIZE})..."
        )

        db = session_factory()
        try:
            exercise = self._produce_single_exercise(chosen_sub, None, chosen_type, db)
            if exercise:
                with self._lock:
                    pool = self._load_pool(chosen_sub, chosen_type)
                    pool.append(exercise)
                    self._save_pool(chosen_sub, chosen_type, pool)
                    logger.info(
                        f"✅ Vorrat erweitert: '{chosen_type}' für {chosen_sub} fertig vorgerendert! "
                        f"(Neuer Stand: {len(pool)}/{TARGET_POOL_SIZE})"
                    )
                return True
        except Exception as e:
            logger.error(f"Fehler beim Hintergrund-Rendern für {chosen_sub}/{chosen_type}: {e}", exc_info=True)
        finally:
            db.close()

        return False

    def _produce_single_exercise(
        self,
        subject_key: str,
        subject_id: Optional[str],
        exercise_type: str,
        db
    ) -> Optional[Dict[str, Any]]:
        """
        Erstellt eine vollwertige, auf Schülermaterialien geerdete Übung mit Audio.
        """
        # Fach ermitteln
        subject_name = "Englisch"
        if "math" in subject_key:
            subject_name = "Mathematik"
        elif "physic" in subject_key:
            subject_name = "Physik"
        elif "bio" in subject_key:
            subject_name = "Biologie"
        elif "german" in subject_key:
            subject_name = "Deutsch"

        target_sub_id = subject_id or subject_key

        subj = db.query(Subject).filter(
            (Subject.id == target_sub_id) | (Subject.name.ilike(f"%{subject_name}%"))
        ).first()

        if subj:
            subject_name = subj.name
            target_sub_id = subj.id

        material_context = None
        source_title = None

        # Falls Schülermaterialien vorhanden sind, Aufgabe darauf erden
        mats = db.query(Material).filter(Material.subject_id == target_sub_id).all()
        if mats:
            mat = random.choice(mats)
            source_title = mat.title
            material_context = {
                "id": mat.id,
                "title": mat.title,
                "kind": mat.kind,
                "topic": mat.topic.name if mat.topic else None,
                "summary": mat.summary,
                "text_snippet": (mat.extracted_text or "")[:3000]
            }

        topic_name = material_context.get("topic") if material_context else None

        res = generate_board_exercise(
            subject_name=subject_name,
            grade_level=7,
            topic_name=topic_name,
            exercise_type=exercise_type,
            difficulty="mittel",
            material_context=material_context,
            audio_enabled=True
        )

        content_json_str = res.get("content_json", "{}")
        try:
            content_obj = json.loads(content_json_str) if isinstance(content_json_str, str) else content_json_str
        except Exception:
            content_obj = {}

        # Bei Lückentexten: Satz-Audio parallel vorrendern
        if exercise_type == "fill_in_the_blank":
            content_obj = normalize_cloze_content(content_obj, generate_sentence_audio=True)
            content_json_str = json.dumps(content_obj)

        return {
            "status": "success",
            "exercise_type": res.get("exercise_type", exercise_type),
            "title": res.get("title", f"Übung: {subject_name}"),
            "topic": res.get("topic") or (material_context.get("topic") if material_context else subject_name),
            "instructions": res.get("instructions") or "Bearbeite die Aufgabe.",
            "source_material_title": source_title,
            "content": content_obj,
            "content_json": content_json_str,
            "solution_hint": res.get("solution_hint"),
            "tutor_speech": res.get("tutor_speech"),
            "audio_base64": res.get("audio_base64"),
            "difficulty": "mittel",
            "pre_generated_at": datetime.now().isoformat()
        }


exercise_pool_manager = ExercisePoolManager()
