"""Rule-based change extractor.

Groups chat messages into threads (a request plus the replies about it), then decides
for each thread: what changed, by how much, at what price, and whether both sides agreed.
It never guesses a price: if nobody stated one and the quote has none, the change is
marked "needs_price" for a person to fill in.

This is the offline fallback, and the baseline any AI extractor has to beat.
"""
import re
from dataclasses import dataclass, field
from datetime import timedelta

from catalogue import Catalogue
from schema import Change

THREAD_WINDOW = timedelta(days=3)       # replies later than this start a new thread
CONTINUATION_WINDOW = timedelta(minutes=10)


def _any(*patterns):
    return re.compile("|".join(patterns), re.I)


ASK = _any(r"\bmore\b", r"\badd\b", r"\btambah\b", r"加多", r"\bextra\b", r"\bwant\b", r"\bneed\b",
           r"\bupgrade\b", r"\bchange\b", r"\bbigger\b", r"\bsmaller\b", r"\binstead\b", r"\bmove\b",
           r"\badjust\b", r"\bcancel\b", r"\bremove\b", r"\bstay (?:until|till)\b", r"\bextend\b")
EXTEND = _any(r"\bstay (?:until|till)\b", r"\bextend\b", r"\bovertime\b", r"\banother hour\b")
CHANGE = _any(r"\bupgrade\b", r"\bchange\b", r"\bbigger\b", r"\bsmaller\b", r"\binstead\b", r"\bmove\b")
REMOVE = _any(r"\bcancel\b", r"\bremove\b")
WITHDRAW = _any(r"\bno need\b", r"\bnever ?mind\b", r"\bnvm\b", r"\bdon'?t want\b")
TENTATIVE = _any(r"\bmaybe\b", r"\bmight\b")
CONFIRM = _any(r"\bok\b", r"\bokay\b", r"\bgo ahead\b", r"\bproceed\b", r"\bfine\b", r"\bboleh\b",
               r"\bnoted\b", r"\bcan\b", r"\byes\b", r"\bagreed\b", r"好", r"\bgo\b", r"\bwill arrange\b")
DEFER = _any(r"\blet me (?:ask|check)\b", r"\bask (?:my )?boss\b", r"\bcheck budget\b", r"\brevert\b",
             r"\bwait\b", r"\bwant me to\b", r"\blet me know\b")
NO_COST = _any(r"\bsame price\b", r"\bsame rate\b", r"\bno extra\b", r"\bincluded\b", r"\bno charge\b")
IGNORE = _any(r"signed quote", r"\binvoice\b", r"\bfinal bill\b")
RECAP = _any(r"\brecap\b", r"\bsummary\b")
DISCOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:discount|off)", re.I)

MONEY = r"RM\s?([\d,]+(?:\.\d+)?)"
PER_UNIT = re.compile(MONEY + r"\s*(?:more\s+)?(?:each|per\s+(\w+))", re.I)
SIGNED = re.compile(r"([+-])\s?" + MONEY, re.I)
MORE_LESS = re.compile(MONEY + r"\s*(more|extra|less|cheaper)", re.I)
PLAIN = re.compile(MONEY, re.I)

# Things that look like quantities but are not: times, dates, sizes, money.
NOT_QTY = [
    re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b", re.I),
    re.compile(r"\b(?:until|till|at)\s+\d{1,2}(?::\d{2})?\b", re.I),
    re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s*m?\s*x\s*\d+(?:\.\d+)?\s*m?\b", re.I),
    re.compile(r"[+-]?\s?" + MONEY, re.I),
    re.compile(r"\d+(?:\.\d+)?\s*%"),
]
WORD_NUMBERS = {"one": "1", "satu": "1", "another": "1", "two": "2", "dua": "2", "both": "2", "three": "3", "tiga": "3"}
DELTA = [re.compile(p, re.I) for p in (r"(\d+)\s*(?:more|extra|additional)\b", r"(?:tambah|add)\s*(\d+)", r"加多\s*(\d+)")]
HOURS = re.compile(r"(\d+)\s*(?:more\s+)?hours?\b", re.I)
REMOVE_QTY = re.compile(r"(?:cancel|remove)\s+(?:the\s+)?(\d+)", re.I)
REMOVED_ALL = re.compile(r"\bremoved (\d+)\b", re.I)
CONTINUATION = re.compile(r"^(?:and|also)\s+(\d+)\b", re.I)
GENERIC_ITEM = re.compile(r"(\d+)\s+(?:extra|more)\s+([a-z][a-z ]{2,30}?)(?=\s+for\b|[,.!?]|$)", re.I)
GENERIC_ADD = re.compile(r"\badd\s+([a-z][a-z ]{2,30}?)(?=\?|[,.!]|$)", re.I)
SWAP = re.compile(r"change\s+(\w+)\s+from\s+(\w+)\s+to\s+(\w+)", re.I)
TARGET_SIZE = re.compile(r"\b(\d+(?:\.\d+)?\s*m?\s*x\s*\d+(?:\.\d+)?\s*m?)\b", re.I)
TARGET_WORD = re.compile(r"\b(?:upgrade|change)\s+to\s+(\d+\s+tier|[a-z][\w-]*)", re.I)
SCHEDULE = re.compile(r"\b(?:start|end|move)\b.*\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b", re.I)


