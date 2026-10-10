#!/usr/bin/env python3
"""
Sicherer Batch-Klassifizierer & Normalisierer für echte Schul-Scans.
WICHTIG:
- Liest NUR die Originale aus 'Schulmaterialien Thea'.
- Rührt die Originale NIEMALS an (kein Ändern, kein Löschen, kein Umbenennen).
- Erstellt Kopien im isolierten Ordner:
    experiments/openai_study/staging_test/
  mit dem perfekten, KI-normierten Dateinamen und Metadaten!
"""

import sys
import os
import json
import shutil
import argparse
from pathlib import Path

# Projektpfad für isolierte Imports bereitstellen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from experiments.openai_study.core.tutor_engine import OpenAISocraticEngine

SOURCE_DEFAULT = "/Users/thilo/Library/Mobile Documents/com~apple~CloudDocs/Schulmaterialien Thea"
TARGET_DIR = Path(__file__).resolve().parent.parent / "staging_test"


def classify_single_file(engine: OpenAISocraticEngine, file_path: Path, model: str = "gpt-6.1-sol") -> dict:
    """Sendet den Scan an die Vision-KI und liefert standardisierte Metadaten."""
    prompt = """Analysiere diesen echten Schul-Scan einer 7.-Klässlerin (Gymnasium Brandenburg).
Lies den Inhalt, die Handschrift oder das Arbeitsblatt und gib mir AUSSCHLIESSLICH folgendes JSON:
{
  "fach": "Mathematik | Physik | Chemie | Biologie | Informatik | Astronomie | Deutsch | Englisch | Französisch | Spanisch | Latein | Russisch | Geschichte | Geografie | Politische Bildung | WAT | LER | Religion | Kunst | Musik | Sport",
  "oberthema": "Das zentrale Schulthema (z. B. Rationale Zahlen, Christianisierung, Akustik, Grammatik...)",
  "dokumentart": "Arbeitsblatt | Hefterseite | Test | Klassenarbeit | Merkblatt",
  "inhaltlicher_titel": "Präziser inhaltlicher Titel",
  "vorgeschlagene_mappe": "Name der thematischen Mappe (z. B. 'Hefter: Bruchrechnung')",
  "normierter_dateiname": "Dateiname nach Schema: [Fach]_[Oberthema]_[Dokumentart]_[Titel].pdf (nur ASCII, keine Umlaute/Leerzeichen)",
  "zusammenfassung": "1-2 Sätze über den Inhalt und Bearbeitungsstand des Blatts"
}
"""

    raw_json = engine.send_prompt(
        prompt_text=prompt,
        image_or_pdf=file_path,
        model=model,
    )

    clean = raw_json.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]

    return json.loads(clean.strip())


def main():
    parser = argparse.ArgumentParser(description="GoThea Sicherer Batch-Scan-Klassifizierer")
    parser.add_argument("--source", default=SOURCE_DEFAULT, help="Quellordner mit den Scans")
    parser.add_argument("--limit", type=int, default=5, help="Anzahl der zu testenden Dateien (Standard: 5)")
    parser.add_argument("--model", default="gpt-6.1-sol", help="Vision-Modell (Standard: gpt-6.1-sol)")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"❌ Quellordner nicht gefunden: {source_path}")
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Alle PDFs aus der Quelle sammeln
    pdf_files = sorted([f for f in source_path.glob("*.pdf") if not f.name.startswith(".")])
    if not pdf_files:
        print("Keine PDF-Dateien im Quellordner gefunden.")
        return 1

    selected_files = pdf_files[: args.limit]

    print("=" * 76)
    print("📁 GoThea – Sicherer Batch-Scan-Normalisierer & Mappen-Klassifizierer")
    print("=" * 76)
    print(f"Quellordner:       {source_path}")
    print(f"Gefundene Scans:   {len(pdf_files)} PDFs")
    print(f"Test-Stichprobe:   {len(selected_files)} Dateien")
    print(f"Ziel-Kopien:       {TARGET_DIR}")
    print("Sicherheits-Status: DIE ORIGINALE WERDEN NICHT VERÄNDERT (NUR KOPIEN!)\n")

    engine = OpenAISocraticEngine()
    results = []

    for idx, pdf in enumerate(selected_files, start=1):
        print(f"[{idx}/{len(selected_files)}] Analysiere: {pdf.name} ... ", end="", flush=True)
        try:
            meta = classify_single_file(engine, pdf, model=args.model)
            norm_name = meta.get("normierter_dateiname", f"Dokument_{idx}.pdf")
            if not norm_name.lower().endswith(".pdf"):
                norm_name += ".pdf"

            # Sichere Kopie im staging_test Verzeichnis anlegen
            dest_file = TARGET_DIR / norm_name
            shutil.copy2(pdf, dest_file)

            # Metadaten-Begleitdatei speichern
            meta_file = TARGET_DIR / f"{norm_name}.json"
            meta_with_orig = {
                "original_filename": pdf.name,
                "original_path": str(pdf),
                **meta
            }
            meta_file.write_text(json.dumps(meta_with_orig, ensure_ascii=False, indent=2), encoding="utf-8")

            results.append(meta_with_orig)
            print(f"✅\n   ➡️ Fach: {meta.get('fach')} | Thema: {meta.get('oberthema')}")
            print(f"   ➡️ Mappe: {meta.get('vorgeschlagene_mappe')}")
            print(f"   ➡️ Neuer Name: {norm_name}\n")

        except Exception as e:
            print(f"❌ Fehler: {e}\n")

    print("=" * 76)
    print(f"🎉 Fertig! {len(results)} Dateien erfolgreich analysiert und sicher als Kopie abgelegt.")
    print(f"Schau dir die Kopien an unter: {TARGET_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
