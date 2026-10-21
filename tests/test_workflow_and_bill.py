from datetime import datetime
from pathlib import Path

import pytest

from bill import build_bill
from catalogue import Catalogue
from chat_import import find_message, parse_chat
from rules_extractor import extract
from workflow import Actor, Job, NotAllowed

CHATS = Path(__file__).resolve().parent.parent / "data" / "chats"
PM, OWNER, CLIENT = Actor("Aisyah", "pm"), Actor("Daniel", "owner"), Actor("Mr Tan", "client")
NOW = datetime(2026, 10, 12, 9, 0)


def dinner_job():
    messages = parse_chat((CHATS / "dinner_client.txt").read_text(encoding="utf-8"))
    catalogue = Catalogue.load("q_dinner.json")
    changes = extract(messages, catalogue)
    by_phrase = lambda p: next(c.key for c in changes if find_message(messages, p).id in c.evidence_ids)
    return catalogue, Job(changes, now=NOW), by_phrase


def test_small_change_skips_owner_and_large_one_needs_owner():
    _, job, key = dinner_job()
    assert job.act(key("2 more roll-up banner"), "review", PM, NOW).state == "approved"       # RM270
    item = job.act(key("upgrade to 4m x 2.5m"), "review", PM, NOW)                             # RM1,100
    assert item.state == "reviewed" and "limit" in item.needs_owner_reason
    assert job.act(key("upgrade to 4m x 2.5m"), "approve", OWNER, NOW).state == "approved"


def test_roles_are_enforced():
    _, job, key = dinner_job()
    banners = key("2 more roll-up banner")
    with pytest.raises(NotAllowed):
        job.act(banners, "approve", CLIENT, NOW)
    with pytest.raises(NotAllowed):
        job.act(banners, "confirm", CLIENT, NOW)      # not approved yet


def test_missing_price_blocks_review_and_staff_price_needs_owner():
    _, job, key = dinner_job()
    mic = key("2 extra wireless mic")
    with pytest.raises(NotAllowed):
        job.act(mic, "review", PM, NOW)
    job.act(mic, "set_price", PM, NOW, price=320, note="2 x RM160 from AV vendor")
    item = job.act(mic, "review", PM, NOW)
    assert item.state == "reviewed" and "staff" in item.needs_owner_reason


def test_only_confirmed_changes_reach_the_bill():
    catalogue, job, key = dinner_job()
    pax, banners = key("195 people attending"), key("2 more roll-up banner")
    for k in (pax, banners):
        job.act(k, "review", PM, NOW)
        if job.items[k].state == "reviewed":
            job.act(k, "approve", OWNER, NOW)
    job.act(pax, "confirm", CLIENT, NOW)
    bill = build_bill(catalogue, job)
    dinner_line = next(l for l in bill.quote_lines if l.label == "Dinner package")
    banner_line = next(l for l in bill.quote_lines if l.label == "Roll-up banner")
    assert dinner_line.qty == 195 and dinner_line.note == "quote: 180"
    assert banner_line.qty == 4                         # approved but not confirmed: not billed yet
    assert bill.draft_total == bill.quote_total + 1920
    assert any(i.change.key == banners for i, _ in bill.outstanding)


def test_whole_dinner_flow_reaches_expected_total():
    catalogue, job, key = dinner_job()
    job.act(key("2 extra wireless mic"), "set_price", PM, NOW, price=320)
    for k, item in job.items.items():
        if item.state == "detected":
            job.act(k, "review", PM, NOW)
        if item.state == "reviewed":
            job.act(k, "approve", OWNER, NOW)
        if item.state == "approved":
            job.act(k, "confirm", CLIENT, NOW)
    bill = build_bill(catalogue, job)
    assert bill.changes_total == 3540 + 320
    assert bill.outstanding == []
    assert bill.agreed_beyond_quote == 1920 + 270 + 1100 + 300 + 250 - 300 + 320


def test_discount_is_owner_only():
    messages = parse_chat((CHATS / "wedding_client.txt").read_text(encoding="utf-8"))
    changes = extract(messages, Catalogue.load("q_wedding.json"))
    job = Job(changes, now=NOW)
    disc = next(c.key for c in changes if c.kind == "discount")
    with pytest.raises(NotAllowed):
        job.act(disc, "review", PM, NOW)
    assert job.act(disc, "decide", OWNER, NOW, price=-2419.5, note="5% of the original quote").state == "approved"


def test_dispute_needs_a_reason_and_returns_to_pm():
    _, job, key = dinner_job()
    banners = key("2 more roll-up banner")
    job.act(banners, "review", PM, NOW)
    with pytest.raises(NotAllowed):
        job.act(banners, "dispute", CLIENT, NOW)
    job.act(banners, "dispute", CLIENT, NOW, note="We asked for 2, not 3")
    assert job.act(banners, "set_price", PM, NOW, price=180).state == "disputed"
    assert job.act(banners, "review", PM, NOW).state == "reviewed"   # staff-changed price now needs the owner


def test_log_records_every_action_and_detects_edits():
    _, job, key = dinner_job()
    job.act(key("2 more roll-up banner"), "review", PM, NOW)
    assert [e.action for e in job.log.entries] == ["import", "review"]
    assert job.log.intact()
    job.log.entries[1].detail = "quietly changed"
    assert not job.log.intact()
