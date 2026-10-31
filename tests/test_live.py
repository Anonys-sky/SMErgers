import hashlib
import hmac
import json

import pytest

import store
import webhook
import whatsapp_bridge
from bill import build_bill
from chat_import import messages_from_whatsapp, parse_chat
from catalogue import DATA
from main import app


@pytest.fixture()
def client(monkeypatch):
    store.reset_demo()
    monkeypatch.setattr(whatsapp_bridge, "start_sync", lambda: None)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.bridge_messages = []
        monkeypatch.setattr(whatsapp_bridge, "fetch_group", lambda *args: ("Test group", list(c.bridge_messages)))
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


# Actual bridge flow against a controlled message source; no demo routes.
def start_live(client, quote="q_dinner.json"):
    chat = next(chat for _, chat, q in store.DEMO_JOBS if q == quote)
    exported = [m for m in parse_chat((DATA / "chats" / chat).read_text()) if m.sender]
    client.pending_messages = messages_from_whatsapp([
        {"wa_id": f"message-{m.seq}", "timestamp": m.sent_at.replace(tzinfo=webhook.KL).timestamp(),
         "sender": m.sender, "text": m.text, "is_media": m.is_media} for m in exported], webhook.KL)
    client.bridge_messages = client.pending_messages[:3]
    client.pending_messages = client.pending_messages[3:]
    project = next(j for j, _, q in store.DEMO_JOBS if q == quote)
    response = client.post("/whatsapp/import", data={"group": "test@g.us", "project": project})
    assert response.status_code == 302
    return response.location.rsplit("/", 1)[-1]


def deliver(client, all=False):
    count = len(client.pending_messages) if all else 1
    client.bridge_messages.extend(client.pending_messages[:count])
    del client.pending_messages[:count]
    whatsapp_bridge.sync_groups()


def pm_view(client):
    client.post("/role", data={"role": "pm"})


def test_bridge_group_starts_with_history_without_simulated_controls(client):
    job_id = start_live(client)
    assert len(store.JOBS[job_id].messages) == 3 and store.JOBS[job_id].job.items == {}
    page = client.get(f"/job/{job_id}").data.decode()
    assert "whatsapp-sync.js" in page and "Tracking new WhatsApp messages" in page
    assert 'id="live-bar"' not in page and "simulated" not in record_page_source(page)


def record_page_source(page):
    return page.split('WhatsApp source ·', 1)[1].split('</p>', 1)[0]


def test_a_message_arriving_is_read_at_once_and_logged_as_the_trigger(client):
    job_id = start_live(client)
    record = store.JOBS[job_id]
    for _ in range(4):
        deliver(client)
    assert len(record.messages) == 7
    assert any(i.change.item == "Dinner package" for i in record.job.items.values())
    assert record.outbox[-1].to == "Aisyah"                      # the PM is told about the new change
    triggers = [e for e in record.job.log.entries if e.action == "trigger"]
    assert len(triggers) == 4  # initial history is imported once; each new arrival is registered once
    assert "WhatsApp bridge" in triggers[0].detail and record.job.log.intact()


def test_simulation_routes_are_removed(client):
    job_id = start_live(client)
    for path in ("/live/start", f"/job/{job_id}/live/next", f"/job/{job_id}/live/send"):
        assert client.post(path).status_code == 404
    assert b"Start live group" not in client.get("/").data
    assert b"Start live group" not in client.get("/imports").data


def test_play_the_rest_ends_with_the_same_changes_as_an_export(client):
    job_id = start_live(client)
    deliver(client, all=True)
    live_items = sorted((i.change.item, i.change.status, i.price) for i in store.JOBS[job_id].job.items.values())
    from rules_extractor import extract
    export_items = sorted((c.item, c.status, c.price_delta) for c in extract(store.JOBS[job_id].messages, store.JOBS[job_id].catalogue))
    assert live_items == export_items and not client.pending_messages


def test_the_webhook_route_feeds_the_live_group(client):
    record = store.build_from_messages("webhook-test", [], "Webhook group", "q_dinner.json")
    record.live = webhook.LiveFeed("webhook@g.us")
    store.GROUPS[record.live.group_id] = record.id
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "m1", "group_id": record.live.group_id, "from": "60123", "timestamp": "1789452300",
        "type": "text", "text": {"body": "195 people attending"}}]}}]}]}
    assert client.post("/webhooks/whatsapp", json=payload).data == b"ok"
    assert any("195 people" in m.text for m in record.messages)


