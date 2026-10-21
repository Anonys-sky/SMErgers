import io

import pytest

import store
from main import app


@pytest.fixture()
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def as_role(client, role):
    client.post("/role", data={"role": role})


def key_for(job_id, item_name):
    return next(k for k, i in store.JOBS[job_id].job.items.items() if i.change.item == item_name)


def test_every_page_renders(client):
    assert client.get("/").status_code == 200
    for path in ("", "/bill", "/client", "/log"):
        page = client.get(f"/job/annual-dinner{path}")
        assert page.status_code == 200, path
    assert b"Simulated data" in client.get("/").data


def test_headline_shows_money_agreed_in_chat(client):
    assert "RM3,540".encode() in client.get("/job/annual-dinner").data


def test_full_flow_through_the_pages(client):
    banners = key_for("annual-dinner", "Roll-up banner")
    as_role(client, "pm")
    client.post(f"/job/annual-dinner/act/{banners}", data={"action": "review"})
    as_role(client, "client")
    client.post(f"/job/annual-dinner/act/{banners}", data={"action": "confirm"})
    assert store.JOBS["annual-dinner"].job.items[banners].state == "confirmed"
    bill = client.get("/job/annual-dinner/bill").data.decode()
    assert "quote: 4" in bill
    assert "confirm" in client.get("/job/annual-dinner/log").data.decode()


def test_server_refuses_actions_the_role_may_not_take(client):
    banners = key_for("annual-dinner", "Roll-up banner")
    as_role(client, "client")
    page = client.post(f"/job/annual-dinner/act/{banners}", data={"action": "review"}, follow_redirects=True)
    assert "cannot review" in page.data.decode()
    assert store.JOBS["annual-dinner"].job.items[banners].state == "detected"


def test_chat_text_is_escaped(client):
    raw = "01/10/2026, 9:00 am - Eve: <script>alert(1)</script> add 2 more banner\n"
    client.post("/import", data={"quote": "q_dinner.json", "chat": (io.BytesIO(raw.encode()), "x.txt")},
                content_type="multipart/form-data")
    job_id = next(j for j in store.JOBS if j.startswith("annual-dinner-2026"))
    html = client.get(f"/job/{job_id}").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_import_rejects_non_text_files(client):
    page = client.post("/import", data={"quote": "q_dinner.json", "chat": (io.BytesIO(b"x"), "x.pdf")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert "Choose a WhatsApp export" in page.data.decode()
