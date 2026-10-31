"""Receives WhatsApp messages the way Meta's official WhatsApp Business (Cloud) API delivers them:
a webhook POST with entry -> changes -> value -> messages and contacts.

Assumption, because we had no API access: for group messages we read the group from a
`group_id` field on each message. Check the field name against Meta's Groups API documentation
before going live.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from chat_import import messages_from_whatsapp
from reader import read as extract
from workflow import SYSTEM

KL = ZoneInfo("Asia/Kuala_Lumpur")


@dataclass
class LiveFeed:
    group_id: str
    received: list = field(default_factory=list)   # message records, as messages_from_whatsapp takes them


def signature_ok(body, header):
    """Meta signs each webhook with the app secret (X-Hub-Signature-256). With no secret set
    (this prototype), every call is accepted."""
    secret = os.environ.get("WHATSAPP_APP_SECRET")
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


def records_from_payload(payload):
    """One record per incoming message: group_id, wa_id, timestamp, sender, text, is_media."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                kind = m.get("type")
                if kind == "text":
                    text, is_media = (m.get("text") or {}).get("body", ""), False
                else:
                    caption = (m.get(kind) or {}).get("caption", "") if isinstance(m.get(kind), dict) else ""
                    text, is_media = caption or "<Media omitted>", True
                out.append({
                    "group_id": m.get("group_id"),
                    "wa_id": m.get("id"),
                    "timestamp": int(m.get("timestamp", 0)),
                    "sender": names.get(m.get("from")) or f"+{m.get('from', '')}",
                    "text": text,
                    "is_media": is_media,
                })
    return out


def ingest(record, records, now=None):
    """Add newly received messages to a job and re-read the chat. Returns the new change keys."""
    import sync  # imported here: sync needs the store's records, the store imports this module

    feed = record.live
    seen = {r["wa_id"] for r in feed.received}
    fresh = [r for r in records if r["wa_id"] not in seen]
    if not fresh:
        return []
    feed.received.extend(fresh)
    for r in fresh:  # the trigger is part of the record: what arrived, from whom, and by which route
        record.job.log.add(now or datetime.now(), SYSTEM, "trigger", "-",
                           f"message from {r['sender']} arrived through the WhatsApp webhook")
    record.messages = messages_from_whatsapp(feed.received, KL)
    new = record.job.refresh(extract(record.messages, record.catalogue, ai=record.ai), now)
    sync.after_detection(record, new, now)
    return new
