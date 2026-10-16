"""Lunas Werkzeug „Unterlagen durchsuchen“: Lösungen bleiben verborgen, Filter, kompakte Treffer."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from openai.types.responses import ResponseFunctionToolCall

from backend.app import config
from backend.app.models.material import Material
from backend.app.models.material_page import MaterialPage
from backend.app.models.taxonomy import Subject
from backend.app.services import llm, luna_tools


def _material(db, mid, title, pages, kind="Mitschrift", subject="sub_math", **kw):
    db.add(Material(id=mid, subject_id=subject, title=title, kind=kind, filename=f"{mid}.pdf",
                    file_path=f"/tmp/{mid}.pdf", page_count=len(pages), **kw))
    db.flush()
    for n, body in enumerate(pages, start=1):
        db.add(MaterialPage(material_id=mid, page_number=n, content_key=f"{mid}_p{n}", text=body))
    db.commit()


def _setup(db):
    for i in range(6):  # BM25 braucht eine Sammlung
        _material(db, f"mat_f{i}", f"Thema {i}", [f"Vulkane, Gedichte und Vokabeln {i}"])
    _material(db, "mat_ab", "Dreisatz", ["Dreisatz Aufgaben", "Dreisatz Lösungen"], kind="Arbeitsblatt",
              solution_pages_json="[2]")
    _material(db, "mat_mi", "Hefteintrag", ["«S: Dreisatz: erst auf 1 rechnen»"])


def _math(db):
    return db.query(Subject).filter_by(id="sub_math").one().name


def test_search_hides_solutions_and_returns_compact_hits(db_session):
    _setup(db_session)
    tool = luna_tools.search_tool(db_session)
    result = tool.run(suchbegriff="Dreisatz")

    found = {(h["material_id"], h["seite"]) for h in result["treffer"]}
    assert found == {("mat_ab", 1), ("mat_mi", 1)}
    hit = next(h for h in result["treffer"] if h["material_id"] == "mat_mi")
    assert hit["fundstelle"] and hit["fach"] == _math(db_session) and hit["art"] == "Mitschrift"
    assert "⟦Dreisatz⟧" in hit["ausschnitt"]
    assert None not in hit.values() and "hinweis" not in result
    json.dumps(result, ensure_ascii=False)  # geht als JSON an die KI


def test_schema_offers_subjects_and_kinds_but_no_solution_switch(db_session):
    spec = luna_tools.search_tool(db_session).spec()
    props = spec["parameters"]["properties"]
    assert spec["name"] == "unterlagen_durchsuchen"
    assert set(props) == {"suchbegriff", "fach", "art"}
    assert _math(db_session) in props["fach"]["enum"]
    assert "Stundenplan" not in props["art"]["enum"]


def test_filters_and_unknown_values(db_session):
    _setup(db_session)
    tool = luna_tools.search_tool(db_session)
    only_sheets = tool.run(suchbegriff="Dreisatz", art="Arbeitsblatt", fach=_math(db_session).upper())
    assert [h["material_id"] for h in only_sheets["treffer"]] == ["mat_ab"]

    unknown = tool.run(suchbegriff="Dreisatz", fach="Klingonisch", art="Zauberbuch")
    assert len(unknown["treffer"]) == 2
    assert "Klingonisch" in unknown["hinweis"] and "Zauberbuch" in unknown["hinweis"]

    nothing = tool.run(suchbegriff="Photosynthese")
    assert nothing["treffer"] == [] and "Nichts gefunden" in nothing["hinweis"]


def test_model_can_search_through_chat_stream(db_session, monkeypatch):
    _setup(db_session)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-fake")

    call = ResponseFunctionToolCall(type="function_call", call_id="c1", name="unterlagen_durchsuchen",
                                    arguments='{"suchbegriff": "Dreisatz"}')
    done = SimpleNamespace(type="response.completed", response=SimpleNamespace(usage=None))
    client = MagicMock()
    client.responses.create.side_effect = [
        iter([SimpleNamespace(type="response.output_item.done", item=call), done]),
        iter([SimpleNamespace(type="response.output_text.delta", delta="Steht im Heft."), done])]

    with patch("openai.OpenAI", return_value=client):
        events = list(llm.chat_stream([{"role": "user", "content": "Dreisatz?"}], purpose="Test",
                                      tools=[luna_tools.search_tool(db_session)]))

    sent = client.responses.create.call_args_list[1].kwargs["input"]
    output = next(m for m in sent if m.get("type") == "function_call_output")["output"]
    assert "mat_mi" in output and "Lösungen" not in output
    assert events[-1].reply.text == "Steht im Heft."
