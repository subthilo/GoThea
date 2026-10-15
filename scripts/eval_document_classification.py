"""
Misst die Dokument-Klassifizierung gegen ein von Hand geprüftes Soll-Ergebnis.

Aufruf (Daten bleiben außerhalb des Repos):
    DATA_DIR=/tmp/eval_data .venv/bin/python scripts/eval_document_classification.py manifest.json --models gpt-4o-mini,gpt-6-luna

manifest.json: [{"file": "...pdf", "expected_kind": "Test", "expected_subject": "Mathematik",
                 "expected_solution_pages": [2], "expected_graded": true, "expected_worked": true}, ...]
Felder außer file/expected_kind sind optional.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypdf import PdfReader  # noqa: E402

from backend.app.services.document_analyzer import query_openai_analyzer  # noqa: E402
from backend.app.services.document_kinds import normalize_kind  # noqa: E402
from backend.app.services.page_renderer import page_renderer  # noqa: E402


def extract_text(path: Path) -> str:
    try:
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    except Exception:
        return ""


def evaluate(model: str, cases: list) -> dict:
    stats = {"kind": 0, "subject": 0, "subject_n": 0, "solutions": 0, "solutions_n": 0,
             "graded": 0, "graded_n": 0, "worked": 0, "worked_n": 0, "prompt_tokens": 0, "completion_tokens": 0, "failed": 0}
    print(f"\n=== {model} ===")
    for case in cases:
        path = Path(case["file"])
        raw = query_openai_analyzer(path, extract_text(path), "application/pdf", model, path.name)
        if not raw:
            stats["failed"] += 1
            print(f"  FEHLER   {path.name}")
            continue
        usage = raw.get("_usage", {})
        stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
        stats["completion_tokens"] += usage.get("completion_tokens", 0)

        kind = normalize_kind(raw.get("dokumentart"))
        ok_kind = kind == case["expected_kind"]
        stats["kind"] += ok_kind
        marks = ["✓" if ok_kind else "✗"]
        if "expected_subject" in case:
            ok = (raw.get("fach") or "").strip() == case["expected_subject"]
            stats["subject"] += ok
            stats["subject_n"] += 1
            marks.append("" if ok else f"Fach:{raw.get('fach')}")
        if "expected_solution_pages" in case:
            ok = sorted(raw.get("loesungsseiten") or []) == sorted(case["expected_solution_pages"])
            stats["solutions"] += ok
            stats["solutions_n"] += 1
            marks.append("" if ok else f"Lösungsseiten:{raw.get('loesungsseiten')}")
        for key, field in (("graded", "von_lehrkraft_bewertet"), ("worked", "von_schuelerin_bearbeitet")):
            if f"expected_{key}" in case:
                ok = bool(raw.get(field)) == case[f"expected_{key}"]
                stats[key] += ok
                stats[f"{key}_n"] += 1
                marks.append("" if ok else f"{key}:{raw.get(field)}")
        detail = " ".join(m for m in marks[1:] if m)
        print(f"  {marks[0]} {kind:13} (soll {case['expected_kind']:13}) {raw.get('inhaltlicher_titel', '')[:45]:45} {detail}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--models", default="gpt-4o-mini")
    args = parser.parse_args()
    cases = json.loads(Path(args.manifest).read_text())
    page_renderer.start()
    results = {m: evaluate(m, cases) for m in args.models.split(",")}
    page_renderer.stop()

    n = len(cases)
    print("\n=== Zusammenfassung ===")
    for model, s in results.items():
        def pct(a, b):
            return f"{a}/{b}" if b else "-"
        print(f"{model:14} Art {pct(s['kind'], n)} | Fach {pct(s['subject'], s['subject_n'])} | "
              f"Lösungsseiten {pct(s['solutions'], s['solutions_n'])} | bewertet {pct(s['graded'], s['graded_n'])} | "
              f"bearbeitet {pct(s['worked'], s['worked_n'])} | Tokens {s['prompt_tokens']}+{s['completion_tokens']} | Fehler {s['failed']}")


if __name__ == "__main__":
    main()
