import os
import json
import base64
import logging
import hashlib
from typing import Dict, Any, List, Optional
from pathlib import Path
import random

from backend.app.config import AUDIO_PHRASES_DIR, OPENAI_API_KEY

logger = logging.getLogger(__name__)

DEFAULT_PHRASES = {
    "error_interjections": [
        "Ups, nicht ganz.",
        "Halt, schau dir das nochmal an.",
        "Fast! Aber da hat sich ein kleiner Fehler eingeschlichen.",
        "Moment, lies den Satz noch einmal genau.",
        "Warte kurz, überleg nochmal.",
        "Nicht aufgeben! Schau mal hier."
    ],
    "correction_success": [
        "Perfekt korrigiert!",
        "Siehst du, geht doch!",
        "Klasse, jetzt passt der Satz!",
        "Super nachgedacht!"
    ],
    "praise": [
        "Genau richtig!",
        "Klasse!",
        "Spitze!",
        "Hervorragend gelöst!"
    ]
}

class PhrasePoolManager:
    def __init__(self, storage_dir: Path = AUDIO_PHRASES_DIR):
        self.storage_dir = storage_dir
        self.catalog_file = self.storage_dir / "phrases_catalog.json"
        self.recent_used: Dict[str, List[str]] = {}
        self.is_busy_with_live_task: bool = False
        self._ensure_storage()

    def _ensure_storage(self):
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        for cat in DEFAULT_PHRASES.keys():
            (self.storage_dir / cat).mkdir(parents=True, exist_ok=True)
        if not self.catalog_file.exists():
            self._init_catalog()

    def _init_catalog(self):
        catalog = {}
        for cat, phrases in DEFAULT_PHRASES.items():
            catalog[cat] = []
            for text in phrases:
                pid = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
                catalog[cat].append({
                    "id": pid,
                    "text": text,
                    "audio_filename": f"{pid}.mp3",
                    "use_count": 0
                })
        with open(self.catalog_file, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)

    def _load_catalog(self) -> Dict[str, List[Dict[str, Any]]]:
        if not self.catalog_file.exists():
            self._init_catalog()
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            self._init_catalog()
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                return json.load(f)

    def _save_catalog(self, catalog: Dict[str, List[Dict[str, Any]]]):
        try:
            with open(self.catalog_file, "w", encoding="utf-8") as f:
                json.dump(catalog, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Fehler beim Speichern des Phrasen-Katalogs: {e}")

    def get_audio_base64_for_phrase(self, category: str, phrase_item: Dict[str, Any]) -> Optional[str]:
        audio_path = self.storage_dir / category / phrase_item["audio_filename"]
        if audio_path.exists():
            try:
                with open(audio_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                logger.warning(f"Fehler beim Lesen der Audio-Phrase: {e}")

        # Falls noch keine MP3 existiert und OpenAI verfügbar ist -> on-demand generieren & cachen
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                tts_res = client.audio.speech.create(
                    model="tts-1",
                    voice="nova",
                    input=phrase_item["text"],
                    response_format="mp3"
                )
                with open(audio_path, "wb") as f:
                    f.write(tts_res.content)
                return base64.b64encode(tts_res.content).decode("utf-8")
            except Exception as e:
                logger.warning(f"Fehler beim Generieren der Audio-Phrase '{phrase_item['text']}': {e}")
                return None
        return None

    def get_phrase(self, category: str) -> Dict[str, Any]:
        """
        Gibt eine Phrase aus dem Pool zurück.
        Stellt sicher, dass sich dieselbe Phrase nicht innerhalb von 2 Durchläufen wiederholt.
        """
        catalog = self._load_catalog()
        phrases = catalog.get(category, [])
        if not phrases:
            # Fallback
            default_list = DEFAULT_PHRASES.get(category, ["Sehr gut!"])
            text = random.choice(default_list)
            return {"id": "fb_1", "text": text, "audio_base64": None}

        recent = self.recent_used.get(category, [])
        # Filtere Phrasen, die nicht in recent liegen
        candidates = [p for p in phrases if p["id"] not in recent]
        if not candidates:
            # Wenn alle kürzlich genutzt wurden, wähle die am längsten nicht genutzte
            candidates = phrases

        # Zufällig aus den Kandidaten wählen
        selected = random.choice(candidates)
        selected_id = selected["id"]

        # Recent History aktualisieren (maximal die letzten 2 merken)
        if category not in self.recent_used:
            self.recent_used[category] = []
        self.recent_used[category].append(selected_id)
        if len(self.recent_used[category]) > 2:
            self.recent_used[category].pop(0)

        # Counter inkrementieren
        selected["use_count"] = selected.get("use_count", 0) + 1
        self._save_catalog(catalog)

        audio_b64 = self.get_audio_base64_for_phrase(category, selected)

        return {
            "id": selected_id,
            "category": category,
            "text": selected["text"],
            "audio_base64": audio_b64
        }


# Singleton Instanz
phrase_pool_manager = PhrasePoolManager()
