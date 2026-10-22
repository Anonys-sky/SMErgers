"""Reading a group live from WhatsApp (whatsapp/bridge.js) must give the same results as an export."""
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import store
import whatsapp_bridge
from catalogue import Catalogue
from chat_import import messages_from_whatsapp, parse_chat
from main import app
from rules_extractor import extract

CHATS = Path(__file__).resolve().parent.parent / "data" / "chats"
KL = ZoneInfo("Asia/Kuala_Lumpur")
GROUP = "120363000000000001@g.us"


def as_records(messages):
    """What the bridge would send for these messages."""
    return [{"wa_id": f"false_{GROUP}_{m.seq:06d}", "timestamp": m.sent_at.replace(tzinfo=KL).timestamp(),
             "sender": m.sender, "text": m.text, "is_media": m.is_media, "from_me": False}
            for m in messages if m.sender]  # the bridge drops system notices, as WhatsApp Web does


def summary(changes):
    return sorted((c.item, c.kind, c.line_id, c.qty_delta, c.price_delta, c.status) for c in changes)


@pytest.mark.parametrize("chat, quote", [(c, q) for _, c, q in store.DEMO_JOBS])
def test_live_messages_find_the_same_changes_as_the_export(chat, quote):
    exported = parse_chat((CHATS / chat).read_text(encoding="utf-8"))
    live = messages_from_whatsapp(as_records(exported), KL)
    catalogue = Catalogue.load(quote)
    assert summary(extract(live, catalogue)) == summary(extract(exported, catalogue))


def test_times_senders_and_text_match_the_export():
    exported = [m for m in parse_chat((CHATS / "dinner_client.txt").read_text(encoding="utf-8")) if m.sender]
    live = messages_from_whatsapp(as_records(exported), KL)
    assert [(m.sent_at, m.sender, m.text, m.is_media) for m in live] == \
           [(m.sent_at, m.sender, m.text, m.is_media) for m in exported]


def test_ids_are_stable_and_unique():
    records = [{"wa_id": "a", "timestamp": 1789452300, "sender": "A", "text": "ok"},
               {"wa_id": "b", "timestamp": 1789452300, "sender": "A", "text": "ok"}]
    first, second = messages_from_whatsapp(records, KL)
    assert first.id != second.id
    assert [m.id for m in messages_from_whatsapp(records, KL)] == [first.id, second.id]


def test_out_of_order_records_are_sorted_and_numbered():
    records = [{"wa_id": "late", "timestamp": 1789455900, "sender": "A", "text": "second"},
               {"wa_id": "early", "timestamp": 1789452300, "sender": "B", "text": "first"}]
    first, second = messages_from_whatsapp(records, KL)
    assert (first.text, first.seq, second.text, second.seq) == ("first", 1, "second", 2)
    assert first.sent_at == datetime(2026, 9, 15, 14, 5)  # 1789452300 is 15 Sep 2026, 2:05 pm in KL


def test_media_placeholder_is_flagged():
    (msg,) = messages_from_whatsapp([{"wa_id": "m", "timestamp": 1789452300, "sender": "A",
                                      "text": "<Media omitted>", "is_media": True}], KL)
    assert msg.is_media


# ---- the HTTP client, against a stand-in bridge ----

import io
import urllib.error


class FakeResponse(io.BytesIO):
    def __init__(self, data, code=200):
        super().__init__(data)
        self.code = code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture()
def bridge(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TIMEZONE", "Asia/Kuala_Lumpur")

    def fake_urlopen(url, timeout=None):
        path = url.replace("http://127.0.0.1:3001", "")
        if path == "/status":
            body, code = {"status": "ready", "qr": None, "me": {"name": "Fiesta", "number": "60123"}}, 200
        elif path == "/groups":
            body, code = {"groups": [{"id": GROUP, "name": "Sinar x Fiesta"}]}, 200
        elif path == f"/groups/{GROUP.replace('@', '%40')}/messages?limit=50":
            body, code = {"group": {"id": GROUP, "name": "Sinar x Fiesta"}, "messages": [
                {"wa_id": "x1", "timestamp": 1789452300, "sender": "Linda", "text": "Can adjust to 195?"}]}, 200
        else:
            data = json.dumps({"error": f"Group not found: {path}"}).encode()
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(data))
        return FakeResponse(json.dumps(body).encode(), code)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    yield


def test_client_reads_status_groups_and_messages(bridge):
    assert whatsapp_bridge.status()["status"] == "ready"
    assert whatsapp_bridge.list_groups()[0]["name"] == "Sinar x Fiesta"
    name, messages = whatsapp_bridge.fetch_group(GROUP, 50)
    assert name == "Sinar x Fiesta"
    assert messages[0].sender == "Linda" and messages[0].sent_at == datetime(2026, 9, 15, 14, 5)


def test_bridge_error_message_reaches_the_user(bridge):
    with pytest.raises(whatsapp_bridge.BridgeError, match="Group not found"):
        whatsapp_bridge.fetch_group("999@g.us", 50)