@dataclass
class Thread:
    key: str
    entry: object                # catalogue Entry, or None for an item not in the catalogue
    item: str
    kind_hint: str
    messages: list = field(default_factory=list)
    replaces: object = None      # the quote line a replacement swaps out

    @property
    def last(self):
        return self.messages[-1]


def _clean_for_qty(text):
    for pattern in NOT_QTY:
        text = pattern.sub(" ", text)
    return re.sub(r"\b(" + "|".join(WORD_NUMBERS) + r")\b", lambda m: WORD_NUMBERS[m.group(1).lower()], text, flags=re.I)


def _total_pattern(entry):
    # "adjust to 195", "so 32 tables", "6 hostesses total", "6 instead of 4": a new total,
    # only when the number is followed by the item's own words (so "4 tier" is not a total).
    words = [re.escape(a) for a in entry.aliases] + [re.escape(entry.unit) + "s?"]
    follow = r"(?=\s*(?:$|[?.!,]|(?:" + "|".join(words) + r")\b))"
    return [
        re.compile(r"(\d+)\s+instead of\s+\d+", re.I),
        re.compile(r"\btotal\s+(\d+)", re.I),
        re.compile(r"(\d+)\s+(?:\w+\s+){0,2}total\b", re.I),
        re.compile(r"\b(?:to|so|need|go)\s+(\d+)\b" + follow, re.I),
        re.compile(r"(?:^|\b(?:ok|yes|noted),?\s+)(\d+)\s+(?:" + "|".join(words) + r")\b", re.I),
    ]


def _quantity(thread, base_qty):
    """Change in quantity for the thread; the latest explicit statement wins."""
    result = None
    for msg in thread.messages:
        text = _clean_for_qty(msg.text)
        if REMOVE.search(msg.text):
            m = REMOVE_QTY.search(text) or REMOVED_ALL.search(text)
            if m:
                result = -int(m.group(1))
                continue
        cont = CONTINUATION.search(text)
        if cont and result is not None:
            result += int(cont.group(1))
            continue
        if thread.entry is not None and thread.entry.line_id and thread.kind_hint == "quantity":
            totals = [m for p in _total_pattern(thread.entry) if (m := p.search(text))]
            if totals:
                result = int(totals[0].group(1)) - base_qty
                continue
        hours = HOURS.search(text)
        if hours and thread.kind_hint == "extend":
            result = int(hours.group(1))
            continue
        for p in DELTA:
            m = p.search(text)
            if m:
                result = int(m.group(1))
                break
    return result


def _price(thread, qty, catalogue):
    """(price_delta, how it was priced) or (None, reason)."""
    stated = None
    for msg in thread.messages:
        text = msg.text
        if m := PER_UNIT.search(text):
            unit_price, per = float(m.group(1).replace(",", "")), m.group(2)
            base = thread.entry or thread.replaces
            if per and base is not None and base.unit.lower().startswith(per.lower()):
                stated = (unit_price * base.qty, f"RM{unit_price:g} per {per} x {base.qty:g} {base.unit} on the quote")
            elif qty:
                stated = (unit_price * qty, f"RM{unit_price:g} each x {qty:g}")
            continue
        if m := SIGNED.search(text):
            sign = -1 if m.group(1) == "-" else 1
            stated = (sign * float(m.group(2).replace(",", "")), "price stated in chat")
            continue
        if m := MORE_LESS.search(text):
            sign = -1 if m.group(2).lower() in ("less", "cheaper") else 1
            stated = (sign * float(m.group(1).replace(",", "")), "price stated in chat")
            continue
        if m := PLAIN.search(text):
            stated = (float(m.group(1).replace(",", "")), "price stated in chat")
    if stated:
        return stated
    entry = thread.entry
    if entry is not None and qty and thread.kind_hint in ("quantity", "extend"):
        source = "the quote" if entry.line_id else "the rate card"
        return entry.unit_price * qty, f"{qty:g} x RM{entry.unit_price:g} from {source}"
    return None, "no price in the chat, the quote or the rate card"


