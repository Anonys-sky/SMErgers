import io

import pytest
from werkzeug.datastructures import MultiDict

import store
from main import app


@pytest.fixture
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    store.reset_demo()


def data(**changes):
    fields = dict(
        title="New conference", client="Test client", company="Test events",
        quote_id="Q-NEW", event_date="2026-12-01", event_type="conference",
        pm="Test PM", owner="Test Director", finance="Test Finance",
        item="Dinner package", qty="100", unit="pax", unit_price="100",
        aliases="guests,pax,dinner",
        chat_text="02/09/2026, 09:12 - Client: Add 10 more guests\n02/09/2026, 09:13 - PM: OK noted",
    )
    fields.update(changes)
    return fields


def test_create_and_complete_existing_workflow(client):
    before = len(store.JOBS)
    response = client.post("/projects/new", data=data())
    assert response.status_code == 302
    record = next(r for r in store.JOBS.values() if r.title == "New conference")
    assert len(store.JOBS) == before + 1
    assert record.team["pm"] == "Test PM"
    assert record.job.items
    assert record.versions[0].total == 10000
    assert b"New conference" in client.get("/?view=projects").data
    for role in ("pm", "owner", "client"):
        client.post("/role", data={"role": role})
        assert client.post(f"/job/{record.id}/bulk").status_code == 302
    assert any(i.state == "confirmed" for i in record.job.items.values())
    assert len(record.versions) > 1
    client.post("/role", data={"role": "finance"})
    for path in ("bill", "bill.csv", "history"):
        assert client.get(f"/job/{record.id}/{path}").status_code == 200
    assert record.job.log.intact()


@pytest.mark.parametrize("changes", [
    {"title": ""}, {"event_date": "bad"}, {"qty": "0"}, {"qty": "NaN"},
    {"unit_price": "Infinity"}, {"unit_price": "-2"}, {"chat_text": "not an export"},
    {"pm": ""}, {"item": ""}, {"aliases": "x" * 201},
])
def test_invalid_data_never_creates_project(client, changes):
    before = set(store.JOBS)
    response = client.post("/projects/new", data=data(**changes))
    assert response.status_code == 400
    assert set(store.JOBS) == before
    assert b"Test client" in response.data


@pytest.mark.parametrize("role", ["client", "finance"])
def test_creation_is_manager_only(client, role):
    client.post("/role", data={"role": role})
    assert client.get("/projects/new").status_code == 403
    assert client.post("/projects/new", data=data()).status_code == 403


def test_upload_and_duplicate_titles(client):
    fields = data(chat_text="")
    fields["chat"] = (io.BytesIO(data()["chat_text"].encode()), "chat.txt")
    assert client.post("/projects/new", data=fields).status_code == 302
    assert client.post("/projects/new", data=data()).status_code == 302
    records = [r for r in store.JOBS.values() if r.title == "New conference"]
    assert len(records) == 2 and records[0].id != records[1].id


def test_reject_invalid_or_conflicting_upload(client):
    for body, filename, chat_text in [
        (b"\xff", "chat.txt", ""), (b"text", "chat.pdf", ""),
        (data()["chat_text"].encode(), "chat.txt", data()["chat_text"]),
    ]:
        before = set(store.JOBS)
        assert client.post("/projects/new", data=data(
            chat_text=chat_text, chat=(io.BytesIO(body), filename))).status_code == 400
        assert set(store.JOBS) == before


def test_multiple_lines_and_rate_card(client):
    fields = MultiDict(data())
    for name, value in dict(item="Stage", qty="1", unit="set", unit_price="500", aliases="stage").items():
        fields.add(name, value)
    fields.update(dict(extra_item="Overtime", extra_unit="hour", extra_price="100", extra_aliases="ot"))
    response = client.post("/projects/new", data=fields)
    assert response.status_code == 302
    record = next(r for r in store.JOBS.values() if r.title == "New conference")
    assert len(record.catalogue.lines) == 2
    assert record.catalogue.extras[0].unit_price == 100


def test_missing_row_values_and_large_request(client):
    fields = MultiDict(data())
    fields.add("item", "Incomplete")
    assert client.post("/projects/new", data=fields).status_code == 400
    assert client.post("/projects/new", data=data(chat_text="x" * 1_000_001)).status_code == 413
