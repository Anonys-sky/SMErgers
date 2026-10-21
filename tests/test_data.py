"""Sanity checks on the synthetic data, so the answer keys stay consistent."""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
KEYS = sorted(p for p in (DATA / "answer_keys").glob("*.json") if "changes" in json.loads(p.read_text(encoding="utf-8")))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_evidence_appears_in_chat(key_path):
    key = load(key_path)
    chat = (DATA / "chats" / key["chat"]).read_text(encoding="utf-8")
    missing = [e for c in key["changes"] for e in c["evidence"] if e not in chat]
    assert missing == []


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_known_delta_matches_ready_changes(key_path):
    key = load(key_path)
    ready = sum(c["price_delta"] for c in key["changes"] if c["status"] == "ready")
    assert ready == pytest.approx(key["expected_known_delta"])


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_line_ids_exist_in_quote(key_path):
    key = load(key_path)
    quote = load(DATA / "quotes" / key["quote"])
    ids = {line["id"] for line in quote["lines"]}
    assert all(c["line_id"] in ids for c in key["changes"] if c["line_id"])


def test_every_data_file_is_labelled_synthetic():
    for path in list((DATA / "quotes").glob("*.json")) + list((DATA / "vendor_invoices").glob("*.json")):
        assert "SIMULATED" in load(path)["label"], path.name


def test_vendor_invoice_total():
    inv = load(DATA / "vendor_invoices" / "sw_1187.json")
    key = load(DATA / "answer_keys" / "dinner_vendor.json")
    assert sum(l["qty"] * l["unit_price"] for l in inv["invoice_lines"]) == key["expected_invoice_total"]