def _agreement(thread):
    """'agreed', 'withdrawn', 'pending' or 'tentative'."""
    requester = thread.messages[0].sender
    price_sender, state = None, "pending"
    for msg in thread.messages[1:] if len(thread.messages) > 1 else []:
        text = msg.text
        if WITHDRAW.search(text):
            return "withdrawn"
        has_price = bool(PLAIN.search(text))
        is_question = text.rstrip().endswith("?")
        if has_price:
            price_sender, state = msg.sender, "pending"
            if CONFIRM.search(text) and not is_question and msg.sender != requester and not TENTATIVE.search(thread.messages[0].text):
                state = "accepted_with_price"   # "Ok, overtime is RM 300": the other side still has to say yes
            continue
        if DEFER.search(text):
            state = "deferred"
            continue
        if CONFIRM.search(text) and not is_question:
            needed_from_other_than = price_sender or requester
            if msg.sender != needed_from_other_than:
                state = "agreed"
    return state


def _open_kind(text, mentions, catalogue):
    """Decide what kind of thread a new message opens, or None if it is not a request."""
    if DISCOUNT.search(text):
        return "discount", None, f"Discount {DISCOUNT.search(text).group(1)}%"
    line = next((e for e in mentions if e.line_id), None)
    if EXTEND.search(text) and line and catalogue.extra_for(line):
        ext = catalogue.extra_for(line)
        return "extend", ext, ext.item
    # "start dinner at 7:30pm instead of 7pm" names a quote item but changes only the time.
    if SCHEDULE.search(text) and not DELTA[0].search(_clean_for_qty(text)):
        return "schedule", None, "Schedule change"
    if mentions:
        entry = mentions[0]
        extra = next((e for e in mentions if not e.line_id), None)
        if CHANGE.search(text) and line and extra:
            return "replacement", extra, extra.item
        if not entry.line_id:
            return "extend", entry, entry.item
        if CHANGE.search(text) and not re.search(r"\d+\s+instead of", _clean_for_qty(text)) and not REMOVE.search(text):
            return "change", entry, entry.item
        return "quantity", entry, entry.item
    if m := SWAP.search(text):
        return "swap", None, f"{m.group(1).capitalize()}: {m.group(2)} to {m.group(3)}"
    if m := GENERIC_ITEM.search(_clean_for_qty(text)):
        return "generic", None, m.group(2).strip().capitalize()
    if m := GENERIC_ADD.search(text):
        return "generic", None, m.group(1).strip().capitalize()
    return None


def extract(messages, catalogue: Catalogue):
    threads: list[Thread] = []
    recaps = []

    def open_thread_for(entry_item, at):
        for t in reversed(threads):
            if t.item == entry_item and at - t.last.sent_at <= THREAD_WINDOW:
                return t
        return None

    for msg in messages:
        if msg.sender is None or msg.is_media:
            continue
        if RECAP.search(msg.text) or msg.text.count("\n- ") >= 3:
            recaps.append(msg)
            continue
        text = msg.text
        mentions = catalogue.mentions(text)
        # Sharing the quote or asking for the invoice is not a change, unless it also names an item
        # ("I update to 195 pax. Will reflect in the final bill").
        if IGNORE.search(text) and (not mentions or "signed quote" in text.lower()):
            continue
        opened = _open_kind(text, mentions, catalogue) if (ASK.search(text) or "?" in text or DISCOUNT.search(text)) else None

        # A reply about something already being discussed joins that thread.
        named = None
        if DISCOUNT.search(text):
            named = open_thread_for(f"Discount {DISCOUNT.search(text).group(1)}%", msg.sent_at)
        elif mentions:
            for e in mentions:
                for t in reversed(threads):
                    if (t.entry is e or t.replaces is e or (t.entry and catalogue.extra_for(e) is t.entry)) \
                            and msg.sent_at - t.last.sent_at <= THREAD_WINDOW:
                        named = t
                        break
                if named:
                    break
        elif opened and opened[0] == "generic":
            named = open_thread_for(opened[2], msg.sent_at)
        if named:
            named.messages.append(msg)
            continue

        if opened and not (opened[0] == "quantity" and _quantity(Thread("", opened[1], "", "quantity", [msg]), 0) is None
                           and not REMOVE.search(text) and "?" not in text and not ASK.search(text)):
            kind, entry, item = opened
            thread = Thread(f"t{len(threads) + 1}", entry, item, kind, [msg])
            if kind == "replacement":
                thread.replaces = next((e for e in mentions if e.line_id), None)
                thread.entry = None
            threads.append(thread)
            continue

        # Replies that name nothing ("ok go ahead", "Fine", "and 1 at the lift lobby also")
        # attach to the most recently active thread, if it is still open.
        if threads and msg.sent_at - threads[-1].last.sent_at <= THREAD_WINDOW:
            latest = max(threads, key=lambda t: t.last.sent_at)
            is_continuation = CONTINUATION.search(_clean_for_qty(text)) and latest.messages[0].sender == msg.sender \
                and msg.sent_at - latest.last.sent_at <= CONTINUATION_WINDOW
            if is_continuation or CONFIRM.search(text) or DEFER.search(text) or WITHDRAW.search(text) \
                    or PLAIN.search(text) or NO_COST.search(text) or HOURS.search(_clean_for_qty(text)):
                latest.messages.append(msg)

    running_qty = {e.line_id: e.qty for e in catalogue.lines}
    changes = []
    for t in threads:
        changes.append(_decide(t, catalogue, running_qty))
    for recap in recaps:
        mentioned = {e.item for e in catalogue.mentions(recap.text)}
        for c in changes:
            line = catalogue.line(c.line_id) if c.line_id else None
            if c.status not in ("withdrawn",) and line is not None and line.item in mentioned:
                c.evidence_ids.append(recap.id)
    return changes


