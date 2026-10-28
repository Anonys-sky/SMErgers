import pytest

import store
from main import app
from navigation import local_return_path


UNSAFE = [
    "https://example.org/untrusted", "http://example.org", "//example.org",
    "///example.org", r"/\example.org", r"\\example.org",
    "javascript:alert(1)", " https://example.org", "\t//example.org",
    "/\t/example.org", "/\n/example.org", "/%2fexample.org",
    "/%5cexample.org", "/%252fexample.org", "/%255cexample.org",
    "/%0d%0aLocation:https://example.org", "https://localhost/job/annual-dinner",
    "job/annual-dinner",
]


@pytest.mark.parametrize("value", UNSAFE + [None, ""])
def test_unsafe_return_paths_use_fallback(value):
    assert local_return_path(value, "/safe") == "/safe"


@pytest.mark.parametrize("value", [
    "/", "/job/annual-dinner", "/job/annual-dinner?view=mine#chat-end",
    "/job/annual-dinner/client#c-example", "/?view=projects",
])
def test_local_returns_preserve_query_and_fragment(value):
    assert local_return_path(value, "/safe") == value


@pytest.fixture
def client():
    store.reset_demo()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    store.reset_demo()


@pytest.mark.parametrize("branch", ["action_success", "action_error", "bulk_success", "bulk_empty"])
@pytest.mark.parametrize("destination", [
    "https://example.org/untrusted", "//example.org", r"/\example.org",
    "/%252fexample.org", "/job/annual-dinner?view=mine#chat-end",
])
def test_all_action_redirect_branches(client, branch, destination):
    record = store.JOBS["annual-dinner"]
    key = next(k for k, i in record.job.items.items() if i.state == "detected")
    form = {"next": destination}
    if branch.startswith("action"):
        path = f"/job/{record.id}/act/{key}"
        form["action"] = "reject" if branch == "action_success" else "invalid"
        form["note"] = "not needed"   # a rejection always carries its reason
        fallback = f"/job/{record.id}?show={key}"
    else:
        path = f"/job/{record.id}/bulk"
        if branch == "bulk_empty":
            for item in record.job.items.values():
                item.state = "rejected"
        fallback = f"/job/{record.id}"
    response = client.post(path, data=form)
    expected = destination if destination.startswith("/job/") else fallback
    assert response.status_code == 302
    assert response.headers["Location"] == expected
    if branch == "action_success":
        assert record.job.items[key].state == "rejected"
    elif branch == "bulk_success":
        assert any(i.state in ("approved", "reviewed") for i in record.job.items.values())
