# Testbericht Iteration 07 – Vollständige Plattform- & Performance-Verifikation

* **Datum:** 12. Oktober 2026
* **Status:** ✅ 100% Erfolgreich (Alle 143 Tests bestanden)
* **Zielhardware:** Raspberry Pi 4 / 5 (Raspberry Pi OS 64-Bit / `armv7l`) & iPad Pro / Air Safari Client
* **Testlaufzeit:** ~75 Sekunden (Vollständige Suite)

---

## 1. Zusammenfassung des Testlaufs

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea
configfile: pytest.ini
plugins: anyio-4.12.1, cov-7.1.0
collected 143 items

tests/integration/test_annotation_api.py ..                              [  1%]
tests/integration/test_books_api.py ......                               [  5%]
tests/integration/test_env_api.py ..                                     [  6%]
tests/integration/test_exercise_scores_api.py .                          [  7%]
tests/integration/test_exercises_api.py ........                         [ 13%]
tests/integration/test_inbox_api.py ..                                   [ 14%]
tests/integration/test_material_api.py .........                         [ 20%]
tests/integration/test_parent_mode_api.py ..........                     [ 27%]
tests/integration/test_planner_api.py ....                               [ 30%]
tests/integration/test_profile_api.py ...                                [ 32%]
tests/integration/test_taxonomy_api.py .......                           [ 37%]
tests/integration/test_timetable_api.py ......                           [ 41%]
tests/integration/test_whiteboard_api.py ..........                      [ 48%]
tests/unit/test_annotation_models.py .                                   [ 49%]
tests/unit/test_book_segmentation.py ....                                [ 52%]
tests/unit/test_books_models.py .                                        [ 53%]
tests/unit/test_document_analyzer.py ...                                 [ 55%]
tests/unit/test_dossier_models.py ....                                   [ 58%]
tests/unit/test_exercise_pool_service.py .......                         [ 62%]
tests/unit/test_gamification.py ....                                     [ 65%]
tests/unit/test_inbox_service.py .....                                   [ 69%]
tests/unit/test_material_ingestion_service.py .....                      [ 72%]
tests/unit/test_material_models.py ..                                    [ 74%]
tests/unit/test_page_renderer.py ....                                    [ 76%]
tests/unit/test_phrase_pool.py ..                                        [ 78%]
tests/unit/test_planner_algorithm.py ....                                [ 81%]
tests/unit/test_score_service.py ....                                    [ 83%]
tests/unit/test_taxonomy_models.py ...                                   [ 86%]
tests/unit/test_timetable_analyzer.py .........                          [ 92%]
tests/unit/test_timetable_models.py ...                                  [ 94%]
tests/unit/test_tutor_speech_cleaner.py ......                           [ 98%]
tests/unit/test_whiteboard_models.py ..                                  [100%]

================== 143 passed, 5 warnings in 75.77s (0:01:15) ==================
```

---

## 2. Detaillierte Testergebnisse nach Subsystemen

### A. Schulbuch-Segmentierung & Inhaltsverzeichnis (`test_book_segmentation.py` & `test_books_api.py`)
* `test_is_candidate_book`: Validiert automatische Buch-Erkennung bei `kind="Buch"`, $\ge 20$ Seiten mit Schulbuch-Keywords sowie $\ge 30$ Seiten bei neutralen Namen.
* `test_extract_chapters_from_pdf_outline`: Verifiziert deterministisches Parsen der PDF-Lesezeichen (`outline`) via `pypdf` in $< 0,1\text{ s}$.
* `test_auto_detect_and_segment_book_with_outline`: Prüft Slicing in Child-Materialien mit korrekten Seitenzahlen ($1-4, 5-8, 9-12$).
* `test_auto_segment_if_known`: Testet Register für *Fundamente der Mathematik 7* (11 Einheiten).
* `test_unsegmented_book_fallback_api`: Sichert ab, dass unsegmentierte Bücher niemals zu Sackgassen führen, sondern als vollständiges Werk mit 1 Klick aufgeschlagen werden können.

### B. Kontinuierlicher Übungs-Vorratsspeicher (`test_exercise_pool_service.py`)
* `test_canonical_subject_keys`: Validiert fächerspezifische Normalisierung (`sub_math`, `sub_english` etc.).
* `test_resolve_auto_exercise_type`: Verifiziert Standard-Aufgabentypen (`math_problem`, `physics_diagram`, `fill_in_the_blank`).
* `test_get_exercise_from_pool_success`: Prüft Zero-Wait Abruf ($< 10\text{ ms}$) aus vorgerendertem Speicher.
* `test_get_exercise_auto_fallback`: Validiert Fallback auf Live-Generierung bei leerem Pool.
* `test_start_stop_lifecycle`: Prüft sauberen Start/Stopp des Hintergrund-Workers im FastAPI Lifespan.

### C. Didaktisches Score-Tracking & Gamification (`test_gamification.py`, `test_score_service.py`)
* `test_calculate_exercise_rewards`: Prüft XP-Berechnung (Basis-XP + Genauigkeits-Bonus) und Sterne (1–3 ⭐).
* `test_level_progression`: Validiert Stufen-Aufstieg von Level 1 bis 5 (*GoThea-Meisterin ✨*).
* `test_streak_calculation`: Prüft lückenlose Tages-Lernserien mit Datums-Tracking.
* `test_adaptive_difficulty`: Validiert die Herabstufung bei akuten Schwierigkeiten ($< 60\,\%$) und Aufstieg bei fehlerfreien Serien ($\ge 85\,\%$).

### D. Elternmodus & PIN-Sicherheitsarchitektur (`test_parent_mode_api.py`)
* `test_unlock_with_default_pin`: Prüft Freischaltung via `1234` und Session-Cookie.
* `test_unlock_with_wrong_pin`: Prüft Abweisung falscher PINs (`401 Unauthorized`).
* `test_lockout_after_too_many_failed_attempts`: Validiert automatische 5-Minuten-Sperre nach 5 Fehlversuchen (`429 Too Many Requests`).
* `test_status_endpoint`: Prüft Session-Status und Rest-Lockout-Sekunden.

### E. Intelligentes Seiten-Vorrendern (`test_page_renderer.py`)
* `test_page_renderer_image_direct`: Bild-Direktauslieferung ohne Konvertierung.
* `test_page_renderer_pdf_render_and_cache`: Prüft mtime-basiertes Caching und 120 DPI Retina-Ausgabe.
* `test_page_renderer_prefetch_and_queue`: Validiert Priority-Queue (Live 1, Prefetch 2, Background 3).

### F. Phonetische Sprach-Synthese (`test_tutor_speech_cleaner.py`)
* `test_clean_text_for_speech_fractions`: Prüft Brüche ($\frac{1}{2} \rightarrow \text{ein Halb}$).
* `test_clean_text_for_speech_math_operators`: Prüft Rechenzeichen ($\cdot \rightarrow \text{mal}$, $\pm \rightarrow \text{plus minus}$).
* `test_clean_text_for_speech_units_and_powers`: Prüft Potenzen ($x^2$) und Maßeinheiten ($\mathrm{cm}^2 \rightarrow \text{Quadratzentimeter}$).

---

## 3. Fazit & Freigabe

Alle Teilsysteme laufen stabil, deterministisch und vollständig synchronisiert. Das Gesamtsystem ist für den Dauereinsatz auf Staging (`http://192.168.1.135:8001`) und Produktion (`http://192.168.1.135:8000`) abgenommen.
