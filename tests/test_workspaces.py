"""Role workspaces use live approval state and preserve read/write boundaries."""
from contextlib import contextmanager

import pytest
from flask import template_rendered

import store
from main import app


@pytest.fixture()
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@contextmanager
def rendered_context():
    contexts = []

    def capture(sender, template, context, **extra):
        contexts.append(context)

    template_rendered.connect(capture, app)
    try:
        yield contexts
    finally:
        template_rendered.disconnect(capture, app)


def workspace(client, persona, **query):
    with rendered_context() as contexts:
        response = client.get(f"/workspace/{persona}", query_string=query)
    assert response.status_code == 200
    return contexts[-1]


@pytest.mark.parametrize("persona,role", [
    ("project-manager", "pm"), ("project-director", "owner"),
    ("client", "client"), ("finance", "finance"),
])
def test_separate_workspaces_and_role_specific_guides(client, persona, role):
    context = workspace(client, persona)
    assert context["role"] == role
    assert context["profile"]["slug"] == persona
    assert context["workspace"]["metrics"]
    assert len(context["workspace"]["checklist"]) == 4
    with client.session_transaction() as session:
        assert session["role"] == role
    assert client.get("/").status_code == 200
    assert client.get("/guide").status_code == 200


def test_persona_not_found_does_not_switch_role(client):
    client.post("/role", data={"role": "finance"})
    assert client.get("/workspace/administrator").status_code == 404
    with client.session_transaction() as session:
        assert session["role"] == "finance"


def test_role_switch_lands_on_dedicated_workspace_not_external_next(client):
    response = client.post("/role", data={"role": "owner", "next": "https://example.com"})
    assert response.location.endswith("/workspace/project-director")


def test_workspace_counts_and_finance_totals_follow_real_actions(client):
    pm = workspace(client, "project-manager")["workspace"]
    assert pm["queue"]
    banner = next(
        key for key, item in store.JOBS["annual-dinner"].job.items.items()
        if item.change.item == "Roll-up banner"
    )
    client.post(f"/job/annual-dinner/act/{banner}", data={"action": "review"})
    director = workspace(client, "project-director")["workspace"]
    assert director["jobs"][0]["confirmed"] == 0
    client_workspace = workspace(client, "client")["workspace"]
    assert len(client_workspace["queue"]) == 1
    client.post(f"/job/annual-dinner/act/{banner}", data={"action": "confirm"})
    finance = workspace(client, "finance")["workspace"]
    dinner = next(row for row in finance["jobs"] if row["record"].id == "annual-dinner")
    assert dinner["confirmed"] == 1
    assert dinner["bill"].changes_total == 270
    assert dinner["bill"].draft_total == 34800
    assert finance["queue"] == []


@pytest.mark.parametrize("role", ["client", "finance"])
@pytest.mark.parametrize("path,method", [
    ("/imports", "get"), ("/import", "post"), ("/reset", "post"),
    ("/whatsapp", "get"), ("/whatsapp/pair", "post"), ("/whatsapp/import", "post"),
])
def test_non_operational_roles_cannot_modify_imports_or_bridge(client, role, path, method):
    client.post("/role", data={"role": role})
    before = list(store.JOBS)
    assert getattr(client, method)(path).status_code == 403
    assert list(store.JOBS) == before


def test_client_workspace_is_limited_to_selected_sample_client(client):
    context = workspace(client, "client")
    assert [row["record"].id for row in context["workspace"]["jobs"]] == ["annual-dinner"]
    assert context["workspace"]["activity"] == []
    assert client.get("/api/jobs/annual-dinner").status_code == 403
    context = workspace(client, "client", job_id="product-launch")
    assert [row["record"].id for row in context["workspace"]["jobs"]] == ["product-launch"]
    # The client reaches a job through its WhatsApp link; opening a link selects that event.
    assert client.get("/job/annual-dinner/client").status_code == 200
    context = workspace(client, "client")
    assert [row["record"].id for row in context["workspace"]["jobs"]] == ["annual-dinner"]
    assert client.get("/job/annual-dinner").location.endswith("/job/annual-dinner/client")


def test_client_cannot_request_internal_activity_workspace(client):
    context = workspace(client, "client", view="activity")
    assert context["workspace"]["view"] == "overview"


def test_finance_can_read_sources_but_cannot_change_approval_state(client):
    workspace(client, "finance")
    record = store.JOBS["annual-dinner"]
    key = next(iter(record.job.items))
    assert client.get("/job/annual-dinner").location.endswith("/job/annual-dinner/bill")
    evidence = client.get(f"/job/annual-dinner/evidence/{key}")
    assert evidence.status_code == 200
    assert b'name="action"' not in evidence.data
    assert client.get("/job/annual-dinner/history").status_code == 200
    state = record.job.items[key].state
    assert client.post(f"/job/annual-dinner/act/{key}", data={"action": "approve"}).status_code == 403
    assert client.post("/job/annual-dinner/bulk").status_code == 403
    assert record.job.items[key].state == state


def test_export_checklist_tracks_current_bill_version_not_stale_exports(client):
    workspace(client, "finance")
    assert client.get("/job/annual-dinner/bill.csv").status_code == 200
    context = workspace(client, "finance")["workspace"]
    dinner = next(row for row in context["jobs"] if row["record"].id == "annual-dinner")
    assert dinner["exported"] is True
    workspace(client, "project-manager")
    record = store.JOBS["annual-dinner"]
    key = next(key for key, item in record.job.items.items() if item.change.item == "Roll-up banner")
    client.post(f"/job/annual-dinner/act/{key}", data={"action": "review"})
    context = workspace(client, "finance")["workspace"]
    dinner = next(row for row in context["jobs"] if row["record"].id == "annual-dinner")
    assert dinner["exported"] is False


def test_project_director_keeps_existing_approval_rules(client):
    workspace(client, "project-manager")
    client.post("/job/annual-dinner/bulk")
    director = workspace(client, "project-director")["workspace"]
    assert any(row["item"].state == "reviewed" for row in director["queue"])
    client.post("/job/annual-dinner/bulk")
    assert not any(item.state == "reviewed" for item in store.JOBS["annual-dinner"].job.items.values())


def test_director_queue_focuses_on_exceptions_not_unreviewed_pm_work(client):
    director = workspace(client, "project-director")["workspace"]
    assert director["queue"]
    assert all(
        row["item"].state in ("reviewed", "disputed")
        or row["item"].change.kind == "discount"
        or row["item"].change.status == "unconfirmed"
        for row in director["queue"]
    )
    assert not any(row["item"].change.item == "Wireless mic" for row in director["queue"])


def test_workspace_projects_list_has_no_duplicate_titles(client):
    context = workspace(client, "project-manager", view="projects")
    titles = [row["title"] for row in context["workspace"]["jobs"]]
    assert titles.count("Annual Dinner 2026") == 1
    assert len(titles) == len(set(titles))

