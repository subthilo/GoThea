"""Vorab eingesprochene Sätze (Anleitungen hinter dem ?-Knopf, Erklär-Stufe): Fingerabdruck und Ablageort.

Der Fingerabdruck umfasst alles, was den Klang bestimmt – vorbereiteter Text (services/speech_text.py), Modell,
Stimme, Anweisung, Satzpause. Ändert sich eins davon, gibt es einen neuen Fingerabdruck und
scripts/build_practice_help_audio.py spricht neu ein.
"""
import hashlib
from pathlib import Path

from backend.app import config
from backend.app.services.speech_text import spoken_german

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
SENTENCE_DIR = FRONTEND / "hilfe" / "saetze"   # Erklär-Sätze, Dateiname = Fingerabdruck
SENTENCE_URL = "/static/hilfe/saetze/"


def audio_key(text: str, voice: str = None, model: str = None) -> str:
    voice = voice or config.OPENAI_TTS_VOICE
    model = model or config.OPENAI_TTS_MODEL
    instructions = "" if model.startswith("tts-1") else config.OPENAI_TTS_INSTRUCTIONS
    key = f"{model}|{voice}|{instructions}|pause {config.OPENAI_TTS_PAUSE_MS}|{spoken_german(text)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def sentence_url(text: str) -> str:
    return f"{SENTENCE_URL}{audio_key(text)}.m4a"