def _describe_upgrade(t):
    """'LED wall 3m x 2m, changed to 4m x 2.5m' instead of just the quoted item."""
    quoted = t.entry.item
    for msg in t.messages:
        for m in TARGET_SIZE.finditer(msg.text):
            size = m.group(1).strip()
            if size.replace(" ", "").lower() not in quoted.replace(" ", "").lower():
                return f"{quoted}, changed to {size}"
        if m := TARGET_WORD.search(msg.text):
            return f"{quoted}, changed to {m.group(1)}"
    return f"{quoted}, changed"


def _decide(t, catalogue, running_qty):
    base_line = t.entry if (t.entry is not None and t.entry.line_id) else t.replaces
    base_qty = running_qty.get(base_line.line_id, 0) if base_line is not None else 0
    qty = _quantity(t, base_qty) if t.kind_hint in ("quantity", "extend", "generic") else 0
    if t.kind_hint == "generic" and qty is None:
        qty = 1
    agreement = _agreement(t)
    no_cost = any(NO_COST.search(m.text) for m in t.messages)
    who = t.messages[0].sender
    evidence = [m.id for m in t.messages]
    line_id = base_line.line_id if base_line is not None else None

    kind = {"quantity": "quantity_change", "extend": "extra", "generic": "extra", "replacement": "replacement",
            "change": "upgrade", "discount": "discount", "swap": "non_billable", "schedule": "non_billable"}[t.kind_hint]
    if t.kind_hint == "extend" and t.entry is not None and t.entry.line_id is None:
        line_id = None
    if t.kind_hint == "change":
        t.item = _describe_upgrade(t)

    if t.kind_hint == "discount":
        return Change(t.key, kind, t.item, None, 0, None, "needs_decision", evidence, "high",
                      f"{who} asked for a {t.item.lower()}. The amount it applies to is not stated, so the owner must decide.")
    if agreement == "withdrawn":
        return Change(t.key, kind, t.item, line_id, 0, 0.0, "withdrawn", evidence, "high",
                      f"{who} raised it, then withdrew it.")
    if no_cost or t.kind_hint in ("swap", "schedule"):
        return Change(t.key, "non_billable", t.item, line_id, 0, 0.0, "log_only", evidence, "high",
                      "Agreed with no change in price. Kept on record.")

    price, how = _price(t, qty, catalogue)
    if agreement != "agreed":
        return Change(t.key, kind, t.item, line_id, qty or 0, price, "unconfirmed", evidence, "medium",
                      f"{who} raised it, but nobody confirmed it in the chat. {how.capitalize()}.")
    if base_line is not None and qty:
        running_qty[base_line.line_id] = base_qty + qty
    if price is None:
        return Change(t.key, kind, t.item, line_id, qty or 0, None, "needs_price", evidence, "low",
                      f"Agreed in the chat, but {how}. A person must add the price.")
    confidence = "high" if how == "price stated in chat" or "from the quote" in how else "medium"
    return Change(t.key, kind, t.item, line_id, qty or 0, round(price, 2), "ready", evidence, confidence,
                  f"Requested by {who} and agreed in the chat. Priced from {how}." if "stated" not in how
                  else f"Requested by {who} and agreed in the chat at the price stated.")
