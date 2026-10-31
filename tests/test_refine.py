"""Rules read a new message at once; the AI reader refines the answer in the background (AI projects only).
The AI is faked, so no model or network is needed."""
import json
from dataclasses import replace

import pytest

import reader
import store
import whatsapp_bridge
from catalogue import DATA, Catalogue
from chat_import import parse_chat
from schema import Change
from test_demo_script import export_text
from workflow import Job


def change(key, item, evidence, status="unconfirmed", price=None, qty=0, line=None, source="rules"):
    return Change(key, "quantity_change", item, line, qty, price, status, list(evidence), "medium", "", source)


def job(*changes):
    return Job(list(changes))


# ---- the reconcile step

def test_the_ai_reading_refines_an_untouched_item_in_place_and_keeps_its_key():
    j = job(change("t1", "Dinner package", ["a", "b"], line="L01", qty=15))
    new = j.reconcile([change("ai1", "195 guests", ["a", "b"], "ready", 1920.0, 15, "L01", "ai")], prefer_incoming=True)
    assert new == [] and list(j.items) == ["t1"]                      # same item, no duplicate
    item = j.items["t1"]
    assert item.change.source == "ai" and item.price == 1920.0 and item.change.status == "ready"
    assert item.change.item == "Dinner package"                           # the quote's name stays, not the model's wording
    assert any("refined by the AI reader" in e.detail for e in j.log.entries)


def test_an_item_a_person_already_acted_on_is_never_touched():
    j = job(change("t1", "Dinner package", ["a"], line="L01", qty=15, status="ready", price=1920.0))
    j.items["t1"].state = "reviewed"                                   # the PM checked it
    j.reconcile([change("ai1", "Dinner package", ["a"], "unconfirmed", None, 15, "L01", "ai")], prefer_incoming=True)
    assert j.items["t1"].change.source == "rules" and j.items["t1"].price == 1920.0 and j.items["t1"].state == "reviewed"


def test_an_item_with_a_note_is_left_alone_too():
    j = job(change("t1", "Dinner package", ["a"], line="L01", qty=15))
    j.items["t1"].notes.append(("pm", "x", "checked with the client"))
    j.reconcile([change("ai1", "Dinner package", ["a"], "ready", 1920.0, 15, "L01", "ai")], prefer_incoming=True)
    assert j.items["t1"].change.source == "rules"


def test_a_change_only_the_ai_found_is_added_with_a_key_that_does_not_clash():
    j = job(change("ai1", "Banners", ["x"], line="L03", qty=2, source="ai"))
    new = j.reconcile([change("ai1", "Wireless mic", ["y"], qty=2, source="ai")], prefer_incoming=True)
    assert new == ["ai2"] and set(j.items) == {"ai1", "ai2"}
    assert j.items["ai1"].change.item == "Banners" and j.items["ai2"].change.item == "Wireless mic"


def test_two_separate_requests_for_the_same_line_are_not_merged():
    j = job(change("t1", "Dinner package", ["m2", "m3"], line="L01", qty=15),
            change("t2", "Dinner package", ["m9", "m10"], line="L01", qty=10))
    j.reconcile([change("ai1", "Dinner package", ["m2", "m3"], "ready", 1920.0, 15, "L01", "ai"),
                 change("ai2", "Dinner package", ["m9", "m10"], "ready", 1280.0, 10, "L01", "ai")], prefer_incoming=True)
    assert len(j.items) == 2
    assert {i.price for i in j.items.values()} == {1920.0, 1280.0}


def test_more_and_fewer_are_not_the_same_request():
    j = job(change("t1", "Roll-up banner", ["a"], line="L03", qty=2))
    j.reconcile([change("ai1", "Roll-up banner", ["a"], "ready", -90.0, -1, "L03", "ai")], prefer_incoming=True)
    assert len(j.items) == 2


def test_the_quick_rules_pass_does_not_undo_the_ai_reading():
    j = job(change("ai1", "195 guests", ["a"], "ready", 1920.0, 15, "L01", "ai"))
    new = j.reconcile([change("t1", "Dinner package", ["a"], "unconfirmed", None, 15, "L01")], prefer_incoming=False)
    assert new == [] and j.items["ai1"].change.source == "ai" and j.items["ai1"].price == 1920.0


# ---- the live path