def test_bridge_not_running(monkeypatch):
    monkeypatch.setenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:9")  # nothing listens on the discard port
    assert whatsapp_bridge.status()["status"] == "offline"
    with pytest.raises(whatsapp_bridge.BridgeError, match="npm run whatsapp"):
        whatsapp_bridge.list_groups()


def test_bad_timezone_and_bad_group_are_refused(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TIMEZONE", "Mars/Olympus")
    with pytest.raises(whatsapp_bridge.BridgeError, match="time zone"):
        whatsapp_bridge.fetch_group(GROUP, 10)
    with pytest.raises(whatsapp_bridge.BridgeError, match="group"):
        whatsapp_bridge.fetch_group("60123456789@c.us", 10)  # a private chat, not a group


# ---- the pages ----

@pytest.fixture()
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def fake_status(monkeypatch, status, **extra):
    monkeypatch.setattr(whatsapp_bridge, "status", lambda: {"status": status, "qr": None, "me": None, **extra})


def test_page_explains_how_to_start_the_bridge(client, monkeypatch):
    fake_status(monkeypatch, "offline", error="not running")
    page = client.get("/whatsapp").data.decode()
    assert "npm run whatsapp" in page and 'http-equiv="refresh"' in page


def test_page_shows_qr_code_while_linking(client, monkeypatch):
    fake_status(monkeypatch, "qr", qr="data:image/png;base64,AAAA")
    page = client.get("/whatsapp").data.decode()
    assert 'src="data:image/png;base64,AAAA"' in page and "Linked devices" in page


def test_page_ignores_a_qr_that_is_not_an_image(client, monkeypatch):
    fake_status(monkeypatch, "qr", qr="javascript:alert(1)")
    assert "javascript:alert" not in client.get("/whatsapp").data.decode()


def test_page_lists_groups_when_connected(client, monkeypatch):
    fake_status(monkeypatch, "ready", me={"name": "Fiesta", "number": "60123"})
    monkeypatch.setattr(whatsapp_bridge, "list_groups",
                        lambda: [{"id": GROUP, "name": "Sinar x Fiesta", "participants": 4, "archived": False}])
    page = client.get("/whatsapp").data.decode()
    assert "Sinar x Fiesta (4 people)" in page and GROUP in page and 'http-equiv="refresh"' not in page


def test_reading_a_group_creates_a_job_like_an_upload(client, monkeypatch):
    exported = parse_chat((CHATS / "dinner_client.txt").read_text(encoding="utf-8"))
    live = messages_from_whatsapp(as_records(exported), KL)
    calls = []
    monkeypatch.setattr(whatsapp_bridge, "fetch_group", lambda gid, limit: calls.append((gid, limit)) or ("Sinar x Fiesta", live))
    resp = client.post("/whatsapp/import", data={"group": GROUP, "quote": "q_dinner.json", "limit": "500"})
    assert calls == [(GROUP, 500)]
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/job/annual-dinner-2026")
    record = store.JOBS["annual-dinner-2026"]
    assert record.chat_name == "WhatsApp group: Sinar x Fiesta"
    assert summary(c.change for c in record.job.items.values()) == \
           summary(c.change for c in store.JOBS["annual-dinner"].job.items.values())
    assert "RM3,540".encode() in client.get("/job/annual-dinner-2026").data


def test_bridge_problem_is_shown_not_crashed(client, monkeypatch):
    def fail(gid, limit):
        raise whatsapp_bridge.BridgeError("WhatsApp is not connected yet")
    monkeypatch.setattr(whatsapp_bridge, "fetch_group", fail)
    resp = client.post("/whatsapp/import", data={"group": GROUP, "quote": "q_dinner.json"}, follow_redirects=False)
    assert resp.headers["Location"].endswith("/whatsapp")
    fake_status(monkeypatch, "offline")
    assert b"WhatsApp is not connected yet" in client.get("/whatsapp").data


@pytest.mark.parametrize("form", [
    {"group": GROUP, "quote": "nope.json"},
    {"group": "", "quote": "q_dinner.json"},
    {"group": GROUP, "quote": "q_dinner.json", "limit": "0"},
    {"group": GROUP, "quote": "q_dinner.json", "limit": "abc"},
])
def test_bad_form_is_refused_without_reading_whatsapp(client, monkeypatch, form):
    monkeypatch.setattr(whatsapp_bridge, "fetch_group", lambda *a: pytest.fail("should not read WhatsApp"))
    resp = client.post("/whatsapp/import", data=form)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/whatsapp")


def test_clients_cannot_see_the_business_groups(client, monkeypatch):
    fake_status(monkeypatch, "ready")
    client.post("/role", data={"role": "client"})
    assert client.get("/whatsapp").status_code == 403
    assert client.post("/whatsapp/import", data={"group": GROUP, "quote": "q_dinner.json"}).status_code == 403
