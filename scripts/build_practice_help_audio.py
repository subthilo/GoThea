"""Spricht vorab ein, was die Übungen vorlesen: die Anleitungen hinter dem ?-Knopf (frontend/hilfe/uebungen.json →
hilfe/audio/) und jeden Satz der Erklär-Stufe (``erklaerung`` in den Übungsdaten → hilfe/saetze/<Fingerabdruck>.m4a).

Einmal vorab erzeugt und mit dem Frontend ausgeliefert: Thea hört alles sofort, ohne Wartezeit und ohne KI-Aufruf
im Betrieb. Stimme wie Luna (services/llm.speech_wav, mit fester Pause zwischen den Sätzen). Neu eingesprochen wird
nur, was sich geändert hat (Fingerabdruck: services/spoken_audio.py); Dateien, die niemand mehr braucht, werden
gelöscht. afconvert (Mac) verkleinert das WAV zu AAC (.m4a).

Aufruf (am Mac, Schlüssel aus experiments/openai_study/.env):
    .venv/bin/python scripts/build_practice_help_audio.py [--force]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
    """Anleitungen: Schlüssel '<typ>_<stufe>' → Text."""
    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    return {f"{typ}_{stage}": text for typ, stages in data.items() if not typ.startswith("_")
            for stage, text in stages.items()}


def explanation_texts() -> set:
    """Jeder Satz, den eine Erklär-Stufe vorliest (alle Übungen, auch Entwürfe)."""
    from backend.app.services import explanations, practice_exercises
    return {t for ex in practice_exercises._load_all().values() if ex.get("erklaerung")
            for t in explanations.spoken_texts(ex)}


def fingerprint(text: str, voice: str, model: str) -> str:
    from backend.app.services.spoken_audio import audio_key
    return audio_key(text, voice, model)


def _speak(text: str, target: Path) -> None:
    from backend.app.services import llm
    wav = llm.speech_wav(text, purpose="practice_help_audio")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.wav"
        src.write_bytes(wav)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "48000", str(src), str(target)], check=True)


def main(force: bool = False) -> None:
    _load_key()
    from backend.app import config
    from backend.app.services import llm
    from backend.app.services.spoken_audio import SENTENCE_DIR, audio_key

    if not llm.is_available():
        sys.exit("Kein OPENAI_API_KEY – Abbruch.")
    if shutil.which("afconvert") is None:
        sys.exit("afconvert fehlt (nur am Mac) – Abbruch.")

    # Anleitungen (feste Dateinamen je Typ und Stufe, Fingerabdruck im Manifest)
    AUDIO.mkdir(parents=True, exist_ok=True)
    old = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    new = {}
    for key, text in entries().items():
        fp = fingerprint(text, config.OPENAI_TTS_VOICE, config.OPENAI_TTS_MODEL)
        prev = old.get(key)
        name = f"{key}.m4a"
        if not force and prev and prev["fp"] == fp and (AUDIO / prev["datei"]).is_file():
            new[key] = prev
            continue
        _speak(text, AUDIO / name)
        new[key] = {"fp": fp, "datei": name}
        print(f"Anleitung eingesprochen: {key}")
    for key, prev in old.items():
        if key not in new:
            (AUDIO / prev["datei"]).unlink(missing_ok=True)
            print(f"Anleitung entfernt: {key}")
    MANIFEST.write_text(json.dumps(new, ensure_ascii=False, indent=1, sort_keys=True) + "\n")

    # Erklär-Sätze (Dateiname = Fingerabdruck, kein Manifest nötig)
    SENTENCE_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {f"{audio_key(t)}.m4a": t for t in explanation_texts()}
    made = 0
    for name, text in sorted(wanted.items()):
        target = SENTENCE_DIR / name
        if force or not target.is_file():
            _speak(text, target)
            made += 1
    removed = 0
    for path in SENTENCE_DIR.glob("*.m4a"):
        if path.name not in wanted:
            path.unlink()
            removed += 1
    print(f"{len(new)} Anleitungen; Erklär-Sätze: {len(wanted)} ({made} neu, {removed} entfernt).")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
