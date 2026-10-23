import json

import evaluate


def write_key(folder, name, split):
    body = {"chat": f"{name}.txt", "quote": "q_dinner.json", "changes": [], "expected_known_delta": 0}
    if split:
        body["split"] = split
    (folder / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


def test_each_split_is_scored_separately(tmp_path, monkeypatch):
    keys = tmp_path / "answer_keys"
    keys.mkdir()
    write_key(keys, "dinner_client", None)             # no split means tuning
    write_key(keys, "launch_client", "held_out")
    write_key(keys, "blind_looi", "blind")
    (keys / "dinner_vendor.json").write_text(json.dumps({"agreed_costs": []}), encoding="utf-8")  # other shape
    monkeypatch.setattr(evaluate, "DATA", tmp_path)

    assert evaluate.key_files("tuning") == ["dinner_client.json"]
    assert evaluate.key_files("held_out") == ["launch_client.json"]
    assert evaluate.key_files("blind") == ["blind_looi.json"]


def test_tuning_split_is_only_the_chat_the_rules_were_built_on():
    assert evaluate.key_files("tuning") == ["dinner_client.json"]
