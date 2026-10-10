#!/usr/bin/env python3
"""
Testskript für die Bildgenerierung mit OpenAI (Standard: gpt-image-2.5-sunburst).
Verwendung:
  .venv/bin/python experiments/openai_study/scratchpad/test_image_gen.py "Dein Bild-Prompt hier"
"""

import sys
import argparse
from pathlib import Path

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine


def main():
    parser = argparse.ArgumentParser(description="GoThea Bildgenerierung mit OpenAI")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Eine freundliche kleine blaue Eule mit runder Brille und Notizbuch, Vektor-Grafik, App-Icon-Stil",
        help="Beschreibung des Bildes",
    )
    parser.add_argument(
        "--model",
        default="gpt-image-2.5-sunburst",
        help="Bildmodell (z. B. gpt-image-2.5-sunburst, gpt-image-2.5-flare, gpt-image-2)",
    )
    parser.add_argument(
        "--out",
        default="experiments/openai_study/samples/generated_sample.png",
        help="Speicherpfad für das Bild",
    )
    args = parser.parse_args()

    print("🎨 [GoThea Feasibility Study] – Bildgenerierung")
    print("-----------------------------------------------")
    print(f"Modell:  {args.model}")
    print(f"Prompt:  \"{args.prompt}\"")
    print(f"Ziel:    {args.out}\n")
    print("⏳ Generiere Bild via OpenAI API (bitte kurz warten)...")

    engine = OpenAISocraticEngine()

    try:
        out_path = Path(args.out)
        img_bytes = engine.generate_image(
            prompt=args.prompt,
            model=args.model,
            save_path=out_path,
        )
        print(f"\n✅ Bild erfolgreich erzeugt und gespeichert:")
        print(f"   file://{out_path.resolve()} ({len(img_bytes)} Bytes)")
    except Exception as e:
        print(f"\n❌ Fehler bei der Bildgenerierung: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
