import json
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from backend.app import config
from backend.app.services import llm


def _client_returning(text, prompt_tokens=11, completion_tokens=7):
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = text
    client.chat.completions.create.return_value = MagicMock(
        choices=[choice], usage=MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens))
    return client


def _bad_request(param):
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    return openai.BadRequestError("unsupported", response=response,
                                  body={"message": "unsupported", "param": param, "code": "unsupported_parameter"})


@pytest.fixture
def fake_key(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-fake")


def _usage_lines():
    f = config.DATA_DIR / "logs" / "llm_usage.jsonl"
    return [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []


def test_without_key_nothing_is_called():
    assert llm.is_available() is False
    with patch("openai.OpenAI") as cls, pytest.raises(llm.LLMError):
        llm.chat([{"role": "user", "content": "hi"}], purpose="Test")
    cls.assert_not_called()


def test_chat_json_sends_model_specific_params_and_records_usage(fake_key):
    client = _client_returning('{"fach": "Physik"}')
    before = len(_usage_lines())
    with patch("openai.OpenAI", return_value=client) as cls:
        data = llm.chat_json([{"role": "user", "content": "x"}], purpose="Dokumentanalyse",
                             model="gpt-6-luna", temperature=0.1)

    assert data == {"fach": "Physik"}
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-6-luna"
    assert "temperature" not in kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert cls.call_args.kwargs["timeout"] == config.OPENAI_TIMEOUT_SECONDS
    entry = _usage_lines()[before]
    assert entry["purpose"] == "Dokumentanalyse" and entry["ok"] is True
    assert entry["prompt_tokens"] == 11 and entry["completion_tokens"] == 7


def test_client_is_shared_between_calls(fake_key):
    with patch("openai.OpenAI", return_value=_client_returning("ok")) as cls:
        llm.chat([], purpose="A")
        llm.chat([], purpose="B")
    assert cls.call_count == 1


def test_rejected_optional_param_is_dropped_once(fake_key):
    client = _client_returning("ok")
    ok = client.chat.completions.create.return_value
    client.chat.completions.create.side_effect = [_bad_request("temperature"), ok]
    with patch("openai.OpenAI", return_value=client):
        reply = llm.chat([], purpose="Test", model="gpt-4o-mini", temperature=0.2)

    assert reply.text == "ok"
    first, second = (c.kwargs for c in client.chat.completions.create.call_args_list)
    assert first["temperature"] == 0.2
    assert "temperature" not in second


def test_other_errors_become_llm_error_and_are_recorded(fake_key):
    client = _client_returning("ok")
    client.chat.completions.create.side_effect = _bad_request("messages")
    before = len(_usage_lines())
    with patch("openai.OpenAI", return_value=client), pytest.raises(llm.LLMError):
        llm.chat([], purpose="Test")
    assert client.chat.completions.create.call_count == 1
    assert _usage_lines()[before]["ok"] is False


def test_invalid_json_is_an_error(fake_key):
    with patch("openai.OpenAI", return_value=_client_returning("kein json")), pytest.raises(llm.LLMError):
        llm.chat_json([], purpose="Test")


def test_speech_uses_configured_voice(fake_key, monkeypatch):
    monkeypatch.setattr(config, "OPENAI_TTS_MODEL", "tts-x")
    monkeypatch.setattr(config, "OPENAI_TTS_VOICE", "nova")
    client = MagicMock()
    client.audio.speech.create.return_value = MagicMock(content=b"mp3")
    with patch("openai.OpenAI", return_value=client):
        assert llm.speech("Hallo", purpose="Test") == b"mp3"
    kwargs = client.audio.speech.create.call_args.kwargs
    assert (kwargs["model"], kwargs["voice"], kwargs["input"]) == ("tts-x", "nova", "Hallo")
