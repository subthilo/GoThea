import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.app.services.boards import default_title

STROKE = [{"tool": "pen", "color": "#fff", "width": 4, "points": [{"x": 1, "y": 2, "pressure": 0.5}]}]
THUMB = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8fakejpeg").decode()


def _new(client, subject_id="sub_math"):
    res = client.post("/api/v1/boards", json={"subject_id": subject_id})
    assert res.status_code == 201
    return res.json()


def _draw(client, board_id, strokes=STROKE, snapshot=THUMB):
    res = client.put(f"/api/v1/whiteboard/sessions/{board_id}/state",
                     json={"board_state_json": json.dumps(strokes), "snapshot_data_url": snapshot})
    assert res.status_code == 200


def _fake_llm(title):
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = json.dumps({"titel": title})
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


def test_new_board_gets_subject_and_date_as_title(client):
    board = _new(client)
    assert board["title"] == default_title("Mathematik", datetime.now())
    assert board["title_source"] == "auto"
    assert board["stroke_count"] == 0 and board["archived"] is False


def test_boards_are_listed_per_subject_newest_change_first(client):
    older, newer = _new(client), _new(client)
    _draw(client, newer["id"])
    _draw(client, older["id"])
    bio = _new(client, "sub_bio")

    ids = [b["id"] for b in client.get("/api/v1/boards", params={"subject_id": "sub_math"}).json()]
    assert ids[:2] == [older["id"], newer["id"]]
    assert bio["id"] not in ids


def test_last_opened_board_is_restored(client):
    first, second = _new(client), _new(client)
    client.post(f"/api/v1/boards/{first['id']}/open")
    last = client.get("/api/v1/boards/last").json()
    assert last["id"] == first["id"]
    assert client.get("/api/v1/boards/last", params={"subject_id": "sub_math"}).json()["id"] == first["id"]
    assert second["id"] != first["id"]


def test_closing_an_empty_board_discards_it(client):
    board = _new(client)
    res = client.post(f"/api/v1/boards/{board['id']}/close").json()
    assert res == {"deleted": True, "board": None}
    assert client.post(f"/api/v1/boards/{board['id']}/open").status_code == 404


def test_closing_names_the_board_from_its_picture(client):
    board = _new(client)
    _draw(client, board["id"])
    fake = _fake_llm("Gleichungen mit Klammern")
    with patch("backend.app.config.OPENAI_API_KEY", "sk-fake"), patch("openai.OpenAI", return_value=fake):
        res = client.post(f"/api/v1/boards/{board['id']}/close").json()

    assert res["deleted"] is False
    assert res["board"]["title"] == "Gleichungen mit Klammern"
    assert res["board"]["title_source"] == "ai"
    image = fake.chat.completions.create.call_args.kwargs["messages"][1]["content"][1]
    assert image["image_url"]["url"] == THUMB


def test_ai_never_overrides_a_name_given_by_hand(client):
    board = _new(client)
    _draw(client, board["id"])
    assert client.patch(f"/api/v1/boards/{board['id']}", json={"title": "Meine Hausaufgabe"}).json()["title_source"] == "user"
    fake = _fake_llm("Etwas anderes")
    with patch("backend.app.config.OPENAI_API_KEY", "sk-fake"), patch("openai.OpenAI", return_value=fake):
        res = client.post(f"/api/v1/boards/{board['id']}/close").json()
    assert res["board"]["title"] == "Meine Hausaufgabe"
    fake.chat.completions.create.assert_not_called()


def test_without_ai_the_automatic_name_stays(client):
    board = _new(client)
    _draw(client, board["id"])
    res = client.post(f"/api/v1/boards/{board['id']}/close").json()
    assert res["board"]["title"] == board["title"] and res["board"]["title_source"] == "auto"


def test_archived_boards_are_hidden_and_only_parents_see_them(client):
    board = _new(client)
    _draw(client, board["id"])
    client.post(f"/api/v1/boards/{board['id']}/archive")

    assert board["id"] not in [b["id"] for b in client.get("/api/v1/boards").json()]
    assert board["id"] in [b["id"] for b in client.get("/api/v1/boards/archived").json()]
    client.post(f"/api/v1/boards/{board['id']}/unarchive")
    assert board["id"] in [b["id"] for b in client.get("/api/v1/boards").json()]


def test_archived_list_requires_parent_mode(strict_client):
    assert strict_client.get("/api/v1/boards/archived").status_code == 403


def test_thumbnail_is_served_as_image(client):
    board = _new(client)
    assert client.get(f"/api/v1/boards/{board['id']}/thumbnail").status_code == 404
    _draw(client, board["id"])
    res = client.get(f"/api/v1/boards/{board['id']}/thumbnail")
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert res.content == b"\xff\xd8fakejpeg"


def test_parent_deletes_a_board_for_good(client):
    board = _new(client)
    _draw(client, board["id"])
    assert client.delete(f"/api/v1/boards/{board['id']}").status_code == 204
    assert board["id"] not in [b["id"] for b in client.get("/api/v1/boards").json()]
    assert client.get(f"/api/v1/boards/{board['id']}/thumbnail").status_code == 404
    assert client.delete(f"/api/v1/boards/{board['id']}").status_code == 404


def test_deleting_a_board_requires_parent_mode(strict_client):
    res = strict_client.post("/api/v1/boards", json={"subject_id": "sub_math"})
    board_id = res.json()["id"]
    assert strict_client.delete(f"/api/v1/boards/{board_id}").status_code == 403
    assert strict_client.patch(f"/api/v1/boards/{board_id}", json={"title": "Bruchrechnung"}).status_code == 200
