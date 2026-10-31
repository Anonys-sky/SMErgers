"""AI chat reader: a language model finds the changes, plain code checks them.

The model only *reads* the chat. It reports what was asked, by which messages, and whether it
was agreed, withdrawn or never answered. Everything after that is deterministic:

- evidence must be real message numbers, or the change is dropped;
- a price counts only if that amount appears in the cited messages, or comes from the quote's
  own unit price; otherwise the change is marked "needs_price" for a person;
- the status is set by code from the model's outcome, never taken on trust;
- any failure (model offline, bad JSON) falls back to the rules reader.

It talks to any OpenAI-compatible endpoint, by default a local Ollama server, which is free and
needs no API key and no internet:

    ollama pull llama3.1:8b
    SMERGERS_READER=llm python src/main.py

On RunPod instead (a GPU endpoint, see runpod/README.md), set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY.

Settings (all optional): SMERGERS_LLM_URL, SMERGERS_LLM_MODEL, SMERGERS_LLM_KEY, SMERGERS_LLM_TIMEOUT.
"""
import json
import os
import re
import urllib.request

from schema import Change

# Where the model runs. With RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY set, the reader calls that RunPod
# serverless endpoint (vLLM worker, OpenAI-compatible); otherwise a local Ollama server.
_RUNPOD = bool(os.environ.get("RUNPOD_ENDPOINT_ID") and os.environ.get("RUNPOD_API_KEY"))
if _RUNPOD:
    _URL = f"https://api.runpod.ai/v2/{os.environ['RUNPOD_ENDPOINT_ID']}/openai/v1/chat/completions"
    _MODEL, _KEY = "meta-llama/Llama-3.1-8B-Instruct", os.environ["RUNPOD_API_KEY"]
else:
    _URL, _MODEL, _KEY = "http://localhost:11434/v1/chat/completions", "llama3.1:8b", ""
URL = os.environ.get("SMERGERS_LLM_URL", _URL)
MODEL = os.environ.get("SMERGERS_LLM_MODEL", _MODEL)
KEY = os.environ.get("SMERGERS_LLM_KEY", _KEY)
TIMEOUT = float(os.environ.get("SMERGERS_LLM_TIMEOUT", "300"))

KINDS = {"quantity_change", "upgrade", "replacement", "extra", "discount", "non_billable"}
OUTCOMES = {"agreed", "asked", "withdrawn", "discount", "no_cost"}
MONEY = re.compile(r"RM\s?([\d,]+(?:\.\d+)?)", re.I)
# Wording that says the price is not settled yet: then the quote's unit price must not stand in for it.
PRICE_LATER = re.compile(
    r"\b(tbc|tba)\b|price\s+(later|to be (confirmed|advised|quoted))|(quote|confirm|advise|revert|let you know|get back)\b.{0,30}\b(price|cost|rate|quotation)\b"
    r"|\b(price|cost|rate)\b.{0,25}\b(later|to follow|afterwards)\b|\bhow much\b"
    r"|\bprice\s+to\s+(be\s+)?(confirm|follow|advis|quot)", re.I)
# "total rm 180" and "rm15 per pack": how a staff member states the amount for a whole change or for one unit.
TOTAL = re.compile(r"\btotal\b\D{0,12}RM\s?([\d,]+(?:\.\d+)?)", re.I)
PER_UNIT = re.compile(r"RM\s?([\d,]+(?:\.\d+)?)\s*(each|per\b|/|a piece|ea\b)", re.I)
GENERIC_WORDS = {"more", "extra", "adds", "addi", "chang", "upgra", "with", "from", "this", "that", "unit", "units", "items", "staff", "crew", "pack", "packs", "first"}
GENERIC_STEMS = {"mor", "ext", "add", "upg", "cha", "and", "for", "the", "can", "not", "tha", "ple", "boc", "tam"}
RECALL = os.environ.get("SMERGERS_RECALL", "1") != "0"
# A later message that takes the request back (English and Malay): "cancel", "never mind", "tak jadi", "kekal 6".
TAKEN_BACK = re.compile(r"\b(cancel(led)?|never\s?mind|no need|forget (it|about)|drop (it|that)|tak jadi|tak payah|batal|kekal)\b", re.I)
# Wording that says someone must check before it is a yes. Only the LAST cited message counts, so a
# "let me check" that is followed by "ok go ahead" does not hold the change back.
NOT_YET = re.compile(
    r"\b(ask|check|discuss|confirm)\s+(with\s+)?(my\s+|the\s+|our\s+)?(boss|manager|director|team|husband|wife|partner|first)\b"
    r"|\blet me (check|ask|confirm|discuss|think)\b|\bget back to you\b|\b(need|have) to (check|ask|discuss)\b|\bnot sure yet\b", re.I)

