"""Reads a WhatsApp "Export chat" text file into Message records.

Supports the Android format ("15/09/2026, 2:05 pm - Name: text") and the iOS format
("[15/09/2026, 2:05:10 PM] Name: text"). Dates are read day-first, as exported in Malaysia.

Also turns messages read live from a WhatsApp group (whatsapp/bridge.js) into the same records,
so the rest of the app cannot tell the two sources apart.
"""
import hashlib
import re
from datetime import datetime

from schema import Message

# Newer exports put a narrow no-break space before am/pm, and iOS adds left-to-right marks.
_INVISIBLE = str.maketrans({" ": " ", " ": " ", "‎": "", "‏": ""})

_ANDROID = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}), (?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s?(?P<ampm>[apAP]\.?[mM]\.?)? - (?P<rest>.*)$"
)
_IOS = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}), (?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s?(?P<ampm>[apAP]\.?[mM]\.?)?\] (?P<rest>.*)$"
)
_MEDIA = re.compile(r"^<Media omitted>$|^(image|video|audio|sticker|document) omitted$|^<attached: ", re.I)


class InvalidChatTimestamp(ValueError):
    """An export contains a message header with an impossible date or time."""


def _parse_timestamp(date_text, time_text, ampm):
    day, month, year = (int(p) for p in date_text.split("/"))
    if year < 100:
        year += 2000
    parts = [int(p) for p in time_text.split(":")]
    hour, minute = parts[0], parts[1]
    second = parts[2] if len(parts) > 2 else 0
    if ampm:
        if not 1 <= hour <= 12:
            raise ValueError("AM/PM hours must be between 1 and 12")
        pm = ampm.lower().startswith("p")
        hour = hour % 12 + (12 if pm else 0)
    return datetime(year, month, day, hour, minute, second)


def _split_sender(rest):
    # System notices ("Messages and calls are end-to-end encrypted...") have no "Name: " part.
    name, sep, text = rest.partition(": ")
    if not sep:
        return None, rest
    return name.strip(), text


def parse_chat(raw_text):
    """Return the chat as a list of Messages. Lines that do not start a new message
    are continuation lines of a multi-line message."""
    starts = []  # (sent_at, sender, [text lines])
    for line_number, line in enumerate(raw_text.translate(_INVISIBLE).splitlines(), start=1):
        match = _ANDROID.match(line) or _IOS.match(line)
        if match:
            try:
                sent_at = _parse_timestamp(match["date"], match["time"], match["ampm"])
            except ValueError as exc:
                raise InvalidChatTimestamp(
                    f"Invalid chat date or time on line {line_number}. "
                    "Use a valid day/month/year date and time in the WhatsApp export."
                ) from exc
            sender, text = _split_sender(match["rest"])
            starts.append((sent_at, sender, [text]))
        elif starts:
            starts[-1][2].append(line)
        # Text before the first timestamp is ignored: it is not part of any message.

    messages, seen = [], {}
    for seq, (sent_at, sender, lines) in enumerate(starts, start=1):
        text = "\n".join(lines).strip()
        base = hashlib.sha1(f"{sent_at.isoformat()}|{sender}|{text}".encode()).hexdigest()[:12]
        # Two identical "ok" messages in the same minute are still two messages.
        seen[base] = seen.get(base, 0) + 1
        msg_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
        messages.append(Message(msg_id, seq, sent_at, sender, text, bool(_MEDIA.match(text))))
    return messages


def find_message(messages, phrase):
    """First message containing the phrase (case-insensitive), or None."""
    phrase = phrase.lower()
    return next((m for m in messages if phrase in m.text.lower()), None)


def messages_from_whatsapp(records, tz=None):
    """Messages read live from a WhatsApp group, as Message records, oldest first.

    Each record is {"wa_id", "timestamp" (Unix seconds), "sender", "text", "is_media"}.
    Times become naive local time like an export: in `tz` (a tzinfo) if given, otherwise
    in this computer's time zone. Ids come from WhatsApp's own message id, so reading the
    same group twice gives the same ids."""
    unique = {}
    for record in records:
        wa_id = str(record.get("wa_id") or "")
        if not wa_id or wa_id == "[object Object]":
            continue
        match = re.fullmatch(r"(true|false)_([^_]+)_([^_]+)(?:_.*)?", wa_id)
        if match:
            wa_id = "_".join(match.groups())
        unique[wa_id] = {**record, "wa_id": wa_id}
    rows = sorted(unique.values(), key=lambda r: r["timestamp"])
    messages = []
    for seq, r in enumerate(rows, start=1):
        if tz is None:
            sent_at = datetime.fromtimestamp(r["timestamp"])
        else:
            sent_at = datetime.fromtimestamp(r["timestamp"], tz).replace(tzinfo=None)
        text = (r.get("text") or "").translate(_INVISIBLE).strip()
        base = hashlib.sha1(str(r["wa_id"]).encode()).hexdigest()[:12]
        is_media = bool(r.get("is_media")) or bool(_MEDIA.match(text))
        messages.append(Message(base, seq, sent_at, r.get("sender") or None, text, is_media))
    return messages
