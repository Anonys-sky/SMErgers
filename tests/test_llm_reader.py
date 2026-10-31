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


def test_a_reduction_is_priced_from_the_quote_and_a_missing_line_is_looked_up(setup):
    messages, catalogue = setup
    cut = llm_extractor.build_changes(
        raw(change(item="registration desk staff", line_id="L10", kind="replacement", qty_delta=-2,
                   messages=[messages[3].seq])), messages, catalogue)
    assert cut[0].price_delta == -2 * catalogue.line("L10").unit_price
    lookup = llm_extractor.build_changes(
        raw(change(item="banners", line_id=None, kind="extra", qty_delta=3, messages=[messages[3].seq])),
        messages, catalogue)
    assert lookup[0].line_id == "L03" and lookup[0].price_delta == 270


def test_runpod_settings_build_the_endpoint_url(monkeypatch):
    import importlib
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "abc123")
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key")
    for name in ("SMERGERS_LLM_URL", "SMERGERS_LLM_MODEL", "SMERGERS_LLM_KEY"):
        monkeypatch.delenv(name, raising=False)
    try:
        fresh = importlib.reload(llm_extractor)
        assert fresh.URL == "https://api.runpod.ai/v2/abc123/openai/v1/chat/completions"
        assert fresh.KEY == "test-key" and "Llama" in fresh.MODEL
    finally:
        monkeypatch.delenv("RUNPOD_ENDPOINT_ID")
        monkeypatch.delenv("RUNPOD_API_KEY")
        importlib.reload(llm_extractor)


