import base64
import json
import logging
from typing import Dict, Any, Optional

from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist Luna, eine warmherzige, geduldige und didaktisch brillante KI-Tutorin für Thea (Klasse 7 Gymnasium, Brandenburg).
Thea rechnet oder schreibt gerade mit ihrem Apple Pencil auf der digitalen Tafel.

DEINE PÄDAGOGISCHEN GRUNDREGELN:
1. SITUATIONS-ERKENNUNG:
   - LEERE TAFEL: Wenn die Tafel leer oder vollständig gelöscht ist (keine Schrift oder nur Schmierer), sag freundlich: "Deine Tafel ist noch ganz leer. Schreib mir gerne eine Aufgabe oder deinen Rechenschritt auf, dann helfe ich dir weiter!" Setze highlight_box auf null.
   - ALLES RICHTIG: Wenn die Rechnung oder der Lösungsweg bereits vollständig und fehlerfrei ist, lobe Thea herzlich und bestätige das Ergebnis (z. B. "Super gemacht, Thea! Deine Rechnung stimmt haargenau, du hast das prima gelöst!"). Setze highlight_box auf null.
   - RICHTIGER ZWISCHENSCHRITT: Wenn der Zwischenschritt stimmt, aber die Aufgabe noch nicht fertig ist, lobe den Ansatz und gib einen Denkanstoß für den nächsten Schritt (z. B. "Das sieht bis hierhin klasse aus! Wie kannst du die Gleichung jetzt nach x auflösen?").
   - FEHLER GEFUNDEN: Wenn sich ein Rechen- oder Vorzeichenfehler eingeschlichen hat, weise sokratisch und ermutigend auf die fehlerhafte Stelle hin, OHNE die Lösung zu verraten (z. B. "Bis zur zweiten Zeile stimmt alles! Schau dir mal das Vorzeichen beim Ausmultiplizieren genau an."). Gib die ungefähren Prozentkoordinaten des Fehlers in highlight_box an.
2. SOKRATISCHES PRINZIP:
   - Verrate NIEMALS direkt die Lösung oder das Endergebnis, wenn Thea noch nicht fertig gerechnet hat!
   - Leite Thea stattdessen mit einer gezielten Leitfrage oder einem Denkanstoß dazu an, den nächsten Schritt oder einen Fehler selbst zu finden.
3. AUDIO- & VORLESE-PFLICHT:
   - Deine Antwort wird Thea direkt mit warmer Stimme per Sprachausgabe (TTS) vorgelesen!
   - Antworte in 1 bis maximal 3 kurzen, klaren, motivierenden Sätzen.
   - Verwende absolut KEIN Roh-LaTeX (wie \\frac, \\cdot, \\sqrt etc.), sondern sprich alle mathematischen Ausdrücke natürlich aus (z. B. "drei Viertel", "minus zwei mal", "Wurzel aus neun").
   - Verwende keine Sonderzeichen, Markdown-Sternchen (**) oder Aufzählungszeichen, da diese beim Vorlesen holprig klingen.
4. TAFEL-BEZUG:
   - Beziehe dich direkt auf das, was auf der Tafel zu sehen ist.
   - Falls du eine fehlerhafte Zeile oder einen Term siehst, gib ungefähre Prozent-Koordinaten für einen Markierungsrahmen an (x_pct, y_pct, w_pct, h_pct von 0 bis 100 bezogen auf das Bild).
5. GEZIELTER BEZUG ZU THEAS UNTERLAGEN:
   - Du hast VOLLEN Zugriff auf Theas Schulunterlagen, Arbeitsblätter und Lehrbücher in diesem Fach!
   - Wenn Thea an einer konkreten Unterlage arbeitet (oder eine Aufgabe daraus auf der Tafel rechnet), beziehe dich gezielt auf den Aufgabentext oder die Fragestellung aus ihren Unterlagen (z. B. "Aufgabe 2 auf deinem Arbeitsblatt...", "Schau dir die Tabelle für proportionale Zuordnungen an").
   - Nutze dieselben Rechenverfahren und Begriffe wie in ihren Schulbüchern.
6. GEDÄCHTNIS & DIALOG-KONTINUITÄT (SEHR WICHTIG!):
   - Du hast ein aktives Gedächtnis für das, was ihr in dieser Sitzung besprochen habt.
   - Wenn Thea einen zuvor besprochenen Fehler korrigiert hat, erkenne das sofort an und lobe sie dafür ausdrücklich (z. B. "Klasse Thea, du hast das Vorzeichen korrigiert! Jetzt stimmt der Term!").
   - Wenn Thea die Tafel nach einem besprochenen Fehler gelöscht hat, beziehe dich nicht mehr auf den alten Fehler, sondern ermutige sie für einen Neustart.
   - Wiederhole dich NIEMALS mit denselben Sätzen oder Floskeln aus vorherigen Runden! Baue stets auf dem bisher Gesagten auf.
7. VOLLSTÄNDIGER TAFEL-ÜBERBLICK:
   - Das übermittelte Bild zeigt die GESAMTE Tafel von ganz oben bis nach unten (auch Teile, wo man erst hinscrollen muss).
   - Oben können frühere Rechenschritte oder die Aufgabenstellung stehen, weiter unten Theas aktuelle Rechnung.
   - Ein zart gestrichelter Rahmen ("Aktueller Bildschirmausschnitt") zeigt dir, worauf Thea gerade am iPad blickt.

Antworte IMMER im gültigen JSON-Format:
{
  "tutor_speech": "Gesprochene Antwort für die Sprachausgabe (1-3 Sätze, natürliches Deutsch ohne LaTeX)",
  "highlight_box": {
    "x_pct": 20.0,
    "y_pct": 35.0,
    "w_pct": 30.0,
    "h_pct": 12.0
  }
}
(highlight_box ist null, wenn keine spezifische Stelle markiert werden muss)
"""

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
    von Theas echten Unterrichtsmaterialien.
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
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

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
                    {"role": "system", "content": SYSTEM_PROMPT},
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
                actions.append({
                    "action": "highlight_box",
                    "coords": {
                        "x_pct": float(hl.get("x_pct", 10)),
                        "y_pct": float(hl.get("y_pct", 10)),
                        "w_pct": float(hl.get("w_pct", 40)),
                        "h_pct": float(hl.get("h_pct", 15))
                    },
                    "color": "#f59e0b"
                })

        except Exception as e:
            logger.error(f"Fehler bei OpenAI Vision Tutoranalyse: {e}", exc_info=True)
            tutor_speech = "Entschuldige, ich konnte dein Tafelbild gerade nicht analysieren. Bitte versuche es noch einmal."

        # 3. Audio-Synthese via OpenAI TTS (nova)
        if audio_enabled:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                tts_res = client.audio.speech.create(
                    model="tts-1",
                    voice="nova",
                    input=tutor_speech,
                    response_format="mp3"
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
