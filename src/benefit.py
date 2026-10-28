"""Measures what SMErgers does for a job, from the code and the activity log, not from a claim.

    python src/benefit.py                  # the four sample jobs, rules reader
    python src/benefit.py --split blind    # the first blind set (also: blind2)
    python src/benefit.py --ai             # use the AI reader (needs a model, see llm_extractor.py)
    python src/benefit.py --write          # also write docs/benefit.md

For each chat it runs the real engine, then plays a CAREFUL team through the real approval flow:
the PM checks every change against its evidence, fixes a wrong price, rejects a change the reader
invented or that nobody agreed, adds a change the reader missed; the director approves what needs
it; the client confirms. The result is read back from the bill and the activity log.

What is counted (from the run): how many agreed changes the reader got right on its own, how many
a person had to fix, add or reject, what reached the bill, and every human action in the log.
What is assumed (the block below): how long each kind of step takes, and the manual effort. The
timed test in docs/timed-bill-test.md replaces these assumptions with a measurement.

The careful team is an assumption too: it notices every change the reader missed. The 'missed'
column is how many changes a person has to find unaided, which is the real residual risk.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from bill import build_bill
from catalogue import Catalogue
from chat_import import find_message, parse_chat
from evaluate import DATA, _same_price, key_files, score_chat
from reader import read as read_chat
from schema import Change
from workflow import Actor, Job, NotAllowed

# --- ASSUMPTIONS: not measured. Change them and the report follows. -------------------------------
WORDS_PER_MINUTE = 200            # how fast a person reads a chat closely enough to find deals
MANUAL_MINUTES_PER_CHANGE = 2.0   # find it in the chat, match it to a quote line, work out the price, type it into the bill
MANUAL_MINUTES_TO_FINISH = 5.0    # total up, check, write the final bill
SECONDS_PER_ACTION = 10           # one click, or one typed price, in SMErgers
SECONDS_PER_EVIDENCE_CHECK = 15   # reading the highlighted messages for one change
SECONDS_PER_ADD = 60              # finding the messages and filling in the "reader missed it" form
# The wireless mics in the Annual Dinner chat have no price anywhere; the demo PM types RM320.
PM_PRICES = {("dinner_client.txt", "Wireless mic"): 320.0}
# ---------------------------------------------------------------------------------------------------

SPLITS = {"sample": ("tuning", "held_out"), "blind": ("blind",), "blind2": ("blind2",)}


def play_team(key_file, ai=False):
    """One chat through the real flow with a careful team. Returns the job, the bill and the counts."""
    key = json.loads((DATA / "answer_keys" / key_file).read_text(encoding="utf-8"))
    catalogue = Catalogue.load(key["quote"])
    messages = parse_chat((DATA / "chats" / key["chat"]).read_text(encoding="utf-8"))
    predicted = read_chat(messages, catalogue, ai=ai)
    score = score_chat(key_file, None, predicted=predicted)
    truth = {best.key: kc for _, best, kc in score["rows"] if best is not None}
    now = datetime(2026, 1, 1, 9, 0)
    job = Job(predicted, policy=catalogue.quote.get("policy"), now=now, catalogue=catalogue)
    pm, owner, client = Actor("PM", "pm"), Actor("Director", "owner"), Actor("Client", "client")
    n = {"fixed": 0, "rejected": 0, "added": 0, "priced": 0}

    def add(kc):
        ids = [find_message(catalogue_messages, e).id for e in kc["evidence"]]
        change = Change("", kc["kind"], kc["key"].replace("_", " "), kc["line_id"], kc["qty_delta"], kc["price_delta"],
                        "ready", ids, "medium", "added by the PM", "manual")
        job.add_change(change, pm, now)
        n["added"] += 1

    catalogue_messages = messages
    for k, item in list(job.items.items()):
        kc = truth.get(k)
        if kc is None:                                         # the reader invented a change
            if item.state != "record_only":                    # a "no charge" note costs nothing and cannot be billed
                job.act(k, "reject", pm, now, note="nobody agreed to this")
                n["rejected"] += 1
        elif kc["status"] == "ready":
            if item.state == "record_only":                    # the reader filed a real, billable change as no-cost
                add(kc)
            else:
                if not _same_price(item.price, kc["price_delta"]):
                    job.act(k, "set_price", pm, now, price=kc["price_delta"], note="price from the chat")
                    n["fixed"] += 1
                _review(job, k, pm, now)
        elif kc["status"] in ("unconfirmed", "withdrawn") and item.state == "detected" and item.change.status == "ready":
            job.act(k, "reject", pm, now, note="not agreed in the chat")   # looked billable, was not
            n["rejected"] += 1
        elif (key["chat"], item.change.item) in PM_PRICES:
            job.act(k, "set_price", pm, now, price=PM_PRICES[(key["chat"], item.change.item)], note="asked the vendor")
            n["priced"] += 1
            _review(job, k, pm, now)
    for _, best, kc in score["rows"]:                          # a billable change the reader never found
        if best is None and kc["status"] == "ready":
            add(kc)
    for k, item in list(job.items.items()):
        if item.change.source == "manual" and item.state == "detected":
            _review(job, k, pm, now)
    for k, item in list(job.items.items()):
        if item.state == "reviewed":
            job.act(k, "approve", owner, now)
    for k, item in list(job.items.items()):
        if item.state == "approved":
            job.act(k, "confirm", client, now)
    return key, job, build_bill(catalogue, job), messages, score, n


def _review(job, key, pm, now):
    item = job.items[key]
    if item.state == "detected" and item.price is not None and item.change.kind != "discount":
        try:
            job.act(key, "review", pm, now, note="agreed in the chat" if item.change.status == "unconfirmed" else "")
        except NotAllowed:
            pass


def measure(key_file, ai=False):
    key, job, bill, messages, score, n = play_team(key_file, ai)
    rows = score["rows"]
    ready = [(best, kc) for _, best, kc in rows if kc["status"] == "ready"]
    right_alone = sum(1 for best, kc in ready if best is not None and best.status == "ready"
                      and _same_price(best.price_delta, kc["price_delta"]))
    wrong = sum(1 for best, kc in ready if best is not None) - right_alone
    missed = sum(1 for best, _ in ready if best is None)
    priced = sum(PM_PRICES.get((key["chat"], i.change.item), 0) > 0 for i in job.items.values())
    expected = sum(kc["price_delta"] for _, kc in ready) + sum(
        PM_PRICES.get((key["chat"], i.change.item), 0) for i in job.items.values())
    human = [e for e in job.log.entries if e.role in ("pm", "owner", "client")]
    words = sum(len(m.text.split()) for m in messages if m.sender)
    changes = len(key["changes"])
    manual = words / WORDS_PER_MINUTE + changes * MANUAL_MINUTES_PER_CHANGE + MANUAL_MINUTES_TO_FINISH
    adds = sum(1 for e in human if e.action == "add")
    tool = ((len(human) - adds) * SECONDS_PER_ACTION + adds * SECONDS_PER_ADD
            + len(job.items) * SECONDS_PER_EVIDENCE_CHECK) / 60
    return {
        "chat": key["chat"], "messages": sum(1 for m in messages if m.sender), "words": words,
        "key_changes": changes, "ready": len(ready) + priced, "right_alone": right_alone, "wrong": wrong, "missed": missed,
        "rejected": n["rejected"], "fixed": n["fixed"], "added": n["added"],
        "on_bill": sum(1 for i in job.items.values() if i.state == "confirmed"),
        "bill": bill.changes_total, "expected": expected,
        "actions": len(human), "log_intact": job.log.intact(), "manual_min": manual, "tool_min": tool,
    }


def table(rows):
    out = ["| Chat | Agreed, billable | Reader right alone | Reader wrong (person fixes) | Reader missed (person adds) | Person rejected | On the bill | Bill RM | Correct RM | Human actions | Manual min (assumed) | SMErgers min |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['chat']} | {r['ready']} | {r['right_alone']} | {r['wrong']} | {r['missed']} | {r['rejected']} | {r['on_bill']} | "
                   f"{r['bill']:,.0f} | {r['expected']:,.0f} | {r['actions']} | {r['manual_min']:.0f} | {r['tool_min']:.0f} |")
    t = {k: sum(r[k] for r in rows) for k in ("ready", "right_alone", "wrong", "missed", "rejected", "on_bill", "actions",
                                              "manual_min", "tool_min", "bill", "expected", "messages")}
    out.append(f"| **Total** | {t['ready']} | {t['right_alone']} | {t['wrong']} | {t['missed']} | {t['rejected']} | {t['on_bill']} | "
               f"{t['bill']:,.0f} | {t['expected']:,.0f} | {t['actions']} | {t['manual_min']:.0f} | {t['tool_min']:.0f} |")
    return "\n".join(out), t


def report(split="sample", ai=False):
    rows = [measure(k, ai) for name in SPLITS[split] for k in key_files(name)]
    body, t = table(rows)
    return body, t, 1 - t["tool_min"] / t["manual_min"], rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    split = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--split"), "sample")
    ai = "--ai" in sys.argv
    body, t, saved, rows = report(split, ai)
    text = (f"### {split} chats, {'AI' if ai else 'rules'} reader, careful team\n\n{body}\n\n"
            f"Of {t['ready']} agreed, billable changes the reader got {t['right_alone']} right on its own ({t['right_alone'] / t['ready']:.0%}); "
            f"a person fixed {t['wrong']} and added {t['missed']} it had missed; with that care {t['on_bill']} reached the bill.\n"
            f"Effort, on the assumptions above: {t['manual_min']:.0f} minutes by hand against {t['tool_min']:.0f} with SMErgers "
            f"({saved:.0%} less). Every cell except the two minute columns is counted from the run.\n")
    print(text)
    if "--write" in sys.argv:
        out = Path(__file__).resolve().parent.parent / "docs" / "benefit.md"
        out.write_text(text, encoding="utf-8")
        print("wrote", out)


if __name__ == "__main__":
    main()
