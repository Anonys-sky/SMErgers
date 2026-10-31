"""Approval flow: who may do what to each extracted change, and the activity log.

    detected --(PM reviews)--> reviewed --(owner approves)--> approved --(client confirms)--> confirmed
         small changes skip the owner: detected --(PM reviews)--> approved

Permissions are checked here, not only hidden in the page, so a client link cannot approve
its own change. Every action is written to a hash-chained log, so later edits show.
"""
import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from pricing import MAX_CHANGE_AMOUNT, usable_change_price
from schema import request_match_score

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

    def __init__(self, changes, policy=None, now=None, catalogue=None):
        self.policy = {**DEFAULT_POLICY, **(policy or {})}
        self.quote_quantities = {line.line_id: line.qty for line in catalogue.lines} if catalogue else {}
        self.log = ActivityLog()
        self.items = {}
        now = now or datetime.now()
        for c in changes:
            item = Item(c, price=usable_change_price(c.price_delta))
            if c.status in ("withdrawn", "log_only"):
                item.state = "record_only"
            self.items[c.key] = item
        self.log.add(now, SYSTEM, "import", "-", f"{len(changes)} changes found in the chat")

    def refresh(self, changes, now=None):
        """Take in a fresh extraction after new chat messages arrive. New changes are added;
        a change nobody has acted on yet is updated (say, its price was just stated); anything
        a person already acted on is left alone unless the chat withdraws a pending change.
        Returns the keys that are new."""
        now = now or datetime.now()
        new = []
        for c in changes:
            item = self.items.get(c.key)
            if item is None:
                item = Item(c, price=usable_change_price(c.price_delta))
                if c.status in ("withdrawn", "log_only"):
                    item.state = "record_only"
                self.items[c.key] = item
                new.append(c.key)
                self.log.add(now, SYSTEM, "detect", c.key, f"found in chat: {c.item}")
            elif self._withdraw_pending(item, c, now):
                continue
            elif item.state in ("detected", "record_only") and not item.notes:
                changed = item.change.status != c.status or item.change.price_delta != c.price_delta
                item.change, item.price = c, usable_change_price(c.price_delta)
                item.state = "record_only" if c.status in ("withdrawn", "log_only") else "detected"
                if changed:
                    self.log.add(now, SYSTEM, "update", c.key, f"updated from chat: {STATE_LABELS[item.state].lower()}")
        return new

    def reconcile(self, changes, prefer_incoming, now=None):
        """Fold a reading by ANOTHER reader into the items already here, without duplicates.
        A change matches the existing item whose cited messages it shares (request_match_score),
        one-to-one. A matched item nobody has acted on is updated in place and keeps its key; an item a
        person already acted on is left alone unless the rules find a later withdrawal. Unmatched
        changes are added as new items. With
        prefer_incoming False, an item already read by the AI keeps the AI's reading (the quick rules pass
        must not undo it). Returns the keys that are new."""
        now = now or datetime.now()
        pairs = sorted(((request_match_score(c, it.change), i, k)
                        for i, c in enumerate(changes) for k, it in self.items.items()), reverse=True)
        matched, used = {}, set()
        for score, i, k in pairs:
            if score > 0 and i not in matched and k not in used:
                matched[i] = k
                used.add(k)
        new = []
        for i, c in enumerate(changes):
            if i in matched:
                self._update_from(self.items[matched[i]], c, prefer_incoming, now)
                continue
            key = c.key if c.key not in self.items else self._free_key(c.key)
            c = replace(c, key=key)
            item = Item(c, price=usable_change_price(c.price_delta))
            if c.status in ("withdrawn", "log_only"):
                item.state = "record_only"
            self.items[key] = item
            new.append(key)
            self.log.add(now, SYSTEM, "detect", key, f"found in chat: {c.item}")
        return new

    def _update_from(self, item, c, prefer_incoming, now):
        if self._withdraw_pending(item, c, now):
            return
        if item.state not in ("detected", "record_only") or item.notes:
            return                                          # a person acted on it: leave it alone
        if not prefer_incoming and item.change.source == "ai" and c.source != "ai":
            return                                          # the quick rules pass keeps the AI's answer
        old = item.change
        c = replace(c, key=old.key)
        if old.line_id and old.line_id == c.line_id:
            c = replace(c, item=old.item)                   # keep the quote's own name for the line, not the model's wording
        changed = (old.status, old.price_delta, old.item) != (c.status, c.price_delta, c.item)
        item.change, item.price = c, usable_change_price(c.price_delta)
        item.state = "record_only" if c.status in ("withdrawn", "log_only") else "detected"
        if changed:
            who = "the AI reader" if c.source == "ai" else "the chat"
            self.log.add(now, SYSTEM, "update", c.key, f"refined by {who}: {STATE_LABELS[item.state].lower()}")

    def _withdraw_pending(self, item, change, now):
        """A chat cancellation supersedes pending approvals, but not a completed confirmation."""
        if (change.source != "rules" or change.status != "withdrawn"
                or item.state not in ("reviewed", "approved", "disputed")):
            return False
        key = item.change.key
        item.change = replace(change, key=key)
        item.price = 0.0
        item.state = "record_only"
        item.needs_owner_reason = ""
        self.log.add(now, SYSTEM, "withdraw", key, "withdrawn in later chat; pending approval cancelled")
        return True

    def _free_key(self, key):
        prefix = "".join(ch for ch in key if ch.isalpha() or ch == "_") or "x"
        taken = [int("".join(ch for ch in k[len(prefix):] if ch.isdigit()) or 0) for k in self.items if k.startswith(prefix)]
        return f"{prefix}{1 + max(taken, default=0)}"

    def add_change(self, change, actor, now=None):
        """A person adds a change the reader missed, with the chat messages that show it was agreed.
        It goes through the same approval flow as any other change, and the director always signs it off."""
        now = now or datetime.now()
        if actor.role not in ("pm", "owner"):
            raise NotAllowed(f"A {actor.role} cannot add a change.")
        if not change.item.strip():
            raise NotAllowed("Name the change.")
        if not change.evidence_ids:
            raise NotAllowed("Pick at least one chat message that shows it was agreed.")
        if change.price_delta is not None and usable_change_price(change.price_delta) is None:
            raise NotAllowed("Enter a valid amount in RM.")
        key = f"m{1 + sum(1 for k in self.items if k.startswith('m'))}"
        change.key = key
        item = Item(change, price=usable_change_price(change.price_delta))
        if change.status == "log_only":
            item.state = "record_only"
        self.items[key] = item
        self.log.add(now, actor, "add", key, f"added by {actor.name}: {change.item} (the reader had not found it)")
        return key

    def needs_owner(self, item):
        """Why the owner must approve this change, or '' if the PM's review is enough."""
        c = item.change
        if c.source == "manual":
            return "added by staff: the reader did not find it"
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
        note = note.strip()
        item = self.items[key]
        roles, from_states = ACTIONS[action]
        if actor.role not in roles:
            raise NotAllowed(f"A {actor.role} cannot {action.replace('_', ' ')}.")
        if item.state not in from_states:
            raise NotAllowed(f"Cannot {action.replace('_', ' ')} a change that is '{STATE_LABELS[item.state]}'.")

        # Validate before changing prices, states, notes or the audit log.
        # Also stop an invalid price already on a record from progressing to billing.
        candidate = price if action in ("set_price", "decide") else item.price
        if candidate is not None and action in ("set_price", "decide", "review", "approve", "confirm"):
            try:
                valid_price = math.isfinite(float(candidate))
            except (TypeError, ValueError, OverflowError):
                valid_price = False
            if not valid_price:
                raise NotAllowed("Enter a finite price. NaN and infinity are not valid amounts.")
            if abs(float(candidate)) > MAX_CHANGE_AMOUNT:
                raise NotAllowed("A change amount must be between -RM1,000,000,000 and RM1,000,000,000.")

        if action in ("review", "approve", "confirm"):
            self._check_quantity(key)
        if action in ("approve", "confirm") and item.price is None:
            raise NotAllowed("Add a valid price and review the change before approval or confirmation.")
        if action == "reject" and not note:
            raise NotAllowed("Say why you are rejecting it, so the record shows the reason.")
        if action == "set_price" and item.change.kind == "discount":
            raise NotAllowed("Only the project director can decide a discount with its basis.")
        if action in ("decide", "approve", "confirm") and item.change.kind == "discount":
            if candidate is not None and float(candidate) > 0:
                raise NotAllowed("A discount must be zero or negative. Enter -100 for RM100 off.")
            if action == "decide" and not note:
                raise NotAllowed("Explain the discount basis, such as 5% of the original quote.")

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

    def _check_quantity(self, key):
        """Only confirmed additions can fund a removal; recheck at every approval stage."""
        item = self.items[key]
        change = item.change
        if change.kind != "quantity_change" or change.line_id not in self.quote_quantities:
            return
        quantities = [self.quote_quantities[change.line_id], change.qty_delta]
        quantities.extend(
            other.change.qty_delta for other_key, other in self.items.items()
            if other_key != key and other.state == "confirmed"
            and other.change.kind == "quantity_change" and other.change.line_id == change.line_id
        )
        amounts = [Decimal(str(quantity)) for quantity in quantities]
        if not all(amount.is_finite() for amount in amounts) or sum(amounts) < 0:
            raise NotAllowed(
                f"This change would leave a negative or invalid quantity for {change.item}. "
                "Reject it and correct the source quantity; changing the price does not fix the quantity."
            )