@pytest.fixture
def group():
    script = json.loads((DATA / "demo_group_script.json").read_text(encoding="utf-8"))
    messages = [m for m in parse_chat(export_text(script)) if m.sender]
    catalogue = Catalogue.load(script["quote"])
    store.reset_demo()
    first, later = messages[:6], messages[6:]
    record = store.build_with_catalogue("refine-test", first, "WhatsApp group: test", catalogue, ai=False)
    record.bridge = whatsapp_bridge.GroupSync("g", 200)
    record.ai = True                                                   # this project asked for the AI reader
    return record, later


def ai_reading(changes):
    return [replace(c, key=f"ai{i}", source="ai", confidence="high", reason="ai") for i, c in enumerate(changes, 1)]


def test_rules_show_a_new_message_at_once_and_the_ai_refines_it_without_duplicates(group, monkeypatch):
    record, later = group
    started = []
    monkeypatch.setattr(whatsapp_bridge, "refine_async", lambda r: started.append(r))
    whatsapp_bridge.apply_messages(record, later)
    assert started == [record]                                         # the AI pass was asked for, not awaited
    quick = {k: i.change.item for k, i in record.job.items.items()}
    assert any(k.startswith("t") for k in quick) and len(quick) >= 4  # the rules answer is already on the page

    monkeypatch.setattr(reader, "read", lambda messages, catalogue, ai=None: ai_reading(
        reader.rules_extractor.extract(messages, catalogue)))
    monkeypatch.setattr(reader, "LAST_NOTE", "", raising=False)
    whatsapp_bridge.refine_ai(record)
    assert set(record.job.items) == set(quick)                         # same items, no duplicates
    assert all(i.change.source == "ai" for i in record.job.items.values())


def test_if_the_ai_cannot_answer_the_rules_reading_stays_and_it_is_logged_once(group, monkeypatch):
    record, later = group
    monkeypatch.setattr(whatsapp_bridge, "refine_async", lambda r: None)
    whatsapp_bridge.apply_messages(record, later)
    before = {k: (i.change.status, i.price) for k, i in record.job.items.items()}

    def failing(messages, catalogue, ai=None):
        reader.LAST_NOTE = "AI reader unavailable, rules used instead (offline)"
        return reader.rules_extractor.extract(messages, catalogue)
    monkeypatch.setattr(reader, "read", failing)
    whatsapp_bridge.refine_ai(record)
    whatsapp_bridge.refine_ai(record)
    assert {k: (i.change.status, i.price) for k, i in record.job.items.items()} == before
    assert sum(1 for e in record.job.log.entries if e.action == "ai") == 1
    reader.LAST_NOTE = ""


def test_a_refinement_that_was_overtaken_by_new_messages_is_dropped(group, monkeypatch):
    record, later = group
    monkeypatch.setattr(whatsapp_bridge, "refine_async", lambda r: None)
    whatsapp_bridge.apply_messages(record, later[:1])
    before = {k: i.change.source for k, i in record.job.items.items()}

    def slow_then_overtaken(messages, catalogue, ai=None):
        whatsapp_bridge.apply_messages(record, later[1:2])             # another message lands while the model reads
        return ai_reading(reader.rules_extractor.extract(messages, catalogue))
    monkeypatch.setattr(reader, "read", slow_then_overtaken)
    monkeypatch.setattr(reader, "LAST_NOTE", "", raising=False)
    assert whatsapp_bridge.refine_ai(record) is None
    assert all(record.job.items[k].change.source == before[k] for k in before)


def test_messages_arriving_during_a_refinement_cost_one_extra_read_not_one_each():
    class Record:
        id = "x"
        bridge = whatsapp_bridge.GroupSync("g", 10)
    Record.bridge.ai_running = True                                    # a refinement is already running
    whatsapp_bridge.refine_async(Record)
    whatsapp_bridge.refine_async(Record)
    assert Record.bridge.ai_dirty is True and Record.bridge.ai_running is True


def test_a_project_that_did_not_ask_for_the_ai_is_untouched_by_all_of_this(group, monkeypatch):
    record, later = group
    record.ai = False
    called = []
    monkeypatch.setattr(whatsapp_bridge, "refine_async", lambda r: called.append(r))
    whatsapp_bridge.apply_messages(record, later)
    assert called == []                                                # no AI pass for a rules-only project
    assert all(k.startswith("t") for k in record.job.items)            # and the original refresh path ran
