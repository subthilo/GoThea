"""
Einziger Zugang zu OpenAI.

- Ein gemeinsamer Client; Schlüssel, Modelle, Zeitlimit und Wiederholungen kommen aus der Config.
- Parameter, die ein Modell nicht kennt (z. B. 'temperature' bei GPT-6), werden weggelassen; lehnt
  die API trotzdem einen optionalen Parameter ab, folgt genau ein Versuch ohne ihn.
- Jeder Aufruf wird mit Zweck, Modell, Tokens und Dauer protokolliert (Log + DATA_DIR/logs/llm_usage.jsonl).
- Fehler kommen einheitlich als LLMError; die Dienste entscheiden selbst über ihren Fallback.
"""
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import backend.app.config as config

logger = logging.getLogger(__name__)

# Optionale Parameter, ohne die ein Aufruf trotzdem sinnvoll ist
OPTIONAL_PARAMS = ("temperature", "max_completion_tokens")

_client = None
_client_key: Optional[str] = None
_client_lock = threading.Lock()
_usage_lock = threading.Lock()


class LLMError(RuntimeError):
    """KI-Aufruf fehlgeschlagen oder Antwort unbrauchbar."""


def is_available() -> bool:
    return bool(config.OPENAI_API_KEY)


def client():
    """Gemeinsamer OpenAI-Client (wird beim ersten Aufruf angelegt)."""
    global _client, _client_key
    if not is_available():
        raise LLMError("Kein OpenAI-API-Schlüssel konfiguriert")
    with _client_lock:
        if _client is None or _client_key != config.OPENAI_API_KEY:
            import openai
            _client = openai.OpenAI(
                api_key=config.OPENAI_API_KEY,
                timeout=config.OPENAI_TIMEOUT_SECONDS,
                max_retries=config.OPENAI_MAX_RETRIES,
            )
            _client_key = config.OPENAI_API_KEY
        return _client


def reset_client() -> None:
    """Verwirft den gemeinsamen Client (Tests, Schlüsselwechsel)."""
    global _client, _client_key
    with _client_lock:
        _client, _client_key = None, None


def supports_temperature(model: str) -> bool:
    """GPT-6- und o-Reasoning-Modelle lehnen den Parameter 'temperature' ab."""
    m = (model or "").lower()
    return not (m.startswith("gpt-6") or m.startswith("o"))


def chat_params(model: str, temperature: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
    """Baut die Parameter für chat.completions.create passend zum gewählten Modell."""
    params: Dict[str, Any] = {"model": model, **kwargs}
    if temperature is not None and supports_temperature(model):
        params["temperature"] = temperature
    return params


@dataclass
class LLMReply:
    text: str
    model: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    seconds: float

    def json(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.text or "{}")
        except ValueError as e:
            raise LLMError(f"Antwort ist kein gültiges JSON: {e}") from e
        if not isinstance(data, dict):
            raise LLMError("JSON-Antwort ist kein Objekt")
        return data


def chat(messages: List[Dict[str, Any]], *, purpose: str, model: Optional[str] = None,
         temperature: Optional[float] = None, max_tokens: Optional[int] = None,
         json_mode: bool = False) -> LLMReply:
    """Ein Chat-Aufruf. 'purpose' benennt den Zweck im Protokoll (z. B. 'Dokumentanalyse')."""
    model = model or config.OPENAI_MODEL
    params = chat_params(model, temperature=temperature, messages=messages)
    if max_tokens is not None:
        params["max_completion_tokens"] = max_tokens
    if json_mode:
        params["response_format"] = {"type": "json_object"}

    start = time.monotonic()
    try:
        response = _create_with_fallback(params, purpose)
        text = response.choices[0].message.content or ""
    except Exception as e:
        _record(purpose, model, time.monotonic() - start, error=e)
        if isinstance(e, LLMError):
            raise
        raise LLMError(f"KI-Aufruf '{purpose}' fehlgeschlagen: {e}") from e

    usage = getattr(response, "usage", None)
    prompt_tokens = _int_or_none(getattr(usage, "prompt_tokens", None))
    completion_tokens = _int_or_none(getattr(usage, "completion_tokens", None))
    seconds = time.monotonic() - start
    _record(purpose, model, seconds, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return LLMReply(text, model, prompt_tokens, completion_tokens, seconds)


def chat_json(messages: List[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
    """Chat-Aufruf mit JSON-Antwort; ungültiges JSON ergibt LLMError."""
    return chat(messages, json_mode=True, **kwargs).json()


def speech(text: str, *, purpose: str, voice: Optional[str] = None, model: Optional[str] = None,
           speed: Optional[float] = None) -> bytes:
    """Sprachausgabe als MP3-Bytes."""
    model = model or config.OPENAI_TTS_MODEL
    params: Dict[str, Any] = {"model": model, "voice": voice or config.OPENAI_TTS_VOICE,
                              "input": text, "response_format": "mp3"}
    if speed is not None:
        params["speed"] = speed

    start = time.monotonic()
    try:
        audio = client().audio.speech.create(**params).content
    except Exception as e:
        _record(purpose, model, time.monotonic() - start, error=e, characters=len(text))
        if isinstance(e, LLMError):
            raise
        raise LLMError(f"Sprachausgabe '{purpose}' fehlgeschlagen: {e}") from e
    _record(purpose, model, time.monotonic() - start, characters=len(text))
    return audio


def _create_with_fallback(params: Dict[str, Any], purpose: str):
    import openai
    try:
        return client().chat.completions.create(**params)
    except openai.BadRequestError as e:
        rejected = getattr(e, "param", None)
        if rejected not in OPTIONAL_PARAMS or rejected not in params:
            raise
        logger.warning("Modell %s lehnt '%s' ab – erneuter Versuch ohne (%s)", params.get("model"), rejected, purpose)
        return client().chat.completions.create(**{k: v for k, v in params.items() if k != rejected})


def _int_or_none(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _record(purpose: str, model: str, seconds: float, error: Optional[BaseException] = None, **extra: Any) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "purpose": purpose,
             "model": model, "seconds": round(seconds, 2), "ok": error is None, **extra}
    if error is not None:
        entry["error"] = f"{type(error).__name__}: {error}"[:300]
        logger.warning("KI %s fehlgeschlagen nach %.1f s (%s): %s", purpose, seconds, model, entry["error"])
    else:
        tokens = f"{extra.get('prompt_tokens')}+{extra.get('completion_tokens')} Tokens" if "prompt_tokens" in extra else ""
        logger.info("KI %s: %s %s %.1f s", purpose, model, tokens, seconds)
    try:
        log_dir = config.DATA_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False)
        with _usage_lock, open(log_dir / "llm_usage.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        logger.debug("Nutzungsprotokoll nicht geschrieben: %s", e)
