"""The scripted demo conversation must give the same five changes every time (rules reader, no network)."""
import json
from datetime import datetime, timedelta

from catalogue import DATA, Catalogue
from chat_import import parse_chat
import reader


def export_text(script):
    """The conversation as a WhatsApp export with two different senders."""
    names = script["senders"]
    start = datetime(2026, 9, 20, 9, 10)
    lines = ["02/09/2026, 9:12 am - Messages and calls are end-to-end encrypted."]
    for i, m in enumerate(script["before_the_pitch"] + script["during_the_pitch"], 1):
        t = start + timedelta(minutes=17 * i)
        lines.append(f"{t.day:02d}/{t.month:02d}/{t.year}, {t.strftime('%I:%M %p').lstrip('0').lower()} - {names[m['from']]}: {m['text']}")
    return "\n".join(lines) + "\n"


def test_the_demo_conversation_gives_the_expected_five_changes():
    script = json.loads((DATA / "demo_group_script.json").read_text(encoding="utf-8"))
    changes = reader.read(parse_chat(export_text(script)), Catalogue.load(script["quote"]), ai=False)
    got = {c.item: (c.status, c.price_delta) for c in changes}
    expected = {name: (v["status"], v["price"]) for name, v in script["final"].items()}
    assert got == expected


def test_the_confirmation_must_come_from_a_different_sender_than_the_request():
    script = json.loads((DATA / "demo_group_script.json").read_text(encoding="utf-8"))
    script["senders"]["staff"] = script["senders"]["client"]          # one person typing both sides
    changes = reader.read(parse_chat(export_text(script)), Catalogue.load(script["quote"]), ai=False)
    assert not any(c.status == "ready" for c in changes)               # nobody else said yes, so nothing is ready
