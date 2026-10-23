from datetime import datetime
from pathlib import Path

from chat_import import find_message, parse_chat

CHATS = Path(__file__).resolve().parent.parent / "data" / "chats"


def dinner():
    return parse_chat((CHATS / "dinner_client.txt").read_text(encoding="utf-8"))


def test_system_notice_has_no_sender():
    first = dinner()[0]
    assert first.sender is None
    assert "end-to-end encrypted" in first.text


def test_sender_and_time_are_read():
    msg = find_message(dinner(), "195 people attending")
    assert msg.sender == "Linda (Sinar)"
    assert msg.sent_at == datetime(2026, 9, 15, 14, 5)


def test_multi_line_recap_stays_one_message():
    messages = dinner()
    recap = find_message(messages, "Recap of changes so far")
    assert recap.text.count("\n") == 6
    assert "dinner start 7:30pm" in recap.text
    assert find_message(messages, "- 195 pax").id == recap.id


def test_media_is_flagged():
    assert any(m.is_media for m in dinner())


def test_emoji_survive():
    assert find_message(dinner(), "Great job team").text.endswith("👍")


def test_ids_are_stable_across_imports():
    assert [m.id for m in dinner()] == [m.id for m in dinner()]


def test_identical_messages_get_distinct_ids():
    raw = "01/10/2026, 9:00 am - A: ok\n01/10/2026, 9:00 am - A: ok\n"
    first, second = parse_chat(raw)
    assert first.id != second.id


def test_ios_format_and_invisible_characters():
    raw = "‎[05/10/2026, 10:35:12 PM] Aisyah: overtime is RM 300\n"
    (msg,) = parse_chat(raw)
    assert msg.sender == "Aisyah"
    assert msg.sent_at == datetime(2026, 10, 5, 22, 35, 12)
    assert msg.text == "overtime is RM 300"


def test_twelve_am_and_pm_edges():
    raw = "01/10/2026, 12:05 am - A: late\n01/10/2026, 12:05 pm - A: noon\n"
    late, noon = parse_chat(raw)
    assert late.sent_at.hour == 0
    assert noon.sent_at.hour == 12


def test_every_chat_parses():
    for path in CHATS.glob("*.txt"):
        messages = parse_chat(path.read_text(encoding="utf-8"))
        assert len(messages) > 5, path.name
        assert all(m.sent_at.year in (2026, 2027) for m in messages), path.name