PROMPT = """You read a WhatsApp chat between an event company and its client, after a quote was signed.
Find every CHANGE to the signed quote: more or fewer items, an upgrade, a replacement, an extra
that is not on the quote, a discount request, or a change with no cost (a menu swap, a time change).

Rules:
- One entry per change. A recap message repeats earlier changes: cite it as evidence, never add it again.
- "outcome" is one of: agreed (both sides clearly said yes, such as "ok", "go ahead", "confirmed"),
  asked (requested but nobody confirmed, or someone said they must check or ask someone first),
  withdrawn (raised, then taken back), discount (asked for a discount), no_cost (agreed and the
  price stays the same, such as a colour, time or menu swap, with kind non_billable).
  A staff "noted" or "will check" is NOT a yes.
- "price_delta" is the extra money in RM ONLY if an amount is written in the chat for it. Otherwise null.
  Never calculate or guess a price. If someone says the price will come later, it is null.
- "qty_delta" is how many more (negative for fewer); 0 if not a quantity change.
- Times, dates and sizes are not quantities.
- "line_id" is the quote line it changes (like L03), or null if it is not on the quote. Match on
  the words people use: for example "pax" or "people" mean the guest line.
- "messages" lists the message numbers that prove it.

Quote lines:
{lines}

Chat:
{chat}

Answer with JSON only: {{"changes": [{{"item": "...", "line_id": "L01 or null", "kind": "quantity_change|upgrade|replacement|extra|discount|non_billable",
"qty_delta": 0, "price_delta": null, "outcome": "agreed|asked|withdrawn|discount|no_cost", "messages": [1, 2], "reason": "one short sentence"}}]}}"""


class ReaderError(Exception):
    pass


