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
    as_role(client, "finance")
    bill = client.get("/job/annual-dinner/bill").data.decode()
    assert "quote: 4" in bill
    assert "confirm" in client.get("/job/annual-dinner/log").data.decode()


def test_server_refuses_actions_the_role_may_not_take(client):
    banners = key_for("annual-dinner", "Roll-up banner")
    as_role(client, "client")
    page = client.post(f"/job/annual-dinner/act/{banners}", data={"action": "review"}, follow_redirects=True)
    assert "cannot review" in page.data.decode()
    assert store.JOBS["annual-dinner"].job.items[banners].state == "detected"


def test_clients_only_see_their_confirmation_page(client):
    as_role(client, "client")
    for path in ("", "/bill", "/bill.csv", "/log"):
        page = client.get(f"/job/annual-dinner{path}")
        assert page.status_code == 302 and page.location.endswith("/job/annual-dinner/client"), path
    assert b"Activity log" not in client.get("/job/annual-dinner/client").data


def test_bill_csv_is_marked_draft_and_totals_match(client):
    rows = client.get("/job/annual-dinner/bill.csv").data.decode().splitlines()
    assert rows[0].startswith("DRAFT - not an invoice")
    assert rows[-1].endswith("34530.0,")


def test_api_reports_changes_bill_and_log(client):
    data = client.get("/api/jobs/annual-dinner").get_json()
    assert data["job"]["simulated"] is True
    assert len(data["changes"]) == 10
    assert data["bill"]["agreed_in_chat_beyond_quote"] == 3540
    assert data["activity_log"]["intact"] is True


def test_do_all_buttons_move_only_ready_changes(client):
    job = store.JOBS["annual-dinner"].job
    as_role(client, "pm")
    page = client.post("/job/annual-dinner/bulk", follow_redirects=True).data.decode()
    assert "Checked 6 changes" in page                        # the mics have no price, so they wait
    assert job.items[key_for("annual-dinner", "Wireless mic")].state == "detected"
    as_role(client, "owner")
    client.post("/job/annual-dinner/bulk")
    as_role(client, "client")
    client.post("/job/annual-dinner/bulk")
    states = {i.state for i in job.items.values()}
    assert states == {"confirmed", "detected", "record_only"}


def test_highlighting_marks_deal_terms_but_still_escapes(client):
    from main import marked
    html = str(marked("<b>x</b> LED upgrade will be RM 1,100 more, ok go ahead"))
    assert "&lt;b&gt;" in html
    assert "<mark>RM 1,100 more</mark>" in html and "<mark>ok</mark>" in html


def test_success_message_after_an_action(client):
    banners = key_for("annual-dinner", "Roll-up banner")
    page = client.post(f"/job/annual-dinner/act/{banners}", data={"action": "review"}, follow_redirects=True)
    assert "Roll-up banner: approved, waiting for client." in page.data.decode()


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
