#!/usr/bin/env python3
"""
Testskript für die Vision-Diagnose von Whiteboard-Handschrift / Aufgaben.
Erzeugt bei Bedarf ein synthetisches Handschrift-Bild (oder lädt ein bestehendes),
sendet es an gpt-4o und prüft die Schritt-für-Schritt Diagnose.
"""

import sys
import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine
from experiments.openai_study.core.prompts import DIAGNOSE_JSON_SYSTEM_PROMPT


def create_synthetic_handwritten_sample(output_path: Path) -> Path:
    """
    Erstellt ein synthetisches Bild eines handschriftlichen Rechenwegs mit einem Denkfehler:
    Aufgabe: 2 * (3x - 5) + 4 = 18
    Zeile 1: 6x - 5 + 4 = 18   <-- Fehler: 2 * (-5) wurde vergessen auszumultiplizieren!
    Zeile 2: 6x - 1 = 18
    """
    img = Image.new("RGB", (900, 450), color="#1e222b")  # Kreidetafel-Look
    draw = ImageDraw.Draw(img)

    text_lines = [
        "Aufgabe: 2 * (3x - 5) + 4 = 18",
        "",
        "Zeile 1:  6x - 5 + 4 = 18",
        "Zeile 2:  6x - 1 = 18",
    ]

    y = 50
    for line in text_lines:
        draw.text((60, y), line, fill="#f8fafc")
        y += 60

    img.save(output_path, "PNG")
    return output_path


def main():
    print("🦉 [GoThea Feasibility Study] – Vision-Diagnose Test")
    print("--------------------------------------------------")

    engine = OpenAISocraticEngine()

    try:
        engine.get_client()
    except ValueError as e:
        print(f"❌ Fehler: {e}")
        return 1

    sample_dir = Path(__file__).resolve().parent.parent / "samples"
    sample_dir.mkdir(exist_ok=True)
    sample_image = sample_dir / "math_sample_distributive_error.png"

    if not sample_image.exists():
        print(f"🎨 Erstelle synthetische Rechenaufgabe mit Denkfehler: {sample_image.name}")
        create_synthetic_handwritten_sample(sample_image)

    print(f"👁️ Sende Tafelbild an Vision-LLM (gpt-4o) zur Schritt-für-Schritt Diagnose...")

    prompt = (
        "Analysiere diese Rechnung einer 7.-Klässlerin auf der Tafel. "
        "Finde den allerersten Rechenschritt, an dem ein Denkfehler aufgetreten ist. "
        "Formuliere einen sokratischen Hinweis nach den Systemregeln."
    )

    try:
        raw_response = engine.send_prompt(
            prompt_text=prompt,
            image_or_pdf=sample_image,
            system_prompt=DIAGNOSE_JSON_SYSTEM_PROMPT,
            model="gpt-4o",
            temperature=0.1,
            max_tokens=1000,
            high_detail=True,
        )

        print("\n📥 Empfangene strukturierte Diagnose (Rohdaten):")
        print(raw_response)

        # Versuche JSON zu parsen
        clean_json = raw_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        data = json.loads(clean_json.strip())

        print("\n✨ Geparste Diagnose:")
        print(f"  Status:             {data.get('status')}")
        print(f"  Erster Fehler:      Zeile {data.get('first_error_line')}")
        print(f"  Lob:                {data.get('positive_praise')}")
        print(f"  Interner Fehler:    {data.get('error_description_internal')}")
        print(f"  Sokratischer Tipp:  \"{data.get('socratic_hint')}\"")
        print(f"  Scaffolding-Stufe:  Stufe {data.get('scaffolding_stage')}")

        print("\n✅ Vision-Diagnose erfolgreich durchgeführt!")
    except Exception as e:
        print(f"❌ Fehler bei Vision-Diagnose: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
