#!/usr/bin/env python3
"""
Interaktiver Terminal-Chat mit GoThea.
Standard-Modell: gpt-6-luna (schnell & reaktionsstark).

Befehle während des Chats:
- /model sol   -> wechselt zu gpt-6.1-sol
- /model astra -> wechselt zu gpt-6-astra
- /model luna  -> wechselt zu gpt-6-luna
- /reset       -> löscht den bisherigen Gesprächsverlauf
- exit / quit  -> beendet den Chat
"""

import os
import sys
import argparse
from pathlib import Path

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine
from experiments.openai_study.core.prompts import SOCRATIC_TUTOR_SYSTEM_PROMPT


def normalize_model_name(name: str) -> str:
    alias = name.strip().lower()
    if alias in ("luna", "6-luna", "gpt-6-luna"):
        return "gpt-6-luna"
    if alias in ("sol", "6-sol", "6.1-sol", "gpt-6.1-sol", "gpt-6-sol"):
        return "gpt-6.1-sol"
    if alias in ("astra", "6-astra", "gpt-6-astra"):
        return "gpt-6-astra"
    if alias in ("5.4", "gpt-5.4"):
        return "gpt-5.4"
    if alias in ("4o", "gpt-4o"):
        return "gpt-4o"
    return name.strip()


def main():
    default_env_model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    parser = argparse.ArgumentParser(description="GoThea Sokratischer Live-Chat")
    parser.add_argument(
        "--model",
        default=default_env_model,
        help="OpenAI Modell (Standard: gpt-6-luna)",
    )
    args = parser.parse_args()

    active_model = normalize_model_name(args.model)

    print("=" * 72)
    print(f"🦉 GoThea – Sokratischer Live-Chat (Aktives Modell: {active_model})")
    print("=" * 72)
    print("Rolle: Schülerin (7. Klasse Gymnasium Brandenburg)")
    print("Befehle:")
    print("  /model <luna|sol|astra|5.4>  -> Modell mitten im Chat wechseln")
    print("  /reset                       -> Tafel & Chat zurücksetzen")
    print("  exit / quit                  -> Chat beenden\n")

    engine = OpenAISocraticEngine(default_model=active_model)
    history = [{"role": "system", "content": SOCRATIC_TUTOR_SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("👧 Du (Schülerin): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBis zum nächsten Mal! 👋")
            break

        if not user_input:
            continue

        # Chat-Befehle abfangen
        if user_input.lower() in ("exit", "quit", "q"):
            print("Chat beendet. 👋")
            break

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                active_model = normalize_model_name(parts[1])
                engine.default_model = active_model
                print(f"🔄 Modell gewechselt zu: {active_model}\n")
            else:
                print(f"Aktuelles Modell: {active_model} (Mögliche Optionen: luna, sol, astra, 5.4)\n")
            continue

        if user_input.lower() == "/reset":
            history = [{"role": "system", "content": SOCRATIC_TUTOR_SYSTEM_PROMPT}]
            print("✨ Gesprächsverlauf zurückgesetzt. Frische Tafel!\n")
            continue

        history.append({"role": "user", "content": user_input})
        print(f"\n🦉 GoThea ({active_model}): ", end="", flush=True)

        try:
            client = engine.get_client()

            kwargs = {
                "model": active_model,
                "messages": history,
                "max_completion_tokens": 400,
                "stream": True,
            }
            if "gpt-6" not in active_model and not active_model.startswith("o"):
                kwargs["temperature"] = 0.2

            stream = client.chat.completions.create(**kwargs)

            full_response = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content if chunk.choices else None
                if content:
                    print(content, end="", flush=True)
                    full_response += content

            print("\n")
            history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            print(f"\n❌ Fehler: {e}\n")


if __name__ == "__main__":
    main()