def test_import_with_ai_falls_back_to_rules_and_says_so(monkeypatch):
    import io
    import main
    monkeypatch.setattr(reader, "_cache", {})
    monkeypatch.setattr(llm_extractor, "URL", "http://127.0.0.1:9/v1/chat/completions")
    monkeypatch.setattr(llm_extractor, "TIMEOUT", 2)
    raw = (DATA / "chats" / "dinner_client.txt").read_text(encoding="utf-8")
    client = main.app.test_client()
    page = client.post("/import", data={"quote": "q_dinner.json", "ai": "1", "chat": (io.BytesIO(raw.encode()), "x.txt")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert b"could not be reached" in page.data


def test_import_with_ai_uses_the_model_when_it_answers(monkeypatch, setup):
    import io
    import main
    import store
    messages, _ = setup
    monkeypatch.setattr(reader, "_cache", {})
    monkeypatch.setattr(llm_extractor, "_call", lambda prompt: raw(change(messages=[messages[3].seq])))
    text = (DATA / "chats" / "dinner_client.txt").read_text(encoding="utf-8")
    page = main.app.test_client().post("/import", data={"quote": "q_dinner.json", "ai": "1", "chat": (io.BytesIO(text.encode()), "y.txt")},
                                       content_type="multipart/form-data", follow_redirects=True)
    assert b"Read by the AI reader" in page.data
    newest = list(store.JOBS.values())[-1]
    assert newest.ai and all(i.change.source == "ai" for i in newest.job.items.values())


def test_a_price_promised_for_later_is_not_filled_in_from_the_quote(setup):
    messages, catalogue = setup
    from schema import Message
    chat = [Message("a", 1, messages[0].sent_at, "Client", "Add 2 more roll-up banners, price later ok?", False),
            Message("b", 2, messages[0].sent_at, "PM", "Ok, we will confirm the price later", False)]
    out = llm_extractor.build_changes(raw(change(messages=[1, 2])), chat, catalogue)
    assert out[0].status == "needs_price" and out[0].price_delta is None


def test_a_last_message_of_let_me_check_is_not_a_yes(setup):
    messages, catalogue = setup
    from schema import Message
    chat = [Message("a", 1, messages[0].sent_at, "Client", "Can we add 2 more banners?", False),
            Message("b", 2, messages[0].sent_at, "Client", "Let me ask my boss first", False)]
    out = llm_extractor.build_changes(raw(change(messages=[1, 2])), chat, catalogue)
    assert out[0].status == "unconfirmed"


def test_let_me_check_followed_by_a_yes_still_counts_as_agreed(setup):
    messages, catalogue = setup
    from schema import Message
    chat = [Message("a", 1, messages[0].sent_at, "Client", "Let me ask my boss first", False),
            Message("b", 2, messages[0].sent_at, "Client", "Boss says ok, go ahead with 2 more banners", False)]
    out = llm_extractor.build_changes(raw(change(messages=[1, 2])), chat, catalogue)
    assert out[0].status == "ready"


def test_a_colour_or_time_swap_with_no_price_is_logged_not_priced(setup):
    messages, catalogue = setup
    out = llm_extractor.build_changes(
        raw(change(item="Backdrop colour", line_id=None, kind="non_billable", qty_delta=0, messages=[messages[3].seq])),
        messages, catalogue)
    assert out[0].status == "log_only" and out[0].price_delta == 0.0


@pytest.fixture
def catering():
    messages = parse_chat((DATA / "chats" / "blind2_catering.txt").read_text(encoding="utf-8"))
    return messages, Catalogue.load("q_blind2_catering.json")


def test_a_price_in_the_next_message_is_found_when_the_model_did_not_cite_it(catering):
    messages, catalogue = catering
    asked, agreed = seq_with(messages, "Cendol boleh"), seq_with(messages, "ok go ahead Hafiz")
    out = llm_extractor.build_changes(
        raw(change(item="Cendol upgrade", line_id="L07", kind="upgrade", qty_delta=0, outcome="agreed",
                   messages=[asked, agreed])), messages, catalogue)
    assert out[0].status == "ready" and out[0].price_delta == 300
    stated = next(m.id for m in messages if "total rm 300" in m.text)
    assert stated in out[0].evidence_ids                    # the message that states it is now shown as proof


def test_two_amounts_for_one_item_are_not_guessed(catering):
    messages, catalogue = catering
    seq = seq_with(messages, "OT crew")
    out = llm_extractor.build_changes(
        raw(change(item="Staff overtime", line_id=None, kind="extra", qty_delta=0, outcome="asked", messages=[seq - 1])),
        messages, catalogue)
    assert out[0].price_delta in (None, 120)               # either nothing, or the one amount that is written


def test_a_later_recap_saying_price_to_confirm_stops_the_unit_price_filling_in(setup):
    messages, catalogue = setup
    seq = messages[3].seq
    recap = type(messages[3])(id="x", seq=seq + 50, sent_at=messages[3].sent_at, sender="Aisyah (Fiesta PM)",
                              text="Recap: more roll-up banner (price to confirm)")
    out = llm_extractor.build_changes(raw(change(item="Roll-up banner", messages=[seq])), messages + [recap], catalogue)
    assert out[0].status == "needs_price" and out[0].price_delta is None


def test_the_second_pass_adds_what_the_first_missed_and_never_a_duplicate(monkeypatch, setup):
    messages, catalogue = setup
    first = raw(change(messages=[messages[3].seq]))
    again = raw(change(messages=[messages[3].seq]),                     # same change again: dropped
                change(item="Wireless mic", line_id=None, kind="extra", qty_delta=2, outcome="asked",
                       messages=[messages[5].seq]))
    answers = iter([first, again])
    monkeypatch.setattr(llm_extractor, "_call", lambda prompt: next(answers))
    out = llm_extractor.extract(messages, catalogue)
    assert [c.item for c in out] == ["Roll-up banner", "Wireless mic"] and [c.key for c in out] == ["ai1", "ai2"]


def test_a_failed_second_pass_keeps_the_first_reading(monkeypatch, setup):
    messages, catalogue = setup
    answers = iter([raw(change(messages=[messages[3].seq]))])

    def call(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise llm_extractor.ReaderError("offline")
    monkeypatch.setattr(llm_extractor, "_call", call)
    assert len(llm_extractor.extract(messages, catalogue)) == 1


@pytest.fixture
def aircond():
    messages = parse_chat((DATA / "chats" / "blind2_aircond.txt").read_text(encoding="utf-8"))
    return messages, Catalogue.load("q_blind2_aircond.json")


def test_a_recap_that_says_price_to_confirm_for_one_item_does_not_hold_back_the_others(aircond):
    messages, catalogue = aircond
    unit = seq_with(messages, "ok noted, dua point")
    asked = seq_with(messages, "tambah dua power point")
    out = llm_extractor.build_changes(
        raw(change(item="2 power points in the kitchen", line_id=None, kind="extra", qty_delta=2, outcome="agreed",
                   messages=[asked, unit])), messages, catalogue)
    assert out[0].status == "ready" and out[0].price_delta == 300          # "RM 150 each" x 2


def test_the_item_the_recap_marks_price_to_confirm_still_waits_for_a_price(aircond):
    messages, catalogue = aircond
    seq = seq_with(messages, "will add the cable tray")
    out = llm_extractor.build_changes(
        raw(change(item="Cable tray along the corridor", line_id="L06", kind="extra", qty_delta=1, outcome="agreed",
                   messages=[seq - 1, seq])), messages, catalogue)
    assert out[0].status == "needs_price" and out[0].price_delta is None


def test_an_upgrade_with_a_quantity_is_priced_like_a_quantity_change(monkeypatch):
    messages = parse_chat((DATA / "chats" / "blind2_webagency.txt").read_text(encoding="utf-8"))
    catalogue = Catalogue.load("q_blind2_webagency.json")
    asked, noted = seq_with(messages, "four boxes not two"), seq_with(messages, "Four boxes noted")
    out = llm_extractor.build_changes(
        raw(change(item="name cards", line_id="L06", kind="upgrade", qty_delta=2, outcome="agreed",
                   messages=[asked, noted])), messages, catalogue)
    assert out[0].status == "ready" and out[0].price_delta == 240


def test_a_later_message_that_says_the_tents_stay_as_they_were_makes_it_withdrawn(catering):
    messages, catalogue = catering
    asked = seq_with(messages, "khemah 10x10")
    out = llm_extractor.build_changes(
        raw(change(item="Extra tents", line_id="L02", kind="quantity_change", qty_delta=2, outcome="asked",
                   price_delta=240, messages=[asked - 1, asked])), messages, catalogue)
    assert out[0].status == "withdrawn"


def test_a_confirmed_reduction_that_says_cancel_is_not_turned_into_a_withdrawal(setup):
    messages, catalogue = setup
    seq = seq_with(messages, "Please cancel the 2 registration desk staff")
    out = llm_extractor.build_changes(
        raw(change(item="registration desk staff", line_id="L10", kind="replacement", qty_delta=-2, outcome="agreed",
                   messages=[seq])), messages, catalogue)
    assert out[0].status == "ready" and out[0].price_delta == -300
