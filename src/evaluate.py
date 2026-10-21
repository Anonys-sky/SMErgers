"""Scores an extractor against the hand-written answer keys.

    python src/evaluate.py            # tuning chats only
    python src/evaluate.py --held-out # the held-out chats (score once, report as is)

A predicted change matches a key change when they share chat messages as evidence.
"""
import json
import re
import sys
from pathlib import Path

from catalogue import Catalogue
from chat_import import find_message, parse_chat
from rules_extractor import extract
from schema import Change

DATA = Path(__file__).resolve().parent.parent / "data"
MONEY = re.compile(r"RM\s?([\d,]+(?:\.\d+)?)", re.I)


def naive_extract(messages, catalogue):
    """Baseline: every message that mentions an RM amount is a change at that amount."""
    out = []
    for m in messages:
        if m.sender and (hit := MONEY.search(m.text)):
            sign = -1 if re.search(r"\b(less|cheaper)\b", m.text, re.I) else 1
            out.append(Change(f"n{m.seq}", "extra", m.text[:40], None, 0,
                              sign * float(hit.group(1).replace(",", "")), "ready", [m.id]))
    return out


def score_chat(key_file, extractor):
    key = json.loads((DATA / "answer_keys" / key_file).read_text(encoding="utf-8"))
    messages = parse_chat((DATA / "chats" / key["chat"]).read_text(encoding="utf-8"))
    predicted = extractor(messages, Catalogue.load(key["quote"]))

    taken, rows = set(), []
    for kc in key["changes"]:
        ids = {find_message(messages, e).id for e in kc["evidence"]}
        best = max((p for p in predicted if p.key not in taken),
                   key=lambda p: len(ids & set(p.evidence_ids)), default=None)
        if best is None or not ids & set(best.evidence_ids):
            rows.append((kc["key"], None, kc))
            continue
        taken.add(best.key)
        rows.append((kc["key"], best, kc))

    found = [r for r in rows if r[1] is not None]
    status_ok = [r for r in found if r[1].status == r[2]["status"]]
    price_ok = [r for r in found if _same_price(r[1].price_delta, r[2]["price_delta"])]
    fully_ok = [r for r in found if r[1].status == r[2]["status"] and _same_price(r[1].price_delta, r[2]["price_delta"])]
    extra = [p for p in predicted if p.key not in taken]
    billed = sum(p.price_delta for p in predicted if p.status == "ready" and p.price_delta is not None)
    return {
        "chat": key["chat"], "split": key.get("split", "tuning"), "key_changes": len(rows),
        "found": len(found), "status_ok": len(status_ok), "price_ok": len(price_ok),
        "fully_ok": len(fully_ok), "false_changes": len(extra),
        "ready_total": billed, "expected_ready_total": key["expected_known_delta"], "rows": rows,
    }


def _same_price(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < 0.5


def key_files(held_out):
    """Answer keys for client chats (the vendor key has a different shape), tuning or held-out."""
    chosen = []
    for path in sorted((DATA / "answer_keys").glob("*.json")):
        key = json.loads(path.read_text(encoding="utf-8"))
        if "changes" in key and (key.get("split") == "held_out") == held_out:
            chosen.append(path.name)
    return chosen


def report(held_out=False, verbose=True):
    lines = []
    for name, fn in (("rules", extract), ("naive baseline", naive_extract)):
        lines.append(f"\n## {name}")
        lines.append("| chat | changes | found | status right | price right | fully right | false changes | RM ready (expected) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for kf in key_files(held_out):
            s = score_chat(kf, fn)
            lines.append(f"| {s['chat']} | {s['key_changes']} | {s['found']} | {s['status_ok']} | {s['price_ok']} | "
                         f"{s['fully_ok']} | {s['false_changes']} | {s['ready_total']:,.0f} ({s['expected_ready_total']:,.0f}) |")
            if verbose and fn is extract:
                for k, p, kc in s["rows"]:
                    got = "MISSED" if p is None else f"{p.status} {p.price_delta}"
                    mark = "ok " if p and p.status == kc["status"] and _same_price(p.price_delta, kc["price_delta"]) else "XX "
                    lines.append(f"    {mark}{k}: expected {kc['status']} {kc['price_delta']} | got {got}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(report(held_out="--held-out" in sys.argv))
