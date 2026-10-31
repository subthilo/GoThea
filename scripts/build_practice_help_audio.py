"""Spricht die Anleitungen hinter dem ?-Knopf der Übungen ein (frontend/hilfe/uebungen.json → Audio-Dateien).

Einmal vorab erzeugt und mit dem Frontend ausgeliefert: Thea hört sie sofort, ohne Wartezeit und ohne KI-Aufruf
im Betrieb. Stimme wie Luna (services/llm.speech_wav, mit fester Pause zwischen den Sätzen). Neu eingesprochen
werden nur Texte, die sich geändert haben (Fingerabdruck in manifest.json); Dateien zu entfernten Texten werden
gelöscht. Auf dem Mac verkleinert afconvert das WAV zu AAC (.m4a), sonst bleibt es WAV.

Aufruf (lokal, Schlüssel aus experiments/openai_study/.env):
    .venv/bin/python scripts/build_practice_help_audio.py [--force]
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXTS = ROOT / "frontend" / "hilfe" / "uebungen.json"
AUDIO = ROOT / "frontend" / "hilfe" / "audio"
MANIFEST = AUDIO / "manifest.json"


def _load_key() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    env = ROOT / "experiments" / "openai_study" / ".env"
    if env.is_file():
        for line in env.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY="):
                os.environ["OPENAI_API_KEY"] = line.split("=", 1)[1].strip().strip('"')


def entries() -> dict:
    """Schlüssel '<typ>_<stufe>' → Text."""
    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    return {f"{typ}_{stage}": text for typ, stages in data.items() if not typ.startswith("_")
            for stage, text in stages.items()}


def fingerprint(text: str, voice: str, model: str) -> str:
    """Was die Stimme wirklich bekommt: vorbereiteter Text, Modell, Stimme und (bei neueren Modellen) Anweisung."""
    sys.path.insert(0, str(ROOT))
    from backend.app import config
    from backend.app.services.speech_text import spoken_german

    instructions = "" if model.startswith("tts-1") else config.OPENAI_TTS_INSTRUCTIONS
    key = f"{model}|{voice}|{instructions}|pause {config.OPENAI_TTS_PAUSE_MS}|{spoken_german(text)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def main(force: bool = False) -> None:
    _load_key()
    sys.path.insert(0, str(ROOT))
    from backend.app import config
    from backend.app.services import llm

    if not llm.is_available():
        sys.exit("Kein OPENAI_API_KEY – Abbruch.")
    AUDIO.mkdir(parents=True, exist_ok=True)
    old = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    use_aac = shutil.which("afconvert") is not None
    new = {}
    for key, text in entries().items():
        fp = fingerprint(text, config.OPENAI_TTS_VOICE, config.OPENAI_TTS_MODEL)
        prev = old.get(key)
        if not force and prev and prev["fp"] == fp and (AUDIO / prev["datei"]).is_file():
            new[key] = prev
            continue
        wav = llm.speech_wav(text, purpose="practice_help_audio")
        name = f"{key}.m4a" if use_aac else f"{key}.wav"
        if use_aac:
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "in.wav"
                src.write_bytes(wav)
                subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "48000", str(src), str(AUDIO / name)],
                               check=True)
        else:
            (AUDIO / name).write_bytes(wav)
        if prev and prev["datei"] != name:
            (AUDIO / prev["datei"]).unlink(missing_ok=True)
        new[key] = {"fp": fp, "datei": name}
        print(f"eingesprochen: {key} ({(AUDIO / name).stat().st_size // 1024} KB)")
    for key, prev in old.items():
        if key not in new:
            (AUDIO / prev["datei"]).unlink(missing_ok=True)
            print(f"entfernt: {key}")
    MANIFEST.write_text(json.dumps(new, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"{len(new)} Anleitungen, Manifest aktuell.")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
