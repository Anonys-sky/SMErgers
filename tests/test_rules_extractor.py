from pathlib import Path

from catalogue import Catalogue
from chat_import import find_message, parse_chat
from evaluate import score_chat
from rules_extractor import extract

CHATS = Path(__file__).resolve().parent.parent / "data" / "chats"


def dinner_changes():
    messages = parse_chat((CHATS / "dinner_client.txt").read_text(encoding="utf-8"))
    return messages, extract(messages, Catalogue.load("q_dinner.json"))


def test_tuning_chat_scores_fully():
    s = score_chat("dinner_client.json", extract)
    assert (s["found"], s["fully_ok"], s["false_changes"]) == (10, 10, 0)


def test_never_invents_a_price():
    messages, changes = dinner_changes()
    mic = find_message(messages, "2 extra wireless mic")
    (change,) = [c for c in changes if mic.id in c.evidence_ids]
    assert change.status == "needs_price" and change.price_delta is None


def test_recap_adds_evidence_not_new_changes():
    messages, changes = dinner_changes()
    recap = find_message(messages, "Recap of changes so far")
    assert len(changes) == 10
    assert any(recap.id in c.evidence_ids for c in changes)


def test_withdrawn_request_is_not_billed():
    messages, changes = dinner_changes()
    arch = find_message(messages, "one more balloon arch")
    (change,) = [c for c in changes if arch.id in c.evidence_ids]
    assert change.status == "withdrawn" and change.price_delta == 0


def test_every_change_explains_itself():
    _, changes = dinner_changes()
    assert all(c.reason and c.evidence_ids for c in changes)
