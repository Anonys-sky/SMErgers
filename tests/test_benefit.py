"""The benefit report is counted from the real engine, so the numbers used in the pitch are checked here."""
import pytest

import benefit


def test_the_annual_dinner_matches_the_story_told_in_the_pitch():
    row = benefit.measure("dinner_client.json")
    assert row["messages"] == 35 and row["key_changes"] == 10 and row["ready"] == 7
    assert row["on_bill"] == 7 and row["bill"] == pytest.approx(3860) == row["expected"]
    assert row["bill"] / 34530 == pytest.approx(0.1118, abs=0.0005)             # 11.2% of the RM34,530 quote
    assert row["log_intact"] is True


@pytest.mark.parametrize("split", ["sample", "blind", "blind2"])
def test_a_careful_team_ends_on_the_correct_bill_and_a_log_that_was_not_edited(split):
    rows = benefit.report(split)[3]
    assert rows
    for row in rows:
        assert row["bill"] == pytest.approx(row["expected"]), row["chat"]
        assert row["on_bill"] == row["ready"], row["chat"]
        assert row["log_intact"] is True
        assert row["tool_min"] < row["manual_min"]


def test_the_report_counts_what_the_reader_got_wrong_instead_of_hiding_it():
    body, totals, saved, rows = benefit.report("blind2")
    assert totals["wrong"] + totals["missed"] > 0 and totals["right_alone"] < totals["ready"]
    assert "Reader wrong (person fixes)" in body and "Reader missed (person adds)" in body
