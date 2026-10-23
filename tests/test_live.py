import hashlib
import hmac
import json

import pytest

import store
from main import app


@pytest.fixture()
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


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


def test_old_pages_redirect_to_history(client):
    assert client.get("/job/annual-dinner/log").location.endswith("/job/annual-dinner/history#log")
    assert client.get("/job/annual-dinner/updates").location.endswith("/job/annual-dinner/history")
