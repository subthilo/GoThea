"""
Einziger Zugang zu OpenAI.

- Ein gemeinsamer Client; Schlüssel, Modelle, Zeitlimit und Wiederholungen kommen aus der Config.
- Parameter, die ein Modell nicht kennt (z. B. 'temperature' bei GPT-6), werden weggelassen; lehnt
  die API trotzdem einen optionalen Parameter ab, folgt genau ein Versuch ohne ihn.
- Jeder Aufruf wird mit Zweck, Modell, Tokens und Dauer protokolliert (Log + DATA_DIR/logs/llm_usage.jsonl).
- Fehler kommen einheitlich als LLMError; die Dienste entscheiden selbst über ihren Fallback.
- chat_stream() liefert die Antwort stückweise und führt Werkzeug-Aufrufe (function calling) selbst aus.
"""
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence

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


@dataclass
class Tool:
    """Werkzeug, das die KI während einer Antwort aufrufen kann. 'run' bekommt die Argumente als
    Schlüsselwörter; das Ergebnis geht als JSON an die KI zurück. Kontext (DB-Session, Rolle) wird beim
    Anlegen des Werkzeugs gebunden, nie von der KI übergeben."""
    name: str
    description: str
    parameters: Dict[str, Any]          # JSON-Schema der Argumente
    run: Callable[..., Any]

    def spec(self) -> Dict[str, Any]:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass
class StreamEvent:
    """Ereignis aus chat_stream():
    'text'        – nächstes Textstück (text)
    'tool_call'   – die KI ruft ein Werkzeug auf (tool, arguments)
    'tool_result' – Ergebnis des Werkzeugs (tool, result)
    'done'        – fertig (reply mit ganzem Text und Tokens aller Runden, messages = Verlauf inkl. Werkzeugen)"""
    type: str
    text: str = ""
    tool: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result: Any = None
    reply: Optional[LLMReply] = None
    messages: Optional[List[Dict[str, Any]]] = None


def chat_stream(messages: List[Dict[str, Any]], *, purpose: str, tools: Sequence[Tool] = (),
                model: Optional[str] = None, temperature: Optional[float] = None,
                max_tokens: Optional[int] = None, max_rounds: int = 4) -> Iterator[StreamEvent]:
    """Chat-Aufruf mit stückweiser Antwort. Ruft die KI Werkzeuge auf, werden sie ausgeführt und die
    Ergebnisse zurückgegeben – höchstens 'max_rounds' Anfragen; in der letzten muss die KI antworten.
    Ein Protokolleintrag für den ganzen Aufruf (Tokens aller Runden, benutzte Werkzeuge)."""
    model = model or config.OPENAI_MODEL
    history = list(messages)
    by_name = {t.name: t for t in tools}
    parts: List[str] = []
    used: List[str] = []
    prompt_tokens = completion_tokens = 0
    rounds = 0
    start = time.monotonic()
    try:
        for rounds in range(1, max_rounds + 1):
            params = chat_params(model, temperature=temperature, messages=history, stream=True,
                                 stream_options={"include_usage": True})
            if max_tokens is not None:
                params["max_completion_tokens"] = max_tokens
            if tools:
                params["tools"] = [t.spec() for t in tools]
                if rounds == max_rounds:
                    params["tool_choice"] = "none"
            round_text: List[str] = []
            calls: Dict[int, Dict[str, str]] = {}
            stream = _create_with_fallback(params, purpose)
            try:
                for chunk in stream:
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        prompt_tokens += _int_or_none(getattr(usage, "prompt_tokens", None)) or 0
                        completion_tokens += _int_or_none(getattr(usage, "completion_tokens", None)) or 0
                    if not getattr(chunk, "choices", None):
                        continue
                    delta = chunk.choices[0].delta
                    if getattr(delta, "content", None):
                        round_text.append(delta.content)
                        yield StreamEvent("text", text=delta.content)
                    # Werkzeug-Aufrufe kommen in Stücken: id und Name zuerst, die Argumente nach und nach
                    for piece in getattr(delta, "tool_calls", None) or []:
                        slot = calls.setdefault(piece.index, {"id": "", "name": "", "arguments": ""})
                        if getattr(piece, "id", None):
                            slot["id"] = piece.id
                        function = getattr(piece, "function", None)
                        if function is not None:
                            slot["name"] += getattr(function, "name", None) or ""
                            slot["arguments"] += getattr(function, "arguments", None) or ""
            finally:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()
            parts.extend(round_text)
            if not calls:
                break
            ordered = [calls[i] for i in sorted(calls)]
            history.append({"role": "assistant", "content": "".join(round_text) or None,
                            "tool_calls": [{"id": c["id"], "type": "function",
                                            "function": {"name": c["name"], "arguments": c["arguments"]}}
                                           for c in ordered]})
            for call in ordered:
                used.append(call["name"])
                arguments, problem = _tool_arguments(by_name, call)
                yield StreamEvent("tool_call", tool=call["name"], arguments=arguments)
                result = problem or _run_tool(by_name[call["name"]], arguments, purpose)
                yield StreamEvent("tool_result", tool=call["name"], result=result)
                history.append({"role": "tool", "tool_call_id": call["id"],
                                "content": json.dumps(result, ensure_ascii=False, default=str)})
    except GeneratorExit:
        _record(purpose, model, time.monotonic() - start, error=LLMError("vom Aufrufer abgebrochen"),
                rounds=rounds, tools=used, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        raise
    except Exception as e:
        _record(purpose, model, time.monotonic() - start, error=e, rounds=rounds, tools=used)
        if isinstance(e, LLMError):
            raise
        raise LLMError(f"KI-Aufruf '{purpose}' fehlgeschlagen: {e}") from e
    seconds = time.monotonic() - start
    _record(purpose, model, seconds, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            rounds=rounds, tools=used)
    if not calls:
        history.append({"role": "assistant", "content": "".join(round_text)})
    yield StreamEvent("done", reply=LLMReply("".join(parts), model, prompt_tokens, completion_tokens, seconds),
                      messages=history)


def _tool_arguments(by_name: Dict[str, Tool], call: Dict[str, str]):
    """Argumente eines Werkzeug-Aufrufs; bei unbekanntem Werkzeug oder kaputtem JSON ein Fehler-Ergebnis."""
    if call["name"] not in by_name:
        return {}, {"fehler": f"Unbekanntes Werkzeug '{call['name']}'"}
    try:
        arguments = json.loads(call["arguments"] or "{}")
    except ValueError as e:
        return {}, {"fehler": f"Ungültige Argumente: {e}"}
    if not isinstance(arguments, dict):
        return {}, {"fehler": "Ungültige Argumente: kein Objekt"}
    return arguments, None


def _run_tool(tool: Tool, arguments: Dict[str, Any], purpose: str) -> Any:
    """Führt ein Werkzeug aus. Fehler gehen als Ergebnis an die KI (sie kann darauf reagieren)."""
    try:
        return tool.run(**arguments)
    except Exception as e:
        logger.warning("Werkzeug %s fehlgeschlagen (%s): %s", tool.name, purpose, e, exc_info=True)
        return {"fehler": f"Werkzeug fehlgeschlagen: {e}"}


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