def test_bridge_request_is_caught_without_guessing_that_it_was_agreed(client):
    job_id = start_live(client)
    record = store.JOBS[job_id]
    sender = "Client"
    client.bridge_messages.extend(messages_from_whatsapp([{"wa_id": "new-request", "timestamp": 1789552300,
        "sender": sender, "text": "Can we add 10 more pax?"}], webhook.KL))
    whatsapp_bridge.sync_groups()
    change = next(iter(record.job.items.values())).change
    assert change.status == "unconfirmed" and record.messages[-1].text == "Can we add 10 more pax?"
    assert any(e.action == "trigger" and sender in e.detail for e in record.job.log.entries)


def test_a_client_cannot_use_the_live_controls(client):
    job_id = start_live(client)
    client.post("/role", data={"role": "client"})
    assert "live-bar" not in client.get(f"/job/{job_id}", follow_redirects=True).data.decode()
    before = len(store.JOBS[job_id].messages)
    client.post(f"/job/{job_id}/live/send", data={"sender": "Client", "text": "ok"})
    client.post(f"/job/{job_id}/live/next")
    assert len(store.JOBS[job_id].messages) == before


@pytest.mark.parametrize("quote", sorted(q for _, _, q in store.DEMO_JOBS))
def test_every_sample_business_can_run_as_a_live_group(client, quote):
    export_id = next(j for j, _, q in store.DEMO_JOBS if q == quote)
    export_items = sorted((i.change.item, i.change.status, i.price) for i in store.JOBS[export_id].job.items.values())
    job_id = start_live(client, quote)
    deliver(client, all=True)
    live_items = sorted((i.change.item, i.change.status, i.price) for i in store.JOBS[job_id].job.items.values())
    assert live_items == export_items


def test_the_live_journey_ends_on_quote_version_two_in_the_group_and_history(client):
    job_id = start_live(client)
    deliver(client, all=True)
    for role in ("pm", "owner", "client"):
        client.post("/role", data={"role": role})
        client.post(f"/job/{job_id}/bulk")
    pm_view(client)
    page = client.get(f"/job/{job_id}").data.decode()
    assert "SMErgers → group" in page and "version 2" in page
    assert "version 2" in client.get(f"/job/{job_id}/history").data.decode()


def test_a_director_rejection_blocks_the_bill_and_is_recorded(client):
    job_id = start_live(client)
    record = store.JOBS[job_id]
    deliver(client, all=True)
    banner = next(k for k, i in record.job.items.items() if i.change.item == "Roll-up banner")
    pm_view(client)
    client.post(f"/job/{job_id}/act/{banner}", data={"action": "review"})
    client.post("/role", data={"role": "owner"})
    client.post(f"/job/{job_id}/act/{banner}", data={"action": "reject", "note": "client agreed to the old banners"})
    assert record.job.items[banner].state == "rejected"
    client.post(f"/job/{job_id}/bulk")                                   # approve all that is ready
    client.post("/role", data={"role": "client"})
    client.post(f"/job/{job_id}/bulk")                                   # confirm all that is ready
    assert record.job.items[banner].state == "rejected"                   # nobody can confirm a rejected change
    bill = build_bill(record.catalogue, record.job)
    on_bill = [key for line in bill.change_lines + bill.quote_lines for key in line.change_keys]
    assert banner not in on_bill and all(banner != item_key for item_key in on_bill)
    assert banner not in [next(k for k, v in record.job.items.items() if v is item) for item, _ in bill.outstanding]
    log = [e for e in record.job.log.entries if e.action == "reject"]
    assert log and log[0].change_key == banner and "old banners" in log[0].detail and record.job.log.intact()


# ---------------------------------------------------------------- saying no, and a second business
def test_a_rejection_without_a_reason_is_refused_and_leaves_no_trace(client):
    record = store.JOBS["annual-dinner"]
    key = next(k for k, i in record.job.items.items() if i.state == "detected")
    before = len(record.job.log.entries)
    client.post(f"/job/annual-dinner/act/{key}", data={"action": "reject"})
    assert record.job.items[key].state == "detected" and len(record.job.log.entries) == before


def test_a_director_rejection_tells_the_pm_with_the_reason(client):
    job_id = start_live(client)
    record = store.JOBS[job_id]
    deliver(client, all=True)
    banner = next(k for k, i in record.job.items.items() if i.change.item == "Roll-up banner")
    pm_view(client)
    client.post(f"/job/{job_id}/act/{banner}", data={"action": "review"})
    client.post("/role", data={"role": "owner"})
    client.post(f"/job/{job_id}/act/{banner}", data={"action": "reject", "note": "old banners are fine"})
    notice = record.outbox[-1]
    assert notice.kind == "reject_notice" and notice.to == "Aisyah"
    assert "old banners are fine" in notice.text and "will not reach the bill" in notice.text


