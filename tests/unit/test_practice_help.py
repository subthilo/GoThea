"""Anleitungen hinter dem ?-Knopf der Übungen: zu jeder Stufe jedes Typs ein Text und dazu aktuelles Audio."""
import importlib
import json
from pathlib import Path

from backend.app import config
from backend.app.services.spoken_audio import SENTENCE_DIR, audio_key
from scripts.build_practice_help_audio import AUDIO, MANIFEST, TEXTS, entries, explanation_texts, fingerprint

TYPES = sorted(p.stem for p in (Path(__file__).resolve().parents[2] / "backend/app/services/exercise_types").glob("*.py")
               if p.stem not in ("__init__", "common"))


def test_every_stage_of_every_type_has_a_help_text():
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    for typ in TYPES:
        stages = importlib.import_module(f"backend.app.services.exercise_types.{typ}").STAGES
        assert sorted(texts[typ]) == sorted([str(s) for s in stages] + (["check"] if typ == "kurzrechnung" else [])), typ
    assert sorted(k for k in texts if not k.startswith("_")) == TYPES


def test_audio_matches_the_current_texts():
    """Schlägt an, wenn ein Text geändert wurde, ohne scripts/build_practice_help_audio.py laufen zu lassen."""
    manifest = json.loads(MANIFEST.read_text())
    assert sorted(manifest) == sorted(entries())
    for key, text in entries().items():
        assert manifest[key]["fp"] == fingerprint(text, config.OPENAI_TTS_VOICE, config.OPENAI_TTS_MODEL), key
        assert (AUDIO / manifest[key]["datei"]).stat().st_size > 10_000, key


def test_every_sentence_of_the_explanations_is_spoken():
    """Schlägt an, wenn eine Erklärung neu ist oder sich geändert hat, ohne dass das Skript lief."""
    texts = explanation_texts()
    assert texts
    missing = [t for t in texts if not (SENTENCE_DIR / f"{audio_key(t)}.m4a").is_file()]
    assert missing == []
