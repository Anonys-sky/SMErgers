import pytest

import store
import suggest
from main import app


def titles(event_type):
    return [(s.category, s.seen_in, s.of_jobs) for s in suggest.for_event_type(event_type)]


def test_dinner_suggestions_are_counted_from_history():
    assert titles("dinner") == [("overtime", 4, 4), ("guests", 3, 4), ("screen", 2, 4), ("av_extras", 2, 4)]


def test_unpriced_changes_are_called_out():
    mics = next(s for s in suggest.for_event_type("dinner") if s.category == "av_extras")
    assert mics.unpriced == 2 and "rate card" in mics.advice


def test_weddings_flag_discounts_given_in_chat():
    discount = next(s for s in suggest.for_event_type("wedding") if s.category == "discount")
    assert (discount.seen_in, discount.typical_amount) == (2, -1650)


def test_no_suggestions_without_enough_history():
    assert suggest.for_event_type("renovation") == []
    assert suggest.for_event_type("dinner", company="Someone Else Sdn Bhd") == []


@pytest.fixture()
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_owner_sees_suggestions_finance_does_not(client):
    client.post("/role", data={"role": "owner"})
    page = client.get("/job/annual-dinner").data.decode()
    assert "Next time, quote it upfront" in page
    assert "Decide amount" not in page and "Nothing waits for you as Owner" in page
    client.post("/role", data={"role": "finance"})
    assert "Next time, quote it upfront" not in client.get("/job/annual-dinner").data.decode()


def test_api_includes_suggestions(client):
    data = client.get("/api/jobs/annual-dinner").get_json()
    assert data["suggestions"][0]["category"] == "overtime"
