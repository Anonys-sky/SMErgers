"""Approval flow: who may do what to each extracted change, and the activity log.

    detected --(PM reviews)--> reviewed --(owner approves)--> approved --(client confirms)--> confirmed
         small changes skip the owner: detected --(PM reviews)--> approved

Permissions are checked here, not only hidden in the page, so a client link cannot approve
its own change. Every action is written to a hash-chained log, so later edits show.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_POLICY = {
    "owner_approval_at": 500.0,   # changes worth this much or more (either direction) need the owner
    "client_confirmation": True,  # a change reaches the bill only after the client confirms it
}

STATE_LABELS = {
    "detected": "Needs the PM's check",
    "reviewed": "Waiting for the project director",
    "approved": "Waiting for the client",
    "confirmed": "On the bill",
    "disputed": "Disputed by the client",
    "rejected": "Rejected",
    "record_only": "No charge",
}

# action: (roles allowed, states it can start from)
ACTIONS = {
    "set_price": ({"pm", "owner"}, {"detected", "disputed"}),
    "review": ({"pm"}, {"detected", "disputed"}),
    "approve": ({"owner"}, {"reviewed"}),
    "decide": ({"owner"}, {"detected", "reviewed", "disputed"}),
    "reject": ({"pm", "owner"}, {"detected", "reviewed", "approved", "disputed"}),
    "confirm": ({"client"}, {"approved"}),
    "dispute": ({"client"}, {"approved"}),
}


class NotAllowed(Exception):
    """Raised when a role tries an action it may not take, or at the wrong stage."""


@dataclass(frozen=True)
class Actor:
    name: str
    role: str  # pm / owner / client / finance


@dataclass
class Item:
    """One change moving through approval."""
    change: object                  # schema.Change from an extractor
    state: str = "detected"
    price: float | None = None
    needs_owner_reason: str = ""
    notes: list = field(default_factory=list)


@dataclass
class LogEntry:
    seq: int
    at: str
    actor: str
    role: str
    action: str
    change_key: str
    detail: str
    prev_hash: str
    hash: str


class ActivityLog:
    def __init__(self):
        self.entries: list[LogEntry] = []

    def add(self, at, actor, action, change_key, detail):
        prev = self.entries[-1].hash if self.entries else "start"
        body = {"seq": len(self.entries) + 1, "at": at.isoformat(timespec="minutes"), "actor": actor.name,
                "role": actor.role, "action": action, "change_key": change_key, "detail": detail}
        digest = hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest()
        self.entries.append(LogEntry(**body, prev_hash=prev, hash=digest))

    def intact(self):
        """True if no entry was changed after it was written."""
        prev = "start"
        for e in self.entries:
            body = {"seq": e.seq, "at": e.at, "actor": e.actor, "role": e.role, "action": e.action,
                    "change_key": e.change_key, "detail": e.detail}
            if e.prev_hash != prev or hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest() != e.hash:
                return False
            prev = e.hash
        return True


SYSTEM = Actor("SMErgers", "system")


class Job:
    """The approval state for one job's changes."""

    def __init__(self, changes, policy=None, now=None):
        self.policy = {**DEFAULT_POLICY, **(policy or {})}
        self.log = ActivityLog()
        self.items = {}
        now = now or datetime.now()
        for c in changes:
            item = Item(c, price=c.price_delta)
            if c.status in ("withdrawn", "log_only"):
                item.state = "record_only"
            self.items[c.key] = item
        self.log.add(now, SYSTEM, "import", "-", f"{len(changes)} changes found in the chat")

    def refresh(self, changes, now=None):
        """Take in a fresh extraction after new chat messages arrive. New changes are added;
        a change nobody has acted on yet is updated (say, its price was just stated); anything
        a person already acted on is left alone. Returns the keys that are new."""
        now = now or datetime.now()
        new = []
        for c in changes:
            item = self.items.get(c.key)
            if item is None:
                item = Item(c, price=c.price_delta)
                if c.status in ("withdrawn", "log_only"):
                    item.state = "record_only"
                self.items[c.key] = item
                new.append(c.key)
                self.log.add(now, SYSTEM, "detect", c.key, f"found in chat: {c.item}")
            elif item.state in ("detected", "record_only") and not item.notes:
                changed = item.change.status != c.status or item.change.price_delta != c.price_delta
                item.change, item.price = c, c.price_delta
                item.state = "record_only" if c.status in ("withdrawn", "log_only") else "detected"
                if changed:
                    self.log.add(now, SYSTEM, "update", c.key, f"updated from chat: {STATE_LABELS[item.state].lower()}")
        return new

    def needs_owner(self, item):
        """Why the owner must approve this change, or '' if the PM's review is enough."""
        c = item.change
        if c.kind == "discount":
            return "discounts always need the owner"
        if c.status == "unconfirmed":
            return "not confirmed in the chat"
        if c.price_delta is None or item.price != c.price_delta:
            return "price added or changed by staff, not taken from the chat"
        if item.price is not None and abs(item.price) >= self.policy["owner_approval_at"]:
            return f"RM{abs(item.price):,.0f} is at or above the RM{self.policy['owner_approval_at']:,.0f} limit"
        return ""

    def act(self, key, action, actor, now=None, price=None, note=""):
        now = now or datetime.now()
        item = self.items[key]
        roles, from_states = ACTIONS[action]
        if actor.role not in roles:
            raise NotAllowed(f"A {actor.role} cannot {action.replace('_', ' ')}.")
        if item.state not in from_states:
            raise NotAllowed(f"Cannot {action.replace('_', ' ')} a change that is '{STATE_LABELS[item.state]}'.")

        if action == "set_price":
            if price is None:
                raise NotAllowed("Enter a price.")
            old, item.price = item.price, float(price)
            detail = f"price set to RM{item.price:,.2f}" + (f" (was RM{old:,.2f})" if old is not None else "")
        elif action == "review":
            if item.price is None:
                raise NotAllowed("Add a price before review.")
            if item.change.status == "unconfirmed" and not note:
                raise NotAllowed("This was not confirmed in the chat. Add a note on how it was agreed.")
            if item.change.kind == "discount":
                raise NotAllowed("Only the owner can decide a discount.")
            item.needs_owner_reason = self.needs_owner(item)
            item.state = "reviewed" if item.needs_owner_reason else self._after_approval()
            detail = "checked" + (f"; owner needed: {item.needs_owner_reason}" if item.needs_owner_reason else "; approved within PM limit")
        elif action == "approve":
            item.state = self._after_approval()
            detail = "approved"
        elif action == "decide":
            if item.change.kind != "discount":
                raise NotAllowed("Only a discount is decided by the owner directly; other changes go through the PM first.")
            if price is None:
                raise NotAllowed("Enter the amount decided.")
            item.price = float(price)
            item.state = self._after_approval()
            detail = f"decided at RM{item.price:,.2f}"
        elif action == "reject":
            item.state = "rejected"
            detail = "rejected"
        elif action == "confirm":
            item.state = "confirmed"
            detail = "confirmed by client"
        else:  # dispute
            if not note:
                raise NotAllowed("Say what is wrong so the team can fix it.")
            item.state = "disputed"
            detail = "disputed"
        if note:
            item.notes.append((now, actor.name, note))
            detail += f": {note}"
        self.log.add(now, actor, action, key, detail)
        return item

    def _after_approval(self):
        return "approved" if self.policy["client_confirmation"] else "confirmed"
