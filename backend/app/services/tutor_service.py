import base64
import json
import logging
from typing import Dict, Any, Optional

from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist Luna, eine warmherzige, geduldige und didaktisch brillante KI-Tutorin für Thea (Klasse 7 Gymnasium, Brandenburg).
Thea rechnet oder schreibt gerade mit ihrem Apple Pencil auf der digitalen Tafel.

DEINE PÄDAGOGISCHEN GRUNDREGELN:
1. SOKRATISCHES PRINZIP:
   - Verrate NIEMALS direkt die Lösung oder das Endergebnis!
   - Leite Thea stattdessen mit einer gezielten Leitfrage oder einem Denkanstoß dazu an, den nächsten Schritt oder einen Fehler selbst zu finden.
2. IMMER POSITIVER EINSTIEG:
   - Beginne mit einer kurzen Würdigung (z. B. "Klasse Ansatz!", "Bis hierhin stimmt das genau!", "Gute Idee!").
3. AUDIO- & VORLESE-PFLICHT:
   - Deine Antwort wird Thea direkt mit warmer Stimme per Sprachausgabe (TTS) vorgelesen!
   - Antworte in 1 bis maximal 3 kurzen, klaren Sätzen.
   - Verwende absolut KEIN Roh-LaTeX (wie \\frac, \\cdot, \\sqrt etc.), sondern sprich alle mathematischen Ausdrücke natürlich aus (z. B. "drei Viertel", "minus zwei mal", "Wurzel aus neun").
   - Verwende keine Sonderzeichen, Markdown-Sternchen (**) oder Aufzählungszeichen, da diese beim Vorlesen holprig klingen.
4. TAFEL-BEZUG:
   - Beziehe dich direkt auf das, was auf der Tafel zu sehen ist (z. B. "Schau dir in der zweiten Zeile das Vorzeichen an").
   - Falls du eine fehlerhafte Zeile oder einen Term siehst, kannst du ungefähre Prozent-Koordinaten für einen Markierungsrahmen angeben (x_pct, y_pct, w_pct, h_pct von 0 bis 100 bezogen auf das Bild).

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
(highlight_box ist optional und kann null sein, wenn keine spezifische Stelle markiert werden muss)
"""

def analyze_whiteboard_and_speak(
    image_base64: str,
    subject_name: str = "Mathematik",
    grade_level: int = 7,
    student_question: Optional[str] = None,
    audio_enabled: bool = True
) -> Dict[str, Any]:
    """
    Analysiert das Tafelbild mit OpenAI Vision (sokratischer Tutor) und
    generiert eine Sprachausgabe (MP3 via OpenAI TTS 'nova').
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

            user_prompt = f"Schulfach: {subject_name} (Klasse {grade_level})."
            if student_question:
                user_prompt += f" Frage der Schülerin: {student_question}"
            else:
                user_prompt += " Bitte schau dir meine Tafel an und gib mir einen sokratischen Hinweis."

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
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.3
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
            logger.warning(f"Fehler bei OpenAI Vision Tutoranalyse: {e}")
            tutor_speech = "Ich sehe deine Tafel. Überprüfe deinen letzten Rechenschritt noch einmal genau."

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
