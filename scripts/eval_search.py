"""Misst die Materialsuche an echten Fragen: Steht eine richtige Seite unter den ersten Treffern?

Aufruf:
  .venv/bin/python scripts/eval_search.py fragen.json [--db pfad/zur/app_data.db] [--title-weight 6]

fragen.json (Soll-Daten liegen außerhalb des Repos):
  [{"q": "Wie geht der Dreisatz?", "relevant": [["mat_ab06df58", 1], ...], "hard": "optional: warum schwer"}, ...]

Ausgabe: je Frage der Rang der ersten richtigen Seite, dazu Treffer@1, Treffer@3 und MRR (mittlerer
Kehrwert des Rangs). Gesucht wird wie für Thea, also ohne Lösungen.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("questions")
    parser.add_argument("--db", help="SQLite-Datei (Standard: Datenbank der Umgebung)")
    parser.add_argument("--title-weight", type=float)
    parser.add_argument("--summary-weight", type=float)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true", help="die ersten Treffer jeder Frage zeigen")
    args = parser.parse_args()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app.services import material_search

    if args.db:
        engine = create_engine(f"sqlite:///{args.db}")
    else:
        from backend.app.database import engine
    material_search.ensure_search_index(engine)
    if args.title_weight is not None:
        material_search.TITLE_WEIGHT = args.title_weight
    if args.summary_weight is not None:
        material_search.SUMMARY_WEIGHT = args.summary_weight
    db = sessionmaker(bind=engine)()

    cases = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    at1 = at3 = 0
    rr = 0.0
    for case in cases:
        relevant = {(m, p) for m, p in case["relevant"]}
        hits = material_search.search(db, case["q"], limit=args.top)
        ranks = [i for i, h in enumerate(hits, start=1) if (h.material_id, h.page) in relevant]
        rank = ranks[0] if ranks else None
        at1 += rank == 1
        at3 += bool(rank and rank <= 3)
        rr += 1 / rank if rank else 0
        mark = f"#{rank}" if rank else "–"
        print(f"{mark:>4}  {case['q']}" + (f"   ({case['hard']})" if case.get("hard") else ""))
        if args.verbose or not rank:
            for i, h in enumerate(hits[:3], start=1):
                print(f"        {i}. {h.label}  [{h.material_id} S{h.page}]")
    n = len(cases)
    print(f"\nTreffer@1 {at1}/{n}   Treffer@3 {at3}/{n}   MRR {rr / n:.2f}")


if __name__ == "__main__":
    main()
