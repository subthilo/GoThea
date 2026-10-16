import base64
import json
import logging
import re
from typing import Dict, Any, Optional

from backend.app.config import OPENAI_MODEL, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE
from backend.app.services import llm
from backend.app.prompts.tutor import TUTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def clean_text_for_speech(text: str, lang: str = "de") -> str:
    """
    Bereitet mathematische, physikalische und naturwissenschaftliche Ausdrücke
    sowie LaTeX-Formeln optimal für die Sprachausgabe (OpenAI TTS) vor.
    Verhindert, dass Operatoren verschluckt oder englisch ('Root', 'times', 'slash', 'c-dot')
    vorgelesen werden, und ersetzt sie durch natürliche deutsche Phonetik
    (z. B. 'Wurzel aus', 'mal', 'geteilt durch', 'Quadratzentimeter', 'ist gleich').
    """
    if not text or not isinstance(text, str):
        return ""

    s = text.strip()
    is_english = (lang or "").lower().startswith("en")

    if is_english:
        # --- ENGLISCHE MATHEMATIK-PHONETIK ---
        s = re.sub(r"\\sqrt\[(\d+)\]\{([^{}]+)\}", r"\1th root of \2", s)
        s = re.sub(r"\\sqrt\{([^{}]+)\}", r"square root of \1", s)
        s = re.sub(r"\\sqrt\s*([0-9a-zA-Z]+)", r"square root of \1", s)
        s = re.sub(r"\\sqrt\b", "square root", s)
        s = re.sub(r"√\s*([0-9a-zA-Z]+)", r"square root of \1", s)
        s = re.sub(r"√", "square root", s)
        s = re.sub(r"\bsqrt\s*\(([^)]+)\)", r"square root of \1", s)
        s = re.sub(r"\bsqrt\b", "square root", s)

        # Brüche
        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1 over \2", s)

        # Operatoren
        s = re.sub(r"\\cdot\b|\\times\b|\\bullet\b|[·×]", " times ", s)
        s = re.sub(r"([0-9a-zA-Z])\s*\*\s*([0-9a-zA-Z])", r"\1 times \2", s)
        s = re.sub(r"\\div\b|÷", " divided by ", s)
        s = re.sub(r"([0-9a-zA-Z])\s+/\s+([0-9a-zA-Z])", r"\1 divided by \2", s)
        s = re.sub(r"\\approx\b|≈", " approximately ", s)
        s = re.sub(r"\\neq\b|≠|!=", " is not equal to ", s)
        s = re.sub(r"\\le\b|\\leq\b|≤|<=", " less than or equal to ", s)
        s = re.sub(r"\\ge\b|\\geq\b|≥|>=", " greater than or equal to ", s)
        s = re.sub(r"\\pm\b|±", " plus or minus ", s)
        s = re.sub(r"\s*=\s*", " equals ", s)

        # Einheiten & Potenzen
        s = re.sub(r"\bcm[²2]\b|cm\^2", "square centimeters", s)
        s = re.sub(r"\bm[²2]\b|m\^2", "square meters", s)
        s = re.sub(r"\bkm/h\b", "kilometers per hour", s)
        s = re.sub(r"\bm/s\b", "meters per second", s)
        s = re.sub(r"\^2|²", " squared", s)
        s = re.sub(r"\^3|³", " cubed", s)
        s = re.sub(r"\^([0-9a-zA-Z]+)", r" to the power of \1", s)
    else:
        # --- DEUTSCHE MATHEMATIK-PHONETIK ---

        # 1. Spezifische physikalische Einheiten zuerst (um Fehlersetzung bei cm², m² etc. zu vermeiden)
        s = re.sub(r"\bcm[²2]\b|cm\^2", "Quadratzentimeter", s)
        s = re.sub(r"\bmm[²2]\b|mm\^2", "Quadratmillimeter", s)
        s = re.sub(r"\bdm[²2]\b|dm\^2", "Quadratdezimeter", s)
        s = re.sub(r"\bm[²2]\b|m\^2", "Quadratmeter", s)
        s = re.sub(r"\bkm[²2]\b|km\^2", "Quadratkilometer", s)

        s = re.sub(r"\bcm[³3]\b|cm\^3", "Kubikzentimeter", s)
        s = re.sub(r"\bmm[³3]\b|mm\^3", "Kubikmillimeter", s)
        s = re.sub(r"\bdm[³3]\b|dm\^3", "Kubikdezimeter", s)
        s = re.sub(r"\bm[³3]\b|m\^3", "Kubikmeter", s)
        s = re.sub(r"\bg/cm[³3]\b|g/cm\^3", "Gramm pro Kubikzentimeter", s)
        s = re.sub(r"\bkg/m[³3]\b|kg/m\^3", "Kilogramm pro Kubikmeter", s)

        s = re.sub(r"\bkm/h\b", "Kilometer pro Stunde", s)
        s = re.sub(r"\bm/s\b", "Meter pro Sekunde", s)

        # 2. Wurzeln (LaTeX, Unicode √, und fälschliches 'root' / 'sqrt')
        s = re.sub(r"\\sqrt\[3\]\{([^{}]+)\}", r"dritte Wurzel aus \1", s)
        s = re.sub(r"\\sqrt\[(\d+)\]\{([^{}]+)\}", r"\1-te Wurzel aus \2", s)
        s = re.sub(r"\\sqrt\{([^{}]+)\}", r"Wurzel aus \1", s)
        s = re.sub(r"\\sqrt\s*([0-9a-zA-Z]+)", r"Wurzel aus \1", s)
        s = re.sub(r"\\sqrt\b", "Wurzel", s)

        # Unicode √ mit Klammern oder Zahlen
        s = re.sub(r"√\s*\{([^{}]+)\}", r"Wurzel aus \1", s)
        s = re.sub(r"√\s*\(([^)]+)\)", r"Wurzel aus \1", s)
        s = re.sub(r"√\s*([0-9a-zA-Z]+)", r"Wurzel aus \1", s)
        s = re.sub(r"√", "Wurzel", s)

        # Textbasiertes sqrt(...) oder alleinstehendes sqrt
        s = re.sub(r"\bsqrt\s*\(([^)]+)\)", r"Wurzel aus \1", s)
        s = re.sub(r"\bsqrt\s+([0-9a-zA-Z]+)", r"Wurzel aus \1", s)
        s = re.sub(r"\bsqrt\b", "Wurzel", s)

        # Vermeidung von englischem "Root" / "Square Root"
        s = re.sub(r"\b[Rr]oot\s+aus\b", "Wurzel aus", s)
        s = re.sub(r"\b[Rr]oot\s+von\b", "Wurzel von", s)
        s = re.sub(r"\b[Ss]quare\s+[Rr]oot\b", "Quadratwurzel", s)
        s = re.sub(r"\b[Rr]oot\b", "Wurzel", s)

        # 3. Griechische Buchstaben & mathematische Symbole zuerst
        s = re.sub(r"\\pi\b|π", "Pi", s)
        s = re.sub(r"\\alpha\b|α", "Alpha", s)
        s = re.sub(r"\\beta\b|β", "Beta", s)
        s = re.sub(r"\\gamma\b|γ", "Gamma", s)
        s = re.sub(r"\\delta\b|δ", "Delta", s)
        s = re.sub(r"\\Delta\b|Δ", "Delta", s)
        s = re.sub(r"\\rho\b|ρ", "Rho", s)
        s = re.sub(r"\\infty\b|∞", "Unendlich", s)
        s = re.sub(r"(\d+)\s*%", r"\1 Prozent", s)
        s = re.sub(r"\\%|%", " Prozent", s)
        s = re.sub(r"°C", " Grad Celsius", s)
        s = re.sub(r"°", " Grad", s)

        # 4. Brüche (\frac{Zähler}{Nenner})
        def _replace_frac(m):
            num = m.group(1).strip()
            den = m.group(2).strip()
            fractions_named = {
                ("1", "2"): "ein Halb",
                ("1", "3"): "ein Drittel",
                ("2", "3"): "zwei Drittel",
                ("1", "4"): "ein Viertel",
                ("3", "4"): "drei Viertel",
                ("1", "5"): "ein Fünftel",
                ("1", "8"): "ein Achtel",
                ("1", "10"): "ein Zehntel",
            }
            if (num, den) in fractions_named:
                return fractions_named[(num, den)]
            return f"{num} geteilt durch {den}"

        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", _replace_frac, s)

        # 5. Multiplikation
        s = re.sub(r"\\cdot\b|\\times\b|\\bullet\b|[·×]", " mal ", s)
        # Sternchen als Malzeichen mit Lookaround (verhindert Überlappungs-Probleme bei 2 * r * Pi)
        s = re.sub(r"(?<=[0-9a-zA-Z\)])\s*\*\s*(?=[0-9a-zA-Z\\(])", " mal ", s)

        # 6. Division
        s = re.sub(r"\\div\b|÷", " geteilt durch ", s)
        # Geteilt durch als Doppelpunkt zwischen Zahlen (z. B. 12 : 3)
        s = re.sub(r"(?<=\d)\s*:\s*(?=\d)", " geteilt durch ", s)
        # Schrägstrich als Division zwischen Variablen/Zahlen (z. B. s / t oder 10 / 2)
        s = re.sub(r"(?<=[0-9a-zA-Z\)])\s+/\s+(?=[0-9a-zA-Z\\(])", " geteilt durch ", s)

        # 7. Potenzen
        s = re.sub(r"([0-9a-zA-Z])(?:\^2\b|²)", r"\1 hoch zwei", s)
        s = re.sub(r"([0-9a-zA-Z])(?:\^3\b|³)", r"\1 hoch drei", s)
        s = re.sub(r"([0-9a-zA-Z])\^([0-9a-zA-Z]+)", r"\1 hoch \2", s)
        s = re.sub(r"\^2|²", " hoch zwei", s)
        s = re.sub(r"\^3|³", " hoch drei", s)

        # 8. Vergleichs- und Gleichheitszeichen
        s = re.sub(r"\\approx\b|≈", " ungefähr gleich ", s)
        s = re.sub(r"\\neq\b|≠|!=", " ungleich ", s)
        s = re.sub(r"\\le\b|\\leq\b|≤|<=", " kleiner gleich ", s)
        s = re.sub(r"\\ge\b|\\geq\b|≥|>=", " größer gleich ", s)
        s = re.sub(r"\\pm\b|±", " plus minus ", s)
        # Gleichheitszeichen in Formeln/Gleichungen
        s = re.sub(r"\s*=\s*", " ist gleich ", s)

    # --- ALLGEMEINE BEREINIGUNG (LaTeX & Markdown) ---
    # Entferne Dollarzeichen aus $Formel$ oder $$Formel$$
    s = re.sub(r"\$+", "", s)
    # Entferne LaTeX-Formatierungen wie \text{...}, \mathbf{...}, \mathit{...}
    s = re.sub(r"\\[a-zA-Z]+\{([^{}]+)\}", r"\1", s)
    # Entferne LaTeX-Befehle wie \left, \right, \, \; \!
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    # Entferne Markdown-Formatierungen (Fett/Kursiv **, *)
    s = re.sub(r"\*+", "", s)
    # Entferne überflüssige Backslashes
    s = re.sub(r"\\", "", s)
    # Mehrfache Leerzeichen auf eins reduzieren
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" (\.|,|!|\?)", r"\1", s)
    return s.strip()


