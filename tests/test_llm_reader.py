"""The AI reader's safety checks, tested with a fake model so no server is needed."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import llm_extractor  # noqa: E402
import reader  # noqa: E402
from catalogue import Catalogue  # noqa: E402
from chat_import import parse_chat  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def setup():
    messages = parse_chat((DATA / "chats" / "dinner_client.txt").read_text(encoding="utf-8"))
    return messages, Catalogue.load("q_dinner.json")


def raw(*changes):
    return json.dumps({"changes": list(changes)})


def change(**kw):
    base = {"item": "Roll-up banner", "line_id": "L03", "kind": "quantity_change", "qty_delta": 2,
            "price_delta": None, "outcome": "agreed", "messages": [1], "reason": "Asked and agreed."}
    return {**base, **kw}


def seq_with(messages, phrase):
    return next(m.seq for m in messages if phrase in m.text)


def test_agreed_change_without_a_stated_price_uses_the_quote_unit_price(setup):
    messages, catalogue = setup
    out = llm_extractor.build_changes(raw(change(messages=[messages[3].seq])), messages, catalogue)
    assert out[0].status == "ready" and out[0].price_delta == 2 * 90.0
    assert out[0].source == "ai"


def test_an_invented_price_is_dropped(setup):
    messages, catalogue = setup
    out = llm_extractor.build_changes(
        raw(change(kind="upgrade", qty_delta=0, price_delta=9999, messages=[messages[3].seq])), messages, catalogue)
    assert out[0].status == "needs_price" and out[0].price_delta is None   # a person must add it


def test_a_price_written_in_the_chat_is_kept(setup):
    messages, catalogue = setup
    seq = seq_with(messages, "RM 1,100 more")
    out = llm_extractor.build_changes(
        raw(change(item="LED wall", line_id="L02", kind="upgrade", qty_delta=0, price_delta=1100, messages=[seq])),
        messages, catalogue)
    assert out[0].status == "ready" and out[0].price_delta == 1100


def test_a_change_with_no_real_evidence_is_dropped(setup):
    messages, catalogue = setup
    assert llm_extractor.build_changes(raw(change(messages=[9999])), messages, catalogue) == []
    assert llm_extractor.build_changes(raw(change(messages=[])), messages, catalogue) == []


def test_unconfirmed_withdrawn_discount_and_no_cost_map_to_the_right_status(setup):
    messages, catalogue = setup
    m = messages[3].seq
    out = llm_extractor.build_changes(raw(
        change(outcome="asked", messages=[m]), change(outcome="withdrawn", messages=[m]),
        change(kind="discount", outcome="discount", qty_delta=0, messages=[m]),
        change(outcome="no_cost", qty_delta=0, messages=[m])), messages, catalogue)
    assert [c.status for c in out] == ["unconfirmed", "withdrawn", "needs_decision", "log_only"]
    assert out[2].price_delta is None            # the owner decides discounts


def test_bad_model_output_raises_so_the_rules_can_take_over(setup):
    messages, catalogue = setup
    for bad in ("not json", "{}", json.dumps({"changes": "x"})):
        with pytest.raises(llm_extractor.ReaderError):
            llm_extractor.build_changes(bad, messages, catalogue)


def test_reader_falls_back_to_rules_when_the_model_is_unreachable(setup, monkeypatch):
    messages, catalogue = setup
    monkeypatch.setenv("SMERGERS_READER", "llm")
    monkeypatch.setattr(reader, "_cache", {})
    monkeypatch.setattr(llm_extractor, "URL", "http://127.0.0.1:9/v1/chat/completions")
    monkeypatch.setattr(llm_extractor, "TIMEOUT", 2)
    out = reader.read(messages, catalogue)
    assert out and all(c.source == "rules" for c in out)
    assert "rules used instead" in reader.LAST_NOTE


def test_reader_defaults_to_rules(setup, monkeypatch):
    messages, catalogue = setup
    monkeypatch.delenv("SMERGERS_READER", raising=False)
    assert all(c.source == "rules" for c in reader.read(messages, catalogue))
