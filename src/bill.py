"""Matches approved changes against the quote and builds the DRAFT final bill.

A draft for the owner's accounting software, not an invoice: nothing is sent or paid from here.
"""
from dataclasses import dataclass, field

BILLABLE = {"confirmed"}
OUTSTANDING = {"detected", "reviewed", "approved", "disputed"}


@dataclass
class BillLine:
    label: str
    qty: float
    unit: str
    unit_price: float | None
    amount: float
    change_keys: list = field(default_factory=list)
    note: str = ""


@dataclass
class Bill:
    quote_id: str
    quote_lines: list
    change_lines: list
    quote_total: float
    changes_total: float
    draft_total: float
    outstanding: list            # (Item, plain reason) not yet on the bill
    outstanding_priced_total: float
    outstanding_unpriced: int
    agreed_beyond_quote: float   # RM agreed in chat on top of the quote, whatever its approval stage


def build_bill(catalogue, job):
    quote = catalogue.quote
    qty = {l.line_id: l.qty for l in catalogue.lines}
    keys_by_line = {l.line_id: [] for l in catalogue.lines}
    change_lines = []

    for key, item in job.items.items():
        if item.state not in BILLABLE:
            continue
        c = item.change
        line = catalogue.line(c.line_id) if c.line_id else None
        # A quantity change priced at the quote's own unit price just moves that line's quantity.
        if c.kind == "quantity_change" and line and item.price is not None \
                and abs(item.price - c.qty_delta * line.unit_price) < 0.005:
            qty[line.line_id] += c.qty_delta
            keys_by_line[line.line_id].append(key)
            continue
        label = c.item if c.kind != "replacement" or not line else f"{line.item} replaced by {c.item}"
        if c.kind == "upgrade" and line:
            label = f"{line.item}: upgrade"
        change_lines.append(BillLine(label, c.qty_delta or 1, "", None, item.price, [key], c.reason))

    quote_lines = []
    for l in catalogue.lines:
        note = f"quote: {l.qty:g}" if qty[l.line_id] != l.qty else ""
        quote_lines.append(BillLine(l.item, qty[l.line_id], l.unit, l.unit_price,
                                    round(qty[l.line_id] * l.unit_price, 2), keys_by_line[l.line_id], note))

    outstanding = []
    for key, item in job.items.items():
        if item.state in OUTSTANDING:
            outstanding.append((item, _waiting_for(item)))

    quote_total = sum(l.qty * l.unit_price for l in catalogue.lines)
    lines_total = sum(l.amount for l in quote_lines)
    changes_total = round(lines_total - quote_total + sum(l.amount for l in change_lines), 2)
    agreed = sum(i.price for i in job.items.values()
                 if i.price and i.state not in ("rejected", "record_only") and i.change.status != "unconfirmed")
    return Bill(
        quote_id=quote["quote_id"], quote_lines=quote_lines, change_lines=change_lines,
        quote_total=quote_total, changes_total=changes_total, draft_total=round(quote_total + changes_total, 2),
        outstanding=outstanding,
        outstanding_priced_total=round(sum(i.price for i, _ in outstanding if i.price is not None), 2),
        outstanding_unpriced=sum(1 for i, _ in outstanding if i.price is None),
        agreed_beyond_quote=round(agreed, 2),
    )


def _waiting_for(item):
    if item.state == "disputed":
        return "Client disputed it. PM to fix and review again."
    if item.price is None:
        return "Needs a price from the PM." if item.change.kind != "discount" else "Needs the owner's decision."
    if item.state == "detected":
        return "Waiting for the PM to check it."
    if item.state == "reviewed":
        return f"Waiting for the owner: {item.needs_owner_reason}."
    return "Waiting for the client to confirm."
