#!/usr/bin/env python3
"""
Testskript für die Basis-Verbindung zu OpenAI.
Prüft:
1. Ist der API-Key vorhanden?
2. Kann ein einfacher sokratischer Prompt erfolgreich gesendet werden?
3. Funktioniert das Streaming?
"""

import sys
from pathlib import Path

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine
from experiments.openai_study.core.prompts import SOCRATIC_TUTOR_SYSTEM_PROMPT


def main():
    print("🦉 [GoThea Feasibility Study] – OpenAI Verbindungstest")
    print("-----------------------------------------------------")

    engine = OpenAISocraticEngine()

    try:
        # 1. Client prüfen
        client = engine.get_client()
        masked_key = f"{client.api_key[:7]}...{client.api_key[-4:]}" if len(client.api_key) > 12 else "***"
        print(f"🔑 API-Key erkannt: {masked_key}")
    except ValueError as e:
        print(f"❌ Fehler: {e}")
        print("\n💡 Bitte erstelle eine Datei 'experiments/openai_study/.env' mit:")
        print("OPENAI_API_KEY=sk-proj-...")
        return 1

    # 2. Test-Prompt (Sokratischer Mathe-Test)
    test_student_question = (
        "Ich rechne gerade die Aufgabe: 3 * (x - 4) = 15.\n"
        "Mein erster Schritt war: 3x - 4 = 15. Stimmt das so?"
    )

    print(f"\n👧 Schülerin fragt:\n\"{test_student_question}\"\n")
    print("🦉 GoThea denkt nach (Streaming-Antwort via gpt-4o-mini)...\n")
    print("Antwort: ", end="", flush=True)

    try:
        for chunk in engine.stream_prompt(
            prompt_text=test_student_question,
            system_prompt=SOCRATIC_TUTOR_SYSTEM_PROMPT,
            model="gpt-4o-mini",
            temperature=0.2,
        ):
            print(chunk, end="", flush=True)
        print("\n\n✅ Verbindung und Sokratischer Prompt erfolgreich getestet!")
    except Exception as e:
        print(f"\n❌ Fehler bei der Anfrage an OpenAI: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
