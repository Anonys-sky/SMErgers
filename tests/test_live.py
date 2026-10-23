import hashlib
import hmac
import json

import pytest

import store
import webhook
from main import app


@pytest.fixture()
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def live():
    return store.JOBS["annual-dinner-live"]


def test_live_job_starts_with_the_quote_messages_only():
    store.reset_demo()
    assert len(live().messages) == 3 and live().job.items == {}


def test_next_message_button_feeds_the_chat(client):
    for _ in range(4):
        client.post("/job/annual-dinner-live/live/next")
    assert len(live().messages) == 7
    assert any(i.change.item == "Dinner package" for i in live().job.items.values())
    assert live().outbox[-1].to == "Aisyah"      # the PM is told about the new change


def test_play_the_rest_ends_with_the_same_changes_as_an_export(client):
    client.post("/job/annual-dinner-live/live/next", data={"all": "1"})
    live_items = sorted((i.change.item, i.change.status, i.price) for i in live().job.items.values())
    export_items = sorted((i.change.item, i.change.status, i.price) for i in store.JOBS["annual-dinner"].job.items.values())
    assert live_items == export_items and not live().live.script


def test_webhook_accepts_metas_payload_format(client):
    msg = store.JOBS["annual-dinner"].messages[4]          # "195 people attending"
    payload = webhook.payload_for(live().live.group_id, msg, 999)
    assert client.post("/webhooks/whatsapp", json=payload).data == b"ok"
    assert any("195 people" in m.text for m in live().messages)


def test_webhook_checks_the_signature_when_a_secret_is_set(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cret")
    body = json.dumps({"entry": []}).encode()
    assert client.post("/webhooks/whatsapp", data=body, content_type="application/json").status_code == 403
    good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    ok = client.post("/webhooks/whatsapp", data=body, content_type="application/json",
                     headers={"X-Hub-Signature-256": good})
    assert ok.status_code == 200


def test_webhook_verification_echoes_the_challenge(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "tok")
    good = client.get("/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=tok&hub.challenge=42")
    assert good.data == b"42"
    assert client.get("/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=no&hub.challenge=42").status_code == 403


def test_confirmation_shows_up_in_the_group_and_versions_page(client):
    client.post("/job/annual-dinner-live/live/next", data={"all": "1"})
    for role in ("pm", "owner", "client"):
        client.post("/role", data={"role": role})
        client.post("/job/annual-dinner-live/bulk")
    client.post("/role", data={"role": "pm"})
    page = client.get("/job/annual-dinner-live").data.decode()
    assert "SMErgers → group" in page and "version 2" in page
    assert "version 2" in client.get("/job/annual-dinner-live/history").data.decode()


def test_guide_walks_through_the_journey(client):
    page = client.get("/job/annual-dinner-live").data.decode()
    assert "New messages are waiting" in page
    client.post("/job/annual-dinner-live/live/next", data={"all": "1"})
    assert "Aisyah checks each change" in client.get("/job/annual-dinner-live").data.decode()
    mic = next(k for k, i in store.JOBS["annual-dinner-live"].job.items.items() if i.change.item == "Wireless mic")
    client.post(f"/job/annual-dinner-live/act/{mic}", data={"action": "set_price", "price": "320"})
    assert "Aisyah checks each change" in client.get("/job/annual-dinner-live").data.decode()   # still the PM's turn
    client.post("/job/annual-dinner-live/bulk")
    page = client.get("/job/annual-dinner-live").data.decode()
    assert "Continue as Daniel (Project director)" in page
    assert client.post("/job/annual-dinner-live/as/owner").location.endswith("/job/annual-dinner-live")
    assert client.post("/job/annual-dinner-live/as/client").location.endswith("/job/annual-dinner-live/client")


def test_old_pages_redirect_to_history(client):
    assert client.get("/job/annual-dinner/log").location.endswith("/job/annual-dinner/history#log")
    assert client.get("/job/annual-dinner/updates").location.endswith("/job/annual-dinner/history")
