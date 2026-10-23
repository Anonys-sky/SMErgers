"""Business rules must hold across manual actions, bulk actions and live extraction."""
from copy import deepcopy
from dataclasses import replace
import math

import pytest

import store
from bill import build_bill
from main import app
from pricing import MAX_CHANGE_AMOUNT
from workflow import Job, NotAllowed


@pytest.fixture
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    store.reset_demo()


def post(client, record, key, role, action, **fields):
    client.post("/role", data={"role": role})
    return client.post(f"/job/{record.id}/act/{key}", data={"action": action, **fields}, follow_redirects=True)


def discount():
    record = store.JOBS["wedding-dinner"]
    key = next(k for k, i in record.job.items.items() if i.change.kind == "discount")
    return record, key


def removal(qty=-10, price=None):
    record = store.build("qa-removal",
        "01/10/2026, 09:00 - Client: Remove 10 roll-up banners\n"
        "01/10/2026, 09:01 - PM: OK noted", "qa.txt", "q_dinner.json")
    key = next(iter(record.job.items))
    change = replace(record.job.items[key].change, qty_delta=qty,
                     price_delta=qty * 90 if price is None else price)
    record.job = Job([change], catalogue=record.catalogue)
    return record, key


@pytest.mark.parametrize("stage,role,action", [
    ("detected", "pm", "review"), ("reviewed", "owner", "approve"), ("approved", "client", "confirm"),
])
@pytest.mark.parametrize("price", [-900, -1])
def test_over_removal_blocked_at_every_stage_even_with_custom_price(client, stage, role, action, price):
    record, key = removal(price=price)
    record.job.items[key].state = stage
    before = deepcopy(record)
    response = post(client, record, key, role, action)
    assert b"negative or invalid quantity" in response.data
    assert record.job.items == before.job.items
    assert record.job.log.entries == before.job.log.entries
    assert record.versions == before.versions
    assert record.outbox == before.outbox
    assert all(line.qty >= 0 for line in build_bill(record.catalogue, record.job).quote_lines)


@pytest.mark.parametrize("bulk", [False, True])
def test_exact_full_cancellation_is_allowed(client, bulk):
    record, key = removal(qty=-4)
    for role, action in [("pm", "review"), ("owner", "approve"), ("client", "confirm")]:
        if bulk:
            client.post("/role", data={"role": role})
            client.post(f"/job/{record.id}/bulk")
        else:
            post(client, record, key, role, action)
    bill = build_bill(record.catalogue, record.job)
    assert record.job.items[key].state == "confirmed"
    assert next(line for line in bill.quote_lines if "banner" in line.label.lower()).qty == 0


def test_two_cancellations_cannot_overdraw_same_quote_line_at_confirmation(client):
    record, key = removal(qty=-3)
    other = replace(record.job.items[key].change, key="second")
    record.job = Job([record.job.items[key].change, other], catalogue=record.catalogue)
    for item in record.job.items.values():
        item.state = "approved"
    client.post("/role", data={"role": "client"})
    page = client.post(f"/job/{record.id}/bulk", follow_redirects=True).data
    assert record.job.items[key].state == "confirmed"
    assert record.job.items["second"].state == "approved"
    assert b"negative or invalid quantity" in page
    assert b"Confirmed 1 change" in page
    assert b"RM270" in page  # Only the successful cancellation is counted.
    assert len(record.versions) == 2
    assert record.versions[-1].change_keys == [key]
    assert next(l for l in build_bill(record.catalogue, record.job).quote_lines if "banner" in l.label.lower()).qty == 1


def test_only_confirmed_additions_can_support_larger_removal(client):
    record, key = removal(qty=-5)
    addition = replace(record.job.items[key].change, key="addition", qty_delta=2, price_delta=180)
    record.job = Job([record.job.items[key].change, addition], catalogue=record.catalogue)
    with pytest.raises(NotAllowed, match="negative"):
        record.job.act(key, "review", record.actor("pm"))
    record.job.act("addition", "review", record.actor("pm"))
    record.job.act("addition", "confirm", record.actor("client"))
    record.job.act(key, "review", record.actor("pm"))
    record.job.act(key, "confirm", record.actor("client"))
    assert next(l for l in build_bill(record.catalogue, record.job).quote_lines if "banner" in l.label.lower()).qty == 1


@pytest.mark.parametrize("amount,note,message", [
    ("100", "Agreed reduction", b"zero or negative"),
    ("-100", "", b"Explain the discount basis"),
    ("-100", "   ", b"Explain the discount basis"),
])
def test_discount_rejects_positive_amounts_and_missing_basis_atomically(client, amount, note, message):
    record, key = discount()
    before = deepcopy(record)
    page = post(client, record, key, "owner", "decide", price=amount, note=note).data
    assert message in page
    assert record.job.items == before.job.items
    assert record.job.log.entries == before.job.log.entries
    assert record.outbox == before.outbox


@pytest.mark.parametrize("amount", [0, -100])
def test_valid_discount_records_basis_and_never_increases_bill(client, amount):
    record, key = discount()
    base = build_bill(record.catalogue, record.job).draft_total
    post(client, record, key, "owner", "decide", price=str(amount), note="Negotiated fixed reduction")
    assert record.job.items[key].notes[-1][2] == "Negotiated fixed reduction"
    post(client, record, key, "client", "confirm")
    assert build_bill(record.catalogue, record.job).draft_total == base + amount
    assert "Negotiated fixed reduction" in record.job.log.entries[-3].detail