def _call(prompt):
    body = json.dumps({
        "model": MODEL, "temperature": 0, "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    request = urllib.request.Request(URL, body, headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())["choices"][0]["message"]["content"]
    except Exception as exc:  # network, timeout, bad envelope
        raise ReaderError(f"model call failed: {exc}") from exc


def _prompt(messages, catalogue):
    lines = "\n".join(f"{l.line_id}: {l.item} (qty {l.qty:g}, RM{l.unit_price:g} each; people also say: {', '.join(l.aliases)})"
                      for l in catalogue.lines)
    chat = "\n".join(f"[{m.seq}] {m.sender}: {m.text}" for m in messages if m.sender)
    return PROMPT.format(lines=lines, chat=chat)


def _amounts(texts):
    found = set()
    for text in texts:
        for m in MONEY.finditer(text):
            found.add(float(m.group(1).replace(",", "")))
    return found


def _stems(text):
    """First three letters of each word: 'vegetarian' and 'veg' meet. Generic words are left out."""
    return {w[:3] for w in re.findall(r"[a-zA-Z]{3,}", text.lower())} - GENERIC_STEMS


def _later_price_cue(name, cited, by_seq, line=None):
    """A recap that comes after the change may say 'price to confirm': then no price is settled yet."""
    return _later_cue(name, cited, by_seq, PRICE_LATER, line)


def _about(name, line, part):
    """True if this piece of text is about the item: a shared distinctive word, or one of the quote line's
    own names for it ('khemah' for a tent). Needs a real word, not a three-letter stem."""
    text = part.lower()
    words = {w[:5] for w in re.findall(r"[a-z]{4,}", name.lower())} - GENERIC_WORDS
    if words & {w[:5] for w in re.findall(r"[a-z]{4,}", text)}:
        return True
    return bool(line) and any(len(a) >= 4 and a.lower() in text for a in line.aliases)


def _later_cue(name, cited, by_seq, pattern, line=None):
    """True if a later message says `pattern` about THIS item. A recap lists many items, so each
    comma or semicolon part is checked on its own: 'cable tray (price to confirm)' must not
    hold back the study room that sits next to it. Messages the model already cited are skipped."""
    first = min(m.seq for m in cited)
    cited_seqs = {m.seq for m in cited}
    for m in by_seq.values():
        if m.seq <= first or m.seq in cited_seqs:
            continue
        for part in re.split(r"[;,\n]|\.\s", m.text):
            if pattern.search(part) and _about(name, line, part):
                return True
    return False


def _recover_price(cited, by_seq, name, qty):
    """The amount can sit in a message next to the cited ones ('total rm 300 more'). Use it only when
    exactly one amount is stated for this item, and say which messages it came from."""
    lo, hi = min(m.seq for m in cited), max(m.seq for m in cited)
    stems = _stems(name)
    cited_seqs = {m.seq for m in cited}
    about = [by_seq[s] for s in range(lo - 1, hi + 3)
             if s in by_seq and (s in cited_seqs or stems & _stems(by_seq[s].text))]
    totals = {float(a.replace(",", "")) for m in about for a in TOTAL.findall(m.text)}
    if len(totals) == 1:
        amount = totals.pop()
    else:
        amounts = {a for m in about for a in _amounts([m.text])}
        if len(amounts) != 1:
            return None
        amount = amounts.pop()
        if qty and any(PER_UNIT.search(m.text) for m in about if amount in _amounts([m.text])):
            amount = amount * abs(qty)
    used = [m for m in about if _amounts([m.text])]
    return amount, used


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_changes(raw, messages, catalogue, note=""):
    """Turn the model's JSON into validated Changes. Pure function: easy to test."""
    try:
        items = json.loads(raw)["changes"]
        if not isinstance(items, list):
            raise TypeError
    except (ValueError, KeyError, TypeError) as exc:
        raise ReaderError("model did not return the expected JSON") from exc

    by_seq = {m.seq: m for m in messages if m.sender}
    changes = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cited = [by_seq[int(n)] for n in item.get("messages", []) if str(n).lstrip("-").isdigit() and int(n) in by_seq]
        outcome = item.get("outcome")
        if not cited or outcome not in OUTCOMES:
            continue                                  # no real evidence, or an outcome we cannot map
        line = catalogue.line(item.get("line_id")) if item.get("line_id") else None
        if line is None:                              # no valid line from the model: look the item up by its name
            line = next((e for e in catalogue.mentions(str(item.get("item", ""))) if e.line_id), None)
        kind = item.get("kind") if item.get("kind") in KINDS else "extra"
        qty = _number(item.get("qty_delta")) or 0.0
        name = (item.get("item") or (line.item if line else "Change")).strip()[:80]
        evidence = [m.id for m in cited]
        key = f"ai{len(changes) + 1}"
        why = (item.get("reason") or "").strip()[:200]

        def make(status, price, delta, confidence, reason):
            return Change(key, kind, name, line.line_id if line else None, delta, price, status,
                          evidence, confidence, reason, source="ai")

        cited_text = [m.text for m in cited]
        if outcome == "asked" and qty >= 0 and _later_cue(name, cited, by_seq, TAKEN_BACK, line):
            outcome = "withdrawn"                     # a request nobody confirmed is later cancelled, or stays as it was
        if outcome == "agreed" and NOT_YET.search(cited[-1].text):
            outcome = "asked"                             # the last word was "let me check", not a yes
        if outcome == "agreed" and kind == "non_billable" and qty == 0 and not _amounts(cited_text):
            outcome = "no_cost"                           # a colour or time swap is logged, not priced
        if outcome == "withdrawn":
            changes.append(make("withdrawn", 0.0, 0, "medium", why or "Raised, then withdrawn."))
        elif outcome == "discount" or kind == "discount":
            changes.append(make("needs_decision", None, 0, "medium", why or "Discount asked: the owner must decide the amount."))
        elif outcome == "no_cost":
            changes.append(make("log_only", 0.0, 0, "medium", why or "Agreed with no change in price."))
        else:
            price = _number(item.get("price_delta"))
            how = "price stated in chat"
            price_later = any(PRICE_LATER.search(t) for t in cited_text) or _later_price_cue(name, cited, by_seq, line)
            if price is not None and abs(price) not in _amounts(m.text for m in cited):
                price = None                          # the model quoted a number nobody wrote
            if price is None and not price_later:
                found = _recover_price(cited, by_seq, name, qty)
                if found:                             # the amount was written in the next message or two
                    price = found[0]
                    evidence = evidence + [m.id for m in found[1] if m.id not in evidence]
            if (price is None and line is not None and qty != 0 and kind in ("quantity_change", "extra", "replacement", "upgrade")
                    and not price_later):
                price, how = qty * line.unit_price, "the quote's unit price"
            if outcome == "asked":
                changes.append(make("unconfirmed", price, qty, "medium", why or "Raised, but nobody confirmed it."))
            elif price is None:
                changes.append(make("needs_price", None, qty, "low", why or "Agreed, but no price is stated. A person must add it."))
            else:
                changes.append(make("ready", round(price, 2), qty, "high" if how.startswith("price") else "medium",
                                    f"{why} Priced from {how}.".strip()))
    return changes


RECALL_PROMPT = """You read a WhatsApp chat between an event company and its client, after a quote was signed.
A first reading found these changes to the signed quote:
{found}

List every OTHER change in the chat that is missing from that list: more or fewer items, an upgrade, a
replacement, an extra, a discount request or a no-cost change. Check each message that asks for something.
Two items in one message are two changes. Do not repeat anything already listed. If nothing is missing,
answer {{"changes": []}}. Use exactly the same rules and JSON format as before.

Quote lines:
{lines}

Chat:
{chat}

Answer with JSON only: {{"changes": [{{"item": "...", "line_id": "L01 or null", "kind": "quantity_change|upgrade|replacement|extra|discount|non_billable",
"qty_delta": 0, "price_delta": null, "outcome": "agreed|asked|withdrawn|discount|no_cost", "messages": [1, 2], "reason": "one short sentence"}}]}}"""


def _same_change(a, b):
    """True if two changes are the same request seen twice."""
    if a.line_id and a.line_id == b.line_id and (a.qty_delta > 0) == (b.qty_delta > 0):
        return True
    shared = _stems(a.item) & _stems(b.item)
    if shared and set(a.evidence_ids) & set(b.evidence_ids):
        return True
    return bool(shared) and len(shared) >= min(len(_stems(a.item)), len(_stems(b.item)))


def extract(messages, catalogue):
    """Read the chat with the model. Raises ReaderError if it cannot.
    A second, short pass asks only 'what is missing?'. Whatever it adds goes through the same checks."""
    first = build_changes(_call(_prompt(messages, catalogue)), messages, catalogue)
    if not RECALL:
        return first
    lines = "\n".join(f"{l.line_id}: {l.item}" for l in catalogue.lines)
    chat = "\n".join(f"[{m.seq}] {m.sender}: {m.text}" for m in messages if m.sender)
    found = "\n".join(f"- {c.item}" for c in first) or "- (none)"
    try:
        second = build_changes(_call(RECALL_PROMPT.format(found=found, lines=lines, chat=chat)), messages, catalogue)
    except ReaderError:
        return first                                  # the extra pass is a bonus: the first reading stands alone
    merged = list(first)
    for change in second:
        if not any(_same_change(change, kept) for kept in merged):
            change.key = f"ai{len(merged) + 1}"
            merged.append(change)
    return merged
