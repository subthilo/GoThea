#!/usr/bin/env python3
"""
Interaktiver Terminal-Chat mit GoThea.
Standard-Modell: gpt-6-luna.

Befehle:
- /subject <deutsch|mathe|geschichte|bio> -> Fachdidaktik wechseln!
- /model <luna|sol|astra|5.4>             -> Modell wechseln
- /reset                                  -> Verlauf zurücksetzen
- exit / quit                             -> Chat beenden
"""

import os
import sys
import argparse
from pathlib import Path

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine
from experiments.openai_study.core.prompts import (
    get_socratic_prompt_for_subject,
    list_supported_subjects,
    SUBJECT_ALIAS_MAP,
)


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


def print_subject_overview():
    """Gibt eine strukturierte Übersicht aller 23 Schulfächer aus."""
    subjects = list_supported_subjects()
    categories = {}
    for key, data in subjects.items():
        cat = data.get("category", "Allgemein")
        categories.setdefault(cat, []).append((key, data["name"], data["icon"]))

    print("\n📚 Verfügbare Schulfächer für GoThea (Klassen 1–13 / Gymnasialer Fächerkanon):")
    print("-" * 74)
    for cat, items in categories.items():
        item_str = ", ".join(f"{icon} {name} (`/subject {key}`)" for key, name, icon in items)
        print(f"  • {cat:15}: {item_str}")
    print("-" * 74)
    print("  Tipp: Du kannst auch Kürzel nutzen (z. B. `/subject inf`, `/subject wat`, `/subject la`).\n")


def main():
    default_env_model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    parser = argparse.ArgumentParser(description="GoThea Sokratischer Live-Chat")
    parser.add_argument(
        "--model",
        default=default_env_model,
        help="OpenAI Modell (Standard: gpt-6-luna)",
    )
    parser.add_argument(
        "--subject",
        default="math",
        help="Schulfach (z. B. math, deutsch, geschichte, bio, informatik, latein, wat...)",
    )
    args = parser.parse_args()

    active_model = normalize_model_name(args.model)
    active_subject = args.subject.lower().strip()

    all_subs = list_supported_subjects()
    mapped_key = SUBJECT_ALIAS_MAP.get(active_subject, "math")
    sub_meta = all_subs.get(mapped_key, {"name": active_subject.capitalize(), "icon": "📚"})

    print("=" * 74)
    print(f"🦉 GoThea – Sokratischer Live-Chat ({sub_meta['icon']} {sub_meta['name'].upper()} | Modell: {active_model})")
    print("=" * 74)
    print("Rolle: Schülerin (7. Klasse Gymnasium Brandenburg)")
    print("Didaktik aktiv: Lesbarkeits-Pflicht (kein Roh-LaTeX!), Audio-Tauglichkeit, Scaffolding")
    print("Befehle:")
    print("  /subject <fach>         -> Fach wechseln (oder `/subjects` für die Gesamtübersicht)")
    print("  /model <luna|sol|astra> -> Modell wechseln")
    print("  /reset                  -> Verlauf zurücksetzen")
    print("  exit / quit             -> Chat beenden\n")

    engine = OpenAISocraticEngine(default_model=active_model)
    current_system_prompt = get_socratic_prompt_for_subject(active_subject)
    history = [{"role": "system", "content": current_system_prompt}]

    while True:
        try:
            user_input = input("👧 Du (Schülerin): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBis zum nächsten Mal! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("Chat beendet. 👋")
            break

        # Fachübersicht oder Fachwechsel
        if user_input.lower() in ("/subjects", "/faecher", "/fächer"):
            print_subject_overview()
            continue

        if user_input.startswith("/subject"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                active_subject = parts[1].strip().lower()
                current_system_prompt = get_socratic_prompt_for_subject(active_subject)
                history = [{"role": "system", "content": current_system_prompt}]
                mapped = SUBJECT_ALIAS_MAP.get(active_subject, "math")
                meta = all_subs.get(mapped, {"name": active_subject.capitalize(), "icon": "📚"})
                print(f"📚 Fach gewechselt zu: {meta['icon']} {meta['name']} (Spezifischer Fachdidaktik-Prompt aktiv)\n")
            else:
                mapped = SUBJECT_ALIAS_MAP.get(active_subject, "math")
                meta = all_subs.get(mapped, {"name": active_subject.capitalize(), "icon": "📚"})
                print(f"Aktuelles Fach: {meta['icon']} {meta['name']}")
                print_subject_overview()
            continue

        # Modell wechseln
        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                active_model = normalize_model_name(parts[1])
                engine.default_model = active_model
                print(f"🔄 Modell gewechselt zu: {active_model}\n")
            else:
                print(f"Aktuelles Modell: {active_model} (Mögliche Optionen: luna, sol, astra)\n")
            continue

        if user_input.lower() == "/reset":
            history = [{"role": "system", "content": current_system_prompt}]
            print("✨ Gesprächsverlauf zurückgesetzt.\n")
            continue

        history.append({"role": "user", "content": user_input})
        print(f"\n🦉 GoThea ({active_subject.upper()} | {active_model}): ", end="", flush=True)

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
