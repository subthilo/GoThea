import os
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.config import CLOZE_POOL_DIR, OPENAI_API_KEY
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.material import Material
from backend.app.services.tutor_service import generate_board_exercise, normalize_cloze_content

logger = logging.getLogger(__name__)

TARGET_POOL_SIZE = 3
DEFAULT_SUBJECTS = ["sub_english", "sub_math", "sub_biology", "sub_german"]


class ClozePoolManager:
    """
    Verwaltet einen vorab generierten Offline-Vorratsspeicher von Lückentext-Übungen
    inklusive aller vorgerenderten Audio-Dateien (Satz-TTS).

    Dadurch öffnet sich jede Lückentext-Übung für Thea INSTANT (< 10 ms),
    während im Hintergrund automatisch der Vorrat wieder auf 3 Übungen aufgefüllt wird.
    """
    def __init__(self, storage_dir: Path = CLOZE_POOL_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._replenishing_subjects = set()

    def _canonical_subject_key(self, subject_id: Optional[str]) -> str:
        s = (subject_id or "sub_english").lower()
        if "english" in s:
            return "sub_english"
        elif "math" in s:
            return "sub_math"
        elif "bio" in s:
            return "sub_biology"
        elif "physic" in s:
            return "sub_physics"
        elif "german" in s or "deutsch" in s:
            return "sub_german"
        return s

    def _get_pool_file(self, subject_key: str) -> Path:
        return self.storage_dir / f"pool_{subject_key}.json"

    def _load_pool(self, subject_key: str) -> List[Dict[str, Any]]:
        pool_file = self._get_pool_file(subject_key)
        if not pool_file.exists():
            return []
        try:
            with open(pool_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Fehler beim Laden des Übungspools für {subject_key}: {e}")
            return []

    def _save_pool(self, subject_key: str, exercises: List[Dict[str, Any]]):
        pool_file = self._get_pool_file(subject_key)
        try:
            with open(pool_file, "w", encoding="utf-8") as f:
                json.dump(exercises, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Fehler beim Speichern des Übungspools für {subject_key}: {e}")

    def get_exercise_from_pool(self, subject_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Holt sofort eine vorab erstellte Übung aus dem Speicher (0 ms Latenz).
        Entfernt sie aus dem Vorrat und stößt im Hintergrund die Nachproduktion an.
        """
        subject_key = self._canonical_subject_key(subject_id)
        with self._lock:
            pool = self._load_pool(subject_key)
            if not pool:
                logger.info(f"Cloze-Pool für {subject_key} ist leer. On-Demand-Generierung erforderlich.")
                return None

            # Erste Übung entnehmen
            exercise = pool.pop(0)
            self._save_pool(subject_key, pool)
            logger.info(f"⚡ Blitzschnelle Übung aus Pool entnommen für {subject_key}! Verbleibend im Pool: {len(pool)}")
            return exercise

    def get_pool_status(self) -> Dict[str, int]:
        with self._lock:
            status = {}
            for f in self.storage_dir.glob("pool_*.json"):
                key = f.stem.replace("pool_", "")
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        items = json.load(fp)
                        status[key] = len(items) if isinstance(items, list) else 0
                except Exception:
                    status[key] = 0
            return status

    def trigger_background_replenish(self, subject_id: Optional[str]):
        """
        Startet einen separaten Hintergrund-Thread, der den Vorrat für dieses Fach
        wieder auf TARGET_POOL_SIZE auffüllt, ohne den aktuellen Request zu blockieren.
        """
        subject_key = self._canonical_subject_key(subject_id)
        if subject_key in self._replenishing_subjects:
            return  # Läuft bereits

        t = threading.Thread(
            target=self._replenish_worker,
            args=(subject_key, subject_id),
            daemon=True
        )
        t.start()

    def _replenish_worker(self, subject_key: str, subject_id: Optional[str]):
        self._replenishing_subjects.add(subject_key)
        try:
            with self._lock:
                current_pool = self._load_pool(subject_key)
                needed = TARGET_POOL_SIZE - len(current_pool)

            if needed <= 0:
                return

            logger.info(f"🔄 Starte Hintergrund-Vorratsproduktion für {subject_key} (fehlen: {needed})...")

            # DB-Session für Kontext holen
            from backend.app.database import SessionLocal
            db = SessionLocal()
            try:
                for i in range(needed):
                    ex = self._produce_single_exercise(subject_key, subject_id, db)
                    if ex:
                        with self._lock:
                            pool = self._load_pool(subject_key)
                            pool.append(ex)
                            self._save_pool(subject_key, pool)
                            logger.info(f"✅ Neue Lückentext-Übung für {subject_key} im Hintergrund vorgerendert! (Pool: {len(pool)}/{TARGET_POOL_SIZE})")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Fehler bei Hintergrund-Vorratsproduktion für {subject_key}: {e}", exc_info=True)
        finally:
            self._replenishing_subjects.discard(subject_key)

    def _produce_single_exercise(
        self,
        subject_key: str,
        subject_id: Optional[str],
        db
    ) -> Optional[Dict[str, Any]]:
        """
        Erstellt eine vollwertige, geerdete Übung mit parallelem Satz-Audio.
        """
        subject_name = "Englisch" if "english" in subject_key else "Mathematik"
        target_sub_id = subject_id or subject_key

        subj = db.query(Subject).filter(
            (Subject.id == target_sub_id) | (Subject.name.ilike(f"%{subject_name}%"))
        ).first()

        if subj:
            subject_name = subj.name
            target_sub_id = subj.id

        material_context = None
        source_title = None

        # Material-Geerdet falls vorhanden
        mats = db.query(Material).filter(Material.subject_id == target_sub_id).all()
        if mats:
            import random
            mat = random.choice(mats)  # Vielfalt in den Vorrat bringen
            source_title = mat.title
            material_context = {
                "id": mat.id,
                "title": mat.title,
                "kind": mat.kind,
                "topic": mat.topic.name if mat.topic else None,
                "summary": mat.summary,
                "text_snippet": (mat.extracted_text or "")[:3200]
            }

        res = generate_board_exercise(
            subject_name=subject_name,
            grade_level=7,
            topic_name=material_context.get("topic") if material_context else None,
            exercise_type="fill_in_the_blank",
            difficulty="mittel",
            material_context=material_context,
            audio_enabled=True
        )

        try:
            content = json.loads(res.get("content_json", "{}"))
        except Exception:
            content = {}

        # Sätze mit Satz-Audio parallel aufbereiten
        content = normalize_cloze_content(content, generate_sentence_audio=True)

        return {
            "status": "success",
            "exercise_type": "fill_in_the_blank",
            "title": res.get("title", f"Lückentext: {subject_name}"),
            "topic": res.get("topic") or (material_context.get("topic") if material_context else subject_name),
            "instructions": res.get("instructions") or "Fülle die Lücken mit den passenden Begriffen aus.",
            "source_material_title": source_title,
            "content": content,
            "tutor_speech": res.get("tutor_speech"),
            "pre_generated_at": datetime.now().isoformat()
        }


cloze_pool_manager = ClozePoolManager()
