import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
)

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


# --- Streaming und Werkzeug-Aufrufe (Responses API) ------------------------------------------------

def _event(type, **kw):
    return SimpleNamespace(type=type, **kw)


def _completed(input_tokens, output_tokens):
    return _event("response.completed",
                  response=SimpleNamespace(usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)))


def _reasoning():
    return _event("response.output_item.done", item=ResponseReasoningItem(
        id="rs_1", type="reasoning", summary=[], encrypted_content="geheim"))


def _tool_round(*calls):
    """Antwort, in der die KI (nach kurzem Nachdenken) Werkzeuge aufruft."""
    events = [_reasoning()]
    for call_id, name, arguments in calls:
        events.append(_event("response.function_call_arguments.delta", delta=arguments[:3]))
        events.append(_event("response.output_item.done", item=ResponseFunctionToolCall(
            type="function_call", id=f"fc_{call_id}", call_id=call_id, name=name, arguments=arguments,
            status="completed")))
    return events + [_completed(20, 5)]


def _text_round(*pieces):
    message = ResponseOutputMessage(id="msg_1", type="message", role="assistant", status="completed", content=[
        ResponseOutputText(type="output_text", text="".join(pieces), annotations=[])])
    return ([_event("response.output_text.delta", delta=p) for p in pieces]
            + [_event("response.output_item.done", item=message), _completed(30, 8)])


def _streaming_client(*rounds):
    client = MagicMock()
    client.responses.create.side_effect = [iter(r) for r in rounds]
    return client


def _search_tool(calls):
    def run(query):
        calls.append(query)
        return {"treffer": [f"Mathebuch S. 84 zu {query}"]}
    return llm.Tool("unterlagen_durchsuchen", "Sucht in den Unterlagen",
                    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}, run)


def test_stream_yields_text_pieces_and_records_usage(fake_key):
    client = _streaming_client(_text_round("Hal", "lo ", "Thea"))
    before = len(_usage_lines())
    with patch("openai.OpenAI", return_value=client):
        events = list(llm.chat_stream([{"role": "user", "content": "hi"}], purpose="Test", model="gpt-6-luna",
                                      temperature=0.3))

    assert [e.text for e in events if e.type == "text"] == ["Hal", "lo ", "Thea"]
    done = events[-1]
    assert done.type == "done" and done.reply.text == "Hallo Thea"
    assert done.messages[-1]["type"] == "message"
    assert done.messages[-1]["content"][0]["text"] == "Hallo Thea"
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["stream"] is True and kwargs["store"] is False
    assert kwargs["include"] == ["reasoning.encrypted_content"]
    assert kwargs["input"][0] == {"role": "user", "content": "hi"}
    assert "temperature" not in kwargs and "tools" not in kwargs
    entry = _usage_lines()[before]
    assert entry["ok"] is True and (entry["prompt_tokens"], entry["completion_tokens"]) == (30, 8)
    assert entry["rounds"] == 1 and entry["tools"] == []


def test_stream_runs_tools_and_sends_results_back(fake_key):
    client = _streaming_client(
        _tool_round(("call_1", "unterlagen_durchsuchen", '{"query": "Dreisatz"}'),
                    ("call_2", "unterlagen_durchsuchen", '{"query": "Prozent"}')),
        _text_round("Im Mathebuch ", "auf S. 84."))
    searched = []
    before = len(_usage_lines())
    with patch("openai.OpenAI", return_value=client):
        events = list(llm.chat_stream([{"role": "user", "content": "Dreisatz?"}], purpose="Test",
                                      tools=[_search_tool(searched)]))

    assert searched == ["Dreisatz", "Prozent"]
    assert [(e.type, e.tool) for e in events if e.type.startswith("tool")] == [
        ("tool_call", "unterlagen_durchsuchen"), ("tool_result", "unterlagen_durchsuchen")] * 2
    assert events[0].arguments == {"query": "Dreisatz"}
    assert events[-1].reply.text == "Im Mathebuch auf S. 84."

    first, second = (c.kwargs for c in client.responses.create.call_args_list)
    assert first["tools"][0]["name"] == "unterlagen_durchsuchen" and first["tools"][0]["strict"] is False
    assert "tool_choice" not in first
    # Zweite Runde: Nachdenken, beide Aufrufe und beide Ergebnisse gehen mit
    sent = second["input"]
    assert sent[1] == {"id": "rs_1", "type": "reasoning", "summary": [], "encrypted_content": "geheim"}
    assert [m["type"] for m in sent[2:6]] == ["function_call", "function_call",
                                             "function_call_output", "function_call_output"]
    assert sent[3]["call_id"] == "call_2" and sent[3]["arguments"] == '{"query": "Prozent"}'
    assert sent[4]["call_id"] == "call_1" and "Dreisatz" in sent[4]["output"]
    assert sent[5]["call_id"] == "call_2"

    entry = _usage_lines()[before]
    assert entry["rounds"] == 2 and entry["tools"] == ["unterlagen_durchsuchen"] * 2
    assert (entry["prompt_tokens"], entry["completion_tokens"]) == (50, 13)


