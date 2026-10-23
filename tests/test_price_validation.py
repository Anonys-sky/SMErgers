"""Non-finite amounts must never advance into a confirmed bill."""
import math
from copy import deepcopy

import pytest

import store
from bill import build_bill
from main import app
from workflow import NotAllowed


@pytest.fixture(autouse=True)
def reset_records():
    store.reset_demo()
    yield
    store.reset_demo()


def target(action):
    for record in store.JOBS.values():
        for key, item in record.job.items.items():
            if item.state == "detected" and (item.change.kind == "discount") == (action == "decide"):
                return record, key
    raise AssertionError("No suitable sample change")


@pytest.mark.parametrize("action,role", [("set_price", "pm"), ("set_price", "owner"), ("decide", "owner")])
@pytest.mark.parametrize("price", ["NaN", "nan", "Infinity", "-Infinity", "inf", "1e309", "-1e309"])
def test_invalid_price_rejected_without_side_effects(action, role, price):
    record, key = target(action)
    snapshot = deepcopy(record)
    app.config["TESTING"] = True
    with app.test_client() as client:
        client.post("/role", data={"role": role})
        response = client.post(f"/job/{record.id}/act/{key}", data={
            "action": action, "price": price, "note": "Must not be saved",
        }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Enter a finite price" in response.data
    assert record.job.items == snapshot.job.items
    assert record.job.log.entries == snapshot.job.log.entries
    assert record.versions == snapshot.versions
    assert record.outbox == snapshot.outbox
    assert math.isfinite(build_bill(record.catalogue, record.job).draft_total)


@pytest.mark.parametrize("action,state,role", [
    ("review", "detected", "pm"), ("approve", "reviewed", "owner"), ("confirm", "approved", "client"),
])
@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_existing_bad_price_cannot_progress(action, state, role, price):
    record, key = target("set_price")
    item = record.job.items[key]
    item.state, item.price = state, price
    before = len(record.job.log.entries)
    with pytest.raises(NotAllowed, match="finite price"):
        record.job.act(key, action, record.actor(role))
    assert item.state == state
    assert len(record.job.log.entries) == before


@pytest.mark.parametrize("action,role,price", [
    ("set_price", "pm", 0), ("set_price", "pm", 125.50), ("set_price", "pm", -125.50),
    ("decide", "owner", 0), ("decide", "owner", -125.50),
])
def test_finite_prices_including_credits_remain_valid(action, role, price):
    record, key = target(action)
    record.job.act(key, action, record.actor(role), price=price, note="Documented basis")
    assert record.job.items[key].price == price
