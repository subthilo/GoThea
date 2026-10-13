#!/usr/bin/env python3
"""
Testskript für die Video-Generierung mit OpenAI Sora 2 (Standard: sora-2, 4 Sekunden).
Verwendung:
  .venv/bin/python experiments/openai_study/scratchpad/test_video_gen.py "Dein Video-Prompt hier"
"""

import sys
import argparse
from pathlib import Path

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine


def main():
    parser = argparse.ArgumentParser(description="GoThea Video-Generierung mit OpenAI Sora 2")
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "Humorvoller 3D-Cartoon: Eine kleine blaue Eule mit runder Brille schaut erstaunt auf "
            "eine riesige Mathe-Klammer ( ), die plötzlich lebendig wird und wie ein Mund zuschnappt. "
            "Die Eule kichert und setzt einen Haken dahinter. Bunt, Pixar-Animationsstil, heiter."
        ),
        help="Beschreibung des Videos",
    )
    parser.add_argument(
        "--seconds",
        choices=["4", "8", "12"],
        default="4",
        help="Dauer des Clips in Sekunden (Standard: 4)",
    )
    parser.add_argument(
        "--size",
        choices=["1280x720", "720x1280", "1792x1024", "1024x1792"],
        default="1280x720",
        help="Auflösung (Standard: 1280x720 Querformat)",
    )
    parser.add_argument(
        "--model",
        default="sora-2",
        help="Video-Modell (z. B. sora-2, sora-2-pro)",
    )
    parser.add_argument(
        "--out",
        default="experiments/openai_study/samples/gothea_cartoon.mp4",
        help="Speicherort für das generierte MP4-Video",
    )
    args = parser.parse_args()

    print("🎬 [GoThea Feasibility Study] – Sora 2 Video-Generierung")
    print("---------------------------------------------------------")
    print(f"Modell:  {args.model}")
    print(f"Dauer:   {args.seconds} Sekunden ({args.size})")
    print(f"Prompt:  \"{args.prompt}\"")
    print(f"Ziel:    {args.out}\n")
    print("⏳ Starte Video-Generierung via OpenAI Sora API...")
    print("   (Videogenerierung dauert in der Regel 1–2 Minuten, der Job wird automatisch gepollt...)")

    engine = OpenAISocraticEngine()

    try:
        out_path = Path(args.out)
        video_bytes = engine.generate_video(
            prompt=args.prompt,
            model=args.model,
            seconds=args.seconds,
            size=args.size,
            save_path=out_path,
        )
        print(f"\n🎉 Video erfolgreich erzeugt und heruntergeladen!")
        print(f"   file://{out_path.resolve()} ({len(video_bytes)} Bytes)")
    except Exception as e:
        print(f"\n❌ Fehler bei der Videogenerierung: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
