"""Keeps everyone in step after each decision.

- When the client confirms changes, the quote moves to a new version (v2, v3, ...) and a summary
  goes back to the WhatsApp group, so nobody works from an older idea of what was agreed.
- When a change needs the next person (owner approval, client confirmation), they get a message.

Messages are queued in the job's outbox. In this prototype nothing is sent; with the official
WhatsApp Business API the outbox would be delivered by the API (docs/orbyte-integration.md).
"""
from dataclasses import dataclass, field
from datetime import datetime

from bill import build_bill
from workflow import SYSTEM


@dataclass
class QuoteVersion:
    number: int
    at: datetime
    by: str
    change_keys: list
    total: float
    note: str = ""


@dataclass
class Outgoing:
    at: datetime
    to: str      # "Group" or a person's name
    kind: str    # group_update / approval_request / confirm_request / new_change
    text: str
    change_keys: list = field(default_factory=list)


def _rm(value):
    sign = "-" if value < 0 else ""
    return f"{sign}RM{abs(value):,.2f}".replace(".00", "")


def _describe(item):
    qty = f" ({item.change.qty_delta:+g})" if item.change.qty_delta and item.change.kind != "non_billable" else ""
    return f"{item.change.item}{qty}: {_rm(item.price or 0)}"


def start(record):
    """Version 1 is the signed quote."""
    total = sum(l.qty * l.unit_price for l in record.catalogue.lines)
    record.versions = [QuoteVersion(1, record.imported_at, "Signed quote", [], total, "original quote")]
    record.outbox = []


def after_actions(record, action, keys, actor, now=None):
    """Call after a person acts on one or more changes. Adds versions and outgoing messages."""
    now = now or datetime.now()
    items = record.job.items
    quote_id = record.catalogue.quote["quote_id"]
    team = record.team

    if action == "dispute":
        for key in keys:
            item = items[key]
            if item.state != "disputed":
                continue
            recipient = team["owner"] if item.change.kind == "discount" else team["pm"]
            reason = item.notes[-1][2]
            _send(record, now, recipient, "dispute_request",
                  f"{actor.name} disputed {_describe(item)}.\nReason: {reason}\n"
                  "Review the evidence and resolve the dispute before requesting confirmation again.", [key])

    if action == "reject":
        for key in keys:
            item = items[key]
            if item.state != "rejected":
                continue
            recipient = team["pm"] if actor.role == "owner" else team["owner"]
            if recipient != actor.name:   # in a one-person team there is nobody else to tell
                _send(record, now, recipient, "reject_notice",
                      f"{actor.name} rejected {_describe(item)}.\nReason: {item.notes[-1][2]}\n"
                      "It will not reach the bill.", [key])

    if action == "confirm":
        confirmed = [k for k in keys if items[k].state == "confirmed"]
        if not confirmed:
            return
        bill = build_bill(record.catalogue, record.job)
        number = len(record.versions) + 1
        record.versions.append(QuoteVersion(number, now, actor.name, confirmed, bill.draft_total))
        lines = "\n".join(f"- {_describe(items[k])}" for k in confirmed)
        text = (f"Confirmed by {actor.name}:\n{lines}\n"
                f"Quote {quote_id} is now version {number}, total {_rm(bill.draft_total)}.")
        _send(record, now, "Group", "group_update", text, confirmed)
        record.job.log.add(now, SYSTEM, "sync", "-", f"quote v{number} ({_rm(bill.draft_total)}) posted to the group")

    waiting_owner = [k for k in keys if items[k].state == "reviewed"]
    if waiting_owner:
        lines = "\n".join(f"- {_describe(items[k])}: {items[k].needs_owner_reason}" for k in waiting_owner)
        _send(record, now, team["owner"], "approval_request",
              f"{len(waiting_owner)} change(s) need your approval:\n{lines}", waiting_owner)

    waiting_client = [k for k in keys if items[k].state == "approved"]
    if waiting_client:
        total = sum(items[k].price or 0 for k in waiting_client)
        _send(record, now, record.catalogue.quote["client"], "confirm_request",
              f"{len(waiting_client)} change(s) ready for you to confirm ({_rm(total)}). "
              f"Open your SMErgers link to confirm or dispute each one.", waiting_client)


def after_detection(record, new_keys, now=None):
    """Tell the PM when a new change turns up in the chat."""
    if not new_keys:
        return
    now = now or datetime.now()
    items = record.job.items
    lines = "\n".join(f"- {items[k].change.item}" for k in new_keys)
    _send(record, now, record.team["pm"], "new_change", f"New in the chat, please check:\n{lines}", new_keys)


def _send(record, now, to, kind, text, keys):
    record.outbox.append(Outgoing(now, to, kind, text, list(keys)))
