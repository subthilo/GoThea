# 🦉 GoThea – OpenAI Feasibility Study

Dieses Verzeichnis enthält die **vollständig isolierte Machbarkeitsstudie** für die KI-Integration von GoThea (Sokratischer Tutor, Bildgenerierung, Batch-Scan-Normalisierung).

👉 **[Hier klicken für den ausführlichen Abschlussbericht: FEASIBILITY_STUDY_REPORT.md](FEASIBILITY_STUDY_REPORT.md)**

---

## 📂 Struktur des Studien-Ordners

```text
experiments/openai_study/
├── HANDOVER_ARCHITECTURE.md      # Architektur-Handover für den Gesamtarchitektur-Chat
├── FEASIBILITY_STUDY_REPORT.md   # Ausführlicher Abschlussbericht (Konzept, Architektur, Roadmap)
├── AUTOMATED_TEST_REPORT.md      # Vollautomatisierter Testbericht (15/15 Tests PASS)
├── run_feasibility_tests.py      # Vollständige Test-Automation Runner-Suite
├── README.md                     # Dieses Verzeichnis-README
├── .env                          # Lokaler API-Key & Modell-Konfiguration (in .gitignore)
├── .env.example                  # Vorlage für neue Umgebungen
│
├── core/                         # Wiederverwendbare Kernmodule (spätere App-Komponenten)
│   ├── tutor_engine.py           # OpenAISocraticEngine (GPT-6, Image 2.5, Streaming)
│   └── prompts.py                # Pädagogischer Governor & 23 Fachdidaktiken (111 Kürzel/Aliase)
│
├── scratchpad/                   # Interaktive Testskripte (Terminal-Tools)
│   ├── test_book_splitter.py     # Lehrbuch-Splitter & Master-Child Ingestion
│   ├── interactive_chat.py       # Live-Chat mit /subject, /subjects, /model, /reset
│   ├── test_safe_batch_importer.py # Scan-Normalisierer & Mappen-Klassifizierer (alle 23 Fächer)
│   ├── test_image_gen.py         # Didaktischer Bild- und Lehrblatt-Generator
│   ├── test_vision_diagnose.py   # Handschrift- und Fehlerdiagnose (JSON)
│   ├── test_connection.py        # Schneller Verbindungstest
│   └── test_video_gen.py         # Sora 2 Test (depriorisiert wegen Latenz)
│
├── samples/                      # Generierte Lehrtafeln & Beispiele
│   ├── arbeitsblatt_hebelgesetz.png # Physik-Arbeitsblatt mit Schreibzeilen für Apple Pencil
│   ├── lernblatt_schwebung.png   # Akustische Schwebung mit Formelherleitung
│   ├── doppelspalt_mit_rechnung.png # Doppelspalt mit vollständiger Beispielrechnung
│   └── gothea_mascot.png         # GoThea Eulen-Maskottchen
│
└── staging_test/                 # Sicher generierte Kopien aus realen Schüler-Scans
    └── *.pdf + *.pdf.json        # Normierte Dateinamen und Metadaten-Begleitdateien
```

---

## ⚡ Schnellstart für Tests im Terminal

```bash
# 1. Interaktiven Sokratischen Chat starten (Standard: GPT-6 Luna):
.venv/bin/python experiments/openai_study/scratchpad/interactive_chat.py

# 2. Physik-Lehrtafel oder Arbeitsblatt generieren:
.venv/bin/python experiments/openai_study/scratchpad/test_image_gen.py "Didaktische Skizze: ..."

# 3. Reale Scans analysieren, normieren und Mappen zuweisen (sichere Kopien):
.venv/bin/python experiments/openai_study/scratchpad/test_safe_batch_importer.py --limit 5
```
