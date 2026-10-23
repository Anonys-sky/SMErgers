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

PROMPT = """You read a WhatsApp chat between an event company and its client, after a quote was signed.
Find every CHANGE to the signed quote: more or fewer items, an upgrade, a replacement, an extra
that is not on the quote, a discount request, or a change with no cost (a menu swap, a time change).

Rules:
- One entry per change. A recap message repeats earlier changes: cite it as evidence, never add it again.
- "outcome" is one of: agreed (both sides said yes), asked (requested but nobody confirmed, or
  someone said they must check first), withdrawn (raised, then taken back), discount (asked for a
  discount), no_cost (agreed and the price stays the same).
- "price_delta" is the extra money in RM ONLY if an amount is written in the chat for it. Otherwise null.
  Never calculate or guess a price.
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

        if outcome == "withdrawn":
            changes.append(make("withdrawn", 0.0, 0, "medium", why or "Raised, then withdrawn."))
        elif outcome == "discount" or kind == "discount":
            changes.append(make("needs_decision", None, 0, "medium", why or "Discount asked: the owner must decide the amount."))
        elif outcome == "no_cost":
            changes.append(make("log_only", 0.0, 0, "medium", why or "Agreed with no change in price."))
        else:
            price = _number(item.get("price_delta"))
            how = "price stated in chat"
            if price is not None and abs(price) not in _amounts(m.text for m in cited):
                price = None                          # the model quoted a number nobody wrote
            if price is None and line is not None and qty != 0 and kind in ("quantity_change", "extra", "replacement"):
                price, how = qty * line.unit_price, "the quote's unit price"
            if outcome == "asked":
                changes.append(make("unconfirmed", price, qty, "medium", why or "Raised, but nobody confirmed it."))
            elif price is None:
                changes.append(make("needs_price", None, qty, "low", why or "Agreed, but no price is stated. A person must add it."))
            else:
                changes.append(make("ready", round(price, 2), qty, "high" if how.startswith("price") else "medium",
                                    f"{why} Priced from {how}.".strip()))
    return changes


def extract(messages, catalogue):
    """Read the chat with the model. Raises ReaderError if it cannot."""
    return build_changes(_call(_prompt(messages, catalogue)), messages, catalogue)
