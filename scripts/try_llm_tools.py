"""Probiert Streaming und Werkzeug-Aufrufe der KI-Schicht an echten Unterlagen aus (ohne Tutor).

Aufruf (Staging auf dem Pi):
  cd ~/GoThea-staging && .venv/bin/python scripts/try_llm_tools.py "Wie geht der Dreisatz?" [--model gpt-6-luna]

Zeigt die Antwort, wie sie ankommt, jede Suche der KI mit ihren Fundstellen und am Ende Tokens und Dauer.
Gesucht wird wie für Thea, also ohne Lösungen. Jeder Aufruf kostet (Protokoll: DATA_DIR/logs/llm_usage.jsonl).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--model", help="Standard: OPENAI_MODEL")
    parser.add_argument("--max-rounds", type=int, default=4)
    args = parser.parse_args()

    from backend.app.database import SessionLocal, engine
    from backend.app.prompts.luna_tools import PROBE_SYSTEM_PROMPT
    from backend.app.services import llm, luna_tools, material_search

    if not llm.is_available():
        sys.exit("Kein OpenAI-API-Schlüssel (OPENAI_API_KEY) konfiguriert.")
    material_search.ensure_search_index(engine)
    db = SessionLocal()
    messages = [{"role": "system", "content": PROBE_SYSTEM_PROMPT}, {"role": "user", "content": args.question}]
    start = time.monotonic()
    first_text = None
    try:
        for event in llm.chat_stream(messages, purpose="Werkzeug-Probe", tools=[luna_tools.search_tool(db)],
                                     model=args.model, max_rounds=args.max_rounds):
            if event.type == "text":
                if first_text is None:
                    first_text = time.monotonic() - start
                print(event.text, end="", flush=True)
            elif event.type == "tool_call":
                print(f"\n[{time.monotonic() - start:4.1f} s] Suche: {event.arguments}", flush=True)
            elif event.type == "tool_result":
                for hit in event.result.get("treffer", []):
                    print(f"         · {hit['fundstelle']} ({hit['fach']})")
                if event.result.get("hinweis"):
                    print(f"         ! {event.result['hinweis']}")
            elif event.type == "done":
                r = event.reply
                print(f"\n\n{r.model}: {r.prompt_tokens}+{r.completion_tokens} Tokens, {r.seconds:.1f} s gesamt, "
                      f"erstes Textstück nach {first_text or 0:.1f} s")
    except llm.LLMError as e:
        sys.exit(f"\nFehler: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