def test_each_business_sets_its_own_approval_limit(client):
    assert store.JOBS["annual-dinner"].job.policy["owner_approval_at"] == 500
    assert store.JOBS["cafe-fit-out"].job.policy["owner_approval_at"] == 2000
    assert "RM2,000 or more" in client.get("/job/cafe-fit-out").data.decode()
    assert "RM500 or more" in client.get("/job/annual-dinner").data.decode()


def test_a_new_business_can_set_its_own_approval_limit_in_the_form(client):
    form = dict(title="Roof repair", client="Test Client", company="Test Roofing", quote_id="Q-1", event_type="repair",
                event_date="2026-11-01", pm="Ben", owner="Ben", finance="Ben", approval_limit="1500",
                item="Roof tiles", qty="100", unit="pcs", unit_price="10", aliases="tiles",
                chat_text="02/11/2026, 10:00 am - Client: add 50 more tiles\n02/11/2026, 10:05 am - Ben: ok")
    response = client.post("/projects/new", data=form)
    assert response.status_code == 302
    record = store.JOBS[response.location.rsplit("/", 1)[-1]]
    assert record.job.policy["owner_approval_at"] == 1500
    form["approval_limit"] = "0"
    assert client.post("/projects/new", data=form).status_code == 400


# ---------------------------------------------------------------- a person adds a change the reader missed
def evidence_ids(record, *phrases):
    from chat_import import find_message
    return [find_message(record.messages, p).id for p in phrases]


def test_a_person_can_add_a_missed_change_and_the_director_must_sign_it_off(client):
    record = store.JOBS["annual-dinner"]
    ids = evidence_ids(record, "195 people attending")
    client.post("/role", data={"role": "pm"})
    answer = client.post("/job/annual-dinner/changes/add", data={
        "item": "Welcome drinks", "kind": "extra", "price": "400", "qty": "1", "evidence": ids, "note": "agreed by voice note"})
    assert answer.status_code == 302 and "show=m1" in answer.location
    item = record.job.items["m1"]
    assert item.state == "detected" and item.price == 400 and item.change.source == "manual"
    client.post("/job/annual-dinner/act/m1", data={"action": "review"})
    assert item.state == "reviewed" and "added by staff" in item.needs_owner_reason       # below RM500, still the director
    client.post("/role", data={"role": "owner"})
    client.post("/job/annual-dinner/act/m1", data={"action": "approve"})
    client.post("/role", data={"role": "client"})
    client.post("/job/annual-dinner/act/m1", data={"action": "confirm"})
    assert item.state == "confirmed"
    assert any(e.action == "add" and e.change_key == "m1" and "had not found it" in e.detail for e in record.job.log.entries)
    assert record.job.log.intact()


def test_adding_a_change_needs_evidence_a_kind_and_a_sensible_price(client):
    record = store.JOBS["annual-dinner"]
    ids = evidence_ids(record, "195 people attending")
    client.post("/role", data={"role": "pm"})
    base = {"item": "Welcome drinks", "kind": "extra", "price": "400", "evidence": ids}
    for bad in ({**base, "evidence": []}, {**base, "item": "  "}, {**base, "kind": "magic"},
                {**base, "price": "four hundred"}, {**base, "price": "1e309"}, {**base, "line_id": "L99"}):
        client.post("/job/annual-dinner/changes/add", data=bad)
    assert "m1" not in record.job.items
    client.post("/job/annual-dinner/changes/add", data={**base, "evidence": ["not-a-message-id"]})
    assert "m1" not in record.job.items                                                    # made-up evidence is dropped


def test_a_discount_added_by_hand_goes_to_the_director_with_no_amount(client):
    record = store.JOBS["annual-dinner"]
    client.post("/role", data={"role": "owner"})
    client.post("/job/annual-dinner/changes/add", data={
        "item": "Loyalty discount", "kind": "discount", "price": "-100", "evidence": evidence_ids(record, "195 people attending")})
    item = record.job.items["m1"]
    assert item.price is None and item.change.status == "needs_decision"


def test_a_client_cannot_add_a_change(client):
    record = store.JOBS["annual-dinner"]
    client.post("/role", data={"role": "client"})
    client.post("/job/annual-dinner/changes/add", data={
        "item": "Free cake", "kind": "extra", "price": "0", "evidence": evidence_ids(record, "195 people attending")})
    assert "m1" not in record.job.items


def test_a_manual_change_survives_new_messages_arriving_in_a_live_group(client):
    job_id = start_live(client)
    record = store.JOBS[job_id]
    deliver(client)
    client.post("/role", data={"role": "pm"})
    client.post(f"/job/{job_id}/changes/add", data={"item": "Welcome drinks", "kind": "extra", "price": "400",
                                                      "evidence": [record.messages[-1].id]})
    deliver(client, all=True)
    assert record.job.items["m1"].change.source == "manual" and record.job.items["m1"].price == 400
