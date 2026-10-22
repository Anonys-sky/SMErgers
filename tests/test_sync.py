from datetime import datetime

import store
import sync
from catalogue import DATA
from chat_import import parse_chat
from rules_extractor import extract

NOW = datetime(2026, 10, 12, 9, 0)


def dinner():
    text = (DATA / "chats" / "dinner_client.txt").read_text(encoding="utf-8")
    return store.build("t-dinner", text, "dinner_client.txt", "q_dinner.json")


def key_for(record, item_name):
    return next(k for k, i in record.job.items.items() if i.change.item == item_name)


def test_version_one_is_the_signed_quote():
    r = dinner()
    assert [(v.number, v.total) for v in r.versions] == [(1, 34530)]


def test_named_people_come_from_the_directory():
    r = dinner()
    assert r.actor("owner").name == "Daniel" and r.actor("pm").name == "Aisyah"
    assert r.actor("client").name == "Sinar Demo Trading Sdn Bhd"


def test_review_asks_the_owner_and_approval_asks_the_client():
    r = dinner()
    led = key_for(r, "LED wall 3m x 2m, changed to 4m x 2.5m")
    r.job.act(led, "review", r.actor("pm"), NOW)
    sync.after_actions(r, "review", [led], r.actor("pm"), NOW)
    assert r.outbox[-1].to == "Daniel" and r.outbox[-1].kind == "approval_request"
    r.job.act(led, "approve", r.actor("owner"), NOW)
    sync.after_actions(r, "approve", [led], r.actor("owner"), NOW)
    assert r.outbox[-1].kind == "confirm_request" and "RM1,100" in r.outbox[-1].text


def test_confirmation_makes_a_new_version_and_tells_the_group():
    r = dinner()
    banners = key_for(r, "Roll-up banner")
    r.job.act(banners, "review", r.actor("pm"), NOW)
    r.job.act(banners, "confirm", r.actor("client"), NOW)
    sync.after_actions(r, "confirm", [banners], r.actor("client"), NOW)
    assert [v.number for v in r.versions] == [1, 2]
    assert r.versions[-1].total == 34530 + 270
    group = r.outbox[-1]
    assert group.to == "Group" and "version 2" in group.text and "RM34,800" in group.text
    assert r.job.log.entries[-1].action == "sync" and r.job.log.intact()


def test_refresh_adds_new_changes_and_keeps_decisions():
    messages = parse_chat((DATA / "chats" / "dinner_client.txt").read_text(encoding="utf-8"))
    early = messages[:12]                        # up to the LED question, before its price
    r = store.build_from_messages("t-live", early, "live", "q_dinner.json")
    banners = key_for(r, "Roll-up banner")
    r.job.act(banners, "review", r.actor("pm"), NOW)
    new = r.job.refresh(extract(messages, r.catalogue), NOW)
    assert new                                   # later changes appear
    assert r.job.items[banners].state == "approved"   # a decision already made is kept
    led = key_for(r, "LED wall 3m x 2m, changed to 4m x 2.5m")
    assert r.job.items[led].price == 1100        # the price stated later was picked up