def analyze_whiteboard_and_speak(
    image_base64: str,
    subject_name: str = "Mathematik",
    grade_level: int = 7,
    student_question: Optional[str] = None,
    audio_enabled: bool = True,
    material_context: Optional[Dict[str, Any]] = None,
    available_materials: Optional[list] = None,
    curriculum_topics: Optional[list] = None,
    dialogue_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    Analysiert das Tafelbild mit OpenAI Vision (sokratischer Tutor) und
    generiert eine Sprachausgabe (MP3 via OpenAI TTS 'nova'), unter Einbezug
    von Theas echten Unterrichtsmaterialien und dem bisherigen Gesprächsgedächtnis.
    """
    # 1. Base64 bereinigen
    clean_b64 = image_base64
    if "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]
    clean_b64 = clean_b64.strip()

    tutor_speech = "Schau dir deine Rechnung noch einmal in Ruhe an. Welcher Schritt kommt als Nächstes?"
    actions = []
    audio_b64 = None

    # 2. OpenAI Vision Abfrage
    if llm.is_available():
        try:
            client = llm.client()

            user_prompt = f"SCHULFACH: {subject_name} (Klasse {grade_level} Gymnasium, Brandenburg).\n"
            if curriculum_topics:
                user_prompt += f"Lehrplanthemen: {', '.join(curriculum_topics[:8])}\n"

            if material_context:
                user_prompt += (
                    f"\nAKTUELL GEWÄHLTE UNTERLAGE AUF DER TAFEL:\n"
                    f"- Titel: {material_context.get('title')} ({material_context.get('kind')})\n"
                    f"- Thema: {material_context.get('topic') or 'Allgemein'}\n"
                )
                if material_context.get("summary"):
                    user_prompt += f"- Inhalt: {material_context.get('summary')}\n"
                if material_context.get("text_snippet"):
                    user_prompt += f"- Aufgabenstellung / Auszug aus der Unterlage:\n\"\"\"{material_context.get('text_snippet')}\"\"\"\n"
            elif available_materials:
                mat_titles = [f"{m['title']} ({m['kind']})" for m in available_materials[:8]]
                user_prompt += f"\nVorhandene Unterlagen der Schülerin in diesem Fach: {'; '.join(mat_titles)}\n"

            if dialogue_history:
                user_prompt += "\nBISHERIGER GESPRÄCHSVERLAUF IN DIESER SITZUNG (DEIN GEDÄCHTNIS):\n"
                for turn in dialogue_history[-8:]:
                    speaker = "Thea" if turn.get("role") in ("student", "user") else "Luna (Du)"
                    content = (turn.get("content") or "").strip()
                    if content:
                        user_prompt += f"- {speaker}: \"{content}\"\n"
                user_prompt += "(Beziehe dich auf diese Vorgeschichte. Wenn Thea einen zuvor erwähnten Fehler korrigiert hat, lobe sie dafür! Wenn sie alles gelöscht hat, beginne neu und wiederhole nicht alte Hinweise.)\n"

            if student_question:
                user_prompt += f"\nFrage der Schülerin: {student_question}\n"
            else:
                user_prompt += "\nBitte schau dir das Tafelbild an und beziehe deine Rückmeldung gezielt auf die bearbeitete Aufgabe und Theas Rechenschritte."

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{clean_b64}",
                                    "detail": "auto"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1500
            )

            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)
            if "tutor_speech" in parsed and parsed["tutor_speech"]:
                tutor_speech = parsed["tutor_speech"].strip()

            hl = parsed.get("highlight_box")
            if hl and isinstance(hl, dict) and "x_pct" in hl:
                x = min(100.0, max(0.0, float(hl.get("x_pct", 10))))
                y = min(100.0, max(0.0, float(hl.get("y_pct", 10))))
                actions.append({
                    "action": "highlight_box",
                    "coords": {
                        "x_pct": x,
                        "y_pct": y,
                        "w_pct": min(100.0 - x, max(0.0, float(hl.get("w_pct", 40)))),
                        "h_pct": min(100.0 - y, max(0.0, float(hl.get("h_pct", 15))))
                    },
                    "color": "#f59e0b"
                })

        except Exception as e:
            logger.error(f"Fehler bei OpenAI Vision Tutoranalyse: {e}", exc_info=True)
            tutor_speech = "Entschuldige, ich konnte dein Tafelbild gerade nicht analysieren. Bitte versuche es noch einmal."

        # 3. Audio-Synthese via OpenAI TTS (nova)
        if audio_enabled:
            try:
                client = llm.client()
                clean_speech = clean_text_for_speech(tutor_speech, lang="en" if "Englisch" in subject_name else "de")
                tts_res = client.audio.speech.create(
                    model=OPENAI_TTS_MODEL,
                    voice=OPENAI_TTS_VOICE,
                    input=clean_speech,
                    response_format="mp3",
                    speed=0.90
                )
                audio_b64 = base64.b64encode(tts_res.content).decode("utf-8")
            except Exception as e:
                logger.warning(f"Fehler bei OpenAI TTS Sprachausgabe: {e}")
                audio_b64 = None
    else:
        # Fallback im Offline- / Testmodus
        tutor_speech = "Toll, dass du auf der Tafel arbeitest! Schau dir den letzten Schritt noch einmal genau an."
        actions.append({
            "action": "highlight_box",
            "coords": {"x": 120, "y": 140, "w": 320, "h": 85},
            "color": "#f59e0b"
        })

    return {
        "status": "success",
        "tutor_speech": tutor_speech,
        "audio_base64": audio_b64,
        "actions": actions
    }