def test_last_round_forbids_further_tools(fake_key):
    client = _streaming_client(_tool_round(("c1", "unterlagen_durchsuchen", '{"query": "a"}')),
                               _text_round("Fertig"))
    with patch("openai.OpenAI", return_value=client):
        events = list(llm.chat_stream([], purpose="Test", tools=[_search_tool([])], max_rounds=2))
    assert client.responses.create.call_args_list[1].kwargs["tool_choice"] == "none"
    assert events[-1].reply.text == "Fertig"


def test_tool_errors_go_back_to_the_model(fake_key):
    def broken(query):
        raise RuntimeError("Datenbank weg")
    tool = llm.Tool("kaputt", "", {"type": "object"}, broken)
    client = _streaming_client(
        _tool_round(("c1", "kaputt", '{"query": "x"}'), ("c2", "gibts_nicht", "{}"), ("c3", "kaputt", "{nope")),
        _text_round("Leider nichts gefunden."))
    with patch("openai.OpenAI", return_value=client):
        events = list(llm.chat_stream([], purpose="Test", tools=[tool]))

    results = [e.result for e in events if e.type == "tool_result"]
    assert "Datenbank weg" in results[0]["fehler"]
    assert "Unbekanntes Werkzeug" in results[1]["fehler"]
    assert "Ungültige Argumente" in results[2]["fehler"]
    assert events[-1].reply.text == "Leider nichts gefunden."


def test_stream_errors_become_llm_error_and_are_recorded(fake_key):
    def failing():
        yield _event("response.output_text.delta", delta="Hal")
        raise httpx.ReadTimeout("weg")
    client = MagicMock()
    client.responses.create.side_effect = [failing()]
    before = len(_usage_lines())
    received = []
    with patch("openai.OpenAI", return_value=client), pytest.raises(llm.LLMError):
        for event in llm.chat_stream([], purpose="Test"):
            received.append(event.text)
    assert received == ["Hal"]
    assert _usage_lines()[before]["ok"] is False


def test_abandoned_stream_is_closed_and_recorded(fake_key):
    stream = MagicMock()
    stream.__iter__.return_value = iter(_text_round("a", "b", "c"))
    client = MagicMock()
    client.responses.create.return_value = stream
    before = len(_usage_lines())
    with patch("openai.OpenAI", return_value=client):
        events = llm.chat_stream([], purpose="Test")
        next(events)
        events.close()
    stream.close.assert_called_once()
    entry = _usage_lines()[before]
    assert entry["ok"] is False and "abgebrochen" in entry["error"]


def test_failed_response_is_an_error(fake_key):
    failed = _event("response.failed", response=SimpleNamespace(usage=None, error="server_error"))
    client = _streaming_client([failed])
    with patch("openai.OpenAI", return_value=client), pytest.raises(llm.LLMError, match="server_error"):
        list(llm.chat_stream([], purpose="Test"))


def test_stream_drops_rejected_output_limit_once(fake_key):
    client = MagicMock()
    client.responses.create.side_effect = [_bad_request("max_output_tokens"), iter(_text_round("ok"))]
    with patch("openai.OpenAI", return_value=client):
        events = list(llm.chat_stream([], purpose="Test", max_tokens=100))
    assert events[-1].reply.text == "ok"
    assert "max_output_tokens" not in client.responses.create.call_args_list[1].kwargs