def test_direct_discount_price_entry_cannot_bypass_decision_basis(client):
    record, key = discount()
    for role in ("pm", "owner"):
        page = post(client, record, key, role, "set_price", price="-100").data
        assert b"Only the project director can decide" in page
    assert record.job.items[key].price is None


def test_discount_form_explains_reduction_and_requires_basis(client):
    record, key = discount()
    client.post("/role", data={"role": "owner"})
    page = client.get(f"/job/{record.id}").data
    assert b'max="0"' in page
    assert b"basis for discount" in page.lower()
    assert b'aria-label="Basis for discount' in page


@pytest.mark.parametrize("amount", ["1e308", "-1e308", "1000000001", "-1000000001"])
def test_out_of_range_finite_prices_rejected_before_billing(client, amount):
    record, key = removal(qty=-1)
    before = deepcopy(record)
    page = post(client, record, key, "pm", "set_price", price=amount).data
    assert b"A change amount must be between" in page
    assert record.job.items == before.job.items
    assert record.job.log.entries == before.job.log.entries
    assert math.isfinite(build_bill(record.catalogue, record.job).draft_total)


@pytest.mark.parametrize("state,action,role", [
    ("detected", "review", "pm"), ("reviewed", "approve", "owner"), ("approved", "confirm", "client"),
])
def test_existing_out_of_range_price_cannot_progress(client, state, action, role):
    record, key = removal(qty=-1)
    record.job.items[key].state = state
    record.job.items[key].price = 1e308
    before = deepcopy(record)
    post(client, record, key, role, action)
    assert record.job.items == before.job.items
    assert record.job.log.entries == before.job.log.entries
    assert record.outbox == before.outbox


@pytest.mark.parametrize("amount", [float("inf"), float("nan"), 1e308, -1e308])
def test_extracted_unusable_prices_stay_unpriced_on_import_and_refresh(client, amount):
    record, key = removal(qty=-1)
    change = replace(record.job.items[key].change, price_delta=amount)
    record.job = Job([change], catalogue=record.catalogue)
    assert record.job.items[key].price is None
    updated = replace(change, key="new")
    record.job.refresh([change, updated])
    assert all(i.price is None for i in record.job.items.values())
    bill = build_bill(record.catalogue, record.job)
    assert math.isfinite(bill.outstanding_priced_total)
    assert math.isfinite(bill.draft_total)


def test_extreme_chat_price_imports_as_unpriced_instead_of_corrupting_totals(client):
    record = store.build("qa-huge-price",
        "01/10/2026, 09:00 - Client: Add 1 more roll-up banner for RM" + "9" * 310 +
        "\n01/10/2026, 09:01 - PM: OK noted", "qa.txt", "q_dinner.json")
    assert record.job.items
    assert all(item.price is None for item in record.job.items.values())
    assert math.isfinite(build_bill(record.catalogue, record.job).draft_total)
    assert client.get(f"/job/{record.id}").status_code == 200


def test_maximum_amount_boundary_remains_finite_with_multiple_changes(client):
    record, key = removal(qty=1, price=MAX_CHANGE_AMOUNT)
    second = replace(record.job.items[key].change, key="second", price_delta=MAX_CHANGE_AMOUNT)
    record.job = Job([record.job.items[key].change, second], catalogue=record.catalogue)
    for key in record.job.items:
        for role, action in [("pm", "review"), ("owner", "approve"), ("client", "confirm")]:
            record.job.act(key, action, record.actor(role))
    assert math.isfinite(build_bill(record.catalogue, record.job).draft_total)


@pytest.mark.parametrize("is_discount", [False, True])
def test_dispute_queues_reason_to_responsible_role_and_reconfirmation_works(client, is_discount):
    if is_discount:
        record, key = discount()
        post(client, record, key, "owner", "decide", price="-100", note="Negotiated reduction")
    else:
        record, key = removal(qty=-1)
        post(client, record, key, "pm", "review")
    base = build_bill(record.catalogue, record.job).draft_total
    before = len(record.outbox)
    post(client, record, key, "client", "dispute", note="Please check our agreed quantity or basis")
    assert len(record.outbox) == before + 1
    outgoing = record.outbox[-1]
    assert outgoing.kind == "dispute_request"
    assert outgoing.to == record.team["owner" if is_discount else "pm"]
    assert outgoing.change_keys == [key]
    assert "Please check our agreed quantity or basis" in outgoing.text
    assert record.catalogue.quote["client"] in outgoing.text
    assert build_bill(record.catalogue, record.job).draft_total == base
    assert len(record.versions) == 1
    # Duplicate dispute is rejected without another notification.
    post(client, record, key, "client", "dispute", note="Duplicate")
    assert len(record.outbox) == before + 1
    client.post("/role", data={"role": "owner"})
    assert outgoing.text.splitlines()[0].encode() in client.get(f"/job/{record.id}/history").data
    if is_discount:
        post(client, record, key, "owner", "decide", price="-50", note="Revised reduction basis")
    else:
        post(client, record, key, "pm", "review")
    post(client, record, key, "client", "confirm")
    assert record.job.items[key].state == "confirmed"
    assert len(record.versions) == 2
    assert record.job.log.intact()
