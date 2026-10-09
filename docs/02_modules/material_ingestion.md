# 02.4 Smarte Material-Ingestion & RAG-Pipeline

## 1. Upload-Kanäle (iPad & Desktop)

* **iPadOS Safari:** Über native File-Inputs (`<input type="file" accept="application/pdf,image/*">`) öffnet das iPad direkt:
  1. *Dateien (Files App):* iCloud Drive, Schul-Clouds, USB-Sticks, Downloads.
  2. *Fotomediathek:* Fotos von Arbeitsblättern.
  3. *Kamera:* Sofortiges Abfotografieren von Hefterseiten.
* **Drag & Drop:** Volle Unterstützung auf dem Desktop und im iPad Split-View.

---

## 2. Der 2-Stufen Human-in-the-Loop Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│ STUFE 1: VORAB-KLASSIFIZIERUNG (ASYNCHRON)                             │
│ - Upload an POST /api/v1/materials/pre-analyze                         │
│ - Vision-LLM liest Deckblatt / erste Seiten                            │
│ - Schlägt Fach, Thema, Klassenstufe & Dokumententitel vor (~1-2 Sek.)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STUFE 2: INTERAKTIVER BESTÄTIGUNGS-DIALOG (MODAL)                      │
│ - Schüler/Eltern sehen die vorgeschlagenen Metadaten                   │
│ - Möglichkeit zur manuellen Korrektur oder Bestätigung                 │
│ - Bestätigung via POST /api/v1/materials/confirm                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ VOLLSTÄNDIGE INGESTION & VEKTORISIERUNG                                │
│ - Speicherung im persistenten Storage                                  │
│ - OCR, Formel-Normalisierung (LaTeX $...$)                             │
│ - Semantisches Chunking nach Regeln, Übungen & Vokabeln                │
│ - Vektorisierung & sqlite-vec Fallback-Speicherung                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Online-Materialien & Brandenburger Lehrplan (OER)

* **Bildungsserver Berlin-Brandenburg (BBB):** Rahmenlehrplan Online, Standardillustrierende Aufgaben.
* **WirLernenOnline (WLO) & MUNDO API:** Freie Bildungsmedien gefiltert nach Bundesland BB, Fach und Klassenstufe.
* **Schulbücher (§ 53 UrhG):** Privilegierte Privatkopie von physischen Heftern/Büchern auf dem persönlichen Pi.
